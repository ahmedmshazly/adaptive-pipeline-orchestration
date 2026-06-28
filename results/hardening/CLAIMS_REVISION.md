# Claims revision — what the paper must change to match the evidence

The paper source (`.tex`) is not in this repository, so this document is the
hand-off: for each claim that outruns the evidence, it gives the location, the
current wording, the problem, the measurement that bears on it, and a revised
wording that a hostile TMLR / systems reviewer would accept. Severity tags:
**[FATAL]** (a stated claim is false or unsupported), **[NARROW]** (true but
overreaching — must be scoped), **[FRAME]** (framing that begs the question or
flatters a weak comparand).

Every measurement cited traces to `results/hardening/LOG.md` and a committed
script under `scripts/hardening/`.

---

## 1. [FATAL] "Trained on exactly the objective it is scored against" (§4.3.3)

**Current:** "The cumulative sum Σ rₜ equals the total episode utility reported
throughout, so the RL agent is trained on exactly the objective it is scored
against."

**Problem:** false on the risk term. The per-step reward uses
`γ·Δ(normalised recent_failures)`; that counter decays −1/step, so the sum
telescopes to its end value (≈0), while the metric penalises `γ·failed_jobs`.

**Evidence** (`diag_reward_identity.py`, `reward_identity.csv`): over seeds
200–209, `Σrₜ − U` has mean **+15.78**, max **+23.0**, and equals
`γ·(failed_jobs − final_counter)` to machine precision. Value and cost terms
telescope; risk does not. Every Phase-5/6 policy trained with the failure
penalty ≈ 0.

**Revision:** either (a) adopt `reward_risk_mode = failed_jobs_delta` (now in
the code; `Σrₜ = U` exactly, `tests/test_reward_identity.py`) and re-run, then
state the identity as a *tested* property; or (b) if keeping the historical
reward, replace the sentence with: "The value and cost terms of the per-step
reward telescope to the reported metric; the risk term uses the per-step change
in the normalised failure counter, which does **not** telescope to
`γ·failed_jobs`. The learner therefore optimises value minus cost with a
near-zero failure penalty. We verify the always-execute result is unchanged
under the corrected reward (§X)." Do not claim a three-role identity the risk
term violates.

---

## 2. [NARROW→FATAL as stated] "The reward shape, not the algorithm and not the observation, determines the attractor" (abstract, §4, §6.9)

**Current:** billed as "the first minimally confounded demonstration of a
reward-shape-induced trivial-attractor failure mode," invariant to weights,
observation, and seed.

**Problem:** the environment — the one factor that actually controls whether any
non-execute action has positive expected value — was never varied. Weights,
observation, and seed were varied; none of them can manufacture a state where
caution pays. So "reward shape" and "benign environment" are confounded.

**Evidence:**
- `diag_local_optimality.py` (MC one-step policy-improvement, true metric): on
  the committed env, **every** non-execute action has a 95% CI ≤ 0 advantage vs
  always-execute (Defer −1.38 [−2.13,−0.68], Scale_Up −1.38 [−2.13,−0.67],
  Scale_Down −7.18, Reprioritize −0.64 [−1.43,+0.20], Pause −2.63). Always-
  execute is a *local optimum of the true objective* here.
- `diag_policy_compare.py` on `config/env_tight.yaml` (contended capacity, all
  tasks still feasible): under the **identical** reward, `scale_when_blocked`
  beats always-execute by **+6.21 utility, p=0.033**. The optimum is no longer
  trivial.

**Revision:** narrow the claim to what is shown. Suggested: "On an environment
whose committed structure (all jobs present at t=0, every task feasible on the
minimum cluster, light-tailed value, decision-independent failure) admits no
reachable state where a non-execute action has positive advantage, a scalar-
utility REINFORCE agent converges to always-execute, and this outcome is
invariant to reward weights, observation dimension, and seed. When the
environment is altered so that a non-execute action provably pays
(`env_tight`), the optimum under the *same* reward is non-trivial." Drop
"reward-shape-induced … failure mode" as the universal headline; it is the
*environment*, jointly with the reward, that yields the trivial optimum, and on
this environment always-execute is the correct optimum rather than a failure.

> The exact final wording depends on the in-progress experiment: does REINFORCE
> *itself* learn to scale on `env_tight`? (a) If yes → "the agent adapts when
> the environment rewards it; the trivial attractor was environment-determined."
> (b) If no (still always-execute despite scaling paying) → a *stronger,
> different* claim: "the always-execute attractor is sticky across the
> curriculum, persisting into a regime where a non-execute action provably pays"
> — an optimisation result to be separated from reward shape with PPO and a flat
> schedule. Fill from `results/hardening/rl_tight_*`.

---

## 3. [FATAL] "Matches the Reflex baseline to within sampling noise" (abstract, §6.7)

**Current:** the learned policy "matches the Reflex baseline to within sampling
noise (p=0.08)" and "has converged to a deterministic version of the same rule
the Reflex Agent implements."

**Problem:** held-out evaluation is deterministic argmax (`phase5_heldout.py:152`
→ `agent.py:61`), so there is **no sampling at evaluation**. The p=0.08 is over
workload variation across seeds, comparing two *different* deterministic
policies. And RL is not "the same rule": it emits Execute unconditionally and
no-ops in blocked states, whereas Reflex scales/defers there.

**Evidence** (`diag_trace_diff.py`): RL is 100% Execute (15000/15000), of which
9.2% are silent no-ops; Reflex emits non-execute 2.0%; per-step **effect
agreement 93.6%**, Reflex consistently slightly ahead (cost 786 vs 766, failure
0.155 vs 0.145).

**Revision (now settled by the power analysis):** the power check was run on a
pre-registered disjoint pool (n=250, seeds 1000–1249). Result: RL−Reflex =
**−3.06, Wilcoxon p=2.3e-3 (significant)**; power at n=50 was only **0.288**, so
the Phase-5 p=0.08 was an underpowered failure-to-reject. The corrected wording:
"The learned policy is deterministic always-execute; it differs from Reflex
(which scales/defers where always-execute no-ops) on ~6.4% of steps. On an
adequately powered held-out pool (n=250) RL is **significantly but slightly
worse** than Reflex (−3.06 utility, p=2.3e-3; TOST-equivalent within ±5 but not
±3). The Phase-5 'matches Reflex within sampling noise (p=0.08)' was an
underpowered failure-to-reject (28.8% power at n=50), not evidence of
equivalence." Drop every "equivalent"/"indistinguishable" phrasing.

---

## 4. [FRAME] "RL significantly outperforms the tuned hand-designed agent" (§6.7)

**Current:** headline that RL beats the Phase-3 grid-best Tuned UB (4,1,4) on
throughput metrics at p<1e-6.

**Problem:** Tuned UB is cost-averse (β=1), defers heavily, and itself *loses* to
Reflex (Δ=−30, p=0.013). "RL beats Tuned UB" reduces to "RL ≈ Reflex > a
deliberately weak comparand."

**Revision:** keep the number but strip the narrative weight: "RL exceeds the
grid-best fixed-weight Utility-Based agent on throughput metrics; note, however,
that this comparand is itself dominated by Reflex, so the comparison bounds RL's
advantage over *tuned hand-designed utility weights*, not over the rule-based
baseline. The decisive comparison is RL vs Reflex (§3)."

---

## 5. [NARROW] "Algorithm-independent in expectation" / "workload-independent by construction" (§7.5, §7.6)

**Current:** expectation arguments that the negative result is independent of
the algorithm (PPO would behave the same) and the workload.

**Problem:** the "workload-independent" claim is now directly contradicted on
`env_tight` (§2 above). The "algorithm-independent" claim is asserted while the
named control (PPO) is declined.

**Revision:** drop "workload-independent by construction." State the env_tight
result. For the algorithm claim, either run PPO on the same env+reward and
report it, or downgrade to: "We did not vary the algorithm; whether a different
policy-gradient method escapes the attractor is left open and is the natural
control."

---

## 6. [NARROW] Ng-Harada-Russell and Skalse are over-applied (§2.3)

**Current:** NHR "establishes that the shape of a reward … determines the set of
optimal policies"; Skalse "implies linear scalarisations generically admit
dominating simplifications."

**Problem:** NHR is about *potential-based additive shaping* invariance; the
paper's utility is the base reward, not a shaping term, so NHR is an analogy,
not an implication. Skalse characterises unhackability of a reward vs a given
simplification; "generically admit dominating simplifications" overstates it —
the paper has one environment where it happened, not a general theorem.

**Revision:** demote both to motivation: "These results frame, but do not
entail, our observation: NHR shows that *potential-based* shaping preserves
optimal policies, and Skalse et al. characterise when a reward simplification is
unhackable; neither directly predicts that a fixed linear scalarisation has a
trivial optimum on a given MDP, which is the empirical question we study." Keep
the CMDP/Lagrangian connection (§2.4) at full strength — it is correct: a fixed
linear scalarisation *is* the Lagrangian of the CMDP at fixed dual multipliers,
and learning the multipliers is the principled corrective.

---

## 7. [FRAME] "Risk" is presented as an actionable trade-off axis

**Current:** the utility trades value vs cost vs *risk*, implying a three-way
trade-off the agent navigates.

**Problem:** with `per_step_single_victim` failure, P(failure)=0.05 whenever ≥1
task runs, independent of the action. No policy can lower failure except by not
running (which forfeits value). The γ·Risk term is decorative *in the
environment*.

**Revision:** state it plainly as a limitation: "Under the committed failure
process, failure probability is decision-independent, so no policy can trade
throughput for lower risk; the risk term is inert in this environment. A
decision-dependent failure process (`per_node_bernoulli`) makes caution
weakly profitable (Δ≈+5 utility, not significant at p=0.05; `env_loadfail`)."

---

## 8. [FRAME] Course-report scaffolding

Remove "Semi-Final Project Report," "Project Mid-term Progress Report," "Project
Evolution Summary," and the running-header phase labels. They signal a course
artefact and invite a desk-reject reflex. Fix all `§??` cross-references and the
garbled inline math in the abstract (`p<106p<10−6` → `p<10⁻⁶`).

---

## Net effect on the contribution

The defensible paper is *not* "scalar reward induces a trivial-attractor failure
mode in systems RL." It is: **"On a benign orchestration MDP, a scalar utility
has a trivial (always-execute) optimum; REINFORCE correctly finds it, robustly
to weights/observation/seed; and we show — by varying the environment and by
diagnosing a reward-term mis-specification — that this is a property of the
environment-plus-reward, not of the algorithm or the observation. When the
environment is altered so caution pays, the optimum under the same reward is
non-trivial."** That is a cleaner, smaller, and fully-supported claim, and it
still motivates the CMDP reformulation as future work.
