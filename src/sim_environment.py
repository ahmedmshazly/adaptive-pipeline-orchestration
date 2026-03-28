from __future__ import annotations

"""Core simulation environment for the v0 orchestration project.

This module defines a small stochastic world for studying adaptive data pipeline
orchestration under limited resources. It is intentionally compact: the goal is
not to mirror every detail of a production scheduler, but to create a clean and
reproducible testbed where value, cost, queue pressure, and failure risk can
pull decisions in different directions.

The rest of the project builds on the public interface in this file:

- ``WorkloadGenerator`` creates seeded simulation episodes.
- ``EpisodeState`` exposes the current world state and helper views.
- ``advance_one_step(...)`` applies one agent action and advances time.

The baseline agents and comparison script import these pieces directly, so this
file aims to stay easy to read and stable across project stages.
"""

from dataclasses import dataclass, field
import random
from typing import Dict, Final, List, Optional


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------
ACTIONS: Final[List[str]] = [
    "Execute_Ready_Job",
    "Defer_Job",
    "Scale_Up",
    "Scale_Down",
    "Reprioritize_Queue",
    "Pause_LowPriority_Job",
]

NODE_FAILURE_PROB: Final[float] = 0.05
DATA_SPIKE_PROB: Final[float] = 0.08
MAX_STEPS_DEFAULT: Final[int] = 300

BASE_CPU_CAPACITY: Final[int] = 10
BASE_RAM_CAPACITY: Final[int] = 16
MIN_CPU_CAPACITY: Final[int] = 6
MIN_RAM_CAPACITY: Final[int] = 8
SCALE_UP_CPU_BOOST: Final[int] = 3
SCALE_UP_RAM_BOOST: Final[int] = 4
SCALE_BOOST_DURATION: Final[int] = 3
MAX_RECENT_FAILURES: Final[int] = 10

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
    """Template for a single task inside a DAG pattern.

    The template stores the structural and nominal resource properties. A real
    episode clones this into a ``TaskInstance`` and then applies random scaling
    factors to duration and resource demand.
    """

    task_id: str
    parents: List[str]
    base_duration: int
    cpu_demand: int
    ram_demand: int


@dataclass(frozen=True)
class DAGTemplate:
    """Reusable job shape made of dependency-linked tasks."""

    name: str
    tasks: List[TaskTemplate]


@dataclass
class TaskInstance:
    """Runtime copy of one task inside a generated job."""

    job_id: int
    task_id: str
    parents: List[str]
    remaining_time: int
    cpu_demand: int
    ram_demand: int
    state: str = TASK_STATE_WAITING

    def full_id(self) -> str:
        """Return a stable runtime identifier in ``jobX:taskY`` form."""
        return f"job{self.job_id}:{self.task_id}"


@dataclass
class JobInstance:
    """Runtime job with its current task states and job-level attributes."""

    job_id: int
    template_name: str
    priority: float
    deadline_steps: int
    value: float
    tasks: Dict[str, TaskInstance]
    failed: bool = False
    completed: bool = False

    def update_status(self) -> None:
        """Refresh job terminal status from the states of its tasks.

        A job is terminal in one of two ways:
        - failed: at least one task failed
        - completed: all tasks completed successfully

        Otherwise the job stays active and neither flag is set.
        """
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
    """Lightweight record for a task currently consuming cluster resources."""

    full_id: str
    cpu_demand: int
    ram_demand: int
    remaining_time: int


@dataclass
class ClusterState:
    """Current infrastructure state for one episode."""

    cpu_capacity: int = BASE_CPU_CAPACITY
    ram_capacity: int = BASE_RAM_CAPACITY
    spot_price: float = 0.5
    scale_boost_remaining: int = 0
    recent_failures: int = 0


@dataclass
class EpisodeState:
    """Complete mutable state of one simulation episode."""

    step: int
    jobs: List[JobInstance]
    cluster: ClusterState
    running_tasks: Dict[str, RunningTask] = field(default_factory=dict)
    event_log: List[str] = field(default_factory=list)

    def ready_tasks(self) -> List[TaskInstance]:
        """Return all tasks that are ready to run and update readiness on demand.

        Readiness is derived, not stored independently. A task moves from
        ``waiting`` to ``ready`` once all of its parent tasks are completed.
        Paused tasks stay paused until some later action changes them.
        """
        ready_tasks: List[TaskInstance] = []
        for job in self.jobs:
            if job.failed or job.completed:
                continue

            for task in job.tasks.values():
                if task.state == TASK_STATE_WAITING and all(
                    job.tasks[parent].state == TASK_STATE_COMPLETED for parent in task.parents
                ):
                    task.state = TASK_STATE_READY

                if task.state == TASK_STATE_READY:
                    ready_tasks.append(task)

        return ready_tasks

    def cpu_in_use(self) -> int:
        """Return current CPU units consumed by running tasks."""
        return sum(task.cpu_demand for task in self.running_tasks.values())

    def ram_in_use(self) -> int:
        """Return current RAM units consumed by running tasks."""
        return sum(task.ram_demand for task in self.running_tasks.values())

    def available_cpu(self) -> int:
        """Return free CPU capacity, clipped at zero."""
        return max(self.cluster.cpu_capacity - self.cpu_in_use(), 0)

    def available_ram(self) -> int:
        """Return free RAM capacity, clipped at zero."""
        return max(self.cluster.ram_capacity - self.ram_in_use(), 0)

    def queue_depth(self) -> int:
        """Return the number of tasks that are currently ready to launch."""
        return len(self.ready_tasks())

    def all_done(self) -> bool:
        """Return ``True`` once every job is either completed or failed."""
        return all(job.failed or job.completed for job in self.jobs)

    def state_vector(self) -> Dict[str, float]:
        """Build the compact normalized observation used by the baseline agents.

        The goal of this vector is not to expose every detail in the state. It
        summarizes the main pressures that matter for orchestration decisions:
        resource load, queue pressure, market price, urgency, and failure memory.
        """
        ready_tasks = self.ready_tasks()
        active_jobs = [job for job in self.jobs if not job.failed and not job.completed]

        if active_jobs:
            avg_priority = sum(job.priority for job in active_jobs) / len(active_jobs)
            avg_urgency = sum(
                max(0.0, 1.0 - (job.deadline_steps / MAX_STEPS_DEFAULT))
                for job in active_jobs
            ) / len(active_jobs)
        else:
            avg_priority = 0.0
            avg_urgency = 0.0

        return {
            "CPU_Load": round(self.cpu_in_use() / max(self.cluster.cpu_capacity, 1), 4),
            "RAM_Available": round(self.available_ram() / max(self.cluster.ram_capacity, 1), 4),
            "Queue_Depth": min(self.queue_depth() / 20.0, 1.0),
            "Spot_Price": round(self.cluster.spot_price, 4),
            "DAG_Ready_Nodes": min(len(ready_tasks) / 20.0, 1.0),
            "Job_Priority": round(avg_priority, 4),
            "Deadline_Urgency": round(avg_urgency, 4),
            "Recent_Failures": min(self.cluster.recent_failures / 5.0, 1.0),
        }


# ---------------------------------------------------------------------------
# DAG templates
# ---------------------------------------------------------------------------
def build_chain_template() -> DAGTemplate:
    """Return a simple linear extract-transform-load style workflow."""
    return DAGTemplate(
        name="chain",
        tasks=[
            TaskTemplate("extract", [], 2, 2, 2),
            TaskTemplate("transform", ["extract"], 3, 3, 3),
            TaskTemplate("load", ["transform"], 2, 2, 2),
        ],
    )


def build_fork_join_template() -> DAGTemplate:
    """Return a fork-join workflow with two parallel feature branches."""
    return DAGTemplate(
        name="fork_join",
        tasks=[
            TaskTemplate("ingest", [], 2, 2, 2),
            TaskTemplate("feature_a", ["ingest"], 3, 2, 2),
            TaskTemplate("feature_b", ["ingest"], 3, 2, 2),
            TaskTemplate("merge", ["feature_a", "feature_b"], 2, 3, 3),
        ],
    )


def build_two_stage_batch_template() -> DAGTemplate:
    """Return a small fan-in batch workflow with three inputs and one aggregate."""
    return DAGTemplate(
        name="two_stage_batch",
        tasks=[
            TaskTemplate("ingest_a", [], 2, 1, 2),
            TaskTemplate("ingest_b", [], 2, 1, 2),
            TaskTemplate("ingest_c", [], 2, 1, 2),
            TaskTemplate("aggregate", ["ingest_a", "ingest_b", "ingest_c"], 4, 4, 4),
        ],
    )


# ---------------------------------------------------------------------------
# Episode generation
# ---------------------------------------------------------------------------
class WorkloadGenerator:
    """Seeded workload generator for reproducible simulation episodes."""

    def __init__(self, seed: int, num_jobs: int = 100) -> None:
        self.rng = random.Random(seed)
        self.seed = seed
        self.num_jobs = num_jobs
        self.templates = [
            build_chain_template(),
            build_fork_join_template(),
            build_two_stage_batch_template(),
        ]

    def _clone_template_into_job(self, job_id: int, template: DAGTemplate) -> JobInstance:
        """Instantiate one randomized job from a template.

        The template gives the structural shape. Small random multipliers make
        different jobs of the same template behave differently at runtime.
        """
        tasks: Dict[str, TaskInstance] = {}
        duration_factor = self.rng.choice([0.8, 1.0, 1.2, 1.5])
        cpu_factor = self.rng.choice([1.0, 1.0, 1.5])
        ram_factor = self.rng.choice([1.0, 1.0, 1.5])

        for template_task in template.tasks:
            tasks[template_task.task_id] = TaskInstance(
                job_id=job_id,
                task_id=template_task.task_id,
                parents=list(template_task.parents),
                remaining_time=max(1, int(round(template_task.base_duration * duration_factor))),
                cpu_demand=max(1, int(round(template_task.cpu_demand * cpu_factor))),
                ram_demand=max(1, int(round(template_task.ram_demand * ram_factor))),
            )

        return JobInstance(
            job_id=job_id,
            template_name=template.name,
            priority=round(self.rng.uniform(0.2, 1.0), 2),
            deadline_steps=self.rng.randint(30, 120),
            value=round(self.rng.uniform(1.0, 5.0), 2),
            tasks=tasks,
        )

    def generate_episode(self) -> EpisodeState:
        """Create one fresh episode and initialize readiness state."""
        jobs = [
            self._clone_template_into_job(job_id=index, template=self.rng.choice(self.templates))
            for index in range(self.num_jobs)
        ]
        cluster = ClusterState(
            cpu_capacity=BASE_CPU_CAPACITY,
            ram_capacity=BASE_RAM_CAPACITY,
            spot_price=round(self.rng.uniform(0.3, 0.7), 2),
        )
        episode = EpisodeState(step=0, jobs=jobs, cluster=cluster)
        episode.ready_tasks()  # Prime the initial ready-set.
        episode.event_log.append(f"seed={self.seed}; jobs={self.num_jobs}")
        return episode


# ---------------------------------------------------------------------------
# Environment dynamics
# ---------------------------------------------------------------------------
def apply_random_events(state: EpisodeState, rng: random.Random) -> None:
    """Apply exogenous events after the chosen action and task progress.

    Current v0 events:
    - bounded spot-price random walk
    - random node failure that kills one running task
    - random data spike that makes a few queued tasks heavier
    - scale-up boost decay back toward baseline capacity
    """
    state.cluster.spot_price = min(
        1.0,
        max(0.1, round(state.cluster.spot_price + rng.uniform(-0.08, 0.08), 2)),
    )

    if state.running_tasks and rng.random() < NODE_FAILURE_PROB:
        victim_id = rng.choice(list(state.running_tasks.keys()))
        state.running_tasks.pop(victim_id)
        job_id_str, task_id = victim_id.split(":")
        job_id = int(job_id_str.replace("job", ""))
        job = state.jobs[job_id]
        job.tasks[task_id].state = TASK_STATE_FAILED
        job.update_status()
        state.cluster.recent_failures = min(state.cluster.recent_failures + 1, MAX_RECENT_FAILURES)
        state.event_log.append(f"step={state.step}: node_failure->{victim_id}")

    if rng.random() < DATA_SPIKE_PROB:
        candidates = [
            task
            for job in state.jobs
            for task in job.tasks.values()
            if task.state in {TASK_STATE_WAITING, TASK_STATE_READY}
        ]
        if candidates:
            affected_count = min(len(candidates), rng.randint(1, 3))
            for task in rng.sample(candidates, k=affected_count):
                task.remaining_time += 1
                task.cpu_demand = min(task.cpu_demand + 1, 6)
            state.event_log.append(f"step={state.step}: data_spike->{affected_count}_tasks")

    if state.cluster.scale_boost_remaining > 0:
        state.cluster.scale_boost_remaining -= 1
        if state.cluster.scale_boost_remaining == 0:
            state.cluster.cpu_capacity = max(
                state.cluster.cpu_capacity - SCALE_UP_CPU_BOOST,
                BASE_CPU_CAPACITY,
            )
            state.cluster.ram_capacity = max(
                state.cluster.ram_capacity - SCALE_UP_RAM_BOOST,
                BASE_RAM_CAPACITY,
            )


def launch_task(state: EpisodeState, task: TaskInstance) -> bool:
    """Launch one ready task if enough free resources exist."""
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
    """Advance every running task by one time unit and close completed work."""
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


def do_action(state: EpisodeState, action: str) -> Optional[str]:
    """Apply one orchestration action and return a short event label.

    The returned string is meant for debugging and light reporting. The actual
    state transition is encoded directly in the mutated ``EpisodeState``.
    """
    ready_tasks = state.ready_tasks()

    if action not in ACTIONS:
        raise ValueError(f"Unknown action: {action}")

    if action == "Execute_Ready_Job":
        if not ready_tasks:
            return "no_ready_job"

        ranked_tasks = sorted(
            ready_tasks,
            key=lambda task: state.jobs[task.job_id].value * state.jobs[task.job_id].priority,
            reverse=True,
        )
        chosen_task = ranked_tasks[0]
        launched = launch_task(state, chosen_task)
        return f"launched:{chosen_task.full_id()}" if launched else "insufficient_resources"

    if action == "Defer_Job":
        return "deferred"

    if action == "Scale_Up":
        state.cluster.cpu_capacity += SCALE_UP_CPU_BOOST
        state.cluster.ram_capacity += SCALE_UP_RAM_BOOST
        state.cluster.scale_boost_remaining = SCALE_BOOST_DURATION
        return "scaled_up"

    if action == "Scale_Down":
        state.cluster.cpu_capacity = max(MIN_CPU_CAPACITY, state.cluster.cpu_capacity - 2)
        state.cluster.ram_capacity = max(MIN_RAM_CAPACITY, state.cluster.ram_capacity - 2)
        return "scaled_down"

    if action == "Reprioritize_Queue":
        for job in state.jobs:
            if not job.completed and not job.failed:
                job.priority = round(min(1.0, job.priority + 0.05), 2)
        return "reprioritized"

    if action == "Pause_LowPriority_Job":
        low_priority_jobs = [
            job
            for job in state.jobs
            if not job.completed and not job.failed and job.priority < 0.4
        ]
        paused_jobs = 0
        for job in low_priority_jobs[:2]:
            for task in job.tasks.values():
                if task.state == TASK_STATE_READY:
                    task.state = TASK_STATE_PAUSED
            paused_jobs += 1
        return f"paused_jobs:{paused_jobs}"

    return None


def advance_one_step(
    state: EpisodeState,
    rng: random.Random,
    action: str,
) -> Dict[str, float | str | int]:
    """Apply one agent action, advance the world by one step, and report a snapshot."""
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
    """Run a tiny local demo for quick sanity checks."""
    seed = 7
    generator = WorkloadGenerator(seed=seed, num_jobs=12)
    environment = generator.generate_episode()
    rng = random.Random(seed)

    print("Initial state vector:")
    print(environment.state_vector())
    print(f"ready_tasks={environment.queue_depth()}")

    for index in range(5):
        step_info = advance_one_step(environment, rng, "Execute_Ready_Job")
        print(f"step_info[{index}]={step_info}")

    print("Final partial state vector:")
    print(environment.state_vector())
    print(f"events={environment.event_log[:5]}")


if __name__ == "__main__":
    _demo()
