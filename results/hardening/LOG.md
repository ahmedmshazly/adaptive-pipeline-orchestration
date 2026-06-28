# Hardening Log — skeptical-reviewer pass

Branch: `hardening/phase0-reviewer`. Parent commit at start: `2ae01ea`.
Every result here traces to a committed script under `scripts/hardening/` and
a CSV under `results/hardening/`. Numbers in the paper are **not** edited until
a replacement run with a manifest exists.

Working rules in force:
- Never silently change a paper number; every figure traces to a committed run.
- When a result contradicts the paper's story, surface it loudly.
- Distinguish "more of the same on the benign env" (low value) from "new
  evidence that varies a previously-fixed factor" (high value).

Environment deviation from the paper (recorded, not hidden): the paper pins
Python 3.11 / torch 2.1.x / numpy 1.26.x / scipy 1.11.x. This machine has no
matching interpreter, so the pass runs under **Python 3.12.3, torch 2.12.1+cpu,
gymnasium 1.3.0, numpy 2.1.3, scipy 1.18.0** (frozen set in
`results/hardening/frozen_env.txt`). All 132 tests pass unchanged on this
stack, which is itself a (previously-unverified) reproducibility result.

---

## Stage A0 — make the code runnable + green tests

- Created `.venv`; added the missing RL deps (`torch`, `gymnasium`) that
  `requirements.txt` never listed despite all of `src/rl/` depending on them.
- `pytest -q`: **132 passed in 30.1s**. The suite was never runnable as
  shipped (system python had no pytest/torch/gymnasium, no venv).
- Froze exact versions → `frozen_env.txt`.

Status: the repository's own test suite had not been executable from a clean
checkout. It is now, and passes on a 3-major-version-newer stack.

---

## Stage A1 — the "shared utility" identity is broken on the risk term [CONFIRMED]

Script: `scripts/hardening/diag_reward_identity.py`
Data: `results/hardening/reward_identity.csv`

Paper §4.3.3 claims: "the cumulative sum Σ r_t equals the total episode utility
reported throughout, so the RL agent is trained on exactly the objective it is
scored against." This is the instrument the whole attribution argument rests on
(the three-role identification of one scalar U).

Measured on seeds 200–209, an always-execute trajectory scored two ways on the
identical seed:

| quantity | result |
|---|---|
| mean( Σr_t − U_metric ) | **+15.78** |
| max \| Σr_t − U_metric \| | **23.0** |
| Σr_t − U_metric == γ·(failed_jobs − final_recent_failures)? | **exact, max err 0.00e+00** |
| value term telescopes (Σ Δvalue == completed_value) | **True** |
| cost term telescopes (Σ step_cost == compute_cost) | **True** |
| risk term telescopes to the METRIC (failed_jobs) | **False** |
| risk term telescopes to the decaying COUNTER | **True** |

Mechanism: the RL reward uses `γ·Δ(normalised recent_failures)` (`env.py:232`),
which telescopes to `γ·(final counter value)`. The counter decays −1 every step
(`sim_environment.py:635`), so it is ≈0 at episode end. The metric uses
`γ·failed_jobs` (`metrics.py:104`). Example (seed 200): 23 jobs fail; the
scoreboard penalises −23, the RL reward's risk contribution is −γ·0.0 = 0.

**Consequence:** every Phase-5/6 RL policy was trained on `α·Value − β·Cost`
with the `γ·Risk` term silently ≈ 0 — i.e. with **no failure penalty** — while
being *scored* with the full one. The "trained on exactly the objective it is
scored against" claim is false, and the three-role identification is violated:
there is a genuine objective mismatch. (Direction of the headline likely
survives, since dropping the failure penalty only makes always-execute *more*
attractive, and failures are decision-independent anyway — but the claim and
the instrument must be fixed and re-run.)

Fix (to implement, config-gated for reproducibility): make the per-step risk
reward `γ·Δfailed_jobs` (jobs newly failed this step) so Σ r_t = U exactly.

---

## Stage A2 — the RL-vs-Reflex gap is a real deterministic difference, not noise [CONFIRMED]

Script: `scripts/hardening/diag_trace_diff.py`
Data: `results/hardening/trace_diff_per_seed.csv`

Held-out eval path is deterministic argmax: `phase5_heldout.py:152`
(`deterministic=True`) → `agent.py:61` (`torch.argmax`). No sampling. So the
reported p=0.08 gap cannot be sampling noise or an entropy tax (c_H only shapes
the *training* distribution). RL (argmax, Phase-5 seed-7 best-by-val) and Reflex
run independently on all 50 held-out seeds (200–249):

| measurement | value |
|---|---|
| RL emitted action = Execute_Ready_Job | **15000/15000 (100%)** on all 50 seeds |
| of which silent no-ops (blocked/empty, nothing launches) | **1373 (9.2%)** |
| Reflex non-execute emissions | **303 (2.0%)** — Scale_Up 176, Defer 127 |
| per-step EFFECT agreement (RL vs Reflex) | **mean 0.936**, min 0.803, max 0.993 |

The two are *different* deterministic policies. RL emits Execute
unconditionally and no-ops in capacity-blocked/empty states; Reflex scales up or
defers in exactly those states (`reflex_agent.py:25`). They disagree on effect
~6.4% of steps, and Reflex is consistently slightly ahead. The paper's "the
learned policy has converged to a deterministic version of the same rule the
Reflex Agent implements" is mechanistically wrong, and p=0.08 is an underpowered
failure-to-reject of a real gap in Reflex's favour. Under more power (Stage D)
this is expected to become "RL is slightly but *significantly worse* than
Reflex." The integrity constraint stands: if it flips, that is the reported
finding.

---

## Stage A3 — always-execute IS a local optimum of the TRUE objective here [CONFIRMED]

Script: `scripts/hardening/diag_local_optimality.py`
Data: `results/hardening/local_optimality.csv`

v1 (single-future CRN, max-over-actions) produced a misleading "70% of states
have an improving deviation." That figure is an artifact of (a) order-statistic
bias from taking the max over 5 actions and (b) event-RNG desync between
branches (different actions consume different numbers of random draws, so the
"common random numbers" break after the first step and failure-sequence noise
dominates — hence ±53 swings). Notably, v1's *per-action* mean advantages were
all ≤ 0, which already leaned benign.

v2 (Monte-Carlo over K=16 paired futures, no max, per-action bootstrap CIs,
scored on the true metric) on seeds 200–204, 75 probed states:

| action | mean advantage A_π(s,a) | 95% CI | P(adv>0) |
|---|---:|---|---:|
| Defer_Job | −1.38 | [−2.13, −0.68] | 29.3% |
| Scale_Up | −1.38 | [−2.13, −0.67] | 29.3% |
| Scale_Down | −7.18 | [−8.40, −6.01] | 2.7% |
| Reprioritize_Queue | −0.64 | [−1.43, +0.20] | 41.3% |
| Pause_LowPriority_Job | −2.63 | [−3.55, −1.67] | 24.0% |

**No non-execute action has a 95% CI entirely above 0.** Every one is, on
average, a negative-advantage deviation from always-execute. So always-execute
is a local optimum of the *true objective* in this environment.

**This is the decisive empirical confirmation of the Q1 critique.** "Always-
execute wins" is determined by the benign environment — one where no reachable
state rewards caution — not (or not only) by the reward shape. The paper's
attribution ("the reward shape, not the algorithm and not the observation,
determines the attractor") is confounded: the environment alone is sufficient.
The honest narrow claim the current experiments support is: *on a benign,
feasibility-unconstrained, decision-independent-failure environment, scalar-
utility REINFORCE correctly finds the always-execute optimum, robustly to
reward weights, observation dimension, and seed.* Separating reward shape from
environment requires varying the environment (Stage B / Phase 2).

Operational note: this run was throttled to ~4% CPU in the background (453s CPU
→ 2h57m wall). Foreground gets full CPU but caps at 600s/call. Phase-2 strategy
therefore: use the *probe* (no training, ~450s foreground) as the decisive test
on each varied environment, and size any confirmatory training run to fit.

---

## Stage A summary

Three Phase-0 findings, all now measured (not just code-read):
1. **A1** — Σr_t ≠ episode utility (risk term); the "shared utility" instrument
   is broken; RL trained with ≈0 failure penalty. *Fix + re-run required.*
2. **A2** — RL ≠ Reflex; the p=0.08 gap is a real deterministic behavioural
   difference (6.4% effect divergence), not noise; expected to go significant
   (against RL) under power.
3. **A3** — always-execute is a local optimum of the true objective *in this
   env*; the headline attribution is confounded with a benign environment.

Next: Stage B — vary the environment (heavy-tail value, capacity-exceeding
jobs, decision-dependent failure) and re-run the A3 probe; if always-execute
stops being locally optimal there, the reward-shape claim is falsified and the
honest claim is "scalar utility + benign env → trivial optimum."
