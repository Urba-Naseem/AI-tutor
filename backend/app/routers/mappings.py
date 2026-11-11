"""US-1.3 - Approve CLO-PLO mappings, validate coverage, and gate course activation."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.audit import record
from ..core.rbac import ensure_course_access, require
from ..db import get_db, utcnow
from ..models.mappings import CloPloMapping
from ..models.outcomes import CLO, PLO, Course, Program
from ..models.user import User
from ..services import ai_gateway, retrieval

router = APIRouter(prefix="/api", tags=["mappings"])


class MappingIn(BaseModel):
    clo_id: int
    plo_id: int
    strength: int = Field(2, ge=1, le=3)
    rationale: str | None = None


class DecideIn(BaseModel):
    decision: str  # approve | reject
    strength: int | None = Field(None, ge=1, le=3)
    note: str | None = None


def _course(db: Session, user: User, cid: int, write=False) -> Course:
    c = db.get(Course, cid)
    if not c:
        raise HTTPException(404, "Course not found")
    ensure_course_access(db, user, cid, write=write)
    return c


def _unlocked(c: Course):
    if c.status == "active":
        raise HTTPException(409, "Mappings of an active course are locked")
    if c.status not in ("approved",):
        raise HTTPException(409, f"Course is '{c.status}'; outcomes must be approved first")


def coverage(db: Session, c: Course) -> dict:
    clos = db.scalars(select(CLO).where(CLO.course_id == c.id).order_by(CLO.code)).all()
    plos = db.scalars(select(PLO).where(PLO.program_id == c.program_id).order_by(PLO.code)).all()
    maps = db.scalars(select(CloPloMapping).where(CloPloMapping.course_id == c.id)).all()
    approved = [m for m in maps if m.status == "approved"]
    unmapped = [o.code for o in clos if not any(m.clo_id == o.id for m in approved)]
    plo_cov = [{"plo_id": p.id, "code": p.code, "clos": sorted(o.code for o in clos for m in approved if m.clo_id == o.id and m.plo_id == p.id)}
               for p in plos]
    blockers = []
    if c.status != "approved" and c.status != "active":
        blockers.append(f"Course outcomes are '{c.status}', not approved")
    if unmapped:
        blockers.append(f"CLOs without an approved PLO mapping: {', '.join(unmapped)}")
    pending = [m for m in maps if m.status == "suggested"]
    return {
        "course": {"id": c.id, "code": c.code, "title": c.title, "status": c.status},
        "clos": [{"id": o.id, "code": o.code, "description": o.description} for o in clos],
        "plos": [{"id": p.id, "code": p.code, "description": p.description} for p in plos],
        "mappings": [{"id": m.id, "clo_id": m.clo_id, "plo_id": m.plo_id, "strength": m.strength, "origin": m.origin,
                      "status": m.status, "rationale": m.rationale} for m in maps],
        "unmapped_clos": unmapped,
        "plo_coverage": plo_cov,
        "uncovered_plos": [p["code"] for p in plo_cov if not p["clos"]],
        "pending_suggestions": len(pending),
        "complete": not unmapped and bool(clos),
        "can_activate": not blockers and c.status == "approved",
        "blockers": blockers,
    }


@router.get("/mappings/course/{cid}")
def get_mappings(cid: int, db: Session = Depends(get_db), user: User = Depends(require("mappings:manage", "reports:read"))):
    return coverage(db, _course(db, user, cid))


def _add(db, c, clo_id, plo_id, strength, origin, status, rationale, user, ai_call_id=None) -> CloPloMapping | None:
    existing = db.scalar(select(CloPloMapping).where(CloPloMapping.clo_id == clo_id, CloPloMapping.plo_id == plo_id))
    if existing:
        return None
    m = CloPloMapping(course_id=c.id, clo_id=clo_id, plo_id=plo_id, strength=strength, origin=origin, status=status,
                      rationale=rationale, created_by=user.id, ai_call_id=ai_call_id)
    if status == "approved":
        m.decided_by, m.decided_at = user.id, utcnow()
    db.add(m)
    db.flush()
    return m


@router.post("/mappings/course/{cid}/import-document")
def import_document(cid: int, db: Session = Depends(get_db), user: User = Depends(require("mappings:manage"))):
    """Turn mappings stated in the curriculum document into suggestions."""
    c = _course(db, user, cid, write=True)
    _unlocked(c)
    clos = {o.code: o.id for o in db.scalars(select(CLO).where(CLO.course_id == c.id))}
    plos = {p.code: p.id for p in db.scalars(select(PLO).where(PLO.program_id == c.program_id))}
    n = 0
    for pair in c.doc_mappings or []:
        if pair["clo"] in clos and pair["plo"] in plos:
            m = _add(db, c, clos[pair["clo"]], plos[pair["plo"]], 2, "document", "suggested", "Stated in the curriculum document", user)
            if m:
                n += 1
                ai_gateway.route_review(db, "mapping", "mapping", m.id, c.id, f"{c.code} {pair['clo']} -> {pair['plo']} (document)", user)
    record(db, user, "mappings.imported", "course", c.id, {"count": n}, course_id=c.id)
    db.commit()
    return coverage(db, c)


SUGGEST_SYSTEM = "You are a curriculum design expert. Map course learning outcomes to programme learning outcomes."


def _offline_suggestions(clos, plos):
    out = []
    for o in clos:
        ot = set(retrieval.tokens(o.description))
        scored = sorted(((len(ot & set(retrieval.tokens(p.description))) / (len(ot | set(retrieval.tokens(p.description))) or 1), p) for p in plos),
                        key=lambda x: -x[0])
        if scored and scored[0][0] > 0:
            s, p = scored[0]
            out.append({"clo": o.code, "plo": p.code, "strength": 3 if s > 0.2 else 2 if s > 0.1 else 1,
                        "rationale": f"Shared terms between the outcome statements (similarity {s:.2f})"})
    return out


@router.post("/mappings/course/{cid}/suggest")
def suggest(cid: int, db: Session = Depends(get_db), user: User = Depends(require("mappings:manage"))):
    """AI suggestions (Gemini, offline fallback). Suggestions are routed for review, never auto-approved."""
    c = _course(db, user, cid, write=True)
    _unlocked(c)
    clos = db.scalars(select(CLO).where(CLO.course_id == c.id).order_by(CLO.code)).all()
    plos = db.scalars(select(PLO).where(PLO.program_id == c.program_id).order_by(PLO.code)).all()
    # programme PLOs first: identical for every course of the programme, so repeated calls share a prompt prefix
    prompt = ("PLOs:\n" + "\n".join(f"{p.code}: {p.description}" for p in plos) +
              f"\n\nCLOs of {c.code} {c.title}:\n" + "\n".join(f"{o.code}: {o.description}" for o in clos) +
              "\n\nMap each CLO to the PLO(s) it contributes to (strength 1 weak - 3 strong, one-sentence rationale). "
              "Use only the codes listed above.")
    try:
        from ..services.schemas import MappingsOut

        data = ai_gateway.call_json(db, user, "mappings.suggest", prompt, SUGGEST_SYSTEM, course_id=c.id, schema=MappingsOut)
        items, origin = [x for x in ai_gateway.as_list(data, "mappings") if isinstance(x, dict)], "ai"
    except ai_gateway.AIUnavailable:
        items, origin = _offline_suggestions(clos, plos), "offline"
    call_id = ai_gateway.last_call_id(db)
    by_clo = {o.code: o.id for o in clos}
    by_plo = {p.code: p.id for p in plos}
    n = 0
    for it in items:
        clo, plo = str(it.get("clo", "")).upper().replace(" ", ""), str(it.get("plo", "")).upper().replace(" ", "")
        if clo in by_clo and plo in by_plo:
            strength = min(3, max(1, int(it.get("strength") or 2)))
            m = _add(db, c, by_clo[clo], by_plo[plo], strength, origin, "suggested", it.get("rationale"), user, call_id)
            if m:
                n += 1
                ai_gateway.route_review(db, "mapping", "mapping", m.id, c.id, f"{c.code} {clo} -> {plo} ({origin})", user, call_id)
    record(db, user, "mappings.suggested", "course", c.id, {"count": n, "origin": origin}, course_id=c.id)
    db.commit()
    return {**coverage(db, c), "suggested": n, "origin": origin}


@router.post("/mappings", status_code=201)
def add_manual(body: MappingIn, db: Session = Depends(get_db), user: User = Depends(require("mappings:manage"))):
    clo = db.get(CLO, body.clo_id)
    plo = db.get(PLO, body.plo_id)
    if not clo or not plo:
        raise HTTPException(404, "CLO or PLO not found")
    c = _course(db, user, clo.course_id, write=True)
    _unlocked(c)
    if plo.program_id != c.program_id:
        raise HTTPException(422, "PLO belongs to a different programme")
    m = _add(db, c, clo.id, plo.id, body.strength, "manual", "approved", body.rationale, user)
    if not m:
        raise HTTPException(409, "This mapping already exists")
    record(db, user, "mappings.approved", "mapping", m.id, {"clo": clo.code, "plo": plo.code, "origin": "manual"}, course_id=c.id)
    db.commit()
    return coverage(db, c)


@router.post("/mappings/{mid}/decide")
def decide(mid: int, body: DecideIn, db: Session = Depends(get_db), user: User = Depends(require("mappings:manage"))):
    m = db.get(CloPloMapping, mid)
    if not m:
        raise HTTPException(404, "Mapping not found")
    c = _course(db, user, m.course_id, write=True)
    _unlocked(c)
    if body.decision not in ("approve", "reject"):
        raise HTTPException(422, "decision must be approve or reject")
    m.status = "approved" if body.decision == "approve" else "rejected"
    if body.strength:
        m.strength = body.strength
    m.decided_by, m.decided_at = user.id, utcnow()
    ai_gateway.close_review(db, "mapping", m.id, m.status, user, body.note)
    record(db, user, f"mappings.{m.status}", "mapping", m.id, {"strength": m.strength, "origin": m.origin, "note": body.note}, course_id=c.id)
    db.commit()
    return coverage(db, c)


@router.post("/courses/{cid}/activate")
def activate(cid: int, db: Session = Depends(get_db), user: User = Depends(require("course:activate"))):
    c = _course(db, user, cid, write=True)
    cov = coverage(db, c)
    if c.status == "active":
        raise HTTPException(409, "Course is already active")
    if not cov["can_activate"]:
        record(db, user, "course.activation_blocked", "course", c.id, {"blockers": cov["blockers"]}, course_id=c.id)
        db.commit()
        raise HTTPException(409, {"message": "Course cannot be activated yet", "blockers": cov["blockers"]})
    c.status, c.activated_at, c.activated_by = "active", utcnow(), user.id
    for m in db.scalars(select(CloPloMapping).where(CloPloMapping.course_id == c.id, CloPloMapping.status == "suggested")):
        m.status = "rejected"
        ai_gateway.close_review(db, "mapping", m.id, "rejected", user, "Closed at activation")
    record(db, user, "course.activated", "course", c.id, {"uncovered_plos": cov["uncovered_plos"]}, course_id=c.id)
    db.commit()
    return coverage(db, c)


@router.get("/mappings/program/{pid}/rollup")
def program_rollup(pid: int, db: Session = Depends(get_db), _=Depends(require("reports:read", "mappings:manage"))):
    """Programme-level roll-up: which active/approved courses contribute to each PLO."""
    prog = db.get(Program, pid)
    if not prog:
        raise HTTPException(404, "Programme not found")
    plos = db.scalars(select(PLO).where(PLO.program_id == pid).order_by(PLO.code)).all()
    courses = {c.id: c for c in db.scalars(select(Course).where(Course.program_id == pid))}
    maps = db.scalars(select(CloPloMapping).where(CloPloMapping.status == "approved", CloPloMapping.course_id.in_(list(courses) or [0]))).all()
    clo_codes = {o.id: o.code for o in db.scalars(select(CLO).where(CLO.course_id.in_(list(courses) or [0])))}
    return [{"plo": p.code, "description": p.description,
             "contributions": [{"course": courses[m.course_id].code, "course_status": courses[m.course_id].status,
                                "clo": clo_codes.get(m.clo_id), "strength": m.strength} for m in maps if m.plo_id == p.id]}
            for p in plos]
