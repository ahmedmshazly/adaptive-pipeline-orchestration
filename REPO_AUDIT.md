# Repo Audit — v0 midterm snapshot

This audit maps the repository state at the start of the reviewer-defect
hardening pass. It is a pre-refactor inventory: it records what exists on
`main` as of the v0 tag, what works end-to-end, what is duplicated, and what
is effectively dead code.

The subsequent commits on `cursor/reviewer-defects-hardening-3365` change
several of the items listed here (config, RNG discipline, run convention,
tests, Makefile). Where a change is already planned in the next commit, it is
called out explicitly in an *"Action"* note.

---

## 1. Modules

### Source code (`src/`)

| File | Role | LOC | Public surface used elsewhere |
|---|---|---|---|
| `src/sim_environment.py` | Simulator: data model, workload generator, dynamics, action application | ~556 | `ACTIONS`, `MAX_STEPS_DEFAULT`, `EpisodeState`, `TaskInstance`, `WorkloadGenerator`, `advance_one_step` |
| `src/reflex_agent.py` | Reflex baseline **+** shared evaluation primitives | ~273 | `ReflexAgent`, `EpisodeMetrics`, `estimate_step_cost`, `summarize_episode`, `run_reflex_episode`, `run_many_reflex_episodes`, and the utility constants `ALPHA / BETA / GAMMA / BASE_CPU / BASE_RAM` |
| `src/utility_agent.py` | Non-learning Utility-Based baseline | ~419 | `UtilityBasedAgent`, `run_utility_episode`, `run_many_utility_episodes` |
| `src/compare_baselines.py` | Matched-seed comparison driver | ~390 | CLI entry (`main`) |

There is no `src/__init__.py`; the modules rely on a manual
`sys.path.insert(0, THIS_DIR)` hack at the top of each file (`reflex_agent.py`
lines 28–33, `utility_agent.py` lines 32–37, `compare_baselines.py` lines
29–35) to support `python src/<file>.py` execution from the repo root.

### Non-source directories

| Path | Contents | Notes |
|---|---|---|
| `results/baselines_v0/` | `reflex_runs.csv`, `utility_runs.csv`, `summary.json`, `comparison_report.md` | Canonical v0 results as committed to the repo. |
| `results/test_results_small/` | Same four-file schema, 3-seed / 20-job sanity run | Redundant with `baselines_v0/`; kept as a smoke artifact. |
| `assets/charts/` | Four PNGs for the README (`baseline_mean_total_utility.png` etc.) | Committed binaries; **no generating script in repo**. |
| `assets/images/` | Six PNGs (architecture, UML, lifecycle, etc.) for the README | Committed binaries; no generating script. |
| `README.md` | Project overview + full midterm writeup | Single source of truth for the narrative. |
| `LICENSE` | MIT | — |

There is no `tests/`, `scripts/`, `config/`, or top-level packaging
(`pyproject.toml`, `requirements.txt`, `Makefile`, `justfile`). **Action** (next
commit): add all of `config/`, `tests/`, `scripts/`, `Makefile`.

---

## 2. Entry points

### Currently runnable

| Command | Script | What it does |
|---|---|---|
| `python src/sim_environment.py` | `_demo()` at the bottom of `sim_environment.py` (lines 534–555) | Smoke test: seed=7, 12 jobs, 5 `Execute_Ready_Job` steps. |
| `python src/reflex_agent.py` | `_demo()` in `reflex_agent.py` (lines 263–272) | Seed=7, 20 jobs, 120 steps; prints one episode summary. |
| `python src/utility_agent.py` | `_demo()` in `utility_agent.py` (lines 409–418) | Same as above for the Utility-Based baseline. |
| `python src/compare_baselines.py` | `main()` in `compare_baselines.py` (lines 376–385) | Full 10-seed comparison; writes to `results/baselines_v0/` by default. |

### CLI surface of the comparison driver

`compare_baselines.py` (lines 64–97) accepts:

- `--seeds` (list of ints, default `0..9`)
- `--num-jobs` (int, default `100`)
- `--max-steps` (int, default `300`)
- `--out-dir` (path, default `results/baselines_v0`)

There is **no** flag for `--config`, `--alpha/--beta/--gamma`, `--seed-split`,
`--sweep`, or `--run-id`. **Action** (next commit): replace/augment the flag
set with `--config`, `--out-root`, and `--run-id`; everything else moves into
`config.yaml`.

### Not present

- No RL training entry point.
- No (α, β, γ) sweep / Pareto driver.
- No plot-generation script.
- No paired-significance / CI aggregator.
- No held-out test-seed evaluator.

---

## 3. Configuration locations (current)

Configuration is implicit and scattered. The reviewer defect "no single source
of truth" is accurate: there is no `config.yaml` today. Every constant is a
`Final` module-level value in Python.

### Simulator constants — `src/sim_environment.py`

| Name | Line | Value | Used by |
|---|---|---|---|
| `ACTIONS` | 29 | six-action list | env, both agents |
| `NODE_FAILURE_PROB` | 38 | `0.05` | `apply_random_events` |
| `DATA_SPIKE_PROB` | 39 | `0.08` | `apply_random_events` |
| `MAX_STEPS_DEFAULT` | 40 | `300` | env, both agents, deadline-urgency normalizer |
| `BASE_CPU_CAPACITY` | 42 | `10` | cluster init, scale-boost decay |
| `BASE_RAM_CAPACITY` | 43 | `16` | cluster init, scale-boost decay |
| `MIN_CPU_CAPACITY` | 44 | `6` | `Scale_Down` floor |
| `MIN_RAM_CAPACITY` | 45 | `8` | `Scale_Down` floor |
| `SCALE_UP_CPU_BOOST` | 46 | `3` | `Scale_Up` action + decay |
| `SCALE_UP_RAM_BOOST` | 47 | `4` | `Scale_Up` action + decay |
| `SCALE_BOOST_DURATION` | 48 | `3` | boost lifetime |
| `MAX_RECENT_FAILURES` | 49 | `10` | `recent_failures` clamp |

Undeclared but still hard-coded in the same file:

- Spot-price random walk bounds `±0.08`, clamp `[0.1, 1.0]` (`apply_random_events` line 367).
- Data-spike hit count `randint(1, 3)`, `remaining_time += 1`, `cpu_demand = min(+1, 6)` (lines 389–392).
- `Scale_Down` step of `-2` for both CPU and RAM (lines 480–481).
- `Reprioritize_Queue` priority bump `+0.05` capped at `1.0` (line 487).
- `Pause_LowPriority_Job` priority threshold `< 0.4` and cap of `[:2]` jobs (lines 494–497).
- `Execute_Ready_Job` ranking `value * priority` (line 463).
- Workload generator `_clone_template_into_job`:
  - `duration_factor ∈ {0.8, 1.0, 1.2, 1.5}` (line 313)
  - `cpu_factor / ram_factor ∈ {1.0, 1.0, 1.5}` (lines 314–315)
  - `priority ∈ U(0.2, 1.0)` (line 330)
  - `deadline_steps ∈ U[30, 120]` (line 331)
  - `value ∈ U(1.0, 5.0)` (line 332)
  - `initial spot_price ∈ U(0.3, 0.7)` (line 345)
- Three DAG templates (`build_chain_template`, `build_fork_join_template`,
  `build_two_stage_batch_template`) with hand-written task durations and
  CPU/RAM demands (lines 252–287).
- Normalization divisors in `state_vector`: `Queue_Depth / 20.0`,
  `DAG_Ready_Nodes / 20.0`, `Recent_Failures / 5.0` (lines 240–245).

### Utility weights — `src/reflex_agent.py`

| Name | Line | Value | Scope |
|---|---|---|---|
| `ALPHA` | 49 | `1.0` | Episode utility |
| `BETA` | 50 | `0.4` | Episode utility |
| `GAMMA` | 51 | `0.8` | Episode utility |
| `BASE_CPU` | 56 | `10` | Reflex `should_scale_down_idle_cluster` |
| `BASE_RAM` | 57 | `16` | Reflex `should_scale_down_idle_cluster` |

Also in `estimate_step_cost` (line 179): the `0.6 * cpu_in_use + 0.4 * ram_in_use`
split is hard-coded and appears again inside `utility_agent._resource_cost`.

Reflex policy thresholds also hard-coded:
- Scale-down when `spot_price >= 0.8` (line 155).
- Scale-up when `queue_depth >= 3` and `spot_price <= 0.7` (lines 166–167).

### Utility-agent scoring constants — `src/utility_agent.py`

Twenty-nine module-level `Final` constants between lines 62 and 102, covering
hard penalties (`NO_EXECUTABLE_TASK_SCORE`, `ACTIVE_SCALE_UP_PENALTY`,
`EMPTY_QUEUE_SCALE_UP_PENALTY`, `UNNECESSARY_SCALE_UP_PENALTY`,
`INVALID_SCALE_DOWN_PENALTY`, `LOW_VALUE_REPRIORITIZE_PENALTY`,
`NO_LOW_PRIORITY_WORK_PENALTY`, `UNNECESSARY_PAUSE_PENALTY`) and every
per-action scoring weight (queue penalty, urgency penalty, failure relief,
price relief, blocked-task benefit, per-action price weights, pause weights,
resource-cost weight, children bonus, load risk, etc.) plus stress guards
(`STRESS_GUARD_FAILURE_LIMIT = 0.6`, `STRESS_GUARD_PRICE_LIMIT = 0.9`). None of
these are reachable from any config.

### Comparison driver defaults — `src/compare_baselines.py`

`DEFAULT_SEEDS`, `DEFAULT_NUM_JOBS`, `DEFAULT_MAX_STEPS`, `DEFAULT_OUT_DIR`,
`RESULT_FILENAMES`, `SUMMARY_FIELDS` (lines 41–61). Single flat seed list; no
train/test split.

**Action** (next commit): every value listed in this section lives in
`config/default.yaml`; agents and env receive a typed `RunConfig` object at
construction; no magic numbers remain in `sim_environment.py`,
`reflex_agent.py`, or `utility_agent.py`.

---

## 4. Test coverage

**None.** There is no `tests/` directory, no `pytest.ini`, no `conftest.py`,
no `doctest` usage, and no CI configuration. The only runtime "tests" are the
`_demo()` functions that run when each source file is executed directly.

**Action** (next commit): introduce `tests/` with pytest fixtures covering
(a) simulator determinism under a fixed seed, (b) action legality across a
sample of reachable states, and (c) the utility function on a hand-computed
fixture.

---

## 5. What works end-to-end today

Running `python src/compare_baselines.py --seeds 0 1 2 --num-jobs 20 --max-steps 80 --out-dir /tmp/smoke`
produces four files (`reflex_runs.csv`, `utility_runs.csv`, `summary.json`,
`comparison_report.md`) with the schema already used by `results/baselines_v0/`.
The existing CSVs and summary.json in `results/baselines_v0/` are consistent
with a 10-seed, 100-job, 300-step run of both baselines.

The reflex → utility → compare pipeline therefore works. What it does *not*
do is match the reviewer-defect requirements — it has no confidence intervals,
no paired test, no manifest, no config hash, no train/test split, no
uncapped-completion metric, and no (α, β, γ) surface.

---

## 6. Duplication

1. **Per-agent run loops** — `run_reflex_episode` (`reflex_agent.py` lines
   213–241) and `run_utility_episode` (`utility_agent.py` lines 359–387) are
   copies of the same structure; only the constructed agent differs. The same
   holds for `run_many_reflex_episodes` and `run_many_utility_episodes`.
   **Action:** fold into a single `run_episode(agent, seed, cfg)` helper.
2. **Verbose-trace printers** — `_print_verbose_step` exists verbatim in both
   `reflex_agent.py` (lines 253–260) and `utility_agent.py` (lines 399–406).
3. **Step-cost formula** — the `0.6 * cpu + 0.4 * ram` split appears in
   `estimate_step_cost` (`reflex_agent.py` line 179) and in
   `UtilityBasedAgent._resource_cost` (`utility_agent.py` line 328). Both are
   meant to represent the same cost model but are disconnected strings of
   numeric literals.
4. **`ALPHA / BETA / GAMMA` imports** — the utility-agent file both imports
   these from `reflex_agent` and relies on the episode-level
   `summarize_episode` that applies them. Fine today, but the constants live
   in the wrong module (reflex shouldn't own the project objective).
5. **Sample-result duplication** — `results/baselines_v0/` and
   `results/test_results_small/` describe the same pipeline at different
   scales.
6. **Evaluation structures** — `EpisodeMetrics` lives in `reflex_agent.py` but
   is used by every other module. That is duplication of *concern* (reflex
   owning evaluation), not of code.

---

## 7. Dead / unreachable code

- **`SUMMARY_FIELDS`'s `steps_executed` entry** (`compare_baselines.py` line
  61): legal but misleading — in the canonical 10-seed run both agents use
  the full 300-step budget, so this column is constant. Not removed; flagged.
- **`event_log`** on `EpisodeState` (`sim_environment.py` line 168): written
  by `WorkloadGenerator.generate_episode` and by `apply_random_events`, but
  never read by the comparison driver, the reports, or the tests. **Action**
  (later commit): either plumb into the run artifacts or explicitly mark as
  debug-only.
- **`completed_all_jobs` on `EpisodeMetrics`**: set but not used anywhere
  except the Markdown report's "all_jobs_completed_runs" counter. Kept,
  because the counter is informative; flagged as low-value surface.
- **`random.choice([0.8, 1.0, 1.2, 1.5])`** in the workload generator uses
  only the three distinct float values `0.8 / 1.0 / 1.2 / 1.5`; the `1.0`
  weight-doubling via list duplication trick (`[1.0, 1.0, 1.5]`) is used for
  cpu/ram factors (lines 314–315) and is intentional, but not documented. Not
  dead, but worth surfacing in config.
- **Unused imports:** none detected via quick scan; all `noqa: E402` imports
  are actually used.
- **`verbose` parameters** on `run_reflex_episode` / `run_utility_episode`:
  accept a bool and call `_print_verbose_step`, but no caller in the repo sets
  `verbose=True`. Not dead; kept for manual debugging.

---

## 8. Randomness discipline

Every random draw in the current repo uses either `random.Random(seed)`
(`WorkloadGenerator.__init__`, the episode runners) or the module-global
`random` inside `apply_random_events`. There is **no** `numpy.random.Generator`
usage anywhere, despite the project's non-negotiable coding practice that "every
random draw goes through a named, seeded `numpy.random.Generator`."

**Action** (next commit): replace every `random.Random(seed)` with
`np.random.default_rng(seed)` and plumb a named generator explicitly into the
workload generator, the env's `apply_random_events`, and the agents.

---

## 9. Output-artifact discipline

Today's run writes four files directly into `--out-dir` with no run id, no
manifest, no resolved-config snapshot. Subsequent runs **overwrite** prior
outputs at the same path. This is incompatible with the reviewer's
reproducibility bar.

**Action** (next commit): every run writes to `results/<run_id>/` with at
least:

- `config.yaml` — the fully resolved config used for the run.
- `run_manifest.json` — commit SHA, config hash, seed list, wall-clock start/end
  in ISO-8601 UTC, library versions (`python`, `numpy`, `scipy`, `pyyaml`,
  `matplotlib` when installed), hostname, platform.
- `metrics.csv` — long-form per-seed-per-agent rows.
- `summary.json` and `report.md` — aggregates with CI and paired significance.

---

## 10. Gap summary vs. reviewer defects

| Defect | Status today | Planned fix (next commits) |
|---|---|---|
| (α, β, γ) not in config | constants in `reflex_agent.py` | `config/default.yaml` + typed `UtilityWeights` |
| n=10, no CI, no Wilcoxon | `pstdev` only | bootstrap CI + paired Wilcoxon in `scripts/aggregate.py` |
| No Pareto / sensitivity | absent | `scripts/sweep_utility.py` + figure |
| Under-specified simulator | hard-coded `Final`s | full `simulator:` block in `config/default.yaml` |
| No train/test seed split | single flat list | `seeds.train / seeds.test` in config; explicit held-out evaluator |
| RL algorithm unspecified | absent | `rl:` block in config + `scripts/train_rl.py` scaffold |
| "Completion rate" budget-capped | only single rate | add `value_weighted_completion_rate`, `uncapped_completion_rate` |

The next commits on this branch close items 1, 4, 5 (config/split), and set up
the scaffolding needed for the remaining items.

---

## 11. Post-refactor state (this branch)

This section reflects the state of `cursor/reviewer-defects-hardening-3365`
after the refactor pass that accompanies this audit.

### New files

- `config/default.yaml` — single source of truth for every simulator and
  agent hyperparameter. All previously hard-coded numeric values have been
  moved here. The config is hashed (sha256 of a deterministic YAML dump) and
  the hash is written into every run manifest.
- `src/config.py` — typed loader (`RunConfig` dataclasses) and
  `override_utility_weights` helper for the (α, β, γ) sweep.
- `src/metrics.py` — `EpisodeMetrics`, `estimate_step_cost`, and
  `summarize_episode` now live here. The Reflex agent no longer owns the
  project objective.
- `src/runner.py` — single shared episode loop used by every agent. Replaces
  the duplicated `run_*_episode` / `run_many_*` code in both agent files.
  Also runs an "uncapped" replay to populate `uncapped_completion_rate`.
- `src/run_artifacts.py` — `results/<run_id>/` convention: writes
  `config.yaml`, `run_manifest.json`, `metrics.csv` for every run.
- `tests/` — 21 pytest tests (determinism, action legality, utility
  fixture, config regression). `pytest -q` runs in ~3 s from a clean checkout.
- `Makefile` — `make test / baseline / baseline-train / baseline-test /
  sweep / train / figs / clean`.
- `scripts/sweep_utility.py` — (α, β, γ) grid driver that reuses the
  baseline comparison per cell and writes `sweep_grid.csv`.
- `scripts/train_rl.py`, `scripts/figs/make_all.py` — scaffolds wired to the
  config loader so `make train` and `make figs` are valid entry points now;
  full implementations land in follow-up commits.
- `requirements.txt` — `numpy`, `pyyaml`, `scipy`, `matplotlib`, `pytest`.

### Removed / replaced

- All 25+ `Final` module-level constants at the top of `src/utility_agent.py`
  are gone; every weight is read from `cfg.utility_agent`.
- `ALPHA / BETA / GAMMA / BASE_CPU / BASE_RAM` constants in
  `src/reflex_agent.py` are gone; replaced by `cfg.utility` and
  `cfg.simulator.cluster`.
- `random.Random(seed)` is no longer used anywhere. Every random draw goes
  through a named `np.random.Generator` derived from
  `numpy.random.SeedSequence(seed).spawn(2)`.
- Duplicated `_print_verbose_step`, `run_*_episode`, `run_many_*` collapsed
  into `src/runner.py`.

### New CSV schema (superset of the old one)

`seed, agent_name, alpha, beta, gamma, num_jobs, steps_executed,
completed_jobs, failed_jobs, completion_rate,
value_weighted_completion_rate, uncapped_completion_rate, failure_rate,
total_completed_value, total_job_value, total_compute_cost,
avg_compute_cost_per_step, total_utility, completed_all_jobs,
hit_step_budget`.

Adds `alpha / beta / gamma` (so a sweep CSV is self-describing),
`value_weighted_completion_rate`, `uncapped_completion_rate`,
`total_job_value`, and `hit_step_budget`.

### Known behavioral delta from midterm Table 1

Switching the event stream from `random.Random` to
`numpy.random.default_rng` changes the realized stochastic sequence under the
same integer seed. The qualitative finding (Utility-Based wins on
utility/cost/failure, loses on completion) is preserved in a 10-seed
canonical_midterm run (`results/canonical_midterm/`), but exact numeric
values differ from the original Table 1. Reproducing Table 1 bit-for-bit
would require keeping the old stdlib RNG, which directly contradicts the
project's non-negotiable coding practice. The new numbers are now the
canonical reference; Table 1 is preserved in `README.md` as a historical
baseline.

### Test summary

```
tests/test_action_legality.py ....... (7 passed)
tests/test_config.py          ..... (5 passed)
tests/test_determinism.py     ...... (6 passed)
tests/test_utility.py         ...  (3 passed)
=================== 21 passed in 2.77s ====================
```
