from __future__ import annotations

"""Typed configuration loader for the orchestration project.

Reads ``config/default.yaml`` (or any override) into immutable dataclasses.
Every consumer module (env, agents, drivers) receives a ``RunConfig`` and
does not touch YAML or magic numbers of its own.

The loader also produces a stable sha256 hash of the canonical YAML dump so
``(commit SHA, config hash, seed list)`` uniquely identifies a run.

Structure of the resolved schema is documented in SPECIFICATION.md and in
``config/default.yaml`` itself.
"""

from dataclasses import dataclass, field
import hashlib
import io
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "default.yaml"


# ---------------------------------------------------------------------------
# Action parameters — one dataclass per action.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExecuteReadyJobParams:
    selection_policy: str
    max_launches_per_step: int


@dataclass(frozen=True)
class DeferJobParams:
    duration_steps: int


@dataclass(frozen=True)
class ScaleUpParams:
    cpu_delta: int
    ram_delta: int
    duration_steps: int


@dataclass(frozen=True)
class ScaleDownParams:
    cpu_delta: int
    ram_delta: int


@dataclass(frozen=True)
class ReprioritizeQueueParams:
    bump: float
    cap: float


@dataclass(frozen=True)
class PauseLowPriorityJobParams:
    priority_threshold: float
    max_jobs: int


@dataclass(frozen=True)
class ActionParams:
    """Container for per-action parameter sets.

    Access pattern: ``cfg.simulator.action_params.scale_up.cpu_delta``.
    """
    execute_ready_job: ExecuteReadyJobParams
    defer_job: DeferJobParams
    scale_up: ScaleUpParams
    scale_down: ScaleDownParams
    reprioritize_queue: ReprioritizeQueueParams
    pause_low_priority_job: PauseLowPriorityJobParams


# ---------------------------------------------------------------------------
# Stochastic processes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NodeFailureConfig:
    mode: str          # "per_step_single_victim" | "per_node_bernoulli"
    prob: float


@dataclass(frozen=True)
class DataSpikeConfig:
    mode: str          # "additive_bump" | "multiplicative_10x"
    prob: float
    min_tasks: int
    max_tasks: int
    duration_bump: int
    cpu_bump: int
    cpu_cap: int
    multiplier: int
    duration_steps: int


@dataclass(frozen=True)
class SpotPriceConfig:
    mode: str          # "bounded_random_walk"
    walk_low: float
    walk_high: float
    price_min: float
    price_max: float


@dataclass(frozen=True)
class StochasticProcessesConfig:
    node_failure: NodeFailureConfig
    data_spike: DataSpikeConfig
    spot_price: SpotPriceConfig


# ---------------------------------------------------------------------------
# Cluster / cost / state vector / workload / DAG
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ClusterConfig:
    base_cpu_capacity: int
    base_ram_capacity: int
    min_cpu_capacity: int
    min_ram_capacity: int
    scale_boost_duration: int
    max_recent_failures: int
    initial_spot_price_low: float
    initial_spot_price_high: float


@dataclass(frozen=True)
class CostConfig:
    cpu_weight: float
    ram_weight: float
    action_costs: Mapping[str, float]


@dataclass(frozen=True)
class StateVectorConfig:
    queue_depth_norm: float
    ready_nodes_norm: float
    recent_failures_norm: float


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
    action_params: ActionParams
    stochastic_processes: StochasticProcessesConfig
    cost: CostConfig
    state_vector: StateVectorConfig
    workload: WorkloadConfig
    dag_templates: Tuple[DAGTemplateSpec, ...]


# ---------------------------------------------------------------------------
# Utility / agents / experiment / RL / sweep / seeds
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class UtilityWeights:
    alpha: float
    beta: float
    gamma: float
    midterm_values: Mapping[str, float]


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
    meta: Mapping[str, Any]
    experiment: ExperimentConfig
    seeds: SeedsConfig
    simulator: SimulatorConfig
    utility: UtilityWeights
    reflex_agent: ReflexAgentConfig
    utility_agent: UtilityAgentConfig
    rl: RLConfig
    sweep: SweepConfig
    raw: Mapping[str, Any] = field(repr=False)

    def config_hash(self) -> str:
        """Stable sha256 over the resolved config (sorted-key YAML dump)."""
        return sha256_of_resolved(self.raw)

    def resolved_yaml(self) -> str:
        """Canonical YAML form of the resolved config."""
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


def _parse_action_params(raw: Mapping[str, Any]) -> ActionParams:
    return ActionParams(
        execute_ready_job=ExecuteReadyJobParams(**raw["Execute_Ready_Job"]),
        defer_job=DeferJobParams(**raw["Defer_Job"]),
        scale_up=ScaleUpParams(**raw["Scale_Up"]),
        scale_down=ScaleDownParams(**raw["Scale_Down"]),
        reprioritize_queue=ReprioritizeQueueParams(**raw["Reprioritize_Queue"]),
        pause_low_priority_job=PauseLowPriorityJobParams(**raw["Pause_LowPriority_Job"]),
    )


def _parse_stochastic_processes(raw: Mapping[str, Any]) -> StochasticProcessesConfig:
    return StochasticProcessesConfig(
        node_failure=NodeFailureConfig(**raw["node_failure"]),
        data_spike=DataSpikeConfig(**raw["data_spike"]),
        spot_price=SpotPriceConfig(**raw["spot_price"]),
    )


def _parse_cost(raw: Mapping[str, Any]) -> CostConfig:
    return CostConfig(
        cpu_weight=float(raw["cpu_weight"]),
        ram_weight=float(raw["ram_weight"]),
        action_costs={
            str(key): float(value) for key, value in dict(raw["action_costs"]).items()
        },
    )


def _parse_simulator(raw: Mapping[str, Any]) -> SimulatorConfig:
    cluster = ClusterConfig(**raw["cluster"])
    action_params = _parse_action_params(raw["action_params"])
    stochastic_processes = _parse_stochastic_processes(raw["stochastic_processes"])
    cost = _parse_cost(raw["cost"])
    state_vec = StateVectorConfig(**raw["state_vector"])

    workload_raw = dict(raw["workload"])
    workload = WorkloadConfig(
        duration_factors=_as_tuple(workload_raw.pop("duration_factors")),
        cpu_factors=_as_tuple(workload_raw.pop("cpu_factors")),
        ram_factors=_as_tuple(workload_raw.pop("ram_factors")),
        **workload_raw,
    )

    templates = []
    for template_raw in raw["dag_templates"]:
        task_specs = []
        for entry in template_raw["tasks"]:
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
        templates.append(
            DAGTemplateSpec(name=str(template_raw["name"]), tasks=tuple(task_specs))
        )

    return SimulatorConfig(
        actions=_as_tuple(raw["actions"]),
        cluster=cluster,
        action_params=action_params,
        stochastic_processes=stochastic_processes,
        cost=cost,
        state_vector=state_vec,
        workload=workload,
        dag_templates=tuple(templates),
    )


def _parse_rl(raw: Mapping[str, Any]) -> RLConfig:
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


def _parse_utility(raw: Mapping[str, Any]) -> UtilityWeights:
    midterm_values = dict(raw.get("midterm_values", {}))
    return UtilityWeights(
        alpha=float(raw["alpha"]),
        beta=float(raw["beta"]),
        gamma=float(raw["gamma"]),
        midterm_values={k: float(v) for k, v in midterm_values.items()},
    )


def _parse_seeds(raw: Mapping[str, Any]) -> SeedsConfig:
    return SeedsConfig(
        train=_as_tuple(raw["train"]),
        test=_as_tuple(raw["test"]),
        midterm_baseline=_as_tuple(raw["midterm_baseline"]),
    )


def _parse_sweep(raw: Mapping[str, Any]) -> SweepConfig:
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
    """Load and validate a YAML config file."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError("config must be a mapping at the top level")
    return build_run_config(raw)


def build_run_config(raw: Mapping[str, Any]) -> RunConfig:
    """Parse an in-memory raw mapping into a typed :class:`RunConfig`."""
    experiment = ExperimentConfig(**raw["experiment"])
    seeds = _parse_seeds(raw["seeds"])
    simulator = _parse_simulator(raw["simulator"])
    utility = _parse_utility(raw["utility"])
    reflex_agent = ReflexAgentConfig(**raw["reflex_agent"])
    utility_agent = UtilityAgentConfig(**raw["utility_agent"])
    rl = _parse_rl(raw["rl"])
    sweep = _parse_sweep(raw["sweep"])

    _validate(simulator=simulator, utility=utility)

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


def _validate(*, simulator: SimulatorConfig, utility: UtilityWeights) -> None:
    """Cheap invariant checks so the loader fails fast on bad configs."""
    valid_modes = {
        "node_failure": {"per_step_single_victim", "per_node_bernoulli"},
        "data_spike": {"additive_bump", "multiplicative_10x"},
        "spot_price": {"bounded_random_walk"},
    }
    sp = simulator.stochastic_processes
    if sp.node_failure.mode not in valid_modes["node_failure"]:
        raise ValueError(f"unknown node_failure mode: {sp.node_failure.mode}")
    if sp.data_spike.mode not in valid_modes["data_spike"]:
        raise ValueError(f"unknown data_spike mode: {sp.data_spike.mode}")
    if sp.spot_price.mode not in valid_modes["spot_price"]:
        raise ValueError(f"unknown spot_price mode: {sp.spot_price.mode}")

    if simulator.action_params.execute_ready_job.selection_policy not in {
        "value",
        "value_times_priority",
    }:
        raise ValueError(
            "Execute_Ready_Job.selection_policy must be 'value' or 'value_times_priority'"
        )

    missing_action_costs = set(simulator.actions) - set(simulator.cost.action_costs)
    if missing_action_costs:
        raise ValueError(f"cost.action_costs missing entries for: {missing_action_costs}")

    for name in (utility.alpha, utility.beta, utility.gamma):
        if not isinstance(name, float):
            raise ValueError("utility weights must be floats")


def _canonical_yaml_dump(raw: Mapping[str, Any]) -> str:
    """Deterministic YAML dump used for hashing."""
    buffer = io.StringIO()
    yaml.safe_dump(
        dict(raw),
        buffer,
        sort_keys=True,
        default_flow_style=False,
        allow_unicode=True,
    )
    return buffer.getvalue()


def sha256_of_resolved(raw: Mapping[str, Any]) -> str:
    canonical = _canonical_yaml_dump(raw)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def override_utility_weights(
    cfg: RunConfig,
    alpha: Optional[float] = None,
    beta: Optional[float] = None,
    gamma: Optional[float] = None,
) -> RunConfig:
    """Return a copy of ``cfg`` with its utility weights replaced."""
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
    "ActionParams",
    "ClusterConfig",
    "CostConfig",
    "CurriculumConfig",
    "CurriculumStage",
    "DAGTaskSpec",
    "DAGTemplateSpec",
    "DataSpikeConfig",
    "DEFAULT_CONFIG_PATH",
    "DeferJobParams",
    "ExecuteReadyJobParams",
    "ExperimentConfig",
    "NetworkConfig",
    "NodeFailureConfig",
    "PauseLowPriorityJobParams",
    "REPO_ROOT",
    "RLConfig",
    "ReflexAgentConfig",
    "ReprioritizeQueueParams",
    "RunConfig",
    "ScaleDownParams",
    "ScaleUpParams",
    "SeedsConfig",
    "SimulatorConfig",
    "SpotPriceConfig",
    "StateVectorConfig",
    "StochasticProcessesConfig",
    "SweepConfig",
    "UtilityAgentConfig",
    "UtilityWeights",
    "WorkloadConfig",
    "build_run_config",
    "load_config",
    "override_utility_weights",
    "sha256_of_resolved",
]
