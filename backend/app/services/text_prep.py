"""Prompt compression for extracted documents (optimisation 2).

Docling's Markdown is faithful but wasteful for an LLM: table cells padded with long runs of spaces, separator rows
of dashes, column headers that repeat the course title in every cell, page headers/footers repeated on every page,
and image placeholders. `compress` removes all of that without dropping any content, and `split_courses` cuts the
document into a head (programme, PLOs) plus one chunk per course, so each piece can be extracted on its own.
"""
from __future__ import annotations

import html
import re
from collections import Counter

RX_SEPARATOR = re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")
RX_COURSE_HEAD = re.compile(r"^\s*(?:#+\s*|\|\s*)?(?:course\s*:\s*)?([A-Z]{2,6}[-\s]?\d{2,4}[A-Z]?)\s*[:\-–—]\s*[A-Za-z]")
RX_CODE = re.compile(r"\b[A-Z]{2,6}[-\s]?\d{2,4}[A-Z]?\b")


def _cells(line: str) -> list[str] | None:
    if "|" not in line:
        return None
    parts = [c.strip() for c in line.strip().strip("|").split("|")]
    return parts if len(parts) >= 2 else None


def _compress_header(cells: list[str]) -> str | None:
    """'X - CLO | X - Statement | Credit Hours: 3 (2+1) - PLO' -> '### X · Credit Hours: 3 (2+1)' + '| CLO | Statement | PLO |'."""
    split = [c.rsplit(" - ", 1) for c in cells]
    if sum(1 for s in split if len(s) == 2) < max(2, len(cells) - 1):
        return None
    prefixes, cols = [], []
    for s in split:
        if len(s) == 2:
            if s[0] not in prefixes:
                prefixes.append(s[0])
            cols.append(s[1])
        else:
            cols.append(s[0])
    return "### " + " · ".join(prefixes) + "\n| " + " | ".join(cols) + " |"


RX_PAGE = re.compile(r"\bpage\b|\bp\.\s*\d", re.I)


def compress(markdown: str) -> str:
    text = html.unescape(markdown).replace("<!-- image -->", "")
    lines = text.splitlines()
    # page headers / footers: lines that repeat (numbers ignored) 3+ times AND name a page ("... Page 3"). Repetition
    # alone is not enough: in plain PDF text, CLO rows such as "1" or "Cognitive, L3 - Applying PLO 2 30%" repeat
    # too, and dropping them lost the Bloom level, PLO and weight of every wrapped CLO.
    norm = [re.sub(r"\d+", "#", ln.strip()) for ln in lines]
    counts = Counter(n for n, ln in zip(norm, lines) if ln.strip() and "|" not in ln and len(ln) < 200)
    out: list[str] = []
    for ln, n in zip(lines, norm):
        if not ln.strip():
            if out and out[-1] != "":
                out.append("")
            continue
        if counts.get(n, 0) >= 3 and "|" not in ln and not RX_COURSE_HEAD.match(ln) and RX_PAGE.search(ln):
            continue
        if RX_SEPARATOR.match(ln) and "-" in ln:
            continue
        cells = _cells(ln)
        if cells is not None:
            header = _compress_header(cells)
            out.append(header if header else "| " + " | ".join(cells) + " |")
            continue
        out.append(re.sub(r"[ \t]+", " ", ln).strip())
    return "\n".join(out).strip()


def split_courses(text: str) -> tuple[str, list[str]]:
    """(head, [course chunk, ...]). A chunk starts at a line that names a course code and title. If fewer than two
    course headings are found, the whole text is returned as the head (callers then use one call)."""
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if RX_COURSE_HEAD.match(ln) and not ln.lstrip().startswith(("PLO", "CLO"))]
    if len(starts) < 2:
        return text, []
    head = "\n".join(lines[:starts[0]]).strip()
    chunks = ["\n".join(lines[a:b]).strip() for a, b in zip(starts, starts[1:] + [len(lines)])]
    return head, [c for c in chunks if c]


def group(chunks: list[str], parts: int) -> list[str]:
    """Join course chunks into at most `parts` roughly equal groups (one AI call each)."""
    if not chunks:
        return []
    parts = max(1, min(parts, len(chunks)))
    size = -(-len(chunks) // parts)
    return ["\n\n".join(chunks[i:i + size]) for i in range(0, len(chunks), size)]


def batches(chunks: list[str], max_courses: int = 5, max_chars: int = 4500) -> list[list[str]]:
    """Course chunks in small batches (one AI call each). Small calls finish quickly and well inside Gemini's
    deadline (a third of a 47-course document timed out), a failed batch costs little to retry, and progress
    can count up in small steps."""
    out: list[list[str]] = []
    cur: list[str] = []
    size = 0
    for c in chunks:
        if cur and (len(cur) >= max_courses or size + len(c) > max_chars):
            out.append(cur)
            cur, size = [], 0
        cur.append(c)
        size += len(c)
    if cur:
        out.append(cur)
    return out


def course_label(chunk: str) -> str:
    """'CS3683 Theory of Automata' from a chunk's heading line (for messages)."""
    first = chunk.splitlines()[0] if chunk else ""
    m = RX_COURSE_HEAD.match(first)
    if not m:
        return first.strip("#| ")[:60]
    rest = re.split(r"[•·|�–—]| Credit", first[m.end(1):], maxsplit=1)[0]
    return f"{m.group(1)} {rest.strip(' :-–—#')}".strip()[:80]


# ---- generic splitting (any layout) ------------------------------------------------------------------------
# Course headings like "CS3683: Theory of Automata" are only PREFERRED cut points: documents from other
# universities may have no codes in headings, "Course Title:" fields, tables, etc. Parts are cut by size; a part
# that starts in the middle of a course is told which course it continues, and the results are merged afterwards.
RX_SOFT_HEAD = re.compile(r"^\s*(?:#{1,6}\s|course\s*(?:code|title|name|no\.?)?\s*[:#-])", re.I)
RX_NUMBERED_HEAD = re.compile(r"^\s*\d+(?:\.\d+)*[.)]?\s+[A-Z]")


def _is_cut(line: str) -> bool:
    """A heading-like line (preferred place to cut). A numbered line counts only when it is short and not a
    sentence ("3. Domain Core Courses", not "3. Students can explain ...")."""
    if RX_COURSE_HEAD.match(line) or RX_SOFT_HEAD.match(line):
        return True
    t = line.strip()
    return bool(RX_NUMBERED_HEAD.match(t)) and len(t) <= 60 and not t.endswith((".", ";", ","))


def course_count_hint(text: str) -> int | None:
    """How many code-style course headings the text has (for progress only); None when there are fewer than 2."""
    n = sum(1 for ln in text.splitlines() if RX_COURSE_HEAD.match(ln) and not ln.lstrip().startswith(("PLO", "CLO")))
    return n if n >= 2 else None


def windows(text: str, max_chars: int = 4500) -> list[tuple[str, str | None]]:
    """[(part, context)] covering the whole text in order. Cuts at a heading-like line when one is reasonably placed,
    else at a blank line, else where the size limit is reached. `context` names the course a part continues (the
    last heading before it) or, without headings, quotes the text just before the part."""
    lines = text.splitlines()
    if not lines:
        return []
    heads = [i for i, ln in enumerate(lines) if _is_cut(ln)]
    out: list[tuple[str, str | None]] = []
    start, size = 0, 0
    i = 0
    while i < len(lines):
        size += len(lines[i]) + 1
        if size >= max_chars and i > start:
            lo = start + max(1, (i - start) * 3 // 10)
            cut = next((k for k in range(i, lo - 1, -1) if _is_cut(lines[k])), None)
            if cut is None:
                cut = next((k for k in range(i, lo - 1, -1) if not lines[k].strip()), i + 1)
            out.append(_part(lines, start, cut, heads))
            start, size, i = cut, 0, cut
            continue
        i += 1
    if start < len(lines):
        out.append(_part(lines, start, len(lines), heads))
    return [(p, c) for p, c in out if p.strip()]


def _part(lines: list[str], a: int, b: int, heads: list[int]) -> tuple[str, str | None]:
    """The part's text and, for every part but the first, what came just before it: the last one or two heading-like
    lines (e.g. "Course Title: X" + "Course Code: Y"), or the preceding text when there are no headings."""
    body = "\n".join(lines[a:b]).strip()
    if a == 0:
        return body, None
    before = [lines[i].strip() for i in heads if i < a][-2:]
    if before:
        return body, ("This part continues the document after these headings (for context only, do not extract "
                      f"them again): {' / '.join(before)}")
    tail = "\n".join(lines[max(0, a - 6):a]).strip()[-400:]
    return body, f"Text just before this part (for context only, do not extract from it): {tail}" if tail else None


def part_label(body: str, context: str | None) -> str:
    """A short name for a part in messages: its first heading, else the heading it continues."""
    first = next((ln for ln in body.splitlines() if ln.strip()), "")
    if _is_cut(first) or not context or "headings" not in context:
        return course_label(body)
    return "(continuing) " + context.split(": ", 1)[-1][-80:]


def _title_key(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def merge_courses(courses: list[dict]) -> list[dict]:
    """Courses from all parts, merged: the same course read from two parts (code, or title when there is no code)
    becomes one, its CLOs joined by CLO code. Two DIFFERENT courses that share a code (titles unlike each other)
    stay separate - the review flags the clash."""
    from difflib import SequenceMatcher

    def alike(a: str, b: str) -> bool:  # same title, one inside the other, or mostly the same words
        if not a or not b or a == b or a in b or b in a:
            return True
        wa, wb = set(a.split()), set(b.split())
        return len(wa & wb) / len(wa | wb) >= 0.6

    out: list[dict] = []
    for c in courses:
        code, title = (c.get("code") or "").strip().upper(), _title_key(c.get("title"))
        same = None
        for o in out:
            ocode, otitle = (o.get("code") or "").strip().upper(), _title_key(o.get("title"))
            if code and ocode and code == ocode and alike(title, otitle):
                same = o
                break
            if not code and title and otitle and (title == otitle or SequenceMatcher(None, title, otitle).ratio() >= 0.9):
                same = o
                break
        if same is None:
            out.append({**c, "clos": list(c.get("clos") or []), "units": list(c.get("units") or [])})
            continue
        for k, v in c.items():
            if k in ("clos", "units", "prerequisites"):
                continue
            if same.get(k) in (None, "", []) and v not in (None, "", []):
                same[k] = v
        same["prerequisites"] = list(dict.fromkeys((same.get("prerequisites") or []) + (c.get("prerequisites") or [])))
        by_code = {str(o.get("code")).upper(): o for o in same["clos"]}
        for o in c.get("clos") or []:
            k = str(o.get("code")).upper()
            mine = by_code.get(k)
            if mine is None:
                same["clos"].append(o)
                by_code[k] = o
            else:  # keep the fuller reading of the same CLO
                for f, v in o.items():
                    if mine.get(f) in (None, "", []) and v not in (None, "", []):
                        mine[f] = v
                if len(str(o.get("description") or "")) > len(str(mine.get("description") or "")):
                    mine["description"] = o["description"]
        seen_units = {u.get("number") for u in same["units"]}
        same["units"] += [u for u in c.get("units") or [] if u.get("number") not in seen_units]
    return out
