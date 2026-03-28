from __future__ import annotations

"""Reflex baseline agent and shared episode-level evaluation helpers.

This module serves two roles in the v0 project stage.

1. It implements the deterministic Reflex Agent baseline used in the first
   round of comparison experiments.
2. It defines the shared evaluation objects and summary logic reused by the
   non-learning utility-based baseline.

The reflex policy is intentionally simple. It does not learn from experience and
it does not score the full action space. Instead, it follows a short set of
static rules that decide whether to execute ready work, scale up under obvious
capacity pressure, scale down when the cluster is idle and expensive, or defer.

That makes it a useful reference point: easy to understand, easy to reproduce,
and simple enough that later performance differences can be attributed to policy
quality rather than hidden complexity.
"""

from dataclasses import dataclass
from pathlib import Path
import random
import sys
from typing import Dict, List

# Allow direct execution from the repository root without requiring package
# installation. This keeps the project easy to run during the early baseline
# stage.
THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from sim_environment import (  # noqa: E402
    MAX_STEPS_DEFAULT,
    EpisodeState,
    WorkloadGenerator,
    advance_one_step,
)


# Shared utility weights used in the current v0 evaluation.
#
# The same utility shape is reused by the fixed utility-based baseline and is
# intended to carry forward into the future learning-based version so that later
# comparisons isolate the effect of policy learning rather than changing the
# objective itself.
ALPHA = 1.0  # Reward for completed job value.
BETA = 0.4   # Penalty weight for accumulated compute cost.
GAMMA = 0.8  # Penalty weight for failed jobs.

# Baseline cluster capacities used to decide whether a temporary scale-up has
# moved the cluster above its normal starting point.
BASE_CPU = 10
BASE_RAM = 16


@dataclass
class EpisodeMetrics:
    """Compact summary of one finished episode.

    The comparison script writes these fields directly to CSV and uses them to
    build aggregate summaries, so the schema here is part of the project's
    public evaluation interface.
    """

    seed: int
    agent_name: str
    num_jobs: int
    steps_executed: int
    completed_jobs: int
    failed_jobs: int
    completion_rate: float
    failure_rate: float
    total_completed_value: float
    total_compute_cost: float
    avg_compute_cost_per_step: float
    total_utility: float
    completed_all_jobs: bool

    def as_dict(self) -> Dict[str, float | int | str | bool]:
        """Return a serialization-friendly row used by CSV and JSON writers."""
        return {
            "seed": self.seed,
            "agent_name": self.agent_name,
            "num_jobs": self.num_jobs,
            "steps_executed": self.steps_executed,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "completion_rate": round(self.completion_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
            "total_completed_value": round(self.total_completed_value, 4),
            "total_compute_cost": round(self.total_compute_cost, 4),
            "avg_compute_cost_per_step": round(self.avg_compute_cost_per_step, 4),
            "total_utility": round(self.total_utility, 4),
            "completed_all_jobs": self.completed_all_jobs,
        }


class ReflexAgent:
    """Deterministic rule-based scheduler for the v0 baseline.

    Policy summary:
    - If the cluster is idle, currently oversized, and spot price is high,
      scale down to reduce unnecessary cost.
    - If there is ready work and at least one ready task fits, execute.
    - If the ready queue is building, spot price is still moderate, and no
      temporary boost is active, scale up once.
    - Otherwise defer.

    The policy is intentionally narrow. It does not reprioritize or pause jobs,
    and it does not use any learned or optimized scoring rule.
    """

    name = "Reflex Agent"

    def choose_action(self, state: EpisodeState) -> str:
        """Choose one orchestration action from the shared action space."""
        ready_tasks = state.ready_tasks()

        # When there is no immediate work to launch, the cluster is above its
        # baseline size, and spot price is expensive, scale down to avoid paying
        # for idle capacity.
        if not ready_tasks and self._should_scale_down_idle_cluster(state):
            return "Scale_Down"

        if ready_tasks:
            # If at least one ready task fits, prefer forward progress.
            if self._can_launch_any_ready_task(state):
                return "Execute_Ready_Job"

            # If the queue is growing because ready tasks do not fit and prices
            # are still reasonable, take one temporary scale-up step.
            if self._should_scale_up_for_queue_pressure(state):
                return "Scale_Up"

        return "Defer_Job"

    @staticmethod
    def _can_launch_any_ready_task(state: EpisodeState) -> bool:
        """Return True if any currently ready task fits in the free capacity."""
        available_cpu = state.available_cpu()
        available_ram = state.available_ram()

        for task in state.ready_tasks():
            if task.cpu_demand <= available_cpu and task.ram_demand <= available_ram:
                return True
        return False

    @staticmethod
    def _should_scale_down_idle_cluster(state: EpisodeState) -> bool:
        """Decide whether idle expensive overprovisioning justifies scaling down."""
        return (
            state.cluster.spot_price >= 0.8
            and (
                state.cluster.cpu_capacity > BASE_CPU
                or state.cluster.ram_capacity > BASE_RAM
            )
        )

    @staticmethod
    def _should_scale_up_for_queue_pressure(state: EpisodeState) -> bool:
        """Decide whether the reflex baseline should use its static scale-up rule."""
        return (
            state.queue_depth() >= 3
            and state.cluster.spot_price <= 0.7
            and state.cluster.scale_boost_remaining == 0
        )


def estimate_step_cost(state: EpisodeState) -> float:
    """Estimate operational cost for the current step.

    This is a deliberately simple v0 approximation. Cost scales with current
    spot price and with a weighted mix of CPU and RAM usage after the step has
    been applied.
    """
    utilization_term = (0.6 * state.cpu_in_use()) + (0.4 * state.ram_in_use())
    return state.cluster.spot_price * utilization_term


def summarize_episode(
    seed: int,
    agent_name: str,
    state: EpisodeState,
    num_jobs: int,
    total_compute_cost: float,
) -> EpisodeMetrics:
    """Convert a finished episode state into a stable metrics record."""
    completed_jobs = sum(1 for job in state.jobs if job.completed)
    failed_jobs = sum(1 for job in state.jobs if job.failed)
    total_completed_value = sum(job.value for job in state.jobs if job.completed)
    total_utility = (ALPHA * total_completed_value) - (BETA * total_compute_cost) - (GAMMA * failed_jobs)

    return EpisodeMetrics(
        seed=seed,
        agent_name=agent_name,
        num_jobs=num_jobs,
        steps_executed=state.step,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        completion_rate=completed_jobs / max(num_jobs, 1),
        failure_rate=failed_jobs / max(num_jobs, 1),
        total_completed_value=total_completed_value,
        total_compute_cost=total_compute_cost,
        avg_compute_cost_per_step=(total_compute_cost / max(state.step, 1)),
        total_utility=total_utility,
        completed_all_jobs=(completed_jobs == num_jobs),
    )


def run_reflex_episode(
    seed: int,
    num_jobs: int = 100,
    max_steps: int = MAX_STEPS_DEFAULT,
    verbose: bool = False,
) -> EpisodeMetrics:
    """Run one episode with the reflex baseline and return its summary metrics."""
    generator = WorkloadGenerator(seed=seed, num_jobs=num_jobs)
    state = generator.generate_episode()
    rng = random.Random(seed)
    agent = ReflexAgent()

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


def run_many_reflex_episodes(
    seeds: List[int],
    num_jobs: int = 100,
    max_steps: int = MAX_STEPS_DEFAULT,
) -> List[EpisodeMetrics]:
    """Run the reflex baseline over multiple seeds."""
    return [run_reflex_episode(seed=seed, num_jobs=num_jobs, max_steps=max_steps) for seed in seeds]


def _print_verbose_step(state: EpisodeState, action: str, step_info: Dict[str, object]) -> None:
    """Print one compact trace line for debugging or manual inspection."""
    print(
        f"step={step_info['step']:>3} action={action:<18} "
        f"queue={state.queue_depth():>2} cpu={state.cpu_in_use():>2}/{state.cluster.cpu_capacity:<2} "
        f"ram={state.ram_in_use():>2}/{state.cluster.ram_capacity:<2} "
        f"spot={state.cluster.spot_price:.2f} event={step_info['event']}"
    )


def _demo() -> None:
    """Run one small demo episode and print its summary."""
    metrics = run_reflex_episode(seed=7, num_jobs=20, max_steps=120, verbose=False)
    print("Reflex Agent v0 episode summary")
    for key, value in metrics.as_dict().items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    _demo()
