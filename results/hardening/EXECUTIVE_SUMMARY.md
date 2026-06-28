# Hardening pass — executive summary

A skeptical-reviewer pass on the orchestration paper. Detail in `LOG.md`;
claim-by-claim fixes in `CLAIMS_REVISION.md`; diagnostics in
`../../scripts/hardening/`. Everything below is a measurement tied to a
committed script, not an assertion.

## The one-line reframe

The paper claims: *"the reward shape — not the algorithm and not the observation
— determines the always-execute attractor."* The evidence (full measured table:
`taxonomy_table.txt`; all on 50 held-out seeds, true metric, multi-seed) says it
is **false in every case**, for **three different reasons**:

| environment (lever) | always-exec util | hand ref | REINFORCE (3 seeds) | PPO (3 seeds) | what determines it |
|---|---:|---:|---|---|---|
| benign default (none) | 111.5 | 114.3 (+2.8) | — | **~always-exec (+1, ~100% exec)** | ENVIRONMENT: trivial optimum; RL correctly does not scale |
| env_tight (scale +6.2) | 82.8 | 89.1 | **stuck, +0.0 all 3** | **+21,+28,+23 (p<1e-7)** | OPTIMISER: REINFORCE too weak; PPO finds it |
| env_heavytail_tight (scale +18.5) | 451.6 | 470.0 | **stuck, +0.0 all 3** | (finishing) | OPTIMISER: even a 3× bigger lever doesn't rescue REINFORCE |
| env_cascade, fixed reward (caution +120) | 21.0 | 34.1 | **+120 (p=1e-15), fail 51%→5%** | **+97..+122** | adequate reward+lever → RL succeeds |
| env_cascade, broken reward (A1 bug) | 21.0 | 34.1 | **stuck reckless, +0.0** | only +18 (partial) | REWARD BUG: removes the direct failure signal |

So the honest contribution is a **taxonomy of why a scalar-utility scheduler can
look trivial**: (1) the *environment* has a trivial optimum, (2) the *optimiser*
(REINFORCE) is too weak to find a real but modest improvement, or (3) the
*reward* is mis-specified (A1). None is "the reward shape." In every cell where a
non-execute action genuinely pays and the reward+optimiser are adequate, RL
learns it — and PPO *adapts*: it stays at always-execute on the benign env
(correct) and scales hard only where scaling pays. The cascade-broken cell is the
sharpest single demonstration that the A1 fix is material: same env, same
REINFORCE, the fix turns reckless-always-execute (51% failure, util 21) into a
caution policy (5% failure, util 141).

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

## The decisive experiments — RESOLVED

- **env_tight, REINFORCE (4 variants: curriculum, +corrected reward, flat
  no-curriculum, +10× entropy; all seeds):** every one converges to 100%
  always-execute, even though a scaling policy pays +6.21 on both the
  undiscounted utility (p=0.033) and the discounted training return (+2.06,
  p=0.012). So it is not a discount artifact — it is a genuine optimisation
  failure.
- **env_tight, PPO (3 seeds):** all three learn to scale and beat always-execute
  by **+21 to +28 utility (p<1e-7)**, beating the hand-crafted scaler too. A
  stronger optimiser removes the attractor under the identical reward and
  environment → the env_tight result is REINFORCE-specific.
- **env_cascade (caution pays), broken vs fixed reward:** with the Phase-5/6
  reward, RL = reckless always-execute (51% failure, util 21); with the A1 fix,
  RL learns caution (4.6% failure, util 141; +120, p=1e-15). The reward bug is
  material.

## What a hostile reviewer could still demand (remaining gaps)

- PPO/CMDP on the *cascade* env (REINFORCE already learns it; PPO and a CMDP
  would likely both succeed — lower priority now that the mechanism is clear).
- The CMDP "corrective" the paper promises: note the analytical catch — a CMDP
  does **not** fix a benign environment (no caution lever to constrain), and on
  a lever-bearing env a *better optimiser or the corrected scalar reward already
  suffices*, so "CMDP is the unique corrective" is overstated. Worth softening.
- Heavy-tailed value (needs a workload-generator mixture; the
  capacity/load-failure/cascade levers were config- or small-code-only and were
  done first).
