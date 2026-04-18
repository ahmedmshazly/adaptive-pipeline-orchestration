# Aggregate statistics — results/phase2_50seeds

- Seeds: **50** (0..49)
- Bootstrap: 10,000 resamples, seed=20260418, confidence=95%

## Per-agent means with 95% bootstrap CI
| Metric | Reflex mean (95% CI) | Utility mean (95% CI) |
|---|---|---|
| `completion_rate` | 0.6366  (0.6282, 0.6448) | 0.5242  (0.4958, 0.5518) |
| `value_weighted_completion_rate` | 0.6970  (0.6864, 0.7074) | 0.5955  (0.5683, 0.6216) |
| `uncapped_completion_rate` | 0.8118  (0.7998, 0.8236) | 0.7882  (0.7772, 0.7994) |
| `failure_rate` | 0.1452  (0.1344, 0.1566) | 0.1264  (0.1166, 0.1358) |
| `total_completed_value` | 209.9578  (206.4692, 213.6263) | 179.5866  (171.1350, 187.7500) |
| `total_compute_cost` | 744.4695  (685.6860, 802.5846) | 554.2255  (521.2797, 587.3003) |
| `avg_compute_cost_per_step` | 2.4816  (2.2835, 2.6781) | 1.8474  (1.7352, 1.9566) |
| `total_utility` | 120.9909  (114.7605, 127.3082) | 111.5240  (102.3454, 120.8045) |
| `steps_executed` | 300.0000  (300.0000, 300.0000) | 300.0000  (300.0000, 300.0000) |

## Paired Wilcoxon signed-rank on Utility − Reflex deltas
| Metric | mean Δ (95% CI) | median Δ | W | p-value | n_nonzero |
|---|---|---|---|---|---|
| `completion_rate` | -0.1124 (-0.1426, -0.0838) | -0.0700 | 32.50 | 1.204e-08 | 48/50 |
| `value_weighted_completion_rate` | -0.1014 (-0.1300, -0.0740) | -0.0541 | 35.00 | 7.656e-12 | 50/50 |
| `uncapped_completion_rate` | -0.0236 (-0.0370, -0.0100) | -0.0200 | 276.50 | 0.002314 | 47/50 |
| `failure_rate` | -0.0188 (-0.0290, -0.0090) | -0.0200 | 230.50 | 0.001172 | 45/50 |
| `total_completed_value` | -30.3712 (-38.8800, -22.4274) | -15.9250 | 35.00 | 7.656e-12 | 50/50 |
| `total_compute_cost` | -190.2440 (-243.4356, -135.7791) | -180.8150 | 107.00 | 1.618e-08 | 50/50 |
| `avg_compute_cost_per_step` | -0.6341 (-0.8135, -0.4524) | -0.6027 | 107.00 | 1.618e-08 | 50/50 |
| `total_utility` | -9.4668 (-17.0500, -1.9431) | -7.8089 | 406.00 | 0.02485 | 50/50 |
| `steps_executed` | 0.0000 (0.0000, 0.0000) | 0.0000 | nan | nan | 0/50 |
