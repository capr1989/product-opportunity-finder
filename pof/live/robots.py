"""Conservative robots policy matching including wildcard and end-of-path rules."""
import re
from urllib.parse import urlsplit


def allowed(document: str, url: str, agent="ProductOpportunityFinder") -> bool:
    groups = []
    agents, rules = [], []
    for raw in document.splitlines() + ["User-agent: __end__"]:
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
        elif field in {"allow", "disallow"} and agents and value:
            rules.append((field, value))
    # A document without interpretable user-agent groups grants no permission.
    if not groups and not agents:
        return False
    matches = []
    for names, entries in groups:
        lengths = [0 if name == "*" else len(name) for name in names if name == "*" or name in agent.lower()]
        if lengths:
            matches.append((max(lengths), entries))
    if not matches:
        # Standard empty Disallow means no restrictions, if a matching group exists.
        return any(name == "*" or name in agent.lower() for name in agents)
    specificity = max(size for size, _ in matches)
    parts = urlsplit(url)
    path = parts.path + ("?" + parts.query if parts.query else "")
    matching_rules = []
    for size, entries in matches:
        if size != specificity:
            continue
        for action, pattern in entries:
            expression = "^" + re.escape(pattern.rstrip("$")).replace(r"\*", ".*")
            if pattern.endswith("$"):
                expression += "$"
            if re.search(expression, path):
                matching_rules.append((len(pattern.replace("*", "").rstrip("$")), action == "allow"))
    return max(matching_rules)[1] if matching_rules else True
