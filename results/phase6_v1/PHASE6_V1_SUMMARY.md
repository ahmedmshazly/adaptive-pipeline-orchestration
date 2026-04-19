# Phase 6 V1 — Richer 14-dim State (committed feature set)

## Scope

Phase 6 V1 extends the observation the RL agent receives from 8 to
14 dimensions (paper §6):

| block | dims | fields |
|---|---:|---|
| Phase-5 (unchanged) | 8 | cpu_load, ram_available, queue_depth, spot_price, dag_ready_nodes, job_priority, deadline_urgency, recent_failures |
| V1 queue features    | 5 | queue_len_abs_norm, mean_remaining_work, max_deadline_urgency, mean_job_value, max_job_value |
| V1 spot-price forecast | 1 | spot_price_forecast (EMA, λ = 0.3, initial 0.5) |

V1 is gated behind `state_v2.use_richer_state`. With the flag off
(default) every Phase-5 numeric is reproduced bit-identically; this is
regression-guarded by `tests/test_regression_phase5.py` (Reflex, Tuned
UB, and the Phase-5 RL-seed-7 checkpoint all match to floating-point
equality on the held-out sample seeds).

V2 (GNN over the DAG-ready frontier) is still gated and intentionally
unimplemented — enabling `feature_set: queue_and_forecast_and_gnn`
raises `NotImplementedError` at config-load time.

## Acceptance-criterion status

**V1 acceptance target (§4.3.7 equivalent — RL beats Tuned UB on
throughput-adjacent metrics).** MET. See the `phase5_aggregate.md` table
below: V1 mean total_utility 111.52 vs Tuned UB 85.47 (Δ = +26.06,
p = 0.26, not significant due to Tuned's wide variance), but
completion_rate, value_weighted_completion_rate, and
total_completed_value all improve at p < 1e-6. Same pattern as Phase 5.

**V1 headline target (RL beats Reflex on total utility at α=0.01).**
NOT MET. V1 total_utility 111.52 vs Reflex 115.49 (Δ = −3.96, p = 0.08).
Identical to Phase 5.

**V1 behavioural target (does the richer state unlock non-execute
actions that Phase-5 couldn't discover?).** NOT MET. The V1 greedy
argmax policy is `Execute_Ready_Job` on 300/300 steps across all five
held-out rollout seeds (`phase6_v1/rollouts/action_histograms.csv`).
**Always-execute %: 100.0** — same as Phase 5.

## Held-out comparison (seeds 200..249, n=50)

The per-seed held-out metrics for the three V1 seeds are **bit-
identical** to the three Phase-5 seeds. Paired Wilcoxon between each V1
and the matching Phase-5 seed shows zero non-zero differences on every
metric (`phase6_v1_vs_phase5.csv`, `n_nonzero=0/50` for all 24 rows).

| Metric | Reflex | Tuned UB (α=4, β=1, γ=4) | V1 RL (all 3 seeds) | Phase-5 RL (all 3 seeds) |
|---|---:|---:|---:|---:|
| `total_utility` | 115.49 (108.27, 122.26) | 85.47 (33.12, 141.16) | 111.52 (104.5, 118.5) | 111.52 (104.5, 118.5) |
| `completion_rate` | 0.633 | 0.548 | 0.629 | 0.629 |
| `value_weighted_completion_rate` | 0.696 | 0.624 | 0.692 | 0.692 |
| `uncapped_completion_rate` (900) | 0.810 | 0.793 | 0.805 | 0.805 |
| `total_compute_cost` | 766.3 | 603.2 | 786.2 | 786.2 |
| `failure_rate` | 0.145 | 0.129 | 0.151 | 0.151 |

### Paired Wilcoxon headline rows

From `phase5_pairwise.csv` (V1 vs Reflex, V1 vs Tuned) and
`phase6_v1_vs_phase5.csv` (V1 vs Phase-5 RL):

| Pair | Metric | mean Δ | p |
|---|---|---:|---:|
| V1 − Reflex | total_utility | −3.96 | 0.080 |
| V1 − Reflex | completion_rate | −0.0042 | 0.074 |
| V1 − Tuned UB | total_utility | +26.06 | 0.261 |
| V1 − Tuned UB | completion_rate | +0.081 | **1.2e-6** |
| V1 − Tuned UB | value_weighted_completion_rate | +0.068 | **7.2e-7** |
| V1 − Tuned UB | total_completed_value | +20.23 | **7.2e-7** |
| V1 − Tuned UB | total_compute_cost | +182.98 | **2.1e-7** |
| V1 − Tuned UB | failure_rate | +0.023 | **2.1e-3** |
| V1 seed 7 − Phase-5 seed 7 | every metric | 0.000 | nan (n_nonzero=0) |
| V1 seed 11 − Phase-5 seed 11 | every metric | 0.000 | nan (n_nonzero=0) |
| V1 seed 13 − Phase-5 seed 13 | every metric | 0.000 | nan (n_nonzero=0) |

## Interpretation

1. **Does V1 converge to always-execute?** Yes, 100%. The richer state
   does not unlock a more diverse policy. Under greedy-argmax evaluation
   with Phase-1 evaluation weights (α=1.0, β=0.1, γ=1.0), always-execute
   is still the attractor — the extra features do not flip the argmax
   at any state the policy actually visits.
2. **Is the 8-scalar state the bottleneck?** No. On this training
   protocol + this reward, the bottleneck is not observation capacity;
   it is the fact that the greedy-argmax optimal fixed action is
   "execute" almost everywhere under β = 0.1. Phase-3's ablation
   already pointed at this: the utility weights act through a
   single-bit gate.
3. **Is there anything the V1 agent learned differently?** Not in
   behaviour. The per-batch training-return curves follow the same
   three-stage staircase as Phase 5 (slightly higher mean-return during
   stage 2 peaks, but the same asymptote). Validation best-so-far is
   pinned at 141.1 in all three V1 runs, exactly like Phase 5. The
   end-of-training policy entropy is comparable (~0.2), so the policy
   is not just staying uncommitted.
4. **What does this say about V2?** The brief's §G V2 decision should
   be made on the paper side. From the V1 evidence, a GNN over the
   ready-frontier is unlikely to change the greedy-argmax attractor
   unless the reward is also changed (e.g. higher β, or an action
   tariff on Scale_Up / Defer). The observation capacity is not the
   limiting factor here; the reward shape is.

## Artifacts

```
results/phase6_v1/
├── rl_seed7/            training run, init seed 7
│   ├── learning_curve.csv   400 updates, ~1.44M env steps
│   ├── validation_log.csv   16 evals, all +141.101
│   ├── policy_best_by_val.pt
│   ├── policy_final.pt
│   ├── summary.json
│   └── run_manifest.json
├── rl_seed11/           training run, init seed 11
├── rl_seed13/           training run, init seed 13
├── heldout/
│   ├── metrics.csv           50 seeds × 5 agents
│   ├── reflex / tuned_utility / rl_v1_seed{7,11,13}/metrics.csv
│   ├── phase5_aggregate.{csv,md}   (inherited aggregate script)
│   ├── phase5_pairwise.csv
│   ├── phase6_v1_vs_phase5.csv     Phase-6 brief's matched V1-vs-Phase5 test
│   ├── heldout_comparison_v1.png
│   └── run_manifest.json
├── rollouts/
│   ├── rollouts.csv              5 seeds × 300 steps, full state+logits
│   ├── rollouts_summary.csv
│   ├── action_histograms.csv     300 Execute / 0 other on every seed
│   └── run_manifest.json
├── training_curves_v1.png
├── pareto_with_rl_v1.png
└── PHASE6_V1_SUMMARY.md  this file
```

Smoke-test run (pre-flight per §D): `results/phase6_v1/smoke/` produced
a 21-update, 10 060-env-step learning curve with first-window return
+5.99 → last-window +8.01, loss −0.015 → −0.018, random-baseline
+7.64, `learned_exceeds_random=True`. No NaN/Inf in the state vector
across 50 random-action validation steps. **All three smoke criteria
met** before the full training runs started.

## Running tally

- Tests: 118 → **132** (+14 Phase-6 tests — state_v2, forecast,
  regression).
- Experiments: canonical_midterm, phase1_baseline, phase2_50seeds,
  phase2_sanity_seeds0_9, sweep_phase3, ablation_phase3_weights{,_n20},
  phase4_baseline_n50, phase4_rl_smoke{,_extended}, phase5/,
  **phase6_v1/**.
- Every experiment directory carries a `run_manifest.json` with commit
  SHA / config hash / seed list / wall-clock / library versions.
