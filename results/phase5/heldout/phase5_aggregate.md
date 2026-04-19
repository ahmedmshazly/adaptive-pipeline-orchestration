# Phase-5 held-out aggregate — results/phase5/heldout

- Seeds (held-out): **50** per agent.
- Bootstrap: 10,000 resamples, seed=20260418, 95% CI.

## Per-agent means with 95% bootstrap CI

| Metric | Reflex Agent | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | rl_seed7 | rl_seed11 | rl_seed13 |
|---|---|---|---|---|---|
| `total_utility` | 115.4850 (108.2674, 122.2567) | 85.4652 (33.1202, 141.1569) | 111.5229 (104.5712, 118.4984) | 111.5229 (104.3543, 118.5014) | 111.5229 (104.4963, 118.2701) |
| `completion_rate` | 0.6332 (0.6236, 0.6422) | 0.5480 (0.5242, 0.5712) | 0.6290 (0.6196, 0.6380) | 0.6290 (0.6196, 0.6384) | 0.6290 (0.6196, 0.6380) |
| `value_weighted_completion_rate` | 0.6962 (0.6844, 0.7075) | 0.6235 (0.6008, 0.6452) | 0.6915 (0.6789, 0.7041) | 0.6915 (0.6791, 0.7040) | 0.6915 (0.6786, 0.7038) |
| `uncapped_completion_rate` | 0.8098 (0.7968, 0.8226) | 0.7930 (0.7798, 0.8060) | 0.8046 (0.7928, 0.8166) | 0.8046 (0.7926, 0.8164) | 0.8046 (0.7926, 0.8164) |
| `failure_rate` | 0.1454 (0.1336, 0.1578) | 0.1288 (0.1168, 0.1416) | 0.1514 (0.1394, 0.1636) | 0.1514 (0.1394, 0.1636) | 0.1514 (0.1392, 0.1638) |
| `total_completed_value` | 206.6564 (202.3615, 210.8755) | 185.0544 (178.1735, 191.7748) | 205.2838 (200.6752, 209.7064) | 205.2838 (200.7974, 209.7584) | 205.2838 (200.7799, 209.6023) |
| `total_compute_cost` | 766.3136 (702.7437, 830.5019) | 603.2324 (559.8769, 646.2626) | 786.2085 (724.1811, 848.3054) | 786.2085 (724.9788, 848.2297) | 786.2085 (722.6186, 846.8616) |
| `avg_compute_cost_per_step` | 2.5544 (2.3416, 2.7676) | 2.0108 (1.8658, 2.1552) | 2.6207 (2.4113, 2.8297) | 2.6207 (2.4136, 2.8254) | 2.6207 (2.4133, 2.8301) |

## Paired Wilcoxon (lhs vs rhs, per metric)
Negative Δ means lhs underperforms rhs on that metric. For compute_cost and failure_rate a negative Δ is an improvement.

| lhs | rhs | metric | mean Δ | median Δ | W | p | n_nonzero |
|---|---|---|---:|---:|---:|---:|---:|
| rl_seed7 | Reflex Agent | `total_utility` | -3.9621 | +0.0000 | 136.00 | 0.07976 | 29/50 |
| rl_seed7 | Reflex Agent | `completion_rate` | -0.0042 | +0.0000 | 80.00 | 0.07419 | 23/50 |
| rl_seed7 | Reflex Agent | `value_weighted_completion_rate` | -0.0047 | +0.0000 | 126.50 | 0.0815 | 28/50 |
| rl_seed7 | Reflex Agent | `uncapped_completion_rate` | -0.0052 | +0.0000 | 120.00 | 0.2512 | 25/50 |
| rl_seed7 | Reflex Agent | `failure_rate` | +0.0060 | +0.0000 | 71.50 | 0.07382 | 22/50 |
| rl_seed7 | Reflex Agent | `total_completed_value` | -1.3726 | +0.0000 | 127.50 | 0.08556 | 28/50 |
| rl_seed7 | Reflex Agent | `total_compute_cost` | +19.8949 | +0.0000 | 169.00 | 0.3042 | 29/50 |
| rl_seed7 | Reflex Agent | `avg_compute_cost_per_step` | +0.0663 | +0.0000 | 169.00 | 0.3042 | 29/50 |
| rl_seed7 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `total_utility` | +26.0577 | +94.4480 | 520.00 | 0.2612 | 50/50 |
| rl_seed7 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `completion_rate` | +0.0810 | +0.0650 | 87.50 | 1.202e-06 | 45/50 |
| rl_seed7 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `value_weighted_completion_rate` | +0.0680 | +0.0500 | 159.00 | 7.239e-07 | 50/50 |
| rl_seed7 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `uncapped_completion_rate` | +0.0116 | +0.0150 | 386.00 | 0.09104 | 46/50 |
| rl_seed7 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `failure_rate` | +0.0226 | +0.0200 | 259.50 | 0.002126 | 46/50 |
| rl_seed7 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `total_completed_value` | +20.2294 | +15.0150 | 159.00 | 7.239e-07 | 50/50 |
| rl_seed7 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `total_compute_cost` | +182.9762 | +200.1150 | 141.00 | 2.15e-07 | 50/50 |
| rl_seed7 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `avg_compute_cost_per_step` | +0.6099 | +0.6670 | 141.00 | 2.15e-07 | 50/50 |
| rl_seed11 | Reflex Agent | `total_utility` | -3.9621 | +0.0000 | 136.00 | 0.07976 | 29/50 |
| rl_seed11 | Reflex Agent | `completion_rate` | -0.0042 | +0.0000 | 80.00 | 0.07419 | 23/50 |
| rl_seed11 | Reflex Agent | `value_weighted_completion_rate` | -0.0047 | +0.0000 | 126.50 | 0.0815 | 28/50 |
| rl_seed11 | Reflex Agent | `uncapped_completion_rate` | -0.0052 | +0.0000 | 120.00 | 0.2512 | 25/50 |
| rl_seed11 | Reflex Agent | `failure_rate` | +0.0060 | +0.0000 | 71.50 | 0.07382 | 22/50 |
| rl_seed11 | Reflex Agent | `total_completed_value` | -1.3726 | +0.0000 | 127.50 | 0.08556 | 28/50 |
| rl_seed11 | Reflex Agent | `total_compute_cost` | +19.8949 | +0.0000 | 169.00 | 0.3042 | 29/50 |
| rl_seed11 | Reflex Agent | `avg_compute_cost_per_step` | +0.0663 | +0.0000 | 169.00 | 0.3042 | 29/50 |
| rl_seed11 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `total_utility` | +26.0577 | +94.4480 | 520.00 | 0.2612 | 50/50 |
| rl_seed11 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `completion_rate` | +0.0810 | +0.0650 | 87.50 | 1.202e-06 | 45/50 |
| rl_seed11 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `value_weighted_completion_rate` | +0.0680 | +0.0500 | 159.00 | 7.239e-07 | 50/50 |
| rl_seed11 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `uncapped_completion_rate` | +0.0116 | +0.0150 | 386.00 | 0.09104 | 46/50 |
| rl_seed11 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `failure_rate` | +0.0226 | +0.0200 | 259.50 | 0.002126 | 46/50 |
| rl_seed11 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `total_completed_value` | +20.2294 | +15.0150 | 159.00 | 7.239e-07 | 50/50 |
| rl_seed11 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `total_compute_cost` | +182.9762 | +200.1150 | 141.00 | 2.15e-07 | 50/50 |
| rl_seed11 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `avg_compute_cost_per_step` | +0.6099 | +0.6670 | 141.00 | 2.15e-07 | 50/50 |
| rl_seed13 | Reflex Agent | `total_utility` | -3.9621 | +0.0000 | 136.00 | 0.07976 | 29/50 |
| rl_seed13 | Reflex Agent | `completion_rate` | -0.0042 | +0.0000 | 80.00 | 0.07419 | 23/50 |
| rl_seed13 | Reflex Agent | `value_weighted_completion_rate` | -0.0047 | +0.0000 | 126.50 | 0.0815 | 28/50 |
| rl_seed13 | Reflex Agent | `uncapped_completion_rate` | -0.0052 | +0.0000 | 120.00 | 0.2512 | 25/50 |
| rl_seed13 | Reflex Agent | `failure_rate` | +0.0060 | +0.0000 | 71.50 | 0.07382 | 22/50 |
| rl_seed13 | Reflex Agent | `total_completed_value` | -1.3726 | +0.0000 | 127.50 | 0.08556 | 28/50 |
| rl_seed13 | Reflex Agent | `total_compute_cost` | +19.8949 | +0.0000 | 169.00 | 0.3042 | 29/50 |
| rl_seed13 | Reflex Agent | `avg_compute_cost_per_step` | +0.0663 | +0.0000 | 169.00 | 0.3042 | 29/50 |
| rl_seed13 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `total_utility` | +26.0577 | +94.4480 | 520.00 | 0.2612 | 50/50 |
| rl_seed13 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `completion_rate` | +0.0810 | +0.0650 | 87.50 | 1.202e-06 | 45/50 |
| rl_seed13 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `value_weighted_completion_rate` | +0.0680 | +0.0500 | 159.00 | 7.239e-07 | 50/50 |
| rl_seed13 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `uncapped_completion_rate` | +0.0116 | +0.0150 | 386.00 | 0.09104 | 46/50 |
| rl_seed13 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `failure_rate` | +0.0226 | +0.0200 | 259.50 | 0.002126 | 46/50 |
| rl_seed13 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `total_completed_value` | +20.2294 | +15.0150 | 159.00 | 7.239e-07 | 50/50 |
| rl_seed13 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `total_compute_cost` | +182.9762 | +200.1150 | 141.00 | 2.15e-07 | 50/50 |
| rl_seed13 | Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | `avg_compute_cost_per_step` | +0.6099 | +0.6670 | 141.00 | 2.15e-07 | 50/50 |
| Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | Reflex Agent | `total_utility` | -30.0198 | -96.1823 | 505.00 | 0.2045 | 50/50 |
| Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | Reflex Agent | `completion_rate` | -0.0852 | -0.0700 | 78.00 | 2.663e-07 | 47/50 |
| Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | Reflex Agent | `value_weighted_completion_rate` | -0.0727 | -0.0606 | 126.00 | 7.235e-08 | 50/50 |
| Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | Reflex Agent | `uncapped_completion_rate` | -0.0168 | -0.0300 | 292.50 | 0.01099 | 45/50 |
| Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | Reflex Agent | `failure_rate` | -0.0166 | -0.0200 | 339.50 | 0.01745 | 47/50 |
| Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | Reflex Agent | `total_completed_value` | -21.6020 | -17.0250 | 125.00 | 7.524e-07 | 50/50 |
| Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | Reflex Agent | `total_compute_cost` | -163.0813 | -181.7490 | 171.00 | 1.547e-06 | 50/50 |
| Tuned Utility-Based Agent (alpha=4.0, beta=1.0, gamma=4.0) | Reflex Agent | `avg_compute_cost_per_step` | -0.5436 | -0.6058 | 171.00 | 1.547e-06 | 50/50 |
