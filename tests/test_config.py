from __future__ import annotations

"""Config-loader regression tests."""

from src.config import load_config, override_utility_weights


def test_default_config_loads_and_has_stable_hash(default_config):
    """The default config parses and its hash is deterministic."""
    first = default_config.config_hash()
    second = load_config().config_hash()
    assert first == second
    assert len(first) == 64  # sha256 hex


def test_default_weights_match_midterm():
    """The project's shared utility weights (alpha, beta, gamma) must be
    exactly the midterm values — they are the scientific control."""
    cfg = load_config()
    assert cfg.utility.alpha == 1.0
    assert cfg.utility.beta == 0.4
    assert cfg.utility.gamma == 0.8


def test_simulator_constants_match_midterm():
    cfg = load_config()
    events = cfg.simulator.events
    cluster = cfg.simulator.cluster
    assert events.node_failure_prob == 0.05
    assert events.data_spike_prob == 0.08
    assert cluster.base_cpu_capacity == 10
    assert cluster.base_ram_capacity == 16
    assert cfg.experiment.num_jobs == 100
    assert cfg.experiment.max_steps == 300


def test_train_test_seeds_are_disjoint():
    cfg = load_config()
    assert set(cfg.seeds.train).isdisjoint(set(cfg.seeds.test))


def test_override_utility_weights_produces_new_hash():
    base = load_config()
    bumped = override_utility_weights(base, alpha=2.0)
    assert bumped.utility.alpha == 2.0
    assert bumped.utility.beta == base.utility.beta
    assert bumped.config_hash() != base.config_hash()
