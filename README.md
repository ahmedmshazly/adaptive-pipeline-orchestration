# A Self-Learning Utility-Based Agent for Adaptive Data Pipeline Orchestration — and what it taught us about scalar rewards

A simulation study of how different orchestration policies behave under changing
workload pressure, limited resources, variable spot prices, and execution
failures. The project compares three agents — a **Reflex** baseline, a
non-learning **Utility-Based** agent, and a **Self-Learning Utility-Based**
(reinforcement-learning) agent — that all share a single utility function
`U = α·Value − β·Cost − γ·Risk`.

> **What this project actually found (the honest headline).** Despite the title,
> the result is a *negative* one. On the committed environment, the self-learning
> agent trained by policy gradient on the shared utility converges to a trivial
> **always-execute** policy that is statistically indistinguishable from the
> Reflex baseline. The interesting question this raised — *is that because of the
> reward's shape, or because the environment has a trivial optimum?* — is being
> answered by the hardening pass documented in
> [`results/hardening/LOG.md`](results/hardening/LOG.md). Short version: on the
> committed (benign) environment, always-execute is genuinely a local optimum of
> the true objective, so the environment is doing more of the work than the
> original framing claimed. Varying the environment (`config/env_tight.yaml`)
> makes a non-execute action significantly better under the *same* reward.

This README describes the repository as it actually is. It is not the abandoned
"v0" baselines-only snapshot; that earlier README referenced files
(`sim_v0_environment.py`, `compare_baselines_v0.py`, `baseline_results_v0/`)
that no longer exist.

---

## Contents

- [Status](#status)
- [Quick start](#quick-start)
- [The three agents](#the-three-agents)
- [The shared utility and the environment](#the-shared-utility-and-the-environment)
- [Repository layout](#repository-layout)
- [Experimental phases and headline results](#experimental-phases-and-headline-results)
- [Hardening pass (ongoing)](#hardening-pass-ongoing)
- [How to run](#how-to-run)
- [Reproducibility](#reproducibility)
- [Limitations](#limitations)

---

## Status

| Component | State |
|---|---|
| Stochastic orchestration simulator (`src/sim_environment.py`) | implemented, tested |
| Reflex agent (`src/reflex_agent.py`) | implemented |
| Non-learning Utility-Based agent (`src/utility_agent.py`) | implemented |
| Self-Learning agent: REINFORCE + Gymnasium env + MLP policy (`src/rl/`) | implemented, trained (Phases 5–6) |
| Phases 1–6 experiments + figures | committed under `results/` |
| Test suite | **132 tests**, green on Python 3.12 / torch 2.12 |
| Hardening / skeptical-reviewer pass | in progress — see `results/hardening/LOG.md` |

---

## Quick start

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt   # includes torch + gymnasium
.venv/bin/python -m pytest -q                          # 132 tests, ~30 s
```

Run the baseline comparison (Reflex vs Utility-Based) on a seed group:

```bash
make baseline SEED_GROUP=midterm_baseline
```

Everything is config-driven from `config/default.yaml`; override with
`CONFIG=path/to/file.yaml`.

---

## The three agents

All three are evaluated against the **same** utility function. The design point
is that this isolates the effect of *learning the policy* from any change in the
objective.

- **Reflex Agent** (`src/reflex_agent.py`) — fixed condition→action rules:
  execute if a ready task fits; scale up under queue pressure at moderate price;
  scale down when idle and over-provisioned at high price; else defer. Does not
  read the utility function. Weight-independent.
- **Utility-Based Agent** (`src/utility_agent.py`) — scores all six actions with
  a hand-designed rule plus control-flow guards. An ablation
  (`results/ablation_phase3_weights_n20/FINDINGS.md`) shows its behaviour is
  dominated by a single binary "force-execute" gate; `(α,β,γ)` enter only
  through the sign of one score. A `StrippedUtilityBasedAgent` removes that gate
  as a control.
- **Self-Learning Utility-Based Agent** (`src/rl/`) — REINFORCE with a
  sequence-specific baseline (Decima-style), an MLP policy (64×64, tanh, softmax
  over 6 actions), no value head, three-stage curriculum, memoryless
  termination. The utility is its reward signal.

## The shared utility and the environment

Episode utility (the evaluation metric, `src/metrics.py`):

```
U = α·(completed value) − β·(total compute cost) − γ·(failed jobs)
```

with the committed Phase-1 weights `(α, β, γ) = (1.0, 0.1, 1.0)`. The simulator
is a discrete-time, single-cluster model with six actions (execute, defer, scale
up/down, reprioritize, pause-low-priority), three DAG templates, and three
stochastic processes (node failure, data spike, spot-price random walk). The
full normative spec is in [`SPECIFICATION.md`](SPECIFICATION.md); every numeric
parameter lives in `config/default.yaml` (no magic numbers in `src/`).

---

## Repository layout

```text
config/            default.yaml (single source of truth) + overrides
src/
  config.py        typed loader; hashes the resolved config
  sim_environment.py  data model, workload generator, dynamics, actions
  state.py         the observation dataclass (8-dim, 14-dim under state_v2)
  cost.py          pure cost(state, action)
  metrics.py       EpisodeMetrics + summarize_episode (the utility)
  reflex_agent.py / utility_agent.py
  runner.py        the single shared episode loop
  pareto.py        Pareto-frontier + best-fixed-weight selection
  rl/              env.py, policy.py, baseline.py, trainer.py, agent.py
scripts/           experiment drivers (sweep, train, aggregate, figures)
  hardening/       skeptical-reviewer-pass diagnostics (this round)
tests/             132 tests
results/           committed run artifacts (one dir per experiment)
  hardening/       LOG.md + diagnostics for the current pass
```

---

## Experimental phases and headline results

| Phase | What | Result |
|---|---|---|
| 1–2 | 50-seed Reflex vs Utility baseline | Utility-Based *underperforms* Reflex on its own objective (Δ=−9.47, p=0.025) |
| 3 | 81-cell (α,β,γ) sweep × 20 seeds | No fixed-weight cell beats Reflex; grid-best trails by 5.2 utility units |
| 3-ablation | action-trace ablation | β and γ are ceremonial (0/6000 action changes); a single binary gate decides behaviour |
| 4 | 3-agent baseline + RL smoke | scaffolding + sequence-specific baseline |
| 5 | full RL training (3 init seeds) | RL converges to deterministic **always-execute**; matches Reflex within noise (Δ=−3.96, p=0.08) |
| 6 (V1) | 14-dim richer state | held-out metrics **bit-identical** to the 8-dim policy → not an observation-capacity problem |

The Phase-5/6 conclusion was: the always-execute attractor is a property of the
committed reward, not of the algorithm or the observation. The hardening pass
below tests that attribution.

## Hardening pass (ongoing)

A skeptical-reviewer pass is interrogating the central claim. Full detail and
every measurement is in [`results/hardening/LOG.md`](results/hardening/LOG.md);
the diagnostics are under `scripts/hardening/`. Findings so far:

1. **The "shared utility" identity was broken on the risk term.** The per-step
   RL reward used `γ·Δ(normalised recent_failures)`, which telescopes to the
   decaying counter (≈0 at episode end), not to the metric's `γ·failed_jobs`. So
   `Σ rₜ ≠ U`: the learner trained with ≈ no failure penalty. Fixed, config-gated:
   `rl.reward_risk_mode = failed_jobs_delta` makes `Σ rₜ = U` exactly
   (`tests/test_reward_identity.py`); the default stays `counter_delta` so
   Phase-5/6 reproduce.
2. **The RL/Reflex gap is a real deterministic difference, not noise.** Held-out
   eval is argmax; RL is 100% execute (9.2% silent no-ops in blocked states);
   Reflex emits non-execute 2% of the time. They are two different deterministic
   policies, Reflex slightly ahead.
3. **The attractor is environment-determined, not (only) reward-determined.** On
   the benign default env, always-execute is a local optimum of the true
   objective (no non-execute action has a positive-advantage 95% CI). On
   `config/env_tight.yaml` (contended capacity, all tasks still feasible), a
   scaling policy beats always-execute by +6.21 utility, p=0.033, under the same
   reward. The open experiment is whether RL itself learns to scale there.

---

## How to run

The `Makefile` is the reproducibility surface. Key targets:

```bash
make test                 # pytest
make baseline             # Reflex vs Utility on a seed group
make phase2               # 50-seed baseline + aggregate + figure
make phase3               # 81-cell (α,β,γ) sweep + Pareto
make phase5-train-all     # 3 RL training runs (slow)
make phase5-heldout       # 3-agent held-out comparison
make phase6-all-v1        # 14-dim richer-state replication
```

Hardening diagnostics (fast, no training):

```bash
.venv/bin/python -m scripts.hardening.diag_reward_identity     # Σr_t vs U
.venv/bin/python -m scripts.hardening.diag_trace_diff          # RL vs Reflex traces
.venv/bin/python -m scripts.hardening.diag_policy_compare --config config/env_tight.yaml
.venv/bin/python -m scripts.hardening.make_env_configs         # regenerate env_*.yaml
```

---

## Reproducibility

- Every run writes `results/<run_id>/` with `config.yaml` (resolved),
  `run_manifest.json` (commit SHA, config sha256, seed list, wall-clock, library
  versions, hostname), and `metrics.csv`.
- Seeds are partitioned into disjoint pools (baseline / sweep / RL train / val /
  test), enforced at config load.
- Randomness goes through named `numpy.random.Generator`s spawned from one
  `SeedSequence` per seed.
- The exact dependency set verified for this pass is pinned in
  `results/hardening/frozen_env.txt` (Python 3.12 / torch 2.12 / numpy 2.1).

---

## Limitations

The committed environment is benign in ways that matter for the headline: all
100 jobs exist at episode start, every task fits on the minimum cluster, value
is light-tailed `U(1,5)`, and failures are decision-independent
(`per_step_single_victim`). On such an environment a scalar utility has a
trivial (always-execute) optimum, and an RL agent finding it is success, not a
pathology. The hardening pass is varying these factors to establish the narrow,
defensible version of the claim. See `results/hardening/LOG.md` for the live
state of that work.
