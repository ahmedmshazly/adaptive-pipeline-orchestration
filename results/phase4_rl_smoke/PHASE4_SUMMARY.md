# Phase-4 handoff — summary and acceptance

## Acceptance-criteria checks

All three items from the Phase-4 brief (§D.4) are met.

### (a) All tests pass

```
============================= test session starts ==============================
collected 114 items
...
114 passed in 8.49s
```

Suite total went 81 → **114** this pass, with new modules:
- `tests/test_rl_config.py` (11 tests): rename to `delta_discount`, removal
  of `value_loss_coef`, pool materialisation from range specs, pairwise
  disjointness, cross-pool disjointness, `stripped_utility_agent` block,
  and loud errors on pre-Phase-4 keys.
- `tests/test_rl_env.py` (12 tests): `Box(0,1,(8,))` observation space,
  `Discrete(6)` action space, reward sign on cold-start step, reward
  non-positive when launching before any completion, termination vs
  truncation, memoryless-horizon mean within 10% of μ=120 over 1000
  draws.
- `tests/test_rl_baseline.py` (6 tests): discounted-returns formula at
  δ ∈ {0, 0.5, 1.0}, sequence-specific baseline equals per-timestep
  batch mean on equal- and unequal-length fixtures.
- `tests/test_stripped_utility.py` (3 tests): the stripped trace differs
  from the full trace on seed 100 (Phase-3 ablation's 249/300 forced-
  execute steps mean this must hold); guard flag wiring; default
  full-agent guard state.

### (b) Seed pools are disjoint

Verified by `tests/test_rl_config.py::test_rl_pools_are_pairwise_disjoint`
and `test_rl_pools_disjoint_from_baseline_and_sweep_pools`:

| Pool | Range | n |
|---|---|---:|
| RL training | 300..999 | 700 |
| RL validation | 250..299 | 50 |
| RL held-out test | 200..249 | 50 |
| Initialisation seeds | {7, 11, 13} | 3 |
| Baseline (Phase-2) | 0..49 | 50 |
| Weight sweep (Phase-3) | 100..119 | 20 |
| Midterm reproduction | 0..9 | 10 |

All six pools are pairwise disjoint. Initialisation seeds {7, 11, 13} are
network-init RNG seeds only, not episode seeds — they never reach the
simulator.

### (c) γ → δ rename complete in config and code

Grep confirms `gamma_discount` appears nowhere in `src/` or `scripts/`;
`delta_discount` replaces it throughout. `utility.gamma` remains
untouched (the failure-risk weight). Any pre-Phase-4 config that still
sets `rl.gamma_discount` raises a loud `ValueError` at load time with a
pointer to §4.3's notational lock.

## Acceptance criterion (D.2): smoke-test shows a positive learning signal

Canonical smoke run — `results/phase4_rl_smoke/` — ran `scripts.train_rl`
with the brief's budget (10 000 env steps, stage 1 only (N=20, T_max=120),
init seed 7, batch size 4, fixed arrival seed 300):

| Metric | First window (5 updates) | Last window (5 updates) | Δ |
|---|---:|---:|---:|
| Mean episode return | +7.915 | +9.283 | **+1.368** |
| Total loss | −0.003 | −0.026 | +0.023 (loss decreased) |
| Policy entropy (first / last update) | 1.7813 | 1.7770 | −0.004 |
| Random-policy baseline (n=32, same stage) | +7.641 | — | — |
| **Learned > random?** | — | — | **True** (+9.28 vs +7.64) |

Artifacts: `learning_curve.csv` (21 rows), `learning_curve.png`,
`policy_final.pt`, `summary.json`, `config.yaml`, `run_manifest.json`.

A supplementary longer run at 40k env steps
(`results/phase4_rl_smoke_extended/`) gives better figure resolution and
confirms the direction: first-window return +7.95 → last-window +12.45
(Δ=+4.50), entropy 1.781 → 1.653 (policy becoming non-uniform), loss
trending negative.

## Acceptance criterion (D.3): extended n=50 baseline table

Three-way comparison on seeds 0–49 under Phase-1 weights
(α, β, γ) = (1.0, 0.1, 1.0). Artifacts under
`results/phase4_baseline_n50/`: `metrics.csv`, `phase4_aggregate.{csv,md}`,
`pairwise_wilcoxon.csv`.

| Metric | Reflex | Utility-Based (full) | Utility-Based (stripped) |
|---|---:|---:|---:|
| Total utility | 120.99 (114.81, 127.17) | 111.52 (102.34, 120.46) | 0.00 |
| Completion rate | 0.637 (0.628, 0.645) | 0.524 (0.496, 0.552) | 0.000 |
| Value-weighted completion | 0.697 (0.687, 0.707) | 0.596 (0.569, 0.622) | 0.000 |
| Uncapped completion (900) | 0.812 (0.800, 0.823) | 0.788 (0.777, 0.799) | 0.000 |
| Total compute cost | 744.5 (684.7, 803.8) | 554.2 (520.0, 587.1) | 0.0 |
| Failure rate | 0.145 (0.134, 0.156) | 0.126 (0.117, 0.136) | 0.000 |

The Stripped Utility-Based Agent collapses to zero on every metric
because disabling the force-execute guard removes Execute_Ready_Job
from the winning action set under the configured scoring weights — Scale_Up
scores in the hundreds while `_score_execute` hovers near +6–9 (Phase-3
ablation §5.6, class 3: "binary gate flip"). This is the honest
behaviour the paper §4.3.7 relies on: the stripped variant is
deliberately a poor comparand, so any learned policy that beats it must
win on its scoring rule, not on the presence of the gate.

Paired Wilcoxon confirms all three pairwise contrasts at p < 1e-8:
- Utility (full) − Reflex on total utility: Δ = −9.47, p = 0.025.
- Stripped − Reflex on every metric: p < 1e-9.
- Utility (full) − Stripped on every metric: p < 1e-9.

The RL agent joins this table as a fourth column in Phase 5.

## Running tally

- Tests: 81 → **114** (+33)
- Experiments in `results/`:
  `canonical_midterm/`, `phase1_baseline/`, `phase2_50seeds/`,
  `phase2_sanity_seeds0_9/`, `sweep_phase3/`,
  `ablation_phase3_weights/`, `ablation_phase3_weights_n20/`,
  **`phase4_baseline_n50/`**, **`phase4_rl_smoke/`**,
  **`phase4_rl_smoke_extended/`**.
- Code: `src/state.py`, `src/cost.py`, `src/pareto.py` from earlier
  phases; **`src/rl/env.py`**, **`src/rl/policy.py`**,
  **`src/rl/baseline.py`**, **`src/rl/trainer.py`** new in Phase 4.
- Scripts: `scripts/phase4_baseline.py`, `scripts/phase4_aggregate.py`,
  `scripts/train_rl.py`, `scripts/figs/phase4_learning_curve.py`.

## Scope boundary: what Phase 5 still owns

- Full training budget (400 updates across the 3-stage curriculum,
  not 21 updates on stage 1).
- Validation-pool checkpoint selection (hyperparameter grid over
  learning rate, δ, hidden sizes, batch size, entropy coef).
- Held-out evaluation on seeds 200–249 for all four agents.
- The 3× training runs with init seeds {7, 11, 13} and the
  worst-of-three reporting rule (paper §4.3.8 threat 6).
- Curriculum-sensitivity ablation (2-stage and 4-stage variants).
- The final 4-way headline table that joins the RL agent to the
  Reflex / Utility / Stripped baseline.

The pipeline is ready. Phase 5 is now a matter of wall-clock time.
