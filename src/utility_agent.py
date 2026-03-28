from __future__ import annotations

"""Non-learning utility-based baseline for the v0 orchestration simulator.

This module implements the second baseline used in the current project stage.
Unlike the Reflex Agent, which follows a short set of fixed rules, this agent
scores every action in the shared action space and picks the one with the
highest hand-designed utility score.

The policy is still fully static. It does not train, adapt, or update from
experience. Its job is to provide a stronger non-learning reference point before
adding the planned self-learning utility-based agent in the next project stage.

The key idea is simple: approximate the value of an action by balancing four
signals available in the current state.

- expected work value
- deadline pressure
- resource cost
- operational risk

Because the scoring rule is explicit and readable, it is a good bridge between a
simple rule-based baseline and a later learned policy that keeps the same broad
optimization goal.
"""

from pathlib import Path
import random
import sys
from typing import Dict, List, Optional, Tuple

# Allow direct execution from the repository root without requiring package
# installation. This keeps the baseline scripts easy to run during development
# and experimentation.
THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from reflex_agent import (  # noqa: E402
    ALPHA,
    BETA,
    GAMMA,
    BASE_CPU,
    BASE_RAM,
    EpisodeMetrics,
    estimate_step_cost,
    summarize_episode,
)
from sim_environment import (  # noqa: E402
    ACTIONS,
    MAX_STEPS_DEFAULT,
    EpisodeState,
    TaskInstance,
    WorkloadGenerator,
    advance_one_step,
)


# Hand-tuned scoring constants used only by the fixed utility-based baseline.
# These are not the final project objective weights. They simply shape the
# action-ranking rule used by this baseline policy.
NO_EXECUTABLE_TASK_SCORE = -10_000.0
ACTIVE_SCALE_UP_PENALTY = -25.0
EMPTY_QUEUE_SCALE_UP_PENALTY = -15.0
UNNECESSARY_SCALE_UP_PENALTY = -6.0
INVALID_SCALE_DOWN_PENALTY = -20.0
LOW_VALUE_REPRIORITIZE_PENALTY = -8.0
NO_LOW_PRIORITY_WORK_PENALTY = -12.0
UNNECESSARY_PAUSE_PENALTY = -10.0

EXECUTION_URGENCY_WEIGHT = 0.25
DEFER_BASE_PENALTY = -0.5
QUEUE_PENALTY_WEIGHT = 4.0
URGENCY_PENALTY_WEIGHT = 4.0
FAILURE_RELIEF_WEIGHT = 0.8
PRICE_RELIEF_WEIGHT = 1.2
BLOCKED_TASK_BENEFIT_WEIGHT = 2.0
SCALE_UP_URGENCY_WEIGHT = 4.0
SCALE_UP_FAILURE_WEIGHT = 2.0
SCALE_UP_PRICE_WEIGHT = 8.0
SCALE_DOWN_PRICE_WEIGHT = 6.0
SCALE_DOWN_BASE_BONUS = 1.5
SCALE_DOWN_QUEUE_WEIGHT = 0.5
REPRIORITIZE_QUEUE_WEIGHT = 2.0
REPRIORITIZE_URGENCY_WEIGHT = 2.0
REPRIORITIZE_FAILURE_WEIGHT = 1.0
REPRIORITIZE_BASE_PENALTY = 2.5
PAUSE_ACTIVE_LOW_WEIGHT = 1.2
PAUSE_QUEUE_WEIGHT = 2.0
PAUSE_FAILURE_WEIGHT = 4.0
PAUSE_PRICE_WEIGHT = 6.0
PAUSE_BASE_PENALTY = 5.0
BEST_TASK_RESOURCE_COST_WEIGHT = 0.35
READY_CHILDREN_BONUS_WEIGHT = 0.15
JOB_VALUE_BASE = 0.7
JOB_PRIORITY_WEIGHT = 0.6
JOB_URGENCY_WEIGHT = 0.4
LOAD_RISK_WEIGHT = 3.0
FAILURE_HISTORY_RISK_WEIGHT = 1.5
QUEUE_PRESSURE_RISK_WEIGHT = 0.4
STRESS_GUARD_FAILURE_LIMIT = 0.6
STRESS_GUARD_PRICE_LIMIT = 0.9


class UtilityBasedAgent:
    """Static action-scoring baseline for the v0 simulator.

    The agent computes a score for each action in ``ACTIONS`` and chooses the
    highest-scoring option. The score is not learned. It is a hand-designed rule
    that tries to capture the same broad trade-off used by the project's summary
    utility: complete valuable work while keeping cost and risk under control.

    Two details are worth keeping in mind:

    1. The agent uses the current state only. It does not simulate future steps.
    2. The scores are heuristic. They are meant to be sensible and consistent,
       not globally optimal.
    """

    name = "Utility-Based Agent (Non-Learning Baseline)"

    def choose_action(self, state: EpisodeState) -> str:
        """Choose the highest-scoring action for the current episode state."""
        scored_actions = [(action, self.score_action(state, action)) for action in ACTIONS]
        score_by_action = {action: score for action, score in scored_actions}
        scored_actions.sort(key=lambda item: item[1], reverse=True)

        # Prevent non-productive queue churn when execution is clearly viable.
        # If a ready task fits, the execution score is positive, and the system
        # is not under extreme failure or price pressure, prefer forward
        # progress over queue-only control actions.
        if self._should_force_execution(state, score_by_action):
            top_action = scored_actions[0][0]
            if top_action in {"Reprioritize_Queue", "Pause_LowPriority_Job", "Defer_Job"}:
                return "Execute_Ready_Job"

        return scored_actions[0][0]

    def score_action(self, state: EpisodeState, action: str) -> float:
        """Return the baseline score for one candidate action."""
        if action == "Execute_Ready_Job":
            return self._score_execute(state)
        if action == "Defer_Job":
            return self._score_defer(state)
        if action == "Scale_Up":
            return self._score_scale_up(state)
        if action == "Scale_Down":
            return self._score_scale_down(state)
        if action == "Reprioritize_Queue":
            return self._score_reprioritize(state)
        if action == "Pause_LowPriority_Job":
            return self._score_pause_low_priority(state)
        raise ValueError(f"Unknown action: {action}")

    def _score_execute(self, state: EpisodeState) -> float:
        """Score executing the best currently launchable ready task."""
        task = self._best_ready_task(state)
        if task is None:
            return NO_EXECUTABLE_TASK_SCORE

        job = state.jobs[task.job_id]
        value_term = self._effective_job_value(state, task)
        resource_cost = self._resource_cost(state, task)
        risk_term = self._launch_risk(state, task)
        urgency_bonus = EXECUTION_URGENCY_WEIGHT * self._job_urgency(job.deadline_steps)
        return (ALPHA * value_term) + urgency_bonus - (BETA * resource_cost) - (GAMMA * risk_term)

    def _score_defer(self, state: EpisodeState) -> float:
        """Score doing nothing for one step.

        Deferring becomes less attractive when the queue is deep or deadlines are
        getting tight. It becomes slightly more attractive when recent failures
        are high or spot price has moved into an expensive regime.
        """
        state_view = state.state_vector()
        queue_penalty = QUEUE_PENALTY_WEIGHT * state_view["Queue_Depth"]
        urgency_penalty = URGENCY_PENALTY_WEIGHT * state_view["Deadline_Urgency"]
        failure_relief = FAILURE_RELIEF_WEIGHT * state_view["Recent_Failures"]
        price_relief = PRICE_RELIEF_WEIGHT * max(state.cluster.spot_price - 0.8, 0.0)
        return DEFER_BASE_PENALTY - queue_penalty - urgency_penalty + failure_relief + price_relief

    def _score_scale_up(self, state: EpisodeState) -> float:
        """Score a temporary scale-up action.

        Scaling up is useful only when there is real queue pressure and some of
        the ready work is blocked by current capacity.
        """
        if state.cluster.scale_boost_remaining > 0:
            return ACTIVE_SCALE_UP_PENALTY

        queue_depth = state.queue_depth()
        if queue_depth == 0:
            return EMPTY_QUEUE_SCALE_UP_PENALTY

        ready_tasks = state.ready_tasks()
        blocked_due_to_capacity = sum(
            1
            for task in ready_tasks
            if task.cpu_demand > state.available_cpu() or task.ram_demand > state.available_ram()
        )
        if blocked_due_to_capacity == 0:
            return UNNECESSARY_SCALE_UP_PENALTY

        state_view = state.state_vector()
        urgency = state_view["Deadline_Urgency"]
        failure_pressure = state_view["Recent_Failures"]
        price_penalty = SCALE_UP_PRICE_WEIGHT * state.cluster.spot_price
        benefit = (
            (BLOCKED_TASK_BENEFIT_WEIGHT * blocked_due_to_capacity)
            + (SCALE_UP_URGENCY_WEIGHT * urgency)
            + queue_depth
            - (SCALE_UP_FAILURE_WEIGHT * failure_pressure)
        )
        return benefit - price_penalty

    def _score_scale_down(self, state: EpisodeState) -> float:
        """Score shrinking the cluster back toward baseline capacity."""
        idle_cluster = state.cpu_in_use() == 0 and state.ram_in_use() == 0
        above_baseline = state.cluster.cpu_capacity > BASE_CPU or state.cluster.ram_capacity > BASE_RAM
        if not idle_cluster or not above_baseline:
            return INVALID_SCALE_DOWN_PENALTY

        return (
            (SCALE_DOWN_PRICE_WEIGHT * state.cluster.spot_price)
            + SCALE_DOWN_BASE_BONUS
            - (SCALE_DOWN_QUEUE_WEIGHT * state.queue_depth())
        )

    def _score_reprioritize(self, state: EpisodeState) -> float:
        """Score queue reprioritization.

        This action is only meant to become attractive when the ready queue is
        meaningfully backed up and deadline pressure is visible.
        """
        queue_depth_raw = state.queue_depth()
        state_view = state.state_vector()
        queue_depth = state_view["Queue_Depth"]
        urgency = state_view["Deadline_Urgency"]
        failure_pressure = state_view["Recent_Failures"]

        if queue_depth_raw < 4 or urgency < 0.6:
            return LOW_VALUE_REPRIORITIZE_PENALTY

        return (
            (REPRIORITIZE_QUEUE_WEIGHT * queue_depth)
            + (REPRIORITIZE_URGENCY_WEIGHT * urgency)
            + (REPRIORITIZE_FAILURE_WEIGHT * failure_pressure)
            - REPRIORITIZE_BASE_PENALTY
        )

    def _score_pause_low_priority(self, state: EpisodeState) -> float:
        """Score pausing low-priority work to reduce contention or exposure."""
        active_low_priority_jobs = sum(
            1
            for job in state.jobs
            if not job.completed and not job.failed and job.priority < 0.4
        )
        if active_low_priority_jobs == 0:
            return NO_LOW_PRIORITY_WORK_PENALTY

        state_view = state.state_vector()
        queue_pressure = state_view["Queue_Depth"]
        failure_pressure = state_view["Recent_Failures"]
        price_pressure = max(state.cluster.spot_price - 0.8, 0.0)

        if failure_pressure < 0.4 and price_pressure == 0.0 and queue_pressure < 0.5:
            return UNNECESSARY_PAUSE_PENALTY

        return (
            (PAUSE_ACTIVE_LOW_WEIGHT * active_low_priority_jobs)
            + (PAUSE_QUEUE_WEIGHT * queue_pressure)
            + (PAUSE_FAILURE_WEIGHT * failure_pressure)
            + (PAUSE_PRICE_WEIGHT * price_pressure)
            - PAUSE_BASE_PENALTY
        )

    def _best_ready_task(self, state: EpisodeState) -> Optional[TaskInstance]:
        """Return the launchable ready task with the best local value-cost score."""
        candidates: List[Tuple[float, TaskInstance]] = []
        available_cpu = state.available_cpu()
        available_ram = state.available_ram()

        for task in state.ready_tasks():
            if task.cpu_demand > available_cpu or task.ram_demand > available_ram:
                continue
            score = self._effective_job_value(state, task) - (
                BEST_TASK_RESOURCE_COST_WEIGHT * self._resource_cost(state, task)
            )
            candidates.append((score, task))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _effective_job_value(self, state: EpisodeState, task: TaskInstance) -> float:
        """Approximate how valuable it is to launch this task now.

        The score increases with job value, job priority, deadline urgency, and
        with the number of downstream tasks that may become easier to unlock once
        this task completes.
        """
        job = state.jobs[task.job_id]
        urgency = self._job_urgency(job.deadline_steps)
        ready_children_bonus = READY_CHILDREN_BONUS_WEIGHT * len(
            [
                child
                for child in job.tasks.values()
                if task.task_id in child.parents and child.state in {"waiting", "ready"}
            ]
        )
        return job.value * (
            JOB_VALUE_BASE
            + (JOB_PRIORITY_WEIGHT * job.priority)
            + (JOB_URGENCY_WEIGHT * urgency)
            + ready_children_bonus
        )

    @staticmethod
    def _job_urgency(deadline_steps: int) -> float:
        """Map remaining deadline slack into a normalized urgency signal."""
        return max(0.0, 1.0 - (deadline_steps / max(MAX_STEPS_DEFAULT, 1)))

    @staticmethod
    def _resource_cost(state: EpisodeState, task: TaskInstance) -> float:
        """Estimate immediate launch cost for a candidate task."""
        return state.cluster.spot_price * ((0.6 * task.cpu_demand) + (0.4 * task.ram_demand))

    @staticmethod
    def _launch_risk(state: EpisodeState, task: TaskInstance) -> float:
        """Estimate a simple local risk score for launching a task now."""
        projected_cpu_load = (state.cpu_in_use() + task.cpu_demand) / max(state.cluster.cpu_capacity, 1)
        projected_ram_load = (state.ram_in_use() + task.ram_demand) / max(state.cluster.ram_capacity, 1)
        load_risk = (
            max(projected_cpu_load - 0.8, 0.0) * LOAD_RISK_WEIGHT
            + max(projected_ram_load - 0.8, 0.0) * LOAD_RISK_WEIGHT
        )
        state_view = state.state_vector()
        failure_history_risk = FAILURE_HISTORY_RISK_WEIGHT * state_view["Recent_Failures"]
        queue_pressure_risk = QUEUE_PRESSURE_RISK_WEIGHT * state_view["Queue_Depth"]
        return load_risk + failure_history_risk + queue_pressure_risk

    def _should_force_execution(self, state: EpisodeState, score_by_action: Dict[str, float]) -> bool:
        """Return True when execution should override queue-only top actions.

        Without this small guardrail, the fixed scoring rule can sometimes keep
        choosing safe control actions even when launching one ready task would be
        a reasonable next move.
        """
        return (
            self._best_ready_task(state) is not None
            and score_by_action["Execute_Ready_Job"] > 0.0
            and state.state_vector()["Recent_Failures"] < STRESS_GUARD_FAILURE_LIMIT
            and state.cluster.spot_price < STRESS_GUARD_PRICE_LIMIT
        )


def run_utility_episode(
    seed: int,
    num_jobs: int = 100,
    max_steps: int = MAX_STEPS_DEFAULT,
    verbose: bool = False,
) -> EpisodeMetrics:
    """Run one episode with the fixed utility-based baseline."""
    generator = WorkloadGenerator(seed=seed, num_jobs=num_jobs)
    state = generator.generate_episode()
    rng = random.Random(seed)
    agent = UtilityBasedAgent()

    total_compute_cost = 0.0

    while not state.all_done() and state.step < max_steps:
        action = agent.choose_action(state)
        step_info = advance_one_step(state, rng, action)
        total_compute_cost += estimate_step_cost(state)

        if verbose:
            _print_verbose_step(state=state, action=action, step_info=step_info)

    return summarize_episode(
        seed=seed,
        agent_name=agent.name,
        state=state,
        num_jobs=num_jobs,
        total_compute_cost=total_compute_cost,
    )


def run_many_utility_episodes(
    seeds: List[int],
    num_jobs: int = 100,
    max_steps: int = MAX_STEPS_DEFAULT,
) -> List[EpisodeMetrics]:
    """Run the utility-based baseline over multiple seeds."""
    return [run_utility_episode(seed=seed, num_jobs=num_jobs, max_steps=max_steps) for seed in seeds]


def _print_verbose_step(state: EpisodeState, action: str, step_info: Dict[str, object]) -> None:
    """Print one compact trace line for debugging or manual inspection."""
    print(
        f"step={step_info['step']:>3} action={action:<22} "
        f"queue={state.queue_depth():>2} cpu={state.cpu_in_use():>2}/{state.cluster.cpu_capacity:<2} "
        f"ram={state.ram_in_use():>2}/{state.cluster.ram_capacity:<2} "
        f"spot={state.cluster.spot_price:.2f} event={step_info['event']}"
    )


def _demo() -> None:
    """Run one small demonstration episode from the command line."""
    metrics = run_utility_episode(seed=7, num_jobs=20, max_steps=120, verbose=False)
    print("Utility-Based Agent v0 episode summary")
    for key, value in metrics.as_dict().items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    _demo()
