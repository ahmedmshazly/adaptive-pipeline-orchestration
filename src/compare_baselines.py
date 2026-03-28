from __future__ import annotations

"""Head-to-head baseline comparison driver for the current project layout.

This script runs the two implemented baseline agents under matched seeds,
collects one metrics record per episode, builds aggregate summaries, and writes
reproducible experiment artifacts to the repository's results directory.

At the current project stage, this file is the main experiment entrypoint for
baseline evaluation. Its job is intentionally narrow:

- run the Reflex Agent baseline
- run the non-learning Utility-Based baseline
- summarize both result sets with the same reporting schema
- compute simple head-to-head comparison counts
- save CSV, JSON, and Markdown outputs for later inspection

The script does not do plotting, hyperparameter search, or learning.
"""

import argparse
import csv
import json
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, Iterable, List, Sequence

# Allow direct execution from the src/ directory without requiring package
# installation. This keeps the current workflow simple while still using the
# cleaner repository layout.
THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from reflex_agent import EpisodeMetrics, run_many_reflex_episodes  # noqa: E402
from utility_agent import run_many_utility_episodes  # noqa: E402


DEFAULT_SEEDS = list(range(10))
DEFAULT_NUM_JOBS = 100
DEFAULT_MAX_STEPS = 300
DEFAULT_OUT_DIR = REPO_ROOT / "results" / "baselines_v0"

RESULT_FILENAMES = {
    "reflex_csv": "reflex_runs.csv",
    "utility_csv": "utility_runs.csv",
    "summary_json": "summary.json",
    "report_md": "comparison_report.md",
}

SUMMARY_FIELDS = [
    "completion_rate",
    "failure_rate",
    "total_completed_value",
    "total_compute_cost",
    "avg_compute_cost_per_step",
    "total_utility",
    "steps_executed",
]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for a baseline comparison run."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the current Reflex and Utility-based baselines under matched "
            "seeds and write CSV/JSON/Markdown summaries."
        )
    )
    parser.add_argument(
        "--seeds",
        nargs="*",
        type=int,
        default=DEFAULT_SEEDS,
        help="List of integer seeds to evaluate. Defaults to 0 through 9.",
    )
    parser.add_argument(
        "--num-jobs",
        type=int,
        default=DEFAULT_NUM_JOBS,
        help="Number of jobs generated in each episode.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help="Maximum number of environment steps allowed in each episode.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory used for CSV, JSON, and Markdown outputs.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """Reject obviously invalid experiment settings early."""
    if not args.seeds:
        raise ValueError("At least one seed is required")
    if args.num_jobs <= 0:
        raise ValueError("num_jobs must be positive")
    if args.max_steps <= 0:
        raise ValueError("max_steps must be positive")


def metrics_to_rows(metrics: Iterable[EpisodeMetrics]) -> List[Dict[str, float | int | str | bool]]:
    """Convert metrics records into row dictionaries ready for CSV export."""
    return [episode_metrics.as_dict() for episode_metrics in metrics]


def summarize_agent(metrics: Sequence[EpisodeMetrics]) -> Dict[str, float | int | str]:
    """Build an aggregate summary for one agent across repeated runs."""
    if not metrics:
        raise ValueError("No metrics provided")

    summary: Dict[str, float | int | str] = {
        "agent_name": metrics[0].agent_name,
        "num_runs": len(metrics),
        "num_jobs": metrics[0].num_jobs,
    }

    for field_name in SUMMARY_FIELDS:
        values = [float(getattr(metric, field_name)) for metric in metrics]
        summary[f"mean_{field_name}"] = round(statistics.fmean(values), 4)
        summary[f"std_{field_name}"] = (
            round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0
        )

    summary["all_jobs_completed_runs"] = sum(1 for metric in metrics if metric.completed_all_jobs)
    summary["mean_completed_jobs"] = round(
        statistics.fmean(metric.completed_jobs for metric in metrics),
        4,
    )
    summary["mean_failed_jobs"] = round(
        statistics.fmean(metric.failed_jobs for metric in metrics),
        4,
    )
    return summary


def build_comparison(
    reflex_metrics: Sequence[EpisodeMetrics],
    utility_metrics: Sequence[EpisodeMetrics],
) -> Dict[str, float | int]:
    """Build a small head-to-head comparison summary across matched runs."""
    if len(reflex_metrics) != len(utility_metrics):
        raise ValueError("Runs must have matching seed counts for head-to-head comparison")

    utility_total_utility_wins = 0
    reflex_total_utility_wins = 0
    ties_total_utility = 0
    utility_better_completion_runs = 0
    utility_lower_cost_runs = 0

    for reflex_run, utility_run in zip(reflex_metrics, utility_metrics):
        if utility_run.total_utility > reflex_run.total_utility:
            utility_total_utility_wins += 1
        elif utility_run.total_utility < reflex_run.total_utility:
            reflex_total_utility_wins += 1
        else:
            ties_total_utility += 1

        if utility_run.completion_rate > reflex_run.completion_rate:
            utility_better_completion_runs += 1
        if utility_run.total_compute_cost < reflex_run.total_compute_cost:
            utility_lower_cost_runs += 1

    return {
        "utility_total_utility_wins": utility_total_utility_wins,
        "reflex_total_utility_wins": reflex_total_utility_wins,
        "ties_total_utility": ties_total_utility,
        "utility_better_completion_runs": utility_better_completion_runs,
        "utility_lower_cost_runs": utility_lower_cost_runs,
        "num_head_to_head_runs": len(reflex_metrics),
    }


def write_csv(path: Path, rows: Sequence[Dict[str, float | int | str | bool]]) -> None:
    """Write row dictionaries to a UTF-8 CSV file."""
    if not rows:
        return

    with path.open("w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write a JSON artifact with stable indentation."""
    with path.open("w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, indent=2)


def markdown_summary_table(agent_summaries: Sequence[Dict[str, float | int | str]]) -> str:
    """Render a compact Markdown table for the two agent summaries."""
    headers = [
        "Agent",
        "Runs",
        "Mean Total Utility",
        "Mean Completion Rate",
        "Mean Compute Cost",
        "Mean Failure Rate",
        "Mean Steps",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]

    for summary in agent_summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(summary["agent_name"]),
                    str(summary["num_runs"]),
                    f"{summary['mean_total_utility']:.4f}",
                    f"{summary['mean_completion_rate']:.4f}",
                    f"{summary['mean_total_compute_cost']:.4f}",
                    f"{summary['mean_failure_rate']:.4f}",
                    f"{summary['mean_steps_executed']:.2f}",
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def render_report(
    seeds: Sequence[int],
    num_jobs: int,
    max_steps: int,
    reflex_summary: Dict[str, float | int | str],
    utility_summary: Dict[str, float | int | str],
    comparison: Dict[str, float | int],
) -> str:
    """Render the human-readable Markdown comparison report."""
    summary_table = markdown_summary_table([reflex_summary, utility_summary])
    delta_total_utility = float(utility_summary["mean_total_utility"]) - float(
        reflex_summary["mean_total_utility"]
    )
    delta_completion_rate = float(utility_summary["mean_completion_rate"]) - float(
        reflex_summary["mean_completion_rate"]
    )
    delta_total_compute_cost = float(utility_summary["mean_total_compute_cost"]) - float(
        reflex_summary["mean_total_compute_cost"]
    )

    lines = [
        "# Baseline Comparison",
        "",
        "## Run configuration",
        f"- Seeds: {list(seeds)}",
        f"- Jobs per run: {num_jobs}",
        f"- Max steps: {max_steps}",
        "",
        "## Summary table",
        summary_table,
        "",
        "## Head-to-head summary",
        (
            f"- Utility baseline had higher total utility in "
            f"{comparison['utility_total_utility_wins']} / {comparison['num_head_to_head_runs']} runs."
        ),
        (
            f"- Reflex baseline had higher total utility in "
            f"{comparison['reflex_total_utility_wins']} / {comparison['num_head_to_head_runs']} runs."
        ),
        f"- Ties on total utility: {comparison['ties_total_utility']}.",
        (
            f"- Utility baseline had better completion rate in "
            f"{comparison['utility_better_completion_runs']} runs."
        ),
        (
            f"- Utility baseline had lower total compute cost in "
            f"{comparison['utility_lower_cost_runs']} runs."
        ),
        "",
        "## Mean deltas (Utility baseline minus Reflex baseline)",
        f"- Total utility delta: {delta_total_utility:.4f}",
        f"- Completion rate delta: {delta_completion_rate:.4f}",
        f"- Total compute cost delta: {delta_total_compute_cost:.4f}",
        "",
        "## Interpretation",
        (
            "These are current baseline runs intended to validate the simulator "
            "and the evaluation pipeline before adding the self-learning agent."
        ),
    ]
    return "\n".join(lines) + "\n"


def build_summary_payload(
    args: argparse.Namespace,
    reflex_summary: Dict[str, float | int | str],
    utility_summary: Dict[str, float | int | str],
    comparison: Dict[str, float | int],
) -> Dict[str, Any]:
    """Build the machine-readable JSON payload saved for the experiment run."""
    return {
        "config": {
            "seeds": args.seeds,
            "num_jobs": args.num_jobs,
            "max_steps": args.max_steps,
            "out_dir": str(args.out_dir),
        },
        "reflex_summary": reflex_summary,
        "utility_summary": utility_summary,
        "comparison": comparison,
    }


def run_comparison(args: argparse.Namespace) -> Dict[str, Any]:
    """Run both baselines and return all result artifacts in memory."""
    reflex_metrics = run_many_reflex_episodes(
        seeds=args.seeds,
        num_jobs=args.num_jobs,
        max_steps=args.max_steps,
    )
    utility_metrics = run_many_utility_episodes(
        seeds=args.seeds,
        num_jobs=args.num_jobs,
        max_steps=args.max_steps,
    )

    reflex_rows = metrics_to_rows(reflex_metrics)
    utility_rows = metrics_to_rows(utility_metrics)

    reflex_summary = summarize_agent(reflex_metrics)
    utility_summary = summarize_agent(utility_metrics)
    comparison = build_comparison(reflex_metrics, utility_metrics)
    report_markdown = render_report(
        seeds=args.seeds,
        num_jobs=args.num_jobs,
        max_steps=args.max_steps,
        reflex_summary=reflex_summary,
        utility_summary=utility_summary,
        comparison=comparison,
    )

    return {
        "reflex_rows": reflex_rows,
        "utility_rows": utility_rows,
        "reflex_summary": reflex_summary,
        "utility_summary": utility_summary,
        "comparison": comparison,
        "summary_payload": build_summary_payload(
            args=args,
            reflex_summary=reflex_summary,
            utility_summary=utility_summary,
            comparison=comparison,
        ),
        "report_markdown": report_markdown,
    }


def save_outputs(out_dir: Path, results: Dict[str, Any]) -> None:
    """Write all comparison artifacts to the requested output directory."""
    out_dir.mkdir(parents=True, exist_ok=True)

    write_csv(out_dir / RESULT_FILENAMES["reflex_csv"], results["reflex_rows"])
    write_csv(out_dir / RESULT_FILENAMES["utility_csv"], results["utility_rows"])
    write_json(out_dir / RESULT_FILENAMES["summary_json"], results["summary_payload"])
    (out_dir / RESULT_FILENAMES["report_md"]).write_text(
        results["report_markdown"],
        encoding="utf-8",
    )


def main() -> None:
    """Run the baseline comparison and save the resulting artifacts."""
    args = parse_args()
    validate_args(args)

    results = run_comparison(args)
    save_outputs(args.out_dir, results)

    print(results["report_markdown"])
    print(f"Saved outputs to: {args.out_dir}")


if __name__ == "__main__":
    main()
