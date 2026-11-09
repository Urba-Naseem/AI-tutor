"""Units for courses whose document lists none.

Many institutes publish CLOs without units. A single "Course content" unit makes every learning path one long
block, so the CLOs are grouped into a few units in teaching order (basics first) with short titles:
  1. the AI proposes the grouping (strict schema, temperature 0, several courses per call, calls in parallel),
  2. the plan is checked in code: every CLO exactly once, 2-5 units, no empty unit, a title for each,
  3. anything unusable (or no AI) falls back to an even split in document order.
The proposal is marked (`units_proposed`) and appears in Outcome review, where a person can change it.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

MIN_CLOS = 3          # a course with fewer CLOs keeps one unit
BATCH = 8             # courses per AI call

SYSTEM = ("You are a curriculum designer. You group a course's learning outcomes (CLOs) into teaching units. "
          "Order units from foundational to advanced; keep closely related CLOs together; never invent or drop CLOs.")


class PlannedUnit(BaseModel):
    title: str = Field(description="Short unit title (2-5 words), e.g. 'Control flow'.")
    clos: list[str] = Field(description="CLO codes in this unit, e.g. ['CLO1', 'CLO2'].")


class CoursePlan(BaseModel):
    code: str
    units: list[PlannedUnit]


class PlansOut(BaseModel):
    courses: list[CoursePlan]


def unit_count(n: int) -> int:
    return 2 if n <= 4 else 3 if n <= 7 else 4 if n <= 10 else 5


def _short_title(text: str) -> str:
    """'Explain how variables, data types and assignment work' -> 'Variables, data types and assignment'."""
    words = re.sub(r"^\s*(?:be able to\s+)?(?:\w+)\s+", "", text.strip(), count=1).split()  # drop the leading verb
    words = [w for w in words if w.lower() not in {"how", "the", "a", "an", "different", "various", "basic"}][:5]
    t = " ".join(words).strip(" ,.;:") or text[:40]
    return t[:1].upper() + t[1:]


def even_split(clos: list[dict]) -> list[dict]:
    """Fallback: CLOs in document order, split into unit_count(n) nearly equal units."""
    n, k = len(clos), unit_count(len(clos))
    size, extra = divmod(n, k)
    units, i = [], 0
    for u in range(k):
        part = clos[i:i + size + (1 if u < extra else 0)]
        i += len(part)
        if part:
            units.append({"number": len(units) + 1, "title": _short_title(part[0]["description"]), "clos": [c["code"] for c in part]})
    return units


def _valid(plan: CoursePlan | dict, clos: list[dict]) -> list[dict] | None:
    units = plan["units"] if isinstance(plan, dict) else [u.model_dump() for u in plan.units]
    codes = [c["code"] for c in clos]
    flat = [str(x).upper().replace(" ", "") for u in units for x in u.get("clos", [])]
    if sorted(flat) != sorted(codes) or not 2 <= len(units) <= 5 or any(not u.get("clos") or not str(u.get("title", "")).strip() for u in units):
        return None
    return [{"number": i + 1, "title": str(u["title"]).strip()[:80], "clos": [str(x).upper().replace(" ", "") for x in u["clos"]]} for i, u in enumerate(units)]


def _prompt(courses: list[dict]) -> str:
    blocks = []
    for c in courses:
        blocks.append(f"COURSE {c['code']}: {c['title']} - make {unit_count(len(c['clos']))} units (2-5 allowed)\n"
                      + "\n".join(f"{o['code']}: {o['description']}" for o in c["clos"]))
    return ("Group each course's CLOs into teaching units. Use every CLO code of a course exactly once.\n\n" + "\n\n".join(blocks))


def apply(course: dict, units: list[dict]) -> None:
    by_code = {u: x["number"] for x in units for u in x["clos"]}
    course["units"] = units
    for o in course["clos"]:
        o["unit"] = by_code.get(o["code"], 1)
    course["auto_unit"] = False
    course["units_proposed"] = True


def propose(db, user, parsed: dict, use_ai: bool = True) -> int:
    """Give unit-less courses (with at least MIN_CLOS CLOs) proposed units. Returns how many courses changed."""
    todo = [c for c in parsed.get("courses", []) if c.get("auto_unit") and len(c.get("clos", [])) >= MIN_CLOS]
    if not todo:
        return 0
    plans: dict[str, list[dict]] = {}
    if use_ai:
        from ..config import get_settings
        from .ai_gateway import AIUnavailable, call_json_many

        groups = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
        jobs = [{"purpose": "curriculum.units", "prompt": _prompt(g), "system": SYSTEM, "schema": PlansOut, "max_output_tokens": 8192,
                 "budget": get_settings().gemini_background_timeout_seconds} for g in groups]
        for g, res in zip(groups, call_json_many(db, user, jobs)):
            if isinstance(res, AIUnavailable):
                continue
            by_code = {str(p.get("code", "")).upper().replace(" ", ""): p for p in res.get("courses", [])}
            for c in g:
                p = by_code.get(c["code"])
                if p and (units := _valid(p, c["clos"])):
                    plans[c["code"]] = units
    for c in todo:
        apply(c, plans.get(c["code"]) or even_split(c["clos"]))
    return len(todo)
