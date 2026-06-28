from __future__ import annotations

"""Final taxonomy evaluation. For each environment, evaluates always-execute,
a hand-crafted reference policy, and every trained RL policy (REINFORCE & PPO,
all seeds) on the TRUE episode metric over the held-out test pool, with paired
Wilcoxon vs always-execute. Produces the definitive 'why does it look trivial'
table.

Run after the training batch completes. Discovers checkpoints by glob.
"""

import argparse
import glob
from pathlib import Path
from typing import List

import numpy as np
from scipy.stats import wilcoxon

from src.config import load_config
from src.reflex_agent import build_reflex_agent
from src.rl.agent import RLPolicyAgent, load_policy
from src.runner import run_many_episodes
from src.sim_environment import ACTIONS, EpisodeState, WorkloadGenerator, advance_one_step, make_episode_rngs


class AlwaysExecute:
    name = "always_execute"
    def __init__(self, cfg): pass
    def choose_action(self, s): return "Execute_Ready_Job"


class ScaleWhenBlocked:
    name = "scale_when_blocked"
    def __init__(self, cfg): pass
    def choose_action(self, s):
        r = s.ready_tasks()
        if not r: return "Execute_Ready_Job"
        ac, ar = s.available_cpu(), s.available_ram()
        if any(t.cpu_demand <= ac and t.ram_demand <= ar for t in r): return "Execute_Ready_Job"
        return "Scale_Up" if s.cluster.scale_boost_remaining == 0 else "Execute_Ready_Job"


class Throttle:
    name = "throttle"
    def __init__(self, cfg, thr=0.4): self.thr = thr
    def choose_action(self, s):
        load = s.cpu_in_use() / max(s.cluster.cpu_capacity, 1)
        return "Defer_Job" if load > self.thr else "Execute_Ready_Job"


# (env config, hand-reference agent class, glob patterns for RL run dirs)
MATRIX = [
    ("config/default.yaml", ScaleWhenBlocked, {
        "PPO": "results/hardening/ppo_benign_seed*",
    }),
    ("config/env_tight_fixedrisk.yaml", ScaleWhenBlocked, {
        "REINFORCE": "results/hardening/rl_tight_fixedrisk_seed7 results/hardening/reinforce_tight_seed*",
        "PPO": "results/hardening/ppo_tight_seed*",
    }),
    ("config/env_cascade.yaml", Throttle, {
        "REINFORCE": "results/hardening/reinforce_cascade_seed7 results/hardening/reinforce_cascade_seed1*",
        "PPO": "results/hardening/ppo_cascade_seed*",
    }),
    ("config/env_cascade_broken.yaml", Throttle, {
        "REINFORCE": "results/hardening/reinforce_cascade_broken_seed*",
        "PPO": "results/hardening/ppo_cascade_broken_seed*",
    }),
    ("config/env_heavytail_tight.yaml", ScaleWhenBlocked, {
        "REINFORCE": "results/hardening/reinforce_heavytail_seed*",
        "PPO": "results/hardening/ppo_heavytail_seed*",
    }),
]


def _exec_frac(cfg, agent, seeds) -> float:
    tot = ex = 0
    for seed in seeds[:10]:  # histogram on a subsample for speed
        wr, er = make_episode_rngs(seed)
        st = WorkloadGenerator(rng=wr, cfg=cfg, num_jobs=cfg.experiment.num_jobs, seed_label=seed).generate_episode()
        while not st.all_done() and st.step < cfg.experiment.max_steps:
            a = agent.choose_action(st); advance_one_step(st, er, a)
            tot += 1; ex += (a == "Execute_Ready_Job")
    return ex / max(tot, 1)


def _metrics(cfg, factory, seeds):
    ms = run_many_episodes(cfg=cfg, agent_factory=factory, seeds=seeds, include_uncapped=False)
    return (np.array([m.total_utility for m in ms]),
            np.array([m.failure_rate for m in ms]),
            np.array([m.completion_rate for m in ms]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", type=int, default=list(range(200, 250)))
    args = ap.parse_args()

    for env_cfg, hand_cls, rl_globs in MATRIX:
        cfg = load_config(Path(env_cfg))
        seeds = args.seeds
        print(f"\n{'='*92}\nENV: {cfg.meta.get('config_name')}  ({env_cfg})  "
              f"seeds {seeds[0]}..{seeds[-1]} n={len(seeds)}")
        print(f"{'policy':<34}{'util':>9}{'95%CI':>20}{'fail':>7}{'compl':>7}{'exec%':>7}{'ΔvsAE':>8}{'p':>9}")

        ae_u, ae_f, ae_c = _metrics(cfg, lambda c: AlwaysExecute(c), seeds)
        ae_x = _exec_frac(cfg, AlwaysExecute(cfg), seeds)
        def row(name, u, f, c, x, base=None):
            lo, hi = np.percentile(u, [2.5, 97.5])
            d = "" ; p = ""
            if base is not None:
                d = f"{u.mean()-base.mean():+.1f}"
                try: p = f"{wilcoxon(u, base).pvalue:.1e}"
                except ValueError: p = "nan"
            print(f"{name:<34}{u.mean():>9.1f}{('['+format(lo,'.1f')+','+format(hi,'.1f')+']'):>20}"
                  f"{f.mean():>7.3f}{c.mean():>7.3f}{x:>7.2f}{d:>8}{p:>9}")
        row("always_execute", ae_u, ae_f, ae_c, ae_x)
        hand = hand_cls(cfg)
        h_u, h_f, h_c = _metrics(cfg, lambda c: hand_cls(c), seeds)
        row(f"{hand.name} (hand)", h_u, h_f, h_c, _exec_frac(cfg, hand, seeds), ae_u)

        for algo, pattern in rl_globs.items():
            dirs = []
            for pat in pattern.split():
                dirs += sorted(glob.glob(pat))
            for d in dirs:
                ckpt = Path(d) / "policy_best_by_val.pt"
                if not ckpt.exists():
                    print(f"{algo} {Path(d).name:<22} [no ckpt yet]")
                    continue
                try:
                    pol = load_policy(cfg, ckpt)
                except Exception as e:
                    print(f"{algo} {Path(d).name:<22} [load failed: {e}]"); continue
                u, f, c = _metrics(cfg, lambda cc, p=pol: RLPolicyAgent(cc, p, deterministic=True), seeds)
                x = _exec_frac(cfg, RLPolicyAgent(cfg, pol, deterministic=True), seeds)
                row(f"{algo}:{Path(d).name.split('_')[-1]}", u, f, c, x, ae_u)


if __name__ == "__main__":
    main()
