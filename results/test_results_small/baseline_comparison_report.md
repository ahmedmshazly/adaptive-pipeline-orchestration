# Baseline Comparison v0

## Run configuration
- Seeds: [0, 1, 2]
- Jobs per run: 20
- Max steps: 80

## Summary table
| Agent | Runs | Mean Total Utility | Mean Completion Rate | Mean Compute Cost | Mean Failure Rate | Mean Steps |
|---|---|---|---|---|---|---|
| Reflex Agent | 3 | -21.9905 | 0.7167 | 155.4347 | 0.2833 | 73.67 |
| Utility-Based Agent (Non-Learning Baseline) | 3 | -18.2337 | 0.6833 | 142.9260 | 0.2833 | 78.33 |

## Head-to-head summary
- Utility baseline had higher total utility in 1 / 3 runs.
- Reflex baseline had higher total utility in 1 / 3 runs.
- Ties on total utility: 1.
- Utility baseline had better completion rate in 0 runs.
- Utility baseline had lower total compute cost in 2 runs.

## Mean deltas (Utility baseline minus Reflex baseline)
- Total utility delta: 3.7568
- Completion rate delta: -0.0334
- Total compute cost delta: -12.5087

## Interpretation
These are v0 simulator baselines intended to validate the environment and the evaluation pipeline before adding the self-learning utility agent.
