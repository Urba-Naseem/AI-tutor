"""US-1.1 / US-1.2 - Turn extracted curriculum text into a structured outline.

Primary parser: Gemini (JSON output). Fallback: a deterministic rule-based
parser for documents that follow the institutional template (see
backend/sample_data/). Both outputs go through `check_structure`, which flags
missing or ambiguous items for the reviewer.
"""
from __future__ import annotations

import html
import re

SCHEMA_HINT = """{
  "program": {"code": "BSCS", "name": "Bachelor of Science in Computer Science"},
  "plos": [{"code": "PLO1", "description": "..."}],
  "courses": [
    {
      "code": "CS101", "title": "...", "credits": 3, "semester": 1, "prerequisites": ["CS100"],
      "description": "...",
      "units": [{"number": 1, "title": "...", "clos": ["CLO1", "CLO2"]}],
      "clos": [{"code": "CLO1", "description": "...", "unit": 1, "bloom": "apply"}],
      "clo_plo": [{"clo": "CLO1", "plo": "PLO1"}]
    }
  ]
}"""

SYSTEM = (
    "You extract academic curriculum structure from documents. Copy wording faithfully. "
    "Never invent courses, outcomes or codes that are not in the text. Use null for anything missing."
)


def llm_prompt(markdown: str) -> str:
    return (
        "Extract the programme, programme learning outcomes (PLOs), courses, units and course learning "
        "outcomes (CLOs) from the curriculum document below. Return ONLY JSON shaped like this example:\n"
        f"{SCHEMA_HINT}\n"
        "Rules: CLO codes are per course (CLO1, CLO2...). 'unit' is the unit number a CLO belongs to, or null. "
        "List clo_plo pairs only if the document states them. Credits are numbers or null. "
        "'semester' is the semester number in which the programme's study plan / roadmap places the course "
        "(1, 2, 3...), or null if the document has no roadmap. With two semesters per year, Year 1 Fall = 1, "
        "Year 1 Spring = 2, Year 2 Fall = 3, and so on.\n\n"
        "DOCUMENT:\n" + markdown[:200_000]
    )


def norm_code(s: str | None) -> str | None:
    if not s:
        return None
    return re.sub(r"[\s_-]+", "", s.strip()).upper()


# ---- deterministic fallback --------------------------------------------
RX_PROGRAM = re.compile(r"Program(?:me)?\s*:\s*([A-Za-z0-9-]+)\s*[-–—:]\s*(.+)", re.I)
RX_COURSE = re.compile(r"Course\s*:\s*([A-Za-z]{2,6}[-\s]?\d{2,4}[A-Za-z]?)\s*[-–—:]\s*(.+)", re.I)
RX_PLO = re.compile(r"\b(PLO[-\s]?\d+)\s*[:.)–—-]\s*(.+)", re.I)
RX_CLO = re.compile(r"\b(CLO[-\s]?\d+)\s*[:.)–—-]\s*(.+?)(?:\s*\(\s*Unit\s*(\d+)\s*\))?\s*$", re.I)
RX_MAP = re.compile(r"\b(CLO[-\s]?\d+)\s*(?:->|→|=>|maps to)\s*((?:PLO[-\s]?\d+[\s,;and]*)+)", re.I)
RX_UNIT = re.compile(r"\bUnit\s+(\d+)\s*[:.–—-]\s*(.+)", re.I)
RX_CREDITS = re.compile(r"Credits?(?:\s*hours?)?\s*:\s*(\d+)", re.I)
RX_PREREQ = re.compile(r"Pre-?requisites?\s*:\s*(.+)", re.I)
RX_DESC = re.compile(r"Description\s*:\s*(.+)", re.I)
RX_CODE = re.compile(r"[A-Za-z]{2,6}[-\s]?\d{2,4}[A-Za-z]?")
# Semester roadmap: "Semester: 2" inside a course, "Semester 1: CS101, MATH110" lists, or headings
# "Semester 3" / "Year 2 - Fall" placed before the courses of that semester.
RX_SEM_FIELD = re.compile(r"^Semester\s*:\s*(\d{1,2})\b", re.I)
RX_SEM_LIST = re.compile(r"^(?:Semester|Sem\.?|Term)\s*(\d{1,2})\s*[:–—-]\s*(.+)$", re.I)
RX_SEM_HEAD = re.compile(r"^(?:Semester|Sem\.?|Term)\s*(\d{1,2})\s*$", re.I)
RX_YEAR_HEAD = re.compile(r"^Year\s*(\d)\s*[,:–—-]?\s*(Fall|Autumn|Spring|First|Second|1st|2nd)\b", re.I)


def year_term_to_semester(year: int, term: str) -> int:
    return (year - 1) * 2 + (1 if term.lower() in ("fall", "autumn", "first", "1st") else 2)


def _clean(line: str) -> str:
    line = re.sub(r"^\s*(?:[#>*|-]+|\d+[.)])\s*", "", line)
    return line.replace("**", "").replace("|", " ").strip()


# PDF extraction often merges list items into one paragraph: split before each keyword.
RX_SPLIT = re.compile(
    r"\s+(?=(?:PLO[-\s]?\d+|CLO[-\s]?\d+)\s*[:.)]|Unit\s+\d+\s*:|Credits?\s*:|Semester\s*\d{0,2}\s*:|Pre-?requisites?\s*:|Description\s*:"
    r"|CLO[-\s]?\d+\s*(?:->|→|=>|maps to))",
    re.I,
)


def _lines(markdown: str):
    for raw in html.unescape(markdown).splitlines():
        yield from RX_SPLIT.split(raw)


def heuristic_parse(markdown: str) -> dict:
    out: dict = {"program": {"code": None, "name": None}, "plos": [], "courses": []}
    course = None
    roadmap: dict[str, int] = {}  # course code -> semester, from "Semester 1: CS101, MATH110" lists
    heading_sem = None  # semester of a "Semester 3" / "Year 2 - Fall" heading above the courses
    for raw in _lines(markdown):
        line = _clean(raw)
        if not line:
            continue
        if m := RX_PROGRAM.search(line):
            out["program"] = {"code": m.group(1).strip().upper(), "name": m.group(2).strip()}
            continue
        if m := RX_SEM_FIELD.search(line):
            if course is not None:
                course["semester"] = int(m.group(1))
            continue
        if m := RX_SEM_LIST.search(line):
            for code in RX_CODE.findall(m.group(2)):
                roadmap[norm_code(code)] = int(m.group(1))
            continue
        if m := RX_SEM_HEAD.search(line):
            heading_sem, course = int(m.group(1)), None
            continue
        if m := RX_YEAR_HEAD.search(line):
            heading_sem, course = year_term_to_semester(int(m.group(1)), m.group(2)), None
            continue
        if m := RX_COURSE.search(line):
            course = {"code": norm_code(m.group(1)), "title": m.group(2).strip(), "credits": None, "prerequisites": [],
                      "description": None, "units": [], "clos": [], "clo_plo": [], "semester": heading_sem}
            out["courses"].append(course)
            continue
        if m := RX_MAP.search(line):
            if course is not None:
                for plo in re.findall(r"PLO[-\s]?\d+", m.group(2), re.I):
                    course["clo_plo"].append({"clo": norm_code(m.group(1)), "plo": norm_code(plo)})
            continue
        if course is None:
            if m := RX_PLO.search(line):
                out["plos"].append({"code": norm_code(m.group(1)), "description": m.group(2).strip()})
            continue
        if m := RX_CREDITS.search(line):
            course["credits"] = int(m.group(1))
        elif m := RX_PREREQ.search(line):
            val = m.group(1)
            course["prerequisites"] = [] if re.match(r"\s*(none|nil|-)", val, re.I) else [norm_code(c) for c in RX_CODE.findall(val)]
        elif m := RX_DESC.search(line):
            course["description"] = m.group(1).strip()
        elif m := RX_UNIT.search(line):
            title = m.group(2)
            clos = []
            parts = re.split(r"\s+[^\w\s(]{1,2}\s+(?=CLO)", title, maxsplit=1)
            if len(parts) == 2:
                title, clos = parts[0], [norm_code(c) for c in re.findall(r"CLO[-\s]?\d+", parts[1], re.I)]
            course["units"].append({"number": int(m.group(1)), "title": title.strip(), "clos": clos})
        elif m := RX_CLO.search(line):
            course["clos"].append({"code": norm_code(m.group(1)), "description": m.group(2).strip(),
                                   "unit": int(m.group(3)) if m.group(3) else None, "bloom": None})
    for c in out["courses"]:  # an explicit roadmap list wins over headings
        if c["code"] in roadmap:
            c["semester"] = roadmap[c["code"]]
    return out


def _semester(v) -> int | None:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 20 else None


def _weight(v) -> float | None:
    try:
        x = float(str(v).strip().rstrip("%")) if v is not None and str(v).strip() else None
    except ValueError:
        return None
    return x if x is not None and 0 <= x <= 100 else None


def normalise(parsed: dict) -> dict:
    """Coerce LLM / heuristic output into the canonical shape."""
    prog = parsed.get("program") or {}
    out = {
        "program": {"code": (prog.get("code") or "").strip().upper() or None, "name": prog.get("name")},
        "plos": [{"code": norm_code(p.get("code")), "description": (p.get("description") or "").strip()}
                 for p in parsed.get("plos") or []],
        "courses": [],
    }
    for c in parsed.get("courses") or []:
        clos = [{"code": norm_code(x.get("code")), "description": (x.get("description") or "").strip(),
                 "unit": x.get("unit"), "bloom": bloom_level(x.get("bloom")),
                 "weight": _weight(x.get("weight"))} for x in c.get("clos") or []]
        units = []
        for i, u in enumerate(c.get("units") or [], start=1):
            units.append({"number": u.get("number") or i, "title": (u.get("title") or "").strip(),
                          "clos": [norm_code(x) for x in u.get("clos") or []]})
        # link CLOs to units in both directions
        for u in units:
            for code in u["clos"]:
                for clo in clos:
                    if clo["code"] == code and not clo["unit"]:
                        clo["unit"] = u["number"]
        for clo in clos:
            for u in units:
                if clo["unit"] == u["number"] and clo["code"] not in u["clos"]:
                    u["clos"].append(clo["code"])
        # Many curricula list CLOs without units: group them in one unit instead of blocking approval
        auto_unit = c.get("auto_unit", False)
        if clos and not units:
            units = [{"number": 1, "title": "Course content", "clos": [x["code"] for x in clos]}]
            for x in clos:
                x["unit"] = 1
            auto_unit = True
        out["courses"].append({
            "auto_unit": auto_unit,
            "units_proposed": bool(c.get("units_proposed")),
            "code": norm_code(c.get("code")), "title": (c.get("title") or "").strip(), "credits": c.get("credits"),
            "semester": _semester(c.get("semester")),
            # a prerequisite must look like a course code (letters and a digit): stray words or letters the
            # extraction picked up (e.g. "S" from "Pre-requisite(s)") are dropped
            "prerequisites": [norm_code(p) for p in c.get("prerequisites") or []
                              if p and re.fullmatch(r"(?=.*[A-Z])(?=.*\d)[A-Z0-9]{3,12}", norm_code(str(p)) or "")],
            "description": c.get("description"), "units": units, "clos": clos,
            "clo_plo": [{"clo": norm_code(m.get("clo")), "plo": norm_code(m.get("plo"))} for m in c.get("clo_plo") or []
                        if m.get("clo") and m.get("plo")],
        })
    return out


def check_structure(p: dict, source: str | None = None, ai_wording: set[str] | None = None) -> list[dict]:
    """Flag missing / ambiguous items. level: error blocks approval, warning is advisory.
    With `source` (the uploaded document's text) the guardrails also check extracted wording against it;
    `ai_wording` limits that check to CLOs still worded as the AI extracted them (a person's edit is trusted)."""
    w: list[dict] = guard(p, source, ai_wording)

    def add(level, path, msg):
        w.append({"level": level, "path": path, "message": msg})

    if not p["program"].get("code"):
        add("error", "program", "Programme code is missing")
    if not p["program"].get("name"):
        add("error", "program", "Programme name is missing")
    if not p["plos"]:
        add("error", "plos", "No programme learning outcomes (PLOs) found")
    seen_plo = set()
    for plo in p["plos"]:
        if plo["code"] in seen_plo:
            add("error", f"plo:{plo['code']}", f"Duplicate PLO code {plo['code']}")
        seen_plo.add(plo["code"])
        if len(plo["description"]) < 15:
            add("warning", f"plo:{plo['code']}", f"{plo['code']} description is missing or too short to be unambiguous")
    if not p["courses"]:
        add("error", "courses", "No courses found")
    codes = {c["code"] for c in p["courses"]}
    titles: dict[str, list[str]] = {}
    for c in p["courses"]:
        if c["code"]:
            titles.setdefault(c["code"], []).append(c["title"])
    for code, names in titles.items():  # the document itself uses one code for different courses
        if len(names) > 1:  # an error: enrolment and prerequisites go by code, so a person must decide
            add("error", f"course:{code}/duplicate",
                f"Course code {code} is used for {len(names)} courses ({'; '.join(names)}). Give each course its own "
                "code (edit the code in the course header)")
    with_sem = [c for c in p["courses"] if c.get("semester")]
    all_auto = bool(p["courses"]) and all(c.get("auto_unit") for c in p["courses"])
    proposed = [c["code"] for c in p["courses"] if c.get("units_proposed")]
    if proposed:  # the document listed no units, so the AI grouped the CLOs (or they were split evenly)
        add("info", "units/proposed", f"The document lists no units, so units were proposed for {len(proposed)} course(s): "
                                      "CLOs grouped in teaching order, basics first. Check or change them in Outcome review.")
    if all_auto:  # a CLO/PLO document without units: nothing to fix, so one note instead of a warning per course
        add("info", "units", "The document lists no units, so each course's CLOs are kept together in one unit "
                             "'Course content' (learning paths then follow CLO order). You can split a course into "
                             "units here if you want.")
    no_sem = [c["code"] for c in p["courses"] if with_sem and not c.get("semester")]
    if no_sem:  # e.g. elective pools: open in any semester
        add("info", "roadmap/unplaced", f"{len(no_sem)} course(s) are not in the semester roadmap, so students can take "
                                        f"them in any semester (usually electives): {', '.join(no_sem)}")
    if p["courses"] and not with_sem:
        add("info", "roadmap", "No semester roadmap found: enrolment will not be limited by semester. "
                               "Add a semester to each course in the review if the programme has a study plan")
    for c in p["courses"]:
        cp = f"course:{c['code']}"
        if not c["code"]:
            add("error", "course:?", f"A course has no code ('{c['title']}')")
        if not c["title"]:
            add("error", cp, f"Course {c['code']} has no title")
        if not c["credits"]:
            add("warning", cp, f"Course {c['code']} has no credit value")

        if not c["clos"]:
            add("error", cp, f"Course {c['code']} has no CLOs")
        if not c["units"]:
            add("error", cp, f"Course {c['code']} has no units")
        elif c.get("auto_unit") and not all_auto:  # only some courses lack units: those are worth a look
            add("warning", cp, f"The document lists no units for {c['code']}: all its CLOs were placed in one unit "
                               f"'Course content'. Split them into units in the review if needed")
        for pre in c["prerequisites"]:
            if pre not in codes:
                add("warning", cp, f"Prerequisite {pre} of {c['code']} is not in this curriculum")
        seen = set()
        unit_nums = {u["number"] for u in c["units"]}
        for clo in c["clos"]:
            if clo["code"] in seen:
                add("error", f"{cp}/clo:{clo['code']}", f"Duplicate {clo['code']} in {c['code']}")
            seen.add(clo["code"])
            if len(clo["description"]) < 15:
                add("warning", f"{cp}/clo:{clo['code']}", f"{c['code']} {clo['code']} description is missing or ambiguous")
            if not clo["unit"] or clo["unit"] not in unit_nums:
                add("error", f"{cp}/clo:{clo['code']}", f"{c['code']} {clo['code']} is not assigned to a unit")
        for u in c["units"]:
            if not u["clos"]:
                add("warning", f"{cp}/unit:{u['number']}", f"{c['code']} unit {u['number']} has no CLOs")
            if not u["title"]:
                add("error", f"{cp}/unit:{u['number']}", f"{c['code']} unit {u['number']} has no title")
    return w


# ---- AI extraction: upfront PLOs, compressed text, courses in parallel chunks (optimisations 1-3) -----------
RULES = (
    "Rules: copy statements word for word; never invent courses, outcomes or codes. CLO codes are per course: write "
    "CLO1, CLO2... (a CLO numbered 3 is CLO3). 'unit' is the unit number a CLO belongs to, or null. 'plos' lists the "
    "PLO codes a CLO maps to only if the document states them. 'weight' is the CLO weight in percent if stated. "
    "'bloom' is the taxonomy level as written. Credits: total hours as a number (4 (3+1) -> 4). 'semester' is the "
    "roadmap semester if stated (Year 1 Fall = 1, Year 1 Spring = 2, Year 2 Fall = 3 ...), else null."
)
RX_PLO_CODE = re.compile(r"\bPLO[-\s]?(\d{1,2})\b", re.I)


def plo_codes(text: str) -> list[str]:
    """PLO codes found in the text without any AI call (upfront static extraction)."""
    seen = []
    for n in RX_PLO_CODE.findall(text):
        c = f"PLO{int(n)}"
        if c not in seen:
            seen.append(c)
    return seen


def head_prompt(head: str) -> str:
    return ("Extract the programme (code and name) and ALL programme learning outcomes (PLOs) from this part of a "
            f"curriculum document. {RULES}\n\nDOCUMENT PART:\n{head}")


def courses_prompt(plos: list[str], chunk: str, context: str | None = None) -> str:
    # static block first (same for every part of this document), the varying part last
    return (f"PROGRAMME PLO CODES: {', '.join(plos) or 'none stated'}\n{RULES}\n\n"
            "Extract EVERY course in this part of the curriculum document with its CLOs. A course may begin before "
            "this part or continue after it: extract what this part contains, under that course's code and title. "
            "Skip text that is not a course (programme overview, PLO lists, study plans)."
            + (f"\n\nCONTEXT: {context}" if context else "") + f"\n\nDOCUMENT PART:\n{chunk}")


def full_prompt(text: str) -> str:
    return ("Extract the programme, PLOs, courses, units and CLOs from this curriculum document. "
            f"{RULES}\n\nDOCUMENT:\n{text[:200_000]}")


def from_schema(data: dict) -> dict:
    """CurriculumOut-shaped data -> the parser's canonical input (CLO 'plos' -> clo_plo pairs)."""
    courses = []
    for c in data.get("courses") or []:
        clos, pairs = [], []
        for o in c.get("clos") or []:
            code = o.get("code") or ""
            if re.fullmatch(r"\s*\d+\s*", code):
                code = f"CLO{int(code)}"
            clos.append({**o, "code": code})
            pairs += [{"clo": code, "plo": p} for p in o.get("plos") or []]
        courses.append({**c, "clos": clos, "clo_plo": pairs})
    return {"program": data.get("program") or {}, "plos": data.get("plos") or [], "courses": courses}


BLOOM = (("remember", ("remember", "recall", "l1")), ("understand", ("understand", "l2")), ("apply", ("apply", "l3")),
         ("analyze", ("analy", "l4")), ("evaluate", ("evaluat", "l5")), ("create", ("creat", "l6")))


def bloom_level(raw: str | None) -> str | None:
    """'Cognitive, L3 - Applying' -> 'apply'. Affective / psychomotor levels keep their own word."""
    if not raw:
        return None
    s = raw.lower()
    if "affective" in s or "psychomotor" in s:
        m = re.search(r"[-–—]\s*([a-z]+)\s*$", s)
        return m.group(1) if m else s.strip()[:20]
    for level, keys in BLOOM:
        if any(k in s.replace(" ", "") if k.startswith("l") and k[1:].isdigit() else k in s for k in keys):
            return level
    return s.strip()[:20]


def _tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", html.unescape(s).lower())


def found_in_source(statement: str, source_tokens: set[str], min_share: float = 0.85) -> bool:
    """Guardrail: most words of an extracted statement must occur in the source document."""
    words = [w for w in _tokens(statement) if len(w) > 2]
    if not words:
        return True
    return sum(1 for w in words if w in source_tokens) / len(words) >= min_share


def guard(p: dict, source: str | None, ai_wording: set[str] | None = None) -> list[dict]:
    """Client-side guardrails on an extracted outline (optimisation 4). Returns review issues."""
    w: list[dict] = []
    plo_set = {x["code"] for x in p["plos"]}
    src = set(_tokens(source)) if source else None
    for c in p["courses"]:
        cp = f"course:{c['code']}"
        weights = [o.get("weight") for o in c["clos"]]
        if any(x is not None for x in weights):
            total = sum(x or 0 for x in weights)
            if any(x is None for x in weights) or abs(total - 100) > 1:
                w.append({"level": "warning", "path": f"{cp}/weights",
                          "message": f"{c['code']} CLO weights total {total:g}%, not 100% - check the document or the extraction"})
        for o in c["clos"]:
            if ai_wording is not None and o["description"] not in ai_wording:
                continue  # edited by a person in review: not the AI's wording any more
            if src is not None and not found_in_source(o["description"], src):
                w.append({"level": "warning", "path": f"{cp}/clo:{o['code']}/source",
                          "message": f"{c['code']} {o['code']} is not worded like anything in the uploaded document - "
                                     "the AI may have invented or reworded it"})
        for pair in c.get("clo_plo", []):
            if plo_set and pair["plo"] not in plo_set:
                w.append({"level": "warning", "path": f"{cp}/map:{pair['clo']}",
                          "message": f"{c['code']} {pair['clo']} maps to {pair['plo']}, which is not a PLO of this programme"})
    return w
