# Reproducibility entry points.
#
# Every target is config-driven. The single source of truth is
# ``config/default.yaml``. Override it per run with ``CONFIG=path/to/file.yaml``.

PYTHON ?= python3
PIP ?= pip
CONFIG ?= config/default.yaml
SEED_GROUP ?= midterm_baseline
RUN_ID ?=
OUT_ROOT ?=
PYTEST ?= pytest

# Resolve optional args so empty strings do not leak into the CLI.
RUN_ID_ARG := $(if $(RUN_ID),--run-id $(RUN_ID),)
OUT_ROOT_ARG := $(if $(OUT_ROOT),--out-root $(OUT_ROOT),)

.PHONY: help install test baseline baseline-train baseline-test sweep train figs clean phase2 phase2-aggregate phase2-figs phase2-sanity phase3 phase3-figs

help:
	@echo "make install        - install python dependencies"
	@echo "make test           - run pytest"
	@echo "make baseline       - run Reflex vs Utility baselines on SEED_GROUP (default: midterm_baseline)"
	@echo "make baseline-train / baseline-test - baselines on train or test seeds"
	@echo "make phase2         - Phase-2: 50-seed (0..49) baseline + aggregate + figure"
	@echo "make phase2-sanity  - re-run seeds 0..9 with midterm weights; diff against canonical_midterm"
	@echo "make phase3         - Phase-3: 80-cell (α, β, γ) sweep x 20 seeds (100..119)"
	@echo "make phase3-figs    - Pareto fronts + best-fixed-weight selection for phase3 run"
	@echo "make sweep          - (α, β, γ) Pareto sweep (older scaffold)"
	@echo "make train          - train the Self-Learning Utility-Based agent (scaffolded)"
	@echo "make figs           - regenerate paper figures from committed CSVs"
	@echo "make clean          - remove __pycache__"

install:
	$(PIP) install -r requirements.txt

test:
	$(PYTEST) -q

baseline:
	$(PYTHON) -m src.compare_baselines --config $(CONFIG) --seed-group $(SEED_GROUP) $(RUN_ID_ARG) $(OUT_ROOT_ARG)

baseline-train:
	$(MAKE) baseline SEED_GROUP=train

baseline-test:
	$(MAKE) baseline SEED_GROUP=test

sweep:
	$(PYTHON) -m scripts.sweep_utility --config $(CONFIG) $(RUN_ID_ARG) $(OUT_ROOT_ARG)

train:
	$(PYTHON) -m scripts.train_rl --config $(CONFIG) $(RUN_ID_ARG) $(OUT_ROOT_ARG)

figs:
	$(PYTHON) -m scripts.figs.make_all --config $(CONFIG)

PHASE2_RUN_ID ?= phase2_50seeds
PHASE2_RUN_DIR := results/$(PHASE2_RUN_ID)
PHASE2_SEEDS := 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49

phase2:
	$(PYTHON) -m src.compare_baselines --config $(CONFIG) --seed-group custom --seeds $(PHASE2_SEEDS) --run-id $(PHASE2_RUN_ID)
	$(MAKE) phase2-aggregate PHASE2_RUN_DIR=$(PHASE2_RUN_DIR)
	$(MAKE) phase2-figs PHASE2_RUN_DIR=$(PHASE2_RUN_DIR)

phase2-aggregate:
	$(PYTHON) -m scripts.aggregate --run-dir $(PHASE2_RUN_DIR)

phase2-figs:
	$(PYTHON) -m scripts.figs.phase2_deltas --run-dir $(PHASE2_RUN_DIR)

PHASE2_SANITY_RUN_ID ?= phase2_sanity_seeds0_9
phase2-sanity:
	$(PYTHON) -m src.compare_baselines --config config/midterm_weights.yaml --seed-group midterm_baseline --run-id $(PHASE2_SANITY_RUN_ID)
	$(PYTHON) -m scripts.compare_runs --reference results/canonical_midterm --candidate results/$(PHASE2_SANITY_RUN_ID)

PHASE3_RUN_ID ?= sweep_phase3
PHASE3_RUN_DIR := results/$(PHASE3_RUN_ID)
PHASE3_SELECTION_RULE ?= mean_utility_then_completion

phase3:
	$(PYTHON) -m scripts.sweep_phase3 --config $(CONFIG) --run-id $(PHASE3_RUN_ID)
	$(MAKE) phase3-figs PHASE3_RUN_DIR=$(PHASE3_RUN_DIR) PHASE3_SELECTION_RULE=$(PHASE3_SELECTION_RULE)

phase3-figs:
	$(PYTHON) -m scripts.figs.phase3_pareto --run-dir $(PHASE3_RUN_DIR) --selection-rule $(PHASE3_SELECTION_RULE)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
