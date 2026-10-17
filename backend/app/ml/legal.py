"""Violation types and legal norms from seed/legal_rules.json (single source for the analyzer, seed and UI)."""
import functools
import json
import os

SEED = os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed", "legal_rules.json")


@functools.lru_cache(maxsize=1)
def load() -> dict:
    with open(SEED, encoding="utf-8") as f:
        data = json.load(f)
    data["rules_by_id"] = {r["id"]: r for r in data["rules"]}
    data["types_by_code"] = {t["code"]: t for t in data["types"]}
    return data


def type_name(code: str) -> str:
    t = load()["types_by_code"].get(code)
    return t["name_ru"] if t else code


def rule_for(code: str, rule_id: str | None = None) -> dict:
    d = load()
    rid = rule_id or d["types_by_code"].get(code, {}).get("rule_id") or "NBRK231_GENERAL"
    return d["rules_by_id"][rid]


def norm_text(code: str, rule_id: str | None = None) -> str:
    """'Норма: <документ>, <пункт>.' Unverified clauses are marked, a missing clause is never invented."""
    d = load()
    rule = rule_for(code, rule_id)
    doc = d["documents"][rule["document"]]["short"]
    parts = [doc]
    if rule.get("clause"):
        parts.append(rule["clause"])
    if rule.get("suffix"):
        parts.append(rule["suffix"])
    text = "Норма: " + ", ".join(parts)
    if not rule.get("verified"):
        text += " (требует проверки)"
    return text + "."
