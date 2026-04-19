# Phase-4 baseline aggregate — results/phase4_baseline_n50

- Seeds: **50**; bootstrap: 10,000 resamples, seed=20260418, 95% CI.

## Per-agent means with 95% bootstrap CI
| Metric | Reflex | Utility-Based (full) | Utility-Based (stripped) |
|---|---|---|---|
| `total_utility` | 120.9909 (114.8137, 127.1728) | 111.5240 (102.3381, 120.4570) | 0.0000 (0.0000, 0.0000) |
| `completion_rate` | 0.6366 (0.6284, 0.6450) | 0.5242 (0.4956, 0.5516) | 0.0000 (0.0000, 0.0000) |
| `value_weighted_completion_rate` | 0.6970 (0.6865, 0.7073) | 0.5955 (0.5690, 0.6219) | 0.0000 (0.0000, 0.0000) |
| `uncapped_completion_rate` | 0.8118 (0.8002, 0.8234) | 0.7882 (0.7774, 0.7992) | 0.0000 (0.0000, 0.0000) |
| `failure_rate` | 0.1452 (0.1344, 0.1562) | 0.1264 (0.1168, 0.1360) | 0.0000 (0.0000, 0.0000) |
| `total_completed_value` | 209.9578 (206.4095, 213.5724) | 179.5866 (171.1350, 187.7500) | 0.0000 (0.0000, 0.0000) |
| `total_compute_cost` | 744.4695 (684.6670, 803.7880) | 554.2255 (519.9641, 587.0879) | 0.0000 (0.0000, 0.0000) |
| `avg_compute_cost_per_step` | 2.4816 (2.2814, 2.6802) | 1.8474 (1.7368, 1.9568) | 0.0000 (0.0000, 0.0000) |

## Paired Wilcoxon signed-rank
Three pairs: (A) Utility − Reflex, (B) Stripped − Reflex, (C) Utility − Stripped. Negative Δ means the lhs agent underperforms the rhs on that metric.

| lhs | rhs | metric | mean Δ | median Δ | W | p |
|---|---|---|---:|---:|---:|---:|
| Utility-Based | Reflex | `total_utility` | -9.4668 | -7.8089 | 406.00 | 0.02485 |
| Utility-Based | Reflex | `completion_rate` | -0.1124 | -0.0700 | 32.50 | 1.204e-08 |
| Utility-Based | Reflex | `value_weighted_completion_rate` | -0.1014 | -0.0541 | 35.00 | 7.656e-12 |
| Utility-Based | Reflex | `uncapped_completion_rate` | -0.0236 | -0.0200 | 276.50 | 0.002314 |
| Utility-Based | Reflex | `failure_rate` | -0.0188 | -0.0200 | 230.50 | 0.001172 |
| Utility-Based | Reflex | `total_completed_value` | -30.3712 | -15.9250 | 35.00 | 7.656e-12 |
| Utility-Based | Reflex | `total_compute_cost` | -190.2440 | -180.8150 | 107.00 | 1.618e-08 |
| Utility-Based | Reflex | `avg_compute_cost_per_step` | -0.6341 | -0.6027 | 107.00 | 1.618e-08 |
| Stripped | Reflex | `total_utility` | -120.9909 | -115.7851 | 0.00 | 1.776e-15 |
| Stripped | Reflex | `completion_rate` | -0.6366 | -0.6400 | 0.00 | 7.082e-10 |
| Stripped | Reflex | `value_weighted_completion_rate` | -0.6970 | -0.6990 | 0.00 | 7.55e-10 |
| Stripped | Reflex | `uncapped_completion_rate` | -0.8118 | -0.8100 | 0.00 | 7.073e-10 |
| Stripped | Reflex | `failure_rate` | -0.1452 | -0.1350 | 0.00 | 7.278e-10 |
| Stripped | Reflex | `total_completed_value` | -209.9578 | -210.2000 | 0.00 | 7.555e-10 |
| Stripped | Reflex | `total_compute_cost` | -744.4695 | -769.8940 | 0.00 | 1.776e-15 |
| Stripped | Reflex | `avg_compute_cost_per_step` | -2.4816 | -2.5663 | 0.00 | 1.776e-15 |
| Utility-Based | Stripped | `total_utility` | +111.5240 | +112.6944 | 0.00 | 1.776e-15 |
| Utility-Based | Stripped | `completion_rate` | +0.5242 | +0.5350 | 0.00 | 7.479e-10 |
| Utility-Based | Stripped | `value_weighted_completion_rate` | +0.5955 | +0.6029 | 0.00 | 7.555e-10 |
| Utility-Based | Stripped | `uncapped_completion_rate` | +0.7882 | +0.7800 | 0.00 | 7.178e-10 |
| Utility-Based | Stripped | `failure_rate` | +0.1264 | +0.1200 | 0.00 | 7.16e-10 |
| Utility-Based | Stripped | `total_completed_value` | +179.5866 | +184.8450 | 0.00 | 1.776e-15 |
| Utility-Based | Stripped | `total_compute_cost` | +554.2255 | +581.6310 | 0.00 | 1.776e-15 |
| Utility-Based | Stripped | `avg_compute_cost_per_step` | +1.8474 | +1.9387 | 0.00 | 1.776e-15 |
