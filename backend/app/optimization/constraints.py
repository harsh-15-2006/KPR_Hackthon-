"""Business constraints applied to the CP-SAT model.

Each handler receives the model, the decision variables and the action
list, and adds constraints. Keeping them here means the optimizer stays
readable and new rules can be added without touching the solve loop.
"""
from collections.abc import Callable

from ortools.sat.python import cp_model

from app.optimization.models import SCALE, Action, BusinessConstraint


def _indices_for_source(actions: list[Action], source: str | None) -> list[int]:
    if not source:
        return list(range(len(actions)))
    return [i for i, a in enumerate(actions) if a.emission_source == source]


def _indices_for_ids(actions: list[Action], ids: tuple[str, ...]) -> list[int]:
    wanted = set(ids)
    return [i for i, a in enumerate(actions) if a.id in wanted]


def _num(c: BusinessConstraint, default: float) -> float:
    """Read numeric_value treating 0 as a REAL value, not as 'unset'.

    `c.numeric_value or default` was wrong: a configured limit of 0
    ("fund nothing in this source") silently became the default.
    """
    return default if c.numeric_value is None else c.numeric_value


def apply_max_actions_per_source(
    model: cp_model.CpModel, x: list, actions: list[Action], c: BusinessConstraint,
    selected: list | None = None,
) -> str:
    """At most N DISTINCT actions funded within one emission source.

    Counts distinct actions via the boolean selection indicators, not units:
    one action funded 3 times is still one action.
    """
    idx = _indices_for_source(actions, c.emission_source)
    n = int(_num(c, 1))
    if not idx:
        return f"{c.name}: no actions in source '{c.emission_source}' (no-op)"
    flags = selected if selected is not None else x
    if n == 1:
        model.add_at_most_one([flags[i] for i in idx])
    else:
        model.add(sum(flags[i] for i in idx) <= n)
    return f"{c.name}: at most {n} distinct action(s) in '{c.emission_source}'"


def apply_mutually_exclusive(
    model: cp_model.CpModel, x: list, actions: list[Action], c: BusinessConstraint,
    selected: list | None = None,
) -> str:
    """At most one of a named set of actions may be funded."""
    idx = _indices_for_ids(actions, c.action_ids)
    if len(idx) < 2:
        return f"{c.name}: fewer than 2 matching actions (no-op)"
    flags = selected if selected is not None else x
    model.add_at_most_one([flags[i] for i in idx])
    return f"{c.name}: at most 1 of {len(idx)} mutually exclusive actions"


def apply_required_action(
    model: cp_model.CpModel, x: list, actions: list[Action], c: BusinessConstraint,
    selected: list | None = None,
) -> str:
    """Named actions MUST be funded.

    If a required action is NOT among the selectable actions, that is a
    genuine contradiction - the model is made INFEASIBLE rather than
    silently downgrading a mandatory rule to a no-op.
    """
    wanted = set(c.action_ids)
    idx = _indices_for_ids(actions, c.action_ids)
    found_ids = {actions[i].id for i in idx}
    missing = wanted - found_ids

    for i in idx:
        model.add(x[i] >= 1)

    if missing:
        # Force infeasibility explicitly: a mandatory action that cannot be
        # funded must surface as INFEASIBLE, never be quietly ignored.
        impossible = model.new_bool_var(f"required_missing_{abs(hash(c.name)) % 10**6}")
        model.add(impossible == 1)
        model.add(impossible == 0)
        return (
            f"{c.name}: REQUIRED action(s) {sorted(missing)} are not available - "
            "model forced INFEASIBLE rather than ignoring a mandatory constraint"
        )
    return f"{c.name}: {len(idx)} action(s) forced to be funded"


def apply_max_total_actions(
    model: cp_model.CpModel, x: list, actions: list[Action], c: BusinessConstraint,
    selected: list | None = None,
) -> str:
    """Cap the total number of DISTINCT funded actions across all sources."""
    n = int(_num(c, len(actions)))
    flags = selected if selected is not None else x
    model.add(sum(flags) <= n)
    return f"{c.name}: at most {n} distinct action(s) in total"


def apply_max_spend_per_source(
    model: cp_model.CpModel, x: list, actions: list[Action], c: BusinessConstraint,
    selected: list | None = None,
) -> str:
    """Cap the money spent within one emission source.

    Costs are scaled with ceil (matching the optimizer) so the cap can never
    be exceeded in real money by sub-paisa rounding.
    """
    import math

    idx = _indices_for_source(actions, c.emission_source)
    if not idx or c.numeric_value is None:
        return f"{c.name}: not applicable (no-op)"
    cap = int(math.floor(c.numeric_value * SCALE))
    model.add(
        sum(x[i] * int(math.ceil(actions[i].cost * SCALE)) for i in idx) <= cap
    )
    return f"{c.name}: spend in '{c.emission_source}' capped at {c.numeric_value}"


HANDLERS: dict[str, Callable] = {
    "max_actions_per_source": apply_max_actions_per_source,
    "mutually_exclusive": apply_mutually_exclusive,
    "required_action": apply_required_action,
    "max_total_actions": apply_max_total_actions,
    "max_spend_per_source": apply_max_spend_per_source,
}


def apply_all(
    model: cp_model.CpModel,
    x: list,
    actions: list[Action],
    constraints: list[BusinessConstraint],
    selected: list | None = None,
) -> list[str]:
    """Apply every active constraint. Returns human-readable descriptions.

    `selected` holds one BoolVar per action, true iff that action is funded
    at all. CP-SAT's add_at_most_one accepts ONLY boolean literals, so an
    IntVar with capacity > 1 raises TypeError if passed directly - which is
    why counting constraints use these indicators.

    'budget' is handled directly by the optimizer, not here.
    An unknown constraint type is recorded rather than silently ignored.
    """
    applied: list[str] = []
    for c in constraints:
        if not c.is_active or c.constraint_type == "budget":
            continue
        handler = HANDLERS.get(c.constraint_type)
        if handler is None:
            applied.append(f"{c.name}: UNKNOWN constraint type '{c.constraint_type}' - NOT applied")
            continue
        applied.append(handler(model, x, actions, c, selected))
    return applied
