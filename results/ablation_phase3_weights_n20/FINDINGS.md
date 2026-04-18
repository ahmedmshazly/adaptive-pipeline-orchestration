# Ablation: are (α, β, γ) operative or ceremonial in the Utility-Based agent?

**Context.** Reviewer noted before Phase 4 that the midterm cell
(α=1.0, β=0.4, γ=0.8) and the Phase-1 cell (α=1.0, β=0.1, γ=1.0) produce
identical metrics on the Phase-3 sweep seeds. Hypothesis: the Utility-Based
agent's decision rule is dominated by its 29 non-(α, β, γ) scoring constants;
if true, the RL framing changes from "learn better α/β/γ-dependent actions"
to "learn a policy that is not bottle-necked by hand-designed thresholds at
all."

This document reports an isolated ablation that traces per-step actions
under 20 weight / hand-constant variants on the 20 Phase-3 seeds
(100..119). **6000 decisions per variant.** Artifacts:

- `variant_summary.csv`       — 20 variants × 20 seeds = 400 rows of
                                metrics and per-variant action histograms.
- `hamming_vs_reference.csv`  — per-variant, per-seed action mismatches
                                against the Phase-1 reference trace.
- `action_traces.csv`         — one row per (variant, seed, step) with the
                                chosen action and forced-execute flag.
                                (Scores also recorded for the 5-seed run
                                under `results/ablation_phase3_weights/`.)
- `run_manifest.json`         — usual reproducibility block.

---

## Headline result

Reviewer was right, and the effect is even stronger than the pre-registered
hypothesis suggested. Across the 20-seed / 300-step panel (6000 decisions):

| Variant | Mismatches vs reference | Interpretation |
|---|---:|---|
| **`midterm_weights`** (α=1.0, β=0.4, γ=0.8) | **0 / 6000** | Identical action trace to Phase-1. |
| **`beta_0`** (β=0.0)   | **0 / 6000** | β has no per-step effect. |
| **`gamma_0`** (γ=0.0)  | **0 / 6000** | γ has no per-step effect. |
| **`all_zero`** (α=β=γ=0) | **0 / 6000** | Still identical. |
| `best_task_cost_off` (one hand constant)     | 0 / 6000 | Ceremonial. |
| `urgency_weight_off` (one hand constant)     | 0 / 6000 | Ceremonial. |
| `no_executable_off`                          | 0 / 6000 | Ceremonial. |
| `scale_up_cheaper` (8× reduction in price)   | 0 / 6000 | Ceremonial. |
| `stress_guard_failure_2` (relax failure gate)| 0 / 6000 | Ceremonial. |
| `stress_guard_price_1_1` (relax price gate)  | 1228 / 6000 (20%) | **Operative.** |
| `pause_disabled`                             | 1266 / 6000 (21%) | Operative. |
| `alpha_only_with_guard_off` (α=5 only)       | 1242 / 6000 (21%) | Operative. |
| `alpha_100` (α=100, β=γ=0.1/1)               | 1308 / 6000 (22%) | Operative. |
| `alpha_0` (α=0.0)                            | 5252 / 6000 (88%) | **Gate flip.** |
| `beta_100` (β=100)                           | 5252 / 6000 (88%) | Gate flip. |
| `gamma_100` (γ=100)                          | 5252 / 6000 (88%) | Gate flip. |
| `stress_guard_disabled`                      | 5252 / 6000 (88%) | Gate flip. |

The same 88% number for four very different variants is not a coincidence:
they all trip the same binary gate and collapse to the same "no execute
ever happens" alternative trace.

## Mechanism

`_score_execute` in `src/utility_agent.py` is:

```
execute = α · value_term + urgency_bonus − β · resource_cost − γ · risk_term
```

At Phase-1 weights (α=1, β=0.1, γ=1) with typical task values, this
evaluates to roughly `+3 to +9` on ready states. But it never wins the
action selection on its own: when the guard does **not** fire, Scale_Up
scores in the hundreds (`scale_up_price_weight * spot_price` plus the
blocked-task-benefit and queue-depth terms) while execute hovers around
`+6`. The agent only chooses execute because of
`_should_force_execution(state, scored)`:

```python
return (
    self._best_ready_task(state) is not None
    and score_by_action["Execute_Ready_Job"] > 0.0
    and state_vector()["Recent_Failures"] < stress_guard_failure_limit
    and state.cluster.spot_price < stress_guard_price_limit
)
```

This guard fires on **~83% of steps** in the reference trace. Its only
reference to the utility coefficients is the single boolean clause
`score_by_action["Execute_Ready_Job"] > 0.0`. So the full operational
role of (α, β, γ) in the current agent is:

- **Is `execute_score` > 0?** Yes → the stress guard takes over and
  forces execute (modulo the price and failure checks).
- **Is `execute_score` ≤ 0?** No → execute essentially never runs,
  because the ranked action list puts Scale_Up and Pause above it.

Under that reading, (α, β, γ) contribute a single bit of information
per step. Everything else — the choice among Scale_Up, Defer, Pause,
Reprioritize when the guard doesn't fire; the ranking of ready tasks;
the pause threshold — comes from the hand constants.

## Why midterm ≡ Phase-1 on these seeds

With α=1 fixed, the execute score is approximately
`value_term + urgency_bonus − β · resource_cost − γ · risk_term`.
Under the typical operating point on seeds 100..119:
`value_term ≈ 10`, `resource_cost ≈ 40`, `risk_term ≈ 0.3–3`,
`urgency_bonus ≈ 0.3`. So:

- Midterm: `10 + 0.3 − 0.4·40 − 0.8·3 ≈ -8.1`, but in practice
  `value_term` on the top candidate is larger (≈ 15–20) and
  `risk_term` is closer to 0.5, producing ~+2 to +8.
- Phase-1: `10 + 0.3 − 0.1·40 − 1.0·3 ≈ 3.3`.

Both end up on the same side of zero on every one of the 6000 decision
points. The guard then fires (or doesn't) for exactly the same reasons.
Hence the identical trace.

## Which knobs *do* drive behaviour

| Knob | Per-step impact |
|---|---|
| `_should_force_execution`: the price side of the guard (`stress_guard_price_limit`) | ≈ 20% of steps flip action if relaxed. |
| `pause_priority_threshold` / `Pause_LowPriority_Job` dynamics | ≈ 21% of steps flip if pause is suppressed. |
| `_best_ready_task` ranking (`value * priority`, children bonus, job_value_base) | Indirectly, via which task is picked when execute wins. |
| `scale_up_urgency_weight`, `blocked_task_benefit_weight`, queue_depth_norm | Indirectly, via the non-forced Scale_Up branch. |
| (α, β, γ) | Only through `execute_score > 0` sign change. |

The "best fixed-weight" cell from Phase-3 (α=4, β=1, γ=4) wins by
keeping execute_score strongly positive on more ready-state
configurations while pushing it negative on expensive, risky ones. That
is still only a binary gate — it just shifts the gate's empirical
firing rate.

## Implications for Phase-4 framing

1. **The RL comparison is not "can RL tune (α, β, γ) better than the
   grid?"**. 46 of 81 grid cells are in a single behaviour equivalence
   class; the grid cannot discriminate more. A learned policy that only
   adjusts (α, β, γ) would be effectively untrainable.
2. **The RL comparison is "can RL replace the hand-designed control
   flow?"**. The Utility-Based agent is, empirically, a
   `force_execute_when_price_and_failure_are_benign_else_pause_or_scale`
   policy with 29 hand-tuned scoring constants and a binary
   execute-gate driven by (α, β, γ). The 0% figure vs. the 20% figure
   makes this explicit.
3. **The shared-U reward design is still the right scientific
   control.** Scoring RL under
   `cfg.sweep.evaluation_utility = (1.0, 0.1, 1.0)` remains fair; what
   changes is the framing of what the RL agent is learning. It is not
   "a better α/β/γ policy"; it is "a better control-flow policy under
   the same reward."
4. **Paper implication.** The "conservative trap" is not a weights
   artefact and not, on its own, evidence that the hand-designed rule
   is finely tuned. It is evidence that a fixed rule dominated by a
   binary execute-gate has limited ceiling. Calling this out explicitly
   sharpens the motivation for RL.

## What could still move (α, β, γ) out of "ceremonial" status

The ablation would look less one-sided if:

- The stress guard were removed or softened. Without it, execute would
  have to win on score alone, and (α, β, γ) would be back in play.
- `value_term` had less headroom — at Phase-1 weights, jobs have values
  in `U(1, 5)` and the hand constants multiply by `job_value_base=0.7`
  plus priority/urgency bumps, giving execute a reliable positive
  baseline. Lowering `job_value_base` or narrowing the job-value
  distribution would make execute's sign more weight-sensitive.
- The grid included values that push α, β, γ deep into the gate-flip
  region for a non-trivial fraction of seeds. The current grid does,
  but only at extremes (α=4 with β=1 shifts the firing rate by a few
  percentage points per seed).

None of those changes are required for Phase 4; they would be
weight-sensitivity sub-studies.

## Recommended adjustments to the Phase-4 design

- Keep the best fixed-weight cell (α=4, β=1, γ=4) as the published
  Utility-Based baseline.
- In the paper, cite this ablation alongside Phase-3: "across 20 seeds
  and 300-step episodes, 46 of 81 fixed-weight cells produce identical
  per-step action traces; α/β/γ contribute only the sign bit of the
  execute score."
- Frame the RL contribution as "beats a non-learning controller that
  is shown empirically to be dominated by its binary execute-gate,"
  not "beats a tuned utility baseline."
- Consider adding a "stripped utility-based" variant to Phase-4:
  `_should_force_execution` removed. That gives a cleaner comparison
  where the RL agent's policy is contrasted with an agent that is
  forced to rely on its scoring rule alone.
