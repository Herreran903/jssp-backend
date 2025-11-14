from __future__ import annotations

from typing import Set, Tuple

from .models import SolverConfig, Solution


def validate_search(search: SolverConfig) -> None:
    """
    Minimal validations beyond Pydantic's schema constraints.
    Raises ValueError with a clear message on failure.
    """
    # Heuristic is constrained by Literal in the model.
    if search.timeLimitSec < 0:
        raise ValueError("search.timeLimitSec must be >= 0")
    if search.maxSolutions < 1:
        raise ValueError("search.maxSolutions must be >= 1")


def validate_solution(solution: Solution) -> None:
    """
    Validates solution consistency per contract:
    - Non-negative times (start, end, duration) and end >= start
    - machineId of each operation must exist in machines
    - Unique Machine.id
    - No duplicate operations for the same (jobId, opId)
    - makespan >= max end of all operations

    Raises ValueError with a clear message on failure.
    """
    # Machines must have unique IDs
    machine_ids = [m.id for m in solution.machines]
    if len(machine_ids) != len(set(machine_ids)):
        raise ValueError("Duplicate machine id detected in machines")

    machine_set = set(machine_ids)

    # Track (jobId, opId) to avoid duplicates within a job scope
    seen_ops: Set[Tuple[str, str]] = set()

    max_end = 0.0
    for op in solution.operations:
        if op.start < 0 or op.end < 0 or op.duration < 0:
            raise ValueError("Operation times must be >= 0")
        if op.end < op.start:
            raise ValueError("Operation end must be >= start")
        # 'Recommended' constraint: end == start + duration (not enforced as hard error)
        if op.machineId not in machine_set:
            raise ValueError(f"Operation references unknown machineId: {op.machineId}")

        key = (op.jobId, op.opId)
        if key in seen_ops:
            raise ValueError(f"Duplicate operation id within job scope: (jobId={op.jobId}, opId={op.opId})")
        seen_ops.add(key)

        if op.end > max_end:
            max_end = op.end

    if solution.makespan < max_end:
        raise ValueError("solution.makespan must be >= max end across operations")