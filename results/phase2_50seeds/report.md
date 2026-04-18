# Baseline comparison

- Config: `default` (hash `10467f620611`)
- Utility weights: alpha=1.0, beta=0.1, gamma=1.0
- Seeds (50): [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49]
- Jobs per run: 100
- Max steps (capped): 300
- Uncapped max steps: 900

## Summary
| Agent | Runs | Mean Total Utility | Mean Completion Rate | Mean Value-Weighted Completion | Mean Uncapped Completion | Mean Compute Cost | Mean Failure Rate |
|---|---|---|---|---|---|---|---|
| Reflex Agent | 50 | 120.9909 | 0.6366 | 0.6970 | 0.8118 | 744.4695 | 0.1452 |
| Utility-Based Agent (Non-Learning Baseline) | 50 | 111.5240 | 0.5242 | 0.5956 | 0.7882 | 554.2255 | 0.1264 |

## Head-to-head
- Utility wins on total utility: 19/50
- Reflex wins on total utility:  31/50
- Ties: 0
- Utility better completion: 4/50
- Utility lower cost: 41/50
