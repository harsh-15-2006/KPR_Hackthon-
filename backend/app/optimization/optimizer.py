"""Budget-constrained reduction optimizer, powered by Google OR-Tools CP-SAT.

This module is AUTHORITATIVE. No AI model participates in, influences or
overrides the decision made here. Gemini only ever reads the structured
result this produces.

Determinism: the solver is pinned to a fixed random seed and a single
worker so the same inputs always produce the same allocation, which is
what makes an optimization run reproducible and auditable.
"""
import math
import time

from ortools.sat.python import cp_model

# CP-SAT works on int64; keep well clear of the boundary.
_MAX_SCALED = 2**53

from app.core.logging import get_logger
from app.optimization.constraints import apply_all
from app.optimization.models import (
    SCALE,
    Action,
    Allocation,
    BusinessConstraint,
    OptimizationResult,
    SolverStatus,
)

logger = get_logger(__name__)

_STATUS_MAP = {
    cp_model.OPTIMAL: SolverStatus.OPTIMAL,
    cp_model.FEASIBLE: SolverStatus.FEASIBLE,
    cp_model.INFEASIBLE: SolverStatus.INFEASIBLE,
    cp_model.MODEL_INVALID: SolverStatus.MODEL_INVALID,
    cp_model.UNKNOWN: SolverStatus.UNKNOWN,
}

STATUS_EXPLANATION = {
    SolverStatus.OPTIMAL: (
        "A provably best allocation was found - no other combination of the "
        "available actions yields more CO2e reduction within this budget and "
        "these constraints."
    ),
    SolverStatus.FEASIBLE: (
        "A valid allocation was found within the time limit, but it was not "
        "proven to be the best possible one."
    ),
    SolverStatus.INFEASIBLE: (
        "No allocation can satisfy all the constraints at once. This usually "
        "means the budget is too small for a required action, or two "
        "constraints contradict each other."
    ),
    SolverStatus.MODEL_INVALID: "The optimization model was rejected as invalid.",
    SolverStatus.UNKNOWN: "The solver could not determine a result within the time limit.",
}


def optimize(
    actions: list[Action],
    budget: float,
    constraints: list[BusinessConstraint] | None = None,
    max_seconds: float = 15.0,
) -> OptimizationResult:
    """Maximize expected CO2e reduction subject to budget and business constraints."""
    constraints = constraints or []
    started = time.perf_counter()

    if budget is None or not math.isfinite(budget):
        return OptimizationResult(
            solver_status=SolverStatus.MODEL_INVALID,
            budget=0.0,
            message="Budget must be a finite number.",
        )
    if budget < 0:
        return OptimizationResult(
            solver_status=SolverStatus.MODEL_INVALID,
            budget=budget,
            message="Budget cannot be negative.",
        )
    if budget * SCALE > _MAX_SCALED:
        return OptimizationResult(
            solver_status=SolverStatus.MODEL_INVALID,
            budget=budget,
            message=(
                f"Budget is too large for the solver (limit {_MAX_SCALED // SCALE:,})."
            ),
        )
    bad = [
        a for a in actions
        if a.cost is not None and (not math.isfinite(a.cost) or a.cost * SCALE > _MAX_SCALED)
    ]
    if bad:
        return OptimizationResult(
            solver_status=SolverStatus.MODEL_INVALID,
            budget=budget,
            message=f"Action '{bad[0].name}' has a non-finite or excessively large cost.",
        )

    usable = [a for a in actions if a.selectable]
    skipped = [a for a in actions if not a.selectable]

    if not usable:
        return OptimizationResult(
            solver_status=SolverStatus.INFEASIBLE,
            budget=budget,
            unused_budget=budget,
            message=(
                "There are no selectable reduction actions. An action needs a "
                "cost, a positive expected reduction, and availability."
            ),
            allocations=[
                Allocation(
                    action_id=a.id,
                    action_name=a.name,
                    emission_source=a.emission_source,
                    selected=False,
                    units=0,
                    allocated_cost=0.0,
                    expected_reduction=0.0,
                    reduction_per_cost=a.reduction_per_cost,
                    rejection_reason="Not selectable (unavailable, or missing cost/reduction).",
                )
                for a in skipped
            ],
        )

    model = cp_model.CpModel()
    x = [model.new_int_var(0, a.max_units, f"x_{i}") for i, a in enumerate(usable)]

    # Boolean "is this action funded at all" indicators.
    # Needed because CP-SAT's add_at_most_one accepts ONLY boolean literals -
    # passing an IntVar with capacity > 1 raises TypeError - and because
    # counting constraints must count DISTINCT actions, not units.
    selected = [model.new_bool_var(f"sel_{i}") for i in range(len(usable))]
    for i, a in enumerate(usable):
        model.add(x[i] >= 1).only_enforce_if(selected[i])
        model.add(x[i] == 0).only_enforce_if(~selected[i])

    # Cost is scaled with CEIL so sub-paisa rounding can never let the
    # solver believe an action is cheaper than it is, which would allow a
    # real-money overspend. Reduction is scaled with FLOOR so the objective
    # never over-credits an action.
    costs = [int(math.ceil(a.cost * SCALE)) for a in usable]
    reductions = [int(math.floor(a.expected_reduction * SCALE)) for a in usable]
    budget_scaled = int(math.floor(budget * SCALE))

    # The budget constraint - the heart of the problem statement.
    model.add(sum(x[i] * costs[i] for i in range(len(usable))) <= budget_scaled)

    applied = apply_all(model, x, usable, constraints, selected)

    model.maximize(sum(x[i] * reductions[i] for i in range(len(usable))))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_seconds
    solver.parameters.num_workers = 1      # determinism
    solver.parameters.random_seed = 42     # determinism
    status = solver.solve(model)
    mapped = _STATUS_MAP.get(status, SolverStatus.UNKNOWN)

    result = OptimizationResult(
        solver_status=mapped,
        budget=budget,
        wall_time_seconds=round(solver.wall_time, 4),
        solver_version=_ortools_version(),
        constraints_applied=applied,
        message=STATUS_EXPLANATION.get(mapped, ""),
    )

    if mapped not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        result.unused_budget = budget
        result.allocations = [
            Allocation(
                action_id=a.id,
                action_name=a.name,
                emission_source=a.emission_source,
                selected=False,
                units=0,
                allocated_cost=0.0,
                expected_reduction=0.0,
                reduction_per_cost=a.reduction_per_cost,
                rejection_reason="No feasible allocation exists under the current constraints.",
            )
            for a in usable + skipped
        ]
        logger.warning(
            "Optimization not solved", extra={"event": "optimize", "status": mapped.value}
        )
        return result

    # --- build allocations with an explanation for every action ---
    allocations: list[Allocation] = []
    total_cost = 0.0
    total_reduction = 0.0

    for i, a in enumerate(usable):
        units = int(solver.value(x[i]))
        alloc_cost = round(units * a.cost, 4)
        alloc_red = round(units * a.expected_reduction, 4)
        total_cost += alloc_cost
        total_reduction += alloc_red
        allocations.append(
            Allocation(
                action_id=a.id,
                action_name=a.name,
                emission_source=a.emission_source,
                selected=units > 0,
                units=units,
                allocated_cost=alloc_cost,
                expected_reduction=alloc_red,
                reduction_per_cost=a.reduction_per_cost,
                rejection_reason=(
                    None if units > 0
                    else _rejection_reason(a, budget, bool(applied))
                ),
            )
        )

    for a in skipped:
        allocations.append(
            Allocation(
                action_id=a.id,
                action_name=a.name,
                emission_source=a.emission_source,
                selected=False,
                units=0,
                allocated_cost=0.0,
                expected_reduction=0.0,
                reduction_per_cost=a.reduction_per_cost,
                rejection_reason="Excluded before solving: unavailable or missing cost/reduction.",
            )
        )

    result.allocations = allocations
    result.total_cost = round(total_cost, 4)
    result.expected_reduction = round(total_reduction, 4)
    result.unused_budget = round(budget - total_cost, 4)
    result.budget_utilization = round((total_cost / budget * 100), 2) if budget else 0.0
    result.objective_value = round(solver.objective_value / SCALE, 4)
    result.best_bound = round(solver.best_objective_bound / SCALE, 4)

    by_cost: dict[str, float] = {}
    by_red: dict[str, float] = {}
    for al in allocations:
        if al.selected:
            by_cost[al.emission_source] = round(
                by_cost.get(al.emission_source, 0.0) + al.allocated_cost, 4
            )
            by_red[al.emission_source] = round(
                by_red.get(al.emission_source, 0.0) + al.expected_reduction, 4
            )
    result.allocation_by_source = by_cost
    result.reduction_by_source = by_red

    logger.info(
        "Optimization solved",
        extra={
            "event": "optimize",
            "status": mapped.value,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return result


def _rejection_reason(action: Action, budget: float, constrained: bool) -> str:
    """An honest, optimizer-grounded reason an action was not funded.

    Only the budget-exceeded case can be asserted with certainty. When
    business constraints are in play, an action may have been blocked by a
    constraint rather than out-competed on efficiency, and claiming
    otherwise would be fabricating an explanation.
    """
    if action.cost is not None and action.cost > budget:
        return f"Cost {action.cost} exceeds the entire budget of {budget}."
    if constrained:
        return (
            "Not selected. With business constraints active, this may be "
            "because a constraint excluded it or because the budget was better "
            "spent elsewhere; the solver does not attribute a single cause."
        )
    return (
        f"Not selected: at {action.reduction_per_cost} tCO2e per unit of cost, "
        "funding it would displace actions that deliver more total reduction "
        "within the same budget."
    )


def _ortools_version() -> str | None:
    try:
        import ortools

        return getattr(ortools, "__version__", None)
    except Exception:  # pragma: no cover - version is metadata only
        return None
