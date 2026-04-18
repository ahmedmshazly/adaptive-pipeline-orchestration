# Phase-2 50-seed baseline summary

This file is generated to accompany the machine-readable
`aggregate.{csv,json,md}`, `wilcoxon.csv`, and `phase2_deltas.png`
artifacts in this run directory. The canonical numbers live in those
files; this document is just the short prose version.

## Run configuration

- Seeds: **50** (0..49)
- Jobs per run: 100
- Max steps (capped): 300
- Uncapped max steps: **900** (3× the capped budget, per Phase-2 spec)
- Utility weights: `alpha=1.0, beta=0.1, gamma=1.0` (Phase-1 default)
- Simulator: `stochastic_processes.node_failure.mode=per_step_single_victim`
  (P=0.05), `data_spike.mode=additive_bump` (P=0.08), spot-price bounded
  random walk on `[0.1, 1.0]`.
- Bootstrap: 10,000 resamples, seed=20260418, 95% confidence.
- Config hash: see `run_manifest.json` (`config_hash`).

## Headline aggregate statistics

Means with 95% bootstrap CI (same data as `aggregate.md`):

| Metric | Reflex mean (95% CI) | Utility mean (95% CI) |
|---|---|---|
| `total_utility` | 120.99 (114.76, 127.31) | 111.52 (102.35, 120.80) |
| `completion_rate` | 0.6366 (0.6282, 0.6448) | 0.5242 (0.4958, 0.5518) |
| `value_weighted_completion_rate` | 0.6970 (0.6864, 0.7074) | 0.5955 (0.5683, 0.6216) |
| `uncapped_completion_rate` | 0.8118 (0.7998, 0.8236) | 0.7882 (0.7772, 0.7994) |
| `total_compute_cost` | 744.47 (685.69, 802.58) | 554.23 (521.28, 587.30) |
| `failure_rate` | 0.1452 (0.1344, 0.1566) | 0.1264 (0.1166, 0.1358) |

## Paired Wilcoxon signed-rank (Utility − Reflex, n = 50, two-sided)

| Metric | mean Δ | median Δ | W | p-value |
|---|---:|---:|---:|---:|
| `total_utility` | -9.47 | -7.81 | 406.00 | **0.0248** |
| `completion_rate` | -0.1124 | -0.0700 | 32.50 | **1.2e-08** |
| `value_weighted_completion_rate` | -0.1014 | -0.0541 | 35.00 | **7.7e-12** |
| `uncapped_completion_rate` | -0.0236 | -0.0200 | 276.50 | **0.00231** |
| `total_completed_value` | -30.37 | -15.93 | 35.00 | **7.7e-12** |
| `total_compute_cost` | -190.24 | -180.82 | 107.00 | **1.6e-08** |
| `failure_rate` | -0.0188 | -0.0200 | 230.50 | **0.00117** |
| `avg_compute_cost_per_step` | -0.6341 | -0.6027 | 107.00 | **1.6e-08** |

## Per-seed win rates (Utility vs Reflex)

- `total_utility` (higher is better): **19/50** — Utility wins in under
  half of seeds, and the paired test says Utility is *significantly lower*
  on average (p=0.025). Under the Phase-1 weights, Reflex is the
  utility-winner.
- `completion_rate` (higher is better): 4/50. Reflex dominates throughput.
- `value_weighted_completion_rate` (higher is better): 5/50. Even the
  value-weighted throughput is worse for Utility — it isn't just dropping
  unimportant jobs.
- `uncapped_completion_rate` (higher is better): 13/50. With a 3× step
  budget the gap shrinks dramatically (mean Δ goes from −0.112 at 300
  steps to −0.024 at 900 steps) but does not collapse.
- `total_compute_cost` (lower is better): 41/50. Utility is cheaper, as
  designed.
- `failure_rate` (lower is better): 31/50. Utility is safer but the edge
  is smaller than the midterm advertised.

## Phase-2 findings

1. **The "conservative trap" is real and statistically significant.** At
   Phase-1 weights (α=1.0, β=0.1, γ=1.0), the Utility-Based agent is
   significantly cheaper (p=1.6e-8) and safer (p=1.2e-3) but also
   significantly worse on total utility (p=0.025). With 50 seeds and
   matched pairs, this is not rounding noise.
2. **Value-weighting does not save Utility-Based.** The
   `value_weighted_completion_rate` gap (mean Δ = −0.101, p = 7.7e-12) is
   almost as large as the raw completion gap, so Utility-Based is not
   merely dropping low-value work — it is under-completing across the
   value distribution.
3. **The 300-step budget truncation explains most of the completion gap
   but not all of it.** `completion_rate` gap ≈ −0.11 at 300 steps,
   `uncapped_completion_rate` gap ≈ −0.024 at 900 steps. The 300-step
   report over-states Utility-Based's weakness by roughly 4.6×. This is
   exactly the reviewer-flagged "budget-capped throughput" artefact, now
   quantified.
4. **The direction of the total-utility ranking is weight-dependent.**
   Under the midterm weights (α=1.0, β=0.4, γ=0.8), Utility-Based wins
   utility 7/10; under Phase-1 weights it loses utility in expectation.
   The Phase-3 Pareto sweep will map this boundary.

## Sanity check (pipeline reproducibility)

`make phase2-sanity` runs seeds 0..9 under `config/midterm_weights.yaml`
and diffs every `total_utility` / `total_compute_cost` row against the
archived `results/canonical_midterm/metrics.csv`. The most recent run
reports:

```
Reference:  results/canonical_midterm  (20 rows)
Candidate:  results/phase2_sanity_seeds0_9  (20 rows)
Max |Δ| total_utility:      0.000000000
Max |Δ| total_compute_cost: 0.000000000
Sanity check PASSED: all rows match within tolerance.
```

i.e. the new 50-seed pipeline reproduces the midterm's 10-seed Table 1
bit-for-bit; no rounding drift.
