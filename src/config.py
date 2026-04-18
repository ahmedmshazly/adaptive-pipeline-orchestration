from __future__ import annotations

"""Typed configuration loader for the orchestration project.

This module is the single Python entry point for reading ``config/default.yaml``
(or any override). The goals are:

1. No consumer code (env, agents, drivers) reads YAML directly.
2. Every constant the simulator or an agent uses is reachable through the
   ``RunConfig`` object returned by :func:`load_config`.
3. The resolved configuration can be rewritten verbatim and hashed for the
   run manifest, so that (commit SHA, config hash, seed list) uniquely
   identifies a run.

The loader intentionally avoids pydantic / attrs to keep the dependency set
small. The dataclasses below are faithful 1:1 mirrors of the YAML sections.
"""

from dataclasses import dataclass, field
import hashlib
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "default.yaml"


# ---------------------------------------------------------------------------
# Dataclasses (1:1 mirror of config/default.yaml)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ClusterConfig:
    base_cpu_capacity: int
    base_ram_capacity: int
    min_cpu_capacity: int
    min_ram_capacity: int
    scale_up_cpu_boost: int
    scale_up_ram_boost: int
    scale_down_cpu_step: int
    scale_down_ram_step: int
    scale_boost_duration: int
    max_recent_failures: int
    initial_spot_price_low: float
    initial_spot_price_high: float


@dataclass(frozen=True)
class EventsConfig:
    node_failure_prob: float
    data_spike_prob: float
    data_spike_min_tasks: int
    data_spike_max_tasks: int
    data_spike_duration_bump: int
    data_spike_cpu_bump: int
    data_spike_cpu_cap: int
    spot_price_walk_low: float
    spot_price_walk_high: float
    spot_price_min: float
    spot_price_max: float


@dataclass(frozen=True)
class CostConfig:
    cpu_weight: float
    ram_weight: float


@dataclass(frozen=True)
class StateVectorConfig:
    queue_depth_norm: float
    ready_nodes_norm: float
    recent_failures_norm: float


@dataclass(frozen=True)
class ActionsConfig:
    execute_ranking: str
    reprioritize_bump: float
    reprioritize_cap: float
    pause_priority_threshold: float
    pause_max_jobs: int


@dataclass(frozen=True)
class WorkloadConfig:
    duration_factors: Tuple[float, ...]
    cpu_factors: Tuple[float, ...]
    ram_factors: Tuple[float, ...]
    priority_low: float
    priority_high: float
    deadline_steps_low: int
    deadline_steps_high: int
    job_value_low: float
    job_value_high: float


@dataclass(frozen=True)
class DAGTaskSpec:
    task_id: str
    parents: Tuple[str, ...]
    base_duration: int
    cpu_demand: int
    ram_demand: int


@dataclass(frozen=True)
class DAGTemplateSpec:
    name: str
    tasks: Tuple[DAGTaskSpec, ...]


@dataclass(frozen=True)
class SimulatorConfig:
    actions: Tuple[str, ...]
    cluster: ClusterConfig
    events: EventsConfig
    cost: CostConfig
    state_vector: StateVectorConfig
    actions_config: ActionsConfig
    workload: WorkloadConfig
    dag_templates: Tuple[DAGTemplateSpec, ...]


@dataclass(frozen=True)
class UtilityWeights:
    alpha: float
    beta: float
    gamma: float


@dataclass(frozen=True)
class ReflexAgentConfig:
    scale_down_spot_price_threshold: float
    scale_up_queue_depth_threshold: int
    scale_up_spot_price_threshold: float


@dataclass(frozen=True)
class UtilityAgentConfig:
    no_executable_task_score: float
    active_scale_up_penalty: float
    empty_queue_scale_up_penalty: float
    unnecessary_scale_up_penalty: float
    invalid_scale_down_penalty: float
    low_value_reprioritize_penalty: float
    no_low_priority_work_penalty: float
    unnecessary_pause_penalty: float

    execution_urgency_weight: float

    defer_base_penalty: float
    queue_penalty_weight: float
    urgency_penalty_weight: float
    failure_relief_weight: float
    price_relief_weight: float
    price_relief_threshold: float

    blocked_task_benefit_weight: float
    scale_up_urgency_weight: float
    scale_up_failure_weight: float
    scale_up_price_weight: float

    scale_down_price_weight: float
    scale_down_base_bonus: float
    scale_down_queue_weight: float

    reprioritize_queue_weight: float
    reprioritize_urgency_weight: float
    reprioritize_failure_weight: float
    reprioritize_base_penalty: float
    reprioritize_min_queue_depth: int
    reprioritize_min_urgency: float

    pause_active_low_weight: float
    pause_queue_weight: float
    pause_failure_weight: float
    pause_price_weight: float
    pause_base_penalty: float
    pause_price_threshold: float
    pause_min_failure_pressure: float
    pause_min_queue_pressure: float

    best_task_resource_cost_weight: float
    ready_children_bonus_weight: float
    job_value_base: float
    job_priority_weight: float
    job_urgency_weight: float

    load_risk_threshold: float
    load_risk_weight: float
    failure_history_risk_weight: float
    queue_pressure_risk_weight: float

    stress_guard_failure_limit: float
    stress_guard_price_limit: float


@dataclass(frozen=True)
class ExperimentConfig:
    num_jobs: int
    max_steps: int
    uncapped_max_steps: int
    out_root: str
    run_id: Optional[str]


@dataclass(frozen=True)
class SeedsConfig:
    train: Tuple[int, ...]
    test: Tuple[int, ...]
    midterm_baseline: Tuple[int, ...]


@dataclass(frozen=True)
class CurriculumStage:
    num_jobs: int
    max_steps: int
    num_updates: int


@dataclass(frozen=True)
class CurriculumConfig:
    enabled: bool
    stages: Tuple[CurriculumStage, ...]


@dataclass(frozen=True)
class NetworkConfig:
    type: str
    hidden_sizes: Tuple[int, ...]
    activation: str


@dataclass(frozen=True)
class RLConfig:
    algorithm: str
    reward: str
    gamma_discount: float
    entropy_coef: float
    value_loss_coef: float
    learning_rate: float
    optimizer: str
    grad_clip_norm: float
    batch_size: int
    num_updates: int
    steps_per_episode_cap: int
    memoryless_termination: bool
    sequence_specific_baseline: bool
    curriculum: CurriculumConfig
    network: NetworkConfig
    training_seed_list: Tuple[int, ...]
    eval_every_updates: int
    checkpoint_every_updates: int


@dataclass(frozen=True)
class SweepConfig:
    alpha_grid: Tuple[float, ...]
    beta_grid: Tuple[float, ...]
    gamma_grid: Tuple[float, ...]
    seeds: Tuple[int, ...]


@dataclass(frozen=True)
class RunConfig:
    meta: Dict[str, Any]
    experiment: ExperimentConfig
    seeds: SeedsConfig
    simulator: SimulatorConfig
    utility: UtilityWeights
    reflex_agent: ReflexAgentConfig
    utility_agent: UtilityAgentConfig
    rl: RLConfig
    sweep: SweepConfig
    raw: Dict[str, Any] = field(repr=False)

    def config_hash(self) -> str:
        """Stable sha256 over the resolved config (sorted-key YAML dump)."""
        return sha256_of_resolved(self.raw)

    def resolved_yaml(self) -> str:
        """Return the canonical YAML form of the resolved config."""
        return _canonical_yaml_dump(self.raw)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def _as_tuple(value: Any) -> Tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    return tuple(value)


def _parse_simulator(raw: Dict[str, Any]) -> SimulatorConfig:
    cluster = ClusterConfig(**raw["cluster"])
    events = EventsConfig(**raw["events"])
    cost = CostConfig(**raw["cost"])
    state_vec = StateVectorConfig(**raw["state_vector"])
    actions_cfg = ActionsConfig(**raw["actions_config"])
    workload_raw = dict(raw["workload"])
    workload = WorkloadConfig(
        duration_factors=_as_tuple(workload_raw.pop("duration_factors")),
        cpu_factors=_as_tuple(workload_raw.pop("cpu_factors")),
        ram_factors=_as_tuple(workload_raw.pop("ram_factors")),
        **workload_raw,
    )

    templates: List[DAGTemplateSpec] = []
    for tpl in raw["dag_templates"]:
        task_specs: List[DAGTaskSpec] = []
        for entry in tpl["tasks"]:
            task_id, parents, base_duration, cpu_demand, ram_demand = entry
            task_specs.append(
                DAGTaskSpec(
                    task_id=str(task_id),
                    parents=_as_tuple(parents),
                    base_duration=int(base_duration),
                    cpu_demand=int(cpu_demand),
                    ram_demand=int(ram_demand),
                )
            )
        templates.append(DAGTemplateSpec(name=str(tpl["name"]), tasks=tuple(task_specs)))

    return SimulatorConfig(
        actions=_as_tuple(raw["actions"]),
        cluster=cluster,
        events=events,
        cost=cost,
        state_vector=state_vec,
        actions_config=actions_cfg,
        workload=workload,
        dag_templates=tuple(templates),
    )


def _parse_rl(raw: Dict[str, Any]) -> RLConfig:
    stages = tuple(CurriculumStage(**stage) for stage in raw["curriculum"]["stages"])
    curriculum = CurriculumConfig(enabled=bool(raw["curriculum"]["enabled"]), stages=stages)
    network = NetworkConfig(
        type=str(raw["network"]["type"]),
        hidden_sizes=_as_tuple(raw["network"]["hidden_sizes"]),
        activation=str(raw["network"]["activation"]),
    )
    rl_kwargs = {
        key: raw[key]
        for key in raw
        if key not in {"curriculum", "network", "training_seed_list"}
    }
    return RLConfig(
        curriculum=curriculum,
        network=network,
        training_seed_list=_as_tuple(raw["training_seed_list"]),
        **rl_kwargs,
    )


def _parse_seeds(raw: Dict[str, Any]) -> SeedsConfig:
    return SeedsConfig(
        train=_as_tuple(raw["train"]),
        test=_as_tuple(raw["test"]),
        midterm_baseline=_as_tuple(raw["midterm_baseline"]),
    )


def _parse_sweep(raw: Dict[str, Any]) -> SweepConfig:
    return SweepConfig(
        alpha_grid=_as_tuple(raw["alpha_grid"]),
        beta_grid=_as_tuple(raw["beta_grid"]),
        gamma_grid=_as_tuple(raw["gamma_grid"]),
        seeds=_as_tuple(raw["seeds"]),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_config(path: Optional[Path] = None) -> RunConfig:
    """Load and validate a YAML config file.

    If ``path`` is ``None`` the bundled ``config/default.yaml`` is used.
    """
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError("config must be a mapping at the top level")

    return build_run_config(raw)


def build_run_config(raw: Dict[str, Any]) -> RunConfig:
    """Parse an in-memory raw mapping into a typed :class:`RunConfig`."""
    experiment = ExperimentConfig(**raw["experiment"])
    seeds = _parse_seeds(raw["seeds"])
    simulator = _parse_simulator(raw["simulator"])
    utility = UtilityWeights(**raw["utility"])
    reflex_agent = ReflexAgentConfig(**raw["reflex_agent"])
    utility_agent = UtilityAgentConfig(**raw["utility_agent"])
    rl = _parse_rl(raw["rl"])
    sweep = _parse_sweep(raw["sweep"])

    return RunConfig(
        meta=dict(raw.get("meta", {})),
        experiment=experiment,
        seeds=seeds,
        simulator=simulator,
        utility=utility,
        reflex_agent=reflex_agent,
        utility_agent=utility_agent,
        rl=rl,
        sweep=sweep,
        raw=raw,
    )


def _canonical_yaml_dump(raw: Dict[str, Any]) -> str:
    """Return a deterministic YAML dump used for hashing."""
    buffer = io.StringIO()
    yaml.safe_dump(
        raw,
        buffer,
        sort_keys=True,
        default_flow_style=False,
        allow_unicode=True,
    )
    return buffer.getvalue()


def sha256_of_resolved(raw: Dict[str, Any]) -> str:
    """Return the short sha256 of the canonical YAML dump."""
    canonical = _canonical_yaml_dump(raw)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def override_utility_weights(
    cfg: RunConfig,
    alpha: Optional[float] = None,
    beta: Optional[float] = None,
    gamma: Optional[float] = None,
) -> RunConfig:
    """Return a copy of ``cfg`` with its utility weights replaced.

    Used by the (α, β, γ) sweep driver so a single config is the base for the
    full grid.
    """
    new_raw = _deepcopy_mapping(cfg.raw)
    u = new_raw["utility"]
    if alpha is not None:
        u["alpha"] = float(alpha)
    if beta is not None:
        u["beta"] = float(beta)
    if gamma is not None:
        u["gamma"] = float(gamma)
    return build_run_config(new_raw)


def _deepcopy_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _deepcopy_mapping(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_deepcopy_mapping(item) for item in value]
    return value


__all__ = [
    "ActionsConfig",
    "ClusterConfig",
    "CostConfig",
    "CurriculumConfig",
    "CurriculumStage",
    "DAGTaskSpec",
    "DAGTemplateSpec",
    "DEFAULT_CONFIG_PATH",
    "EventsConfig",
    "ExperimentConfig",
    "NetworkConfig",
    "REPO_ROOT",
    "RLConfig",
    "ReflexAgentConfig",
    "RunConfig",
    "SeedsConfig",
    "SimulatorConfig",
    "StateVectorConfig",
    "SweepConfig",
    "UtilityAgentConfig",
    "UtilityWeights",
    "WorkloadConfig",
    "build_run_config",
    "load_config",
    "override_utility_weights",
    "sha256_of_resolved",
]
