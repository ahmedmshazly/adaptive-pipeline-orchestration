from __future__ import annotations

"""Self-Learning Utility-Based agent training — scaffold.

A full REINFORCE-with-baseline implementation lands in a follow-up commit.
This scaffold exists so that:

- ``make train`` is a real entry point wired to the config loader.
- The run layout is pinned: ``<out_root>/<run_id>/`` with
  ``config.yaml``, ``run_manifest.json``, and a placeholder ``training_log.csv``.
- The config surface the trainer will consume (``cfg.rl``) is already
  validated by the loader.
"""

import argparse
import time
from pathlib import Path

from src.config import load_config
from src.run_artifacts import (
    ensure_run_dir,
    generate_run_id,
    write_manifest,
    write_metrics_csv,
    write_resolved_config,
    write_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--out-root", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config) if args.config else load_config()
    out_root = Path(args.out_root) if args.out_root else Path(cfg.experiment.out_root)
    run_id = args.run_id or generate_run_id("rl_train")
    run_dir = ensure_run_dir(out_root, run_id)

    started = time.time()
    write_resolved_config(run_dir, cfg)
    write_text(
        run_dir,
        "README.md",
        "RL training scaffold. `src.config.RLConfig` surface:\n"
        f"- algorithm={cfg.rl.algorithm}\n"
        f"- reward={cfg.rl.reward}\n"
        f"- network.hidden_sizes={list(cfg.rl.network.hidden_sizes)}\n"
        f"- curriculum.enabled={cfg.rl.curriculum.enabled}\n"
        f"- training_seed_list={list(cfg.rl.training_seed_list)}\n"
        "\nTrainer arrives in a follow-up commit.\n",
    )
    write_metrics_csv(run_dir, rows=[], filename="training_log.csv")
    write_manifest(
        run_dir=run_dir,
        cfg=cfg,
        seeds=list(cfg.rl.training_seed_list),
        extra={"entrypoint": "train_rl", "status": "scaffold"},
        wall_clock_start=started,
    )
    print(f"Wrote RL training scaffold to: {run_dir}")


if __name__ == "__main__":
    main()
