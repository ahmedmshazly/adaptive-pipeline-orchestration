# Hardening pass — executive summary

A skeptical-reviewer pass on the orchestration paper. Detail in `LOG.md`;
claim-by-claim fixes in `CLAIMS_REVISION.md`; diagnostics in
`../../scripts/hardening/`. Everything below is a measurement tied to a
committed script, not an assertion.

## The one-line reframe

The paper claims: *"the reward shape — not the algorithm and not the observation
— determines the always-execute attractor."* The evidence says: **the benign
environment determines it.** On the committed environment, always-execute is the
genuine optimum of the true objective; an RL agent finding it is success, not a
failure mode. The defensible paper is *"benign env + scalar reward → trivial
optimum that RL correctly finds,"* shown by varying the environment.

## What was claimed vs what is true

| # | Paper claim | Status | Evidence |
|---|---|---|---|
| 1 | "Σrₜ equals the episode utility — trained on exactly what it is scored against" (§4.3.3) | **FALSE** | risk term telescopes to a decaying counter (≈0), not `failed_jobs`; mean gap +15.78. Fixed config-gated (`failed_jobs_delta`). `diag_reward_identity.py` |
| 2 | "Matches Reflex within sampling noise (p=0.08)" | **FALSE (underpowered)** | eval is argmax (no sampling); at n=250 RL is **significantly worse** (−3.06, p=2.3e-3); power at n=50 was 0.29. `diag_power_rliable.py` |
| 3 | "Reward shape, not env/algorithm/observation, determines the attractor" | **CONFOUNDED** | env never varied; on benign env always-execute is a local optimum (all non-exec actions CI≤0); on `env_tight` a scaling policy beats it +6.21, p=0.033, same reward. `diag_local_optimality.py`, `diag_policy_compare.py` |
| 4 | "RL beats the tuned hand-designed agent" | **WEAK COMPARAND** | Tuned UB itself loses to Reflex (−30, p=0.013); reduces to "RL ≈ Reflex > a deliberately weak agent" |
| 5 | NHR / Skalse "imply" the result | **OVERREACH** | both are about adjacent setups (potential-based shaping; reward simplification); analogy, not implication. CMDP/Lagrangian leg is sound |
| 6 | γ·Risk is a real trade-off axis | **INERT in env** | `per_step_single_victim` makes failure decision-independent; no policy can trade throughput for risk |

## What changed in the code (all committed, tests green: 132 → 136)

- `rl.reward_risk_mode` added; `failed_jobs_delta` makes `Σrₜ = U` exactly
  (`tests/test_reward_identity.py`). Default unchanged → Phase-5/6 reproduce.
- `requirements.txt` now declares `torch` + `gymnasium` (were missing); venv +
  frozen lockfile; suite runs from a clean checkout.
- `config/env_*.yaml` environment-variation configs + generator.
- `scripts/hardening/` diagnostics (reward identity, trace diff, local
  optimality probe, policy compare, power/rliable, figures).
- README rewritten to match reality (was describing the abandoned v0).
- `SPECIFICATION.md` §5.4 documents the reward identity.

## The decisive open experiment (in progress)

Does REINFORCE *itself* learn to scale on `env_tight`, where scaling pays
+6.21? Three runs (curriculum / curriculum+corrected-reward / flat no-curriculum,
all seed 7). Early reads (updates 100–250): **still 100% Execute, byte-identical
to always-execute**, validation pinned at the always-execute value. If this holds
at convergence, the finding sharpens to: *"the always-execute attractor is
sticky across the curriculum, persisting into a regime where a non-execute action
provably pays"* — an optimisation result, separable from reward shape by the flat
schedule and (next) an entropy/PPO control. **[Final verdict pending run
completion — see LOG.md Stage B-RL.]**

## What a hostile reviewer should still demand (honest gaps)

- PPO / actor-critic on the same env+reward (algorithm-independence is asserted,
  not shown). Cheap intermediate: entropy-boosted REINFORCE.
- CMDP/RCPO corrective — but note the analytical catch: a CMDP does **not** fix a
  benign environment (no caution lever to satisfy a constraint over), so the
  paper's "CMDP is the corrective" is itself mis-targeted; the corrective for a
  trivial optimum is a richer *environment*, not a reward reformulation.
- Heavy-tailed value (needs a workload-generator mixture; config-only variants
  done for capacity and load-failure).
