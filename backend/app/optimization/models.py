"""Optimization domain model.

Deliberately plain dataclasses with no FastAPI, SQLAlchemy or OR-Tools
imports, so the optimizer can be unit-tested in isolation and so the
mathematical model is readable on its own.

Mathematical model
------------------
Decision variable
    x_i  in  {0, 1, ..., capacity_i}     units of action i to fund

Objective
    maximize  SUM_i ( expected_reduction_i * x_i )

Subject to
    SUM_i ( cost_i * x_i )  <=  budget
    0 <= x_i <= capacity_i                     (capacity)
    x_i = 0                                    (unavailable actions)
    plus configured business constraints (see constraints.py)

Costs and reductions are floats (INR lakh, tCO2e). CP-SAT is an integer
solver, so both are scaled to integers by SCALE before being handed over.
"""
from dataclasses import dataclass, field
from enum import Enum

# Two decimal places of precision on cost and reduction.
SCALE = 100


class ParameterType(str, Enum):
    BINARY = "binary"      # fund it or don't
    INTEGER = "integer"    # fund N units, up to capacity


class SolverStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"


@dataclass(frozen=True)
class Action:
    """One candidate reduction action."""

    id: str
    name: str
    emission_source: str
    cost: float                      # INR lakh per unit
    expected_reduction: float        # tCO2e per unit
    maximum_capacity: int = 1
    availability: str = "available"
    parameter_type: ParameterType = ParameterType.BINARY
    is_demo_assumption: bool = True

    @property
    def selectable(self) -> bool:
        return (
            self.availability != "unavailable"
            and self.cost is not None
            and self.expected_reduction is not None
            and self.cost >= 0
            and self.expected_reduction > 0
        )

    @property
    def max_units(self) -> int:
        if self.parameter_type == ParameterType.BINARY:
            return 1
        return max(1, int(self.maximum_capacity))

    @property
    def reduction_per_cost(self) -> float | None:
        """tCO2e per INR lakh. Used for EXPLANATION only, never for the decision."""
        if not self.cost:
            return None
        return round(self.expected_reduction / self.cost, 4)


@dataclass(frozen=True)
class BusinessConstraint:
    """A configured business rule applied on top of the budget."""

    name: str
    constraint_type: str
    emission_source: str | None = None
    action_ids: tuple[str, ...] = ()
    numeric_value: float | None = None
    is_active: bool = True


@dataclass
class Allocation:
    """What the optimizer decided about one action, and why."""

    action_id: str
    action_name: str
    emission_source: str
    selected: bool
    units: int
    allocated_cost: float
    expected_reduction: float
    reduction_per_cost: float | None = None
    rejection_reason: str | None = None


@dataclass
class OptimizationResult:
    """The complete, reproducible outcome of one solve."""

    solver_status: SolverStatus
    allocations: list[Allocation] = field(default_factory=list)
    total_cost: float = 0.0
    expected_reduction: float = 0.0
    budget: float = 0.0
    unused_budget: float = 0.0
    budget_utilization: float = 0.0
    objective_value: float | None = None
    best_bound: float | None = None
    wall_time_seconds: float = 0.0
    solver: str = "ortools-cpsat"
    solver_version: str | None = None
    allocation_by_source: dict[str, float] = field(default_factory=dict)
    reduction_by_source: dict[str, float] = field(default_factory=dict)
    constraints_applied: list[str] = field(default_factory=list)
    message: str = ""

    @property
    def is_solved(self) -> bool:
        return self.solver_status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)

    @property
    def proven_optimal(self) -> bool:
        return self.solver_status == SolverStatus.OPTIMAL

    @property
    def selected_actions(self) -> list[Allocation]:
        return [a for a in self.allocations if a.selected]
