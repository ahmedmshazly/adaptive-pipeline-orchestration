# Phase-3 (α, β, γ) sweep + Pareto analysis

This file is the human summary for the machine-readable artifacts in
this run directory:

- `sweep.csv`              — per-(cell, seed) rows (1620 rows = 81 cells × 20 seeds).
- `cells.csv`              — per-cell aggregate statistics.
- `reflex.csv`,
  `reflex_aggregate.csv`   — weight-independent Reflex baseline on the same seed pool.
- `pareto_fronts.csv`      — Pareto-frontier membership per 2D projection.
- `best_fixed_weight.json` — the selected "best fixed-weight" Utility-Based cell
                             that the RL agent will be benchmarked against.
- `phase3_pareto.png`      — three-panel frontier figure (horizontal layout).
- `phase3_pareto_vertical.png` — same figure, vertical layout.

## Run configuration

- Grid: 4 × 5 × 4 = **80 Utility-Based cells**.
  - α ∈ {0.5, 1.0, 2.0, 4.0}
  - β ∈ {0.05, 0.1, 0.25, 0.5, 1.0}
  - γ ∈ {0.5, 1.0, 2.0, 4.0}
- Plus one off-grid reference cell (midterm weights, β=0.4), so the total
  number of Utility-Based cells executed is **81**.
- Seeds: **100..119** (20 seeds, a dedicated sweep pool that does not
  overlap with the 0..49 baseline pool or the 200+ RL-evaluation pool).
- 100 jobs per episode, 300-step capped budget.
- Evaluation utility (shared across cells and used for cross-cell ranking
  and as the RL reward): **α=1.0, β=0.1, γ=1.0**.
- Reflex baseline: run once on the same 20 seeds (weight-independent).
- Config hash: see `run_manifest.json`.

## Reference points

| Agent | α | β | γ | mean_U | completion | cost | failure |
|---|---:|---:|---:|---:|---:|---:|---:|
| Reflex baseline | — | — | — | **123.41** | **0.636** | 668.6 | 0.165 |
| Midterm Utility | 1.0 | 0.4 | 0.8 | 113.88 | 0.542 | 548.6 | 0.144 |
| Phase-1 Utility | 1.0 | 0.1 | 1.0 | 113.88 | 0.542 | 548.6 | 0.144 |
| **Best fixed-weight** | **4.0** | **1.0** | **4.0** | **118.24** | 0.584 | 605.7 | 0.153 |

(The Phase-1 cell in this sweep has the same measured metrics as the
midterm cell because γ does not affect the utility agent's scoring rule
at the points where the Utility-Based policy is saturated at "execute or
block" — both cells produce the same per-seed action sequence under the
20 seeds 100..119. The cells remain distinct in the config and are only
numerically equal here.)

## Best fixed-weight: α=4.0, β=1.0, γ=4.0

Selected by `mean_utility_then_completion`: the single cell with the
highest `mean_utility_mean` under the shared evaluation utility (ties
broken by higher completion_rate). Alternative selection rules
(`completion`, `dominator_of_midterm`) are supported by
`scripts/figs/phase3_pareto.py --selection-rule …`.

| Metric | Best fixed-weight | Midterm | Δ vs midterm | Reflex | Δ vs Reflex |
|---|---:|---:|---:|---:|---:|
| `mean_utility` (eval) | 118.24 | 113.88 | **+4.36** | 123.41 | **−5.17** |
| `completion_rate` | 0.5835 | 0.5415 | +0.042 | 0.6365 | −0.053 |
| `value_weighted_completion_rate` | 0.6523 | 0.6148 | +0.038 | 0.6952 | −0.043 |
| `cost` | 605.67 | 548.59 | +57.09 | 668.59 | −62.92 |
| `failure_rate` | 0.1525 | 0.1440 | +0.009 | 0.1650 | −0.013 |

So the best hand-tuned Utility cell:

- **Beats the midterm Utility cell by +4.36 units of mean_utility**
  (strictly better on completion and utility; strictly worse on cost and
  failure).
- **Does not beat Reflex on any single axis except cost and failure.**
  Reflex remains ahead on mean_utility by 5.17 units; on completion by
  0.053; on value-weighted completion by 0.043.

## Pareto-frontier findings

Frontier cells per 2D projection (from `pareto_fronts.csv`):

| Projection | # frontier cells |
|---|---:|
| completion_rate vs cost | **67** / 81 |
| completion_rate vs failure_rate | **60** / 81 |
| cost vs failure_rate | **1** / 81 |

The (cost, failure) plane has a single dominant cell — α=0.5, β=1.0,
γ=4.0, with cost=503.84 and failure=0.134. This cell jointly minimises
both axes, which visually matches the very tight frontier in the
rightmost panel of `phase3_pareto.png`. Every other projection is a real
trade-off with many non-dominated cells.

### Midterm dominance

For each projection, how many grid cells strictly Pareto-dominate the
midterm Utility reference (α=1.0, β=0.4, γ=0.8):

| Projection | # dominators |
|---|---:|
| completion vs cost | 0 |
| completion vs failure | 0 |
| cost vs failure | **11** |

No grid cell dominates the midterm on completion — which is consistent
with the "Utility-Based under-completes vs Reflex" finding from Phase 2.
11 cells jointly improve on cost **and** failure (including
α=0.5/β=1.0/γ=4.0, which Pareto-dominates the midterm on those two axes
and has a lower completion rate). Dominator cell IDs are in
`best_fixed_weight.json.midterm_dominance`.

### Notable corner cells

| Criterion | Cell | mean_U | completion | cost | failure |
|---|---|---:|---:|---:|---:|
| Highest completion | α=4, β=0.05, γ=1 | 117.24 | **0.600** | 641.8 | 0.155 |
| Lowest cost       | α=0.5, β=1.0, γ=4 | 100.86 | 0.475 | **503.8** | 0.134 |
| Lowest failure    | α=0.5, β=1.0, γ=4 | 100.86 | 0.475 | 503.8 | **0.134** |
| Highest mean_U    | α=4.0, β=1.0, γ=4 | **118.24** | 0.584 | 605.7 | 0.153 |

## Implications for the paper and the RL comparison

1. **The "conservative trap" has a Pareto face now.** The midterm
   critique ("the Utility-Based agent is dominated on completion; maybe
   this is just a weight choice") is answered empirically: among 80
   fixed-weight cells across a generous α, β, γ grid, **no cell
   dominates Reflex on completion-vs-cost or completion-vs-failure**.
   Reflex's throughput advantage is not a weight artefact; it is an
   artefact of the policy (launch whenever a ready task fits). The paper
   can now state "Pareto-frontier analysis in `phase3_pareto.png`"
   instead of claiming a trap.
2. **The RL agent's fixed-weight baseline is α=4, β=1, γ=4.** Under the
   same evaluation utility the RL reward uses, this is the strongest
   hand-tuned fixed-weight Utility-Based policy measured. Beating *this*
   is the bar to clear. Merely beating the midterm weights (113.88) or
   the Phase-1 default is no longer informative.
3. **The RL agent also has Reflex as an upper reference.** At Phase-1
   weights, Reflex beats even the best fixed-weight Utility cell by
   **+5.17** on mean_utility. If the RL agent cannot match or exceed
   Reflex on this axis, it does not justify the additional complexity.
4. **The shared-U experimental design holds.** Every fixed cell and the
   Reflex baseline are scored under the same evaluation utility
   (α=1.0, β=0.1, γ=1.0). The RL agent must be trained and evaluated
   under the same U so the eventual Phase-4 comparison is apples-to-
   apples.
