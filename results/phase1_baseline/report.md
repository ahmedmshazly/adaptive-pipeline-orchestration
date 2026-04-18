# Baseline comparison

- Config: `default` (hash `a8a5dd78dc96`)
- Utility weights: alpha=1.0, beta=0.1, gamma=1.0
- Seeds (10): [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
- Jobs per run: 100
- Max steps (capped): 300
- Uncapped max steps: 3000

## Summary
| Agent | Runs | Mean Total Utility | Mean Completion Rate | Mean Value-Weighted Completion | Mean Uncapped Completion | Mean Compute Cost | Mean Failure Rate |
|---|---|---|---|---|---|---|---|
| Reflex Agent | 10 | 113.1651 | 0.6310 | 0.6930 | 0.8050 | 781.6192 | 0.1630 |
| Utility-Based Agent (Non-Learning Baseline) | 10 | 106.0767 | 0.5120 | 0.5839 | 0.7720 | 535.3928 | 0.1560 |

## Head-to-head
- Utility wins on total utility: 4/10
- Reflex wins on total utility:  6/10
- Ties: 0
- Utility better completion: 0/10
- Utility lower cost: 9/10
