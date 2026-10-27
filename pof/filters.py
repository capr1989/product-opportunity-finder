"""Nested AND/OR hard filters with explicit handling of unknown metrics."""
import operator

OPS = {"eq": operator.eq, "ne": operator.ne, "gte": operator.ge, "lte": operator.le,
       "contains": lambda value, target: str(target).casefold() in str(value).casefold(),
       "not_contains": lambda value, target: str(target).casefold() not in str(value).casefold(),
       "in": lambda value, target: value in target}


def evaluate(row: dict, group: dict, depth: int = 0) -> tuple[bool, list[str]]:
    if depth > 8:
        raise ValueError("Filter nesting limit is 8")
    if "rules" in group:
        if group.get("logic", "AND") not in {"AND", "OR"} or len(group["rules"]) > 100:
            raise ValueError("Invalid filter group")
        results = [evaluate(row, rule, depth + 1) for rule in group["rules"]]
        if not results:
            return True, []
        fn = all if group.get("logic", "AND") == "AND" else any
        return fn(passed for passed, _ in results), [w for _, warnings in results for w in warnings]
    field, op, target = group["field"], group["op"], group["value"]
    if op not in OPS:
        raise ValueError("Unknown filter operator")
    value = row.get(field)
    if value is None or value == "" or value == "unknown":
        return group.get("unknown", "exclude") == "include", [f"Unknown {field}"]
    try:
        return OPS[op](value, target), []
    except TypeError:
        raise ValueError(f"Filter value has wrong type for {field}") from None
