from __future__ import annotations

"""Core simulation environment for the orchestration project.

This module defines a stochastic world for adaptive data-pipeline
orchestration. Every numeric parameter it uses comes from a ``RunConfig``
produced by :mod:`src.config`; this module contains no magic numbers.

Randomness discipline:
- Every random draw goes through a named ``numpy.random.Generator``.
- Generators are constructed from a deterministic
  ``numpy.random.SeedSequence`` in :func:`make_episode_rngs`, so a single
  integer seed reproduces both the workload generator's draws and the event
  loop's draws independently.
"""

from dataclasses import dataclass, field
from typing import Dict, Final, List, Optional, Sequence, Tuple

import numpy as np

from .config import RunConfig, SimulatorConfig, load_config


# ---------------------------------------------------------------------------
# Action space (structural; the action *names* are part of the problem
# specification). Numeric parameters governing action semantics live in
# ``cfg.simulator.actions_config`` and ``cfg.simulator.cluster``.
# ---------------------------------------------------------------------------
ACTIONS: Final[Tuple[str, ...]] = (
    "Execute_Ready_Job",
    "Defer_Job",
    "Scale_Up",
    "Scale_Down",
    "Reprioritize_Queue",
    "Pause_LowPriority_Job",
)

TASK_STATE_WAITING: Final[str] = "waiting"
TASK_STATE_READY: Final[str] = "ready"
TASK_STATE_RUNNING: Final[str] = "running"
TASK_STATE_COMPLETED: Final[str] = "completed"
TASK_STATE_FAILED: Final[str] = "failed"
TASK_STATE_PAUSED: Final[str] = "paused"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TaskTemplate:
    task_id: str
    parents: Tuple[str, ...]
    base_duration: int
    cpu_demand: int
    ram_demand: int


@dataclass(frozen=True)
class DAGTemplate:
    name: str
    tasks: Tuple[TaskTemplate, ...]


@dataclass
class TaskInstance:
    job_id: int
    task_id: str
    parents: Tuple[str, ...]
    remaining_time: int
    cpu_demand: int
    ram_demand: int
    state: str = TASK_STATE_WAITING

    def full_id(self) -> str:
        return f"job{self.job_id}:{self.task_id}"


@dataclass
class JobInstance:
    job_id: int
    template_name: str
    priority: float
    deadline_steps: int
    value: float
    tasks: Dict[str, TaskInstance]
    failed: bool = False
    completed: bool = False

    def update_status(self) -> None:
        if any(task.state == TASK_STATE_FAILED for task in self.tasks.values()):
            self.failed = True
            self.completed = False
            return

        if all(task.state == TASK_STATE_COMPLETED for task in self.tasks.values()):
            self.completed = True
            self.failed = False
            return

        self.failed = False
        self.completed = False


@dataclass
class RunningTask:
    full_id: str
    cpu_demand: int
    ram_demand: int
    remaining_time: int


@dataclass
class ClusterState:
    cpu_capacity: int
    ram_capacity: int
    spot_price: float
    scale_boost_remaining: int = 0
    recent_failures: int = 0


@dataclass
class EpisodeState:
    step: int
    jobs: List[JobInstance]
    cluster: ClusterState
    cfg: RunConfig
    running_tasks: Dict[str, RunningTask] = field(default_factory=dict)
    event_log: List[str] = field(default_factory=list)

    # ---- derived views -----------------------------------------------------
    def ready_tasks(self) -> List[TaskInstance]:
        ready: List[TaskInstance] = []
        for job in self.jobs:
            if job.failed or job.completed:
                continue
            for task in job.tasks.values():
                if task.state == TASK_STATE_WAITING and all(
                    job.tasks[parent].state == TASK_STATE_COMPLETED for parent in task.parents
                ):
                    task.state = TASK_STATE_READY
                if task.state == TASK_STATE_READY:
                    ready.append(task)
        return ready

    def cpu_in_use(self) -> int:
        return sum(task.cpu_demand for task in self.running_tasks.values())

    def ram_in_use(self) -> int:
        return sum(task.ram_demand for task in self.running_tasks.values())

    def available_cpu(self) -> int:
        return max(self.cluster.cpu_capacity - self.cpu_in_use(), 0)

    def available_ram(self) -> int:
        return max(self.cluster.ram_capacity - self.ram_in_use(), 0)

    def queue_depth(self) -> int:
        return len(self.ready_tasks())

    def all_done(self) -> bool:
        return all(job.failed or job.completed for job in self.jobs)

    def state_vector(self) -> Dict[str, float]:
        ready = self.ready_tasks()
        active_jobs = [job for job in self.jobs if not job.failed and not job.completed]
        sv = self.cfg.simulator.state_vector
        experiment = self.cfg.experiment

        if active_jobs:
            avg_priority = sum(job.priority for job in active_jobs) / len(active_jobs)
            avg_urgency = sum(
                max(0.0, 1.0 - (job.deadline_steps / experiment.max_steps))
                for job in active_jobs
            ) / len(active_jobs)
        else:
            avg_priority = 0.0
            avg_urgency = 0.0

        return {
            "CPU_Load": round(self.cpu_in_use() / max(self.cluster.cpu_capacity, 1), 4),
            "RAM_Available": round(self.available_ram() / max(self.cluster.ram_capacity, 1), 4),
            "Queue_Depth": min(self.queue_depth() / sv.queue_depth_norm, 1.0),
            "Spot_Price": round(self.cluster.spot_price, 4),
            "DAG_Ready_Nodes": min(len(ready) / sv.ready_nodes_norm, 1.0),
            "Job_Priority": round(avg_priority, 4),
            "Deadline_Urgency": round(avg_urgency, 4),
            "Recent_Failures": min(self.cluster.recent_failures / sv.recent_failures_norm, 1.0),
        }


# ---------------------------------------------------------------------------
# Template instantiation from config
# ---------------------------------------------------------------------------
def build_templates(sim_cfg: SimulatorConfig) -> Tuple[DAGTemplate, ...]:
    """Convert config DAG specs into immutable runtime templates."""
    templates: List[DAGTemplate] = []
    for template_spec in sim_cfg.dag_templates:
        tasks = tuple(
            TaskTemplate(
                task_id=spec.task_id,
                parents=spec.parents,
                base_duration=spec.base_duration,
                cpu_demand=spec.cpu_demand,
                ram_demand=spec.ram_demand,
            )
            for spec in template_spec.tasks
        )
        templates.append(DAGTemplate(name=template_spec.name, tasks=tasks))
    return tuple(templates)


# ---------------------------------------------------------------------------
# Episode RNG discipline
# ---------------------------------------------------------------------------
def make_episode_rngs(
    seed: int,
) -> Tuple[np.random.Generator, np.random.Generator]:
    """Spawn two independent generators from a single integer seed.

    The returned pair is ``(workload_rng, event_rng)``. They are derived via
    ``numpy.random.SeedSequence`` so a run is fully reproducible from one
    integer seed without entangling workload generation with event streams.
    """
    seed_sequence = np.random.SeedSequence(int(seed))
    workload_ss, event_ss = seed_sequence.spawn(2)
    return np.random.default_rng(workload_ss), np.random.default_rng(event_ss)


# ---------------------------------------------------------------------------
# Workload generation
# ---------------------------------------------------------------------------
class WorkloadGenerator:
    """Seeded workload generator.

    Takes an explicit ``np.random.Generator``; call sites are expected to
    derive it from :func:`make_episode_rngs` or equivalent.
    """

    def __init__(
        self,
        rng: np.random.Generator,
        cfg: RunConfig,
        num_jobs: Optional[int] = None,
        seed_label: Optional[int] = None,
    ) -> None:
        self.rng = rng
        self.cfg = cfg
        self.num_jobs = num_jobs if num_jobs is not None else cfg.experiment.num_jobs
        self.seed_label = seed_label
        self.templates = build_templates(cfg.simulator)

    def _clone_template_into_job(self, job_id: int, template: DAGTemplate) -> JobInstance:
        workload = self.cfg.simulator.workload
        duration_factor = float(self.rng.choice(workload.duration_factors))
        cpu_factor = float(self.rng.choice(workload.cpu_factors))
        ram_factor = float(self.rng.choice(workload.ram_factors))

        tasks: Dict[str, TaskInstance] = {}
        for template_task in template.tasks:
            tasks[template_task.task_id] = TaskInstance(
                job_id=job_id,
                task_id=template_task.task_id,
                parents=template_task.parents,
                remaining_time=max(1, int(round(template_task.base_duration * duration_factor))),
                cpu_demand=max(1, int(round(template_task.cpu_demand * cpu_factor))),
                ram_demand=max(1, int(round(template_task.ram_demand * ram_factor))),
            )

        priority = round(
            float(self.rng.uniform(workload.priority_low, workload.priority_high)), 2
        )
        deadline = int(
            self.rng.integers(
                low=workload.deadline_steps_low,
                high=workload.deadline_steps_high + 1,
            )
        )
        job_value = round(
            float(self.rng.uniform(workload.job_value_low, workload.job_value_high)), 2
        )

        return JobInstance(
            job_id=job_id,
            template_name=template.name,
            priority=priority,
            deadline_steps=deadline,
            value=job_value,
            tasks=tasks,
        )

    def generate_episode(self) -> EpisodeState:
        cluster_cfg = self.cfg.simulator.cluster
        template_indices = self.rng.integers(
            low=0, high=len(self.templates), size=self.num_jobs
        )
        jobs = [
            self._clone_template_into_job(
                job_id=index,
                template=self.templates[int(template_indices[index])],
            )
            for index in range(self.num_jobs)
        ]
        initial_spot_price = round(
            float(
                self.rng.uniform(
                    cluster_cfg.initial_spot_price_low,
                    cluster_cfg.initial_spot_price_high,
                )
            ),
            2,
        )
        cluster = ClusterState(
            cpu_capacity=cluster_cfg.base_cpu_capacity,
            ram_capacity=cluster_cfg.base_ram_capacity,
            spot_price=initial_spot_price,
        )
        episode = EpisodeState(step=0, jobs=jobs, cluster=cluster, cfg=self.cfg)
        episode.ready_tasks()  # prime the initial ready-set
        episode.event_log.append(
            f"seed={self.seed_label if self.seed_label is not None else 'na'};"
            f" jobs={self.num_jobs}"
        )
        return episode


# ---------------------------------------------------------------------------
# Environment dynamics
# ---------------------------------------------------------------------------
def apply_random_events(
    state: EpisodeState,
    rng: np.random.Generator,
) -> None:
    """Apply exogenous events after action/progress for the current step."""
    events = state.cfg.simulator.events
    cluster_cfg = state.cfg.simulator.cluster

    walk = float(rng.uniform(events.spot_price_walk_low, events.spot_price_walk_high))
    state.cluster.spot_price = min(
        events.spot_price_max,
        max(events.spot_price_min, round(state.cluster.spot_price + walk, 2)),
    )

    if state.running_tasks and rng.random() < events.node_failure_prob:
        running_ids = list(state.running_tasks.keys())
        victim_index = int(rng.integers(low=0, high=len(running_ids)))
        victim_id = running_ids[victim_index]
        state.running_tasks.pop(victim_id)
        job_id_str, task_id = victim_id.split(":")
        job_id = int(job_id_str.replace("job", ""))
        job = state.jobs[job_id]
        job.tasks[task_id].state = TASK_STATE_FAILED
        job.update_status()
        state.cluster.recent_failures = min(
            state.cluster.recent_failures + 1,
            cluster_cfg.max_recent_failures,
        )
        state.event_log.append(f"step={state.step}: node_failure->{victim_id}")

    if rng.random() < events.data_spike_prob:
        candidates = [
            task
            for job in state.jobs
            for task in job.tasks.values()
            if task.state in {TASK_STATE_WAITING, TASK_STATE_READY}
        ]
        if candidates:
            hi = min(len(candidates), events.data_spike_max_tasks) + 1
            lo = min(events.data_spike_min_tasks, max(1, len(candidates)))
            hi = max(hi, lo + 1)
            affected_count = int(rng.integers(low=lo, high=hi))
            affected_count = max(1, min(affected_count, len(candidates)))
            chosen_indices = rng.choice(
                len(candidates), size=affected_count, replace=False
            )
            for idx in np.atleast_1d(chosen_indices):
                task = candidates[int(idx)]
                task.remaining_time += events.data_spike_duration_bump
                task.cpu_demand = min(
                    task.cpu_demand + events.data_spike_cpu_bump,
                    events.data_spike_cpu_cap,
                )
            state.event_log.append(f"step={state.step}: data_spike->{affected_count}_tasks")

    if state.cluster.scale_boost_remaining > 0:
        state.cluster.scale_boost_remaining -= 1
        if state.cluster.scale_boost_remaining == 0:
            state.cluster.cpu_capacity = max(
                state.cluster.cpu_capacity - cluster_cfg.scale_up_cpu_boost,
                cluster_cfg.base_cpu_capacity,
            )
            state.cluster.ram_capacity = max(
                state.cluster.ram_capacity - cluster_cfg.scale_up_ram_boost,
                cluster_cfg.base_ram_capacity,
            )


def launch_task(state: EpisodeState, task: TaskInstance) -> bool:
    if task.state != TASK_STATE_READY:
        return False
    if task.cpu_demand > state.available_cpu() or task.ram_demand > state.available_ram():
        return False
    task.state = TASK_STATE_RUNNING
    state.running_tasks[task.full_id()] = RunningTask(
        full_id=task.full_id(),
        cpu_demand=task.cpu_demand,
        ram_demand=task.ram_demand,
        remaining_time=task.remaining_time,
    )
    return True


def progress_running_tasks(state: EpisodeState) -> None:
    completed_task_ids: List[str] = []
    for full_id, running_task in state.running_tasks.items():
        running_task.remaining_time -= 1
        if running_task.remaining_time <= 0:
            completed_task_ids.append(full_id)
    for full_id in completed_task_ids:
        state.running_tasks.pop(full_id)
        job_id_str, task_id = full_id.split(":")
        job_id = int(job_id_str.replace("job", ""))
        task = state.jobs[job_id].tasks[task_id]
        task.remaining_time = 0
        task.state = TASK_STATE_COMPLETED
        state.jobs[job_id].update_status()
    state.cluster.recent_failures = max(state.cluster.recent_failures - 1, 0)


def _execute_ranking_key(state: EpisodeState, task: TaskInstance) -> float:
    ranking = state.cfg.simulator.actions_config.execute_ranking
    job = state.jobs[task.job_id]
    if ranking == "value":
        return job.value
    if ranking == "value_times_priority":
        return job.value * job.priority
    raise ValueError(f"Unknown execute_ranking: {ranking}")


def do_action(state: EpisodeState, action: str) -> Optional[str]:
    """Apply one orchestration action; returns a short debug label."""
    ready = state.ready_tasks()
    actions_cfg = state.cfg.simulator.actions_config
    cluster_cfg = state.cfg.simulator.cluster

    if action not in ACTIONS:
        raise ValueError(f"Unknown action: {action}")

    if action == "Execute_Ready_Job":
        if not ready:
            return "no_ready_job"
        ranked = sorted(
            ready, key=lambda t: _execute_ranking_key(state, t), reverse=True
        )
        chosen = ranked[0]
        launched = launch_task(state, chosen)
        return f"launched:{chosen.full_id()}" if launched else "insufficient_resources"

    if action == "Defer_Job":
        return "deferred"

    if action == "Scale_Up":
        state.cluster.cpu_capacity += cluster_cfg.scale_up_cpu_boost
        state.cluster.ram_capacity += cluster_cfg.scale_up_ram_boost
        state.cluster.scale_boost_remaining = cluster_cfg.scale_boost_duration
        return "scaled_up"

    if action == "Scale_Down":
        state.cluster.cpu_capacity = max(
            cluster_cfg.min_cpu_capacity,
            state.cluster.cpu_capacity - cluster_cfg.scale_down_cpu_step,
        )
        state.cluster.ram_capacity = max(
            cluster_cfg.min_ram_capacity,
            state.cluster.ram_capacity - cluster_cfg.scale_down_ram_step,
        )
        return "scaled_down"

    if action == "Reprioritize_Queue":
        for job in state.jobs:
            if not job.completed and not job.failed:
                job.priority = round(
                    min(actions_cfg.reprioritize_cap, job.priority + actions_cfg.reprioritize_bump),
                    2,
                )
        return "reprioritized"

    if action == "Pause_LowPriority_Job":
        low_priority_jobs = [
            job
            for job in state.jobs
            if not job.completed
            and not job.failed
            and job.priority < actions_cfg.pause_priority_threshold
        ]
        paused_jobs = 0
        for job in low_priority_jobs[: actions_cfg.pause_max_jobs]:
            for task in job.tasks.values():
                if task.state == TASK_STATE_READY:
                    task.state = TASK_STATE_PAUSED
            paused_jobs += 1
        return f"paused_jobs:{paused_jobs}"

    return None


def advance_one_step(
    state: EpisodeState,
    rng: np.random.Generator,
    action: str,
) -> Dict[str, float | str | int]:
    """Apply an action, advance the world one step, and return a snapshot."""
    event = do_action(state, action)
    progress_running_tasks(state)
    apply_random_events(state, rng)
    state.step += 1
    state.ready_tasks()

    return {
        "step": state.step,
        "action": action,
        "event": event or "none",
        "cpu_in_use": state.cpu_in_use(),
        "ram_in_use": state.ram_in_use(),
        "queue_depth": state.queue_depth(),
        "spot_price": state.cluster.spot_price,
        "done": int(state.all_done()),
    }


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
def _demo() -> None:
    cfg = load_config()
    seed = 7
    workload_rng, event_rng = make_episode_rngs(seed)
    generator = WorkloadGenerator(rng=workload_rng, cfg=cfg, num_jobs=12, seed_label=seed)
    environment = generator.generate_episode()

    print("Initial state vector:")
    print(environment.state_vector())
    print(f"ready_tasks={environment.queue_depth()}")

    for index in range(5):
        step_info = advance_one_step(environment, event_rng, "Execute_Ready_Job")
        print(f"step_info[{index}]={step_info}")

    print("Final partial state vector:")
    print(environment.state_vector())
    print(f"events={environment.event_log[:5]}")


if __name__ == "__main__":
    _demo()
