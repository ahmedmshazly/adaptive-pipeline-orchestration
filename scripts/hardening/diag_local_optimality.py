from __future__ import annotations

"""Diagnostic A3 (v2) — is always-execute a LOCAL OPTIMUM of the true
objective in the current (benign) environment?

Decides whether the Phase-0 Q1 critique is fatal: is "always-execute wins"
determined by the reward *shape* (paper's claim) or by an *environment* that
never instantiates a state where caution pays (competing explanation)?

Operator: the one-step policy-improvement advantage against the always-
execute policy pi:
    A_pi(s, a) = E_future[ Q_pi(s, a) - V_pi(s) ]
i.e. "deviate to a once at s, then follow always-execute to the end; how
much does the true episode utility change, in expectation over futures?"
If A_pi(s,a) <= 0 for every a at every visited s, always-execute is locally
optimal and the environment is the operative cause.

v2 fixes the two flaws in v1:
  (1) Monte-Carlo over the FUTURE. v1 used the single real event-RNG snapshot,
      so different actions desynced the draw counts and the advantage was
      contaminated by failure-sequence noise. v2 evaluates each (state,action)
      under K independent continuation RNGs and averages, with the SAME K
      seeds reused for the baseline and every action (paired). This integrates
      out the exogenous shock noise.
  (2) No max-over-actions. v1's "best of 5" is positively biased under noise
      (order-statistic bias). v2 reports each action's advantage separately
      with a paired bootstrap CI across probed states; positivity must clear
      the CI, not a single noisy draw.

Scored on the EPISODE METRIC (true objective with the failure penalty), so
the A1 reward bug does not contaminate this probe.

Outputs results/hardening/local_optimality.csv (per (state,action) MC advantage)
and a per-action summary with bootstrap CIs.
"""

import argparse
import csv
from dataclasses import replace
from pathlib import Path
from typing import Dict, List

import numpy as np

from src.config import load_config
from src.cost import cost as cost_fn
from src.sim_environment import (
    ACTIONS,
    EpisodeState,
    JobInstance,
    RunningTask,
    TaskInstance,
    WorkloadGenerator,
    advance_one_step,
    make_episode_rngs,
)

BOOT_SEED = 20260418


def _clone_episode(state: EpisodeState) -> EpisodeState:
    jobs: List[JobInstance] = []
    for job in state.jobs:
        tasks = {
            tid: TaskInstance(
                job_id=t.job_id, task_id=t.task_id, parents=t.parents,
                remaining_time=t.remaining_time, cpu_demand=t.cpu_demand,
                ram_demand=t.ram_demand, state=t.state,
            )
            for tid, t in job.tasks.items()
        }
        jobs.append(JobInstance(
            job_id=job.job_id, template_name=job.template_name,
            priority=job.priority, deadline_steps=job.deadline_steps,
            value=job.value, tasks=tasks, failed=job.failed, completed=job.completed,
        ))
    return EpisodeState(
        step=state.step, jobs=jobs, cluster=replace(state.cluster), cfg=state.cfg,
        running_tasks={
            k: RunningTask(full_id=v.full_id, cpu_demand=v.cpu_demand,
                           ram_demand=v.ram_demand, remaining_time=v.remaining_time)
            for k, v in state.running_tasks.items()
        },
        event_log=[],
    )


def _continue_execute(cfg, state: EpisodeState, rng: np.random.Generator,
                      cost_so_far: float) -> float:
    max_steps = cfg.experiment.max_steps
    total_cost = cost_so_far
    while not state.all_done() and state.step < max_steps:
        advance_one_step(state, rng, "Execute_Ready_Job")
        total_cost += cost_fn(state, "Execute_Ready_Job")
    u = cfg.utility
    completed_value = sum(j.value for j in state.jobs if j.completed)
    failed = sum(1 for j in state.jobs if j.failed)
    return (u.alpha * completed_value) - (u.beta * total_cost) - (u.gamma * failed)


def _mc_advantage(cfg, base: EpisodeState, action: str, base_cost: float,
                  future_seeds: List[int]) -> np.ndarray:
    """Paired per-future advantage of (deviate to `action`, then execute)
    vs (execute, then execute), across `future_seeds`."""
    diffs = np.empty(len(future_seeds), dtype=np.float64)
    for i, fseed in enumerate(future_seeds):
        # Baseline branch: execute now, then execute.
        b = _clone_episode(base)
        rng_b = np.random.default_rng(fseed)
        advance_one_step(b, rng_b, "Execute_Ready_Job")
        u_exec = _continue_execute(cfg, b, rng_b, base_cost + cost_fn(b, "Execute_Ready_Job"))
        # Deviation branch: action now, then execute. Same future seed (paired).
        d = _clone_episode(base)
        rng_d = np.random.default_rng(fseed)
        advance_one_step(d, rng_d, action)
        u_a = _continue_execute(cfg, d, rng_d, base_cost + cost_fn(d, action))
        diffs[i] = u_a - u_exec
    return diffs


def _bootstrap_ci(x: np.ndarray, n_boot: int = 10000, alpha: float = 0.05):
    rng = np.random.default_rng(BOOT_SEED)
    means = np.array([rng.choice(x, size=len(x), replace=True).mean()
                      for _ in range(n_boot)])
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None,
                        help="config path (default: config/default.yaml = benign env)")
    parser.add_argument("--seeds", nargs="*", type=int, default=[200, 201, 202, 203, 204])
    parser.add_argument("--every", type=int, default=20, help="probe every k-th step")
    parser.add_argument("--futures", type=int, default=16, help="MC futures per (state,action)")
    parser.add_argument("--out", type=Path, default=Path("results/hardening/local_optimality.csv"))
    args = parser.parse_args()

    cfg = load_config(args.config) if args.config else load_config()
    print(f"config: {args.config or 'config/default.yaml'} "
          f"(config_name={cfg.meta.get('config_name')})")
    alt_actions = [a for a in ACTIONS if a != "Execute_Ready_Job"]
    future_seeds = list(range(args.futures))

    rows: List[dict] = []
    adv_by_action: Dict[str, List[float]] = {a: [] for a in alt_actions}
    n_states = 0

    for seed in args.seeds:
        workload_rng, event_rng = make_episode_rngs(seed)
        gen = WorkloadGenerator(rng=workload_rng, cfg=cfg,
                                num_jobs=cfg.experiment.num_jobs, seed_label=seed)
        base = gen.generate_episode()
        base_cost = 0.0
        step_idx = 0
        max_steps = cfg.experiment.max_steps
        while not base.all_done() and base.step < max_steps:
            if step_idx % args.every == 0:
                row = {"seed": seed, "step": base.step}
                for a in alt_actions:
                    diffs = _mc_advantage(cfg, base, a, base_cost, future_seeds)
                    mc_adv = float(diffs.mean())
                    adv_by_action[a].append(mc_adv)
                    row[f"adv_{a}"] = round(mc_adv, 4)
                rows.append(row)
                n_states += 1
            advance_one_step(base, event_rng, "Execute_Ready_Job")
            base_cost += cost_fn(base, "Execute_Ready_Job")
            step_idx += 1

    print(f"=== A3 v2: MC one-step policy-improvement vs always-execute ===")
    print(f"seeds {args.seeds} | every {args.every} | futures {args.futures} | "
          f"probed states n={n_states}\n")
    print(f"{'action':<24} {'meanAdv':>9} {'95% CI':>22} {'P(adv>0)':>9} "
          f"{'CI>0?':>6}")
    any_positive = False
    for a in alt_actions:
        arr = np.array(adv_by_action[a])
        mean = arr.mean()
        lo, hi = _bootstrap_ci(arr)
        frac_pos = 100 * (arr > 1e-9).mean()
        ci_pos = lo > 0
        any_positive = any_positive or ci_pos
        print(f"{a:<24} {mean:>+9.4f} [{lo:>+8.3f},{hi:>+8.3f}] {frac_pos:>8.1f}% "
              f"{str(ci_pos):>6}")
    print()
    print("Reading: a non-execute action is a SYSTEMATIC improver only if its "
          "95% CI lies entirely > 0.")
    print(f"any action with CI entirely > 0 (i.e. always-execute NOT locally "
          f"optimal): {any_positive}")
    if not any_positive:
        print("=> No non-execute action systematically improves the true "
              "objective. Always-execute is a local optimum HERE -> the benign "
              "environment, not the reward shape, determines the attractor. "
              "Phase-2 must vary the environment to separate the two.")

    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
