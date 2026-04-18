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

.PHONY: help install test baseline baseline-train baseline-test sweep train figs clean

help:
	@echo "make install   - install python dependencies"
	@echo "make test      - run pytest"
	@echo "make baseline  - run Reflex vs Utility baselines on SEED_GROUP (default: midterm_baseline)"
	@echo "make baseline-train / baseline-test - baselines on train or test seeds"
	@echo "make sweep     - (α, β, γ) Pareto sweep (scaffolded; see scripts/sweep_utility.py)"
	@echo "make train     - train the Self-Learning Utility-Based agent (scaffolded)"
	@echo "make figs      - regenerate paper figures from committed CSVs"
	@echo "make clean     - remove __pycache__"

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

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
