from __future__ import annotations

from copy import deepcopy

from scripts._workflow_playbook import TRANSITIONS

_RESERVED_RUNTIME_KEYS = frozenset({"current_step", "next_step", "last_result"})


def _require_current_step(runtime: dict[str, object]) -> str:
    current_step = runtime.get("current_step")
    if not isinstance(current_step, str) or not current_step:
        raise ValueError(
            f"invalid current_step {current_step!r}: expected a non-empty string"
        )
    return current_step


def advance_step(runtime: dict[str, object], *, result: str) -> dict[str, object]:
    updated = deepcopy(runtime)
    current_step = _require_current_step(updated)
    try:
        next_step, side_effects = TRANSITIONS[(current_step, result)]
    except KeyError as error:
        raise ValueError(
            f"unknown transition for current_step={current_step!r}, result={result!r}"
        ) from error
    reserved_keys = sorted(set(side_effects) & _RESERVED_RUNTIME_KEYS)
    if reserved_keys:
        joined_keys = ", ".join(reserved_keys)
        raise ValueError(
            f"side_effects must not override reserved runtime keys: {joined_keys}"
        )
    updated["last_result"] = result
    updated["current_step"] = next_step
    updated["next_step"] = next_step
    updated.update(side_effects)
    return updated
