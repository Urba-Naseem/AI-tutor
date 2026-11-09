"""US-1.2 - Review and approve parsed outcomes (courses, units, CLOs, PLOs)."""
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.audit import record
from ..core.rbac import accessible_course_ids, ensure_course_access, require
from ..db import get_db, utcnow
from ..models.curriculum import CurriculumVersion
from ..models.outcomes import CLO, PLO, Course, Program, ReviewAck, Unit
from ..models.user import User
from ..services.curriculum_parser import check_structure, norm_code, normalise

router = APIRouter(prefix="/api/outcomes", tags=["outcomes"])


# ---- helpers -----------------------------------------------------------
def _get(db: Session, model, obj_id: int):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


def _version(db: Session, vid: int) -> CurriculumVersion:
    v = db.get(CurriculumVersion, vid)
    if not v:
        raise HTTPException(404, "Curriculum version not found")
    return v


def _editable(db: Session, vid: int):
    v = _version(db, vid)
    if v.status != "in_review":
        raise HTTPException(409, f"Version is '{v.status}'; only versions in review can be edited")
    return v


def _program(db: Session, vid: int) -> Program:
    p = db.scalar(select(Program).where(Program.curriculum_version_id == vid))
    if not p:
        raise HTTPException(404, "Review has not been started for this version")
    return p


def snapshot(db: Session, vid: int) -> dict:
    """Current reviewed structure in the canonical parser shape (for validation)."""
    prog = _program(db, vid)
    out = {"program": {"code": prog.code, "name": prog.name},
           "plos": [{"code": p.code, "description": p.description} for p in db.scalars(select(PLO).where(PLO.program_id == prog.id).order_by(PLO.code))],
           "courses": []}
    for c in db.scalars(select(Course).where(Course.curriculum_version_id == vid).order_by(Course.code)):
        units = db.scalars(select(Unit).where(Unit.course_id == c.id).order_by(Unit.number)).all()
        num = {u.id: u.number for u in units}
        clos = db.scalars(select(CLO).where(CLO.course_id == c.id).order_by(CLO.code)).all()
        out["courses"].append({
            "auto_unit": len(units) == 1 and units[0].title == "Course content",
            "code": c.code, "title": c.title, "credits": c.credits, "semester": c.semester, "prerequisites": c.prerequisites,
            "units": [{"number": u.number, "title": u.title, "clos": [o.code for o in clos if o.unit_id == u.id]} for u in units],
            "clos": [{"code": o.code, "description": o.description, "unit": num.get(o.unit_id), "weight": o.weight} for o in clos],
        })
    return out


def issue_key(issue: dict) -> str:
    return hashlib.sha1(f"{issue['path']}|{issue['message']}".encode()).hexdigest()[:16]


def issues_with_acks(db: Session, vid: int) -> list[dict]:
    acks = {a.issue_key: a for a in db.scalars(select(ReviewAck).where(ReviewAck.curriculum_version_id == vid))}
    out = []
    v = db.get(CurriculumVersion, vid)
    ai_wording = {o.get("description") for c in normalise((v.parsed if v else None) or {}).get("courses", [])
                  for o in c.get("clos", [])}
    seen: set[str] = set()
    for i in check_structure(snapshot(db, vid), v.extracted_markdown if v else None, ai_wording):
        k = issue_key(i)
        if k in seen:  # identical issue twice (e.g. two courses sharing one code): list it once, acknowledge it once
            continue
        seen.add(k)
        a = acks.get(k)
        out.append({**i, "key": k, "acknowledged": bool(a), "ack_note": a.note if a else None})
    return out


def course_tree(db: Session, c: Course) -> dict:
    units = db.scalars(select(Unit).where(Unit.course_id == c.id).order_by(Unit.number)).all()
    clos = db.scalars(select(CLO).where(CLO.course_id == c.id).order_by(CLO.code)).all()
    return {
        "id": c.id, "code": c.code, "title": c.title, "credits": c.credits, "semester": c.semester, "description": c.description,
        "prerequisites": c.prerequisites, "status": c.status, "program_id": c.program_id,
        "curriculum_version_id": c.curriculum_version_id,
        "units": [{"id": u.id, "number": u.number, "title": u.title} for u in units],
        "clos": [{"id": o.id, "code": o.code, "description": o.description, "unit_id": o.unit_id, "bloom": o.bloom, "weight": o.weight} for o in clos],
    }


def _scoped_course(db: Session, user: User, course_id: int, write=False) -> Course:
    c = db.get(Course, course_id)
    if not c:
        raise HTTPException(404, "Course not found")
    ensure_course_access(db, user, c.id, write=write)
    return c


# ---- start review: materialise the parsed outline ----------------------
@router.post("/versions/{vid}/start-review")
def start_review(vid: int, db: Session = Depends(get_db), user: User = Depends(require("curriculum:manage"))):
    v = _version(db, vid)
    if v.status != "preview":
        raise HTTPException(409, f"Version is already '{v.status}'")
    other = db.scalar(select(CurriculumVersion).where(CurriculumVersion.program_key == v.program_key,
                                                      CurriculumVersion.status == "in_review"))
    if other:
        raise HTTPException(409, f"Version {other.version_no} of {v.program_key} is already in review")
    p = normalise(v.parsed)  # re-apply current normalisation (e.g. versions uploaded before a parser fix)
    v.parsed = p
    prog = Program(curriculum_version_id=v.id, code=p["program"].get("code") or v.program_key,
                   name=p["program"].get("name") or v.title)
    db.add(prog)
    db.flush()
    for plo in p["plos"]:
        db.add(PLO(program_id=prog.id, code=plo["code"] or "PLO?", description=plo["description"]))
    for i, c in enumerate(p["courses"]):
        course = Course(program_id=prog.id, curriculum_version_id=v.id, code=c["code"] or f"UNKNOWN{i + 1}",
                        title=c["title"], credits=c["credits"], semester=c.get("semester"), description=c.get("description"),
                        prerequisites=c["prerequisites"], doc_mappings=c.get("clo_plo", []), status="draft")
        db.add(course)
        db.flush()
        unit_ids = {}
        for u in c["units"]:
            unit = Unit(course_id=course.id, number=u["number"], title=u["title"])
            db.add(unit)
            db.flush()
            unit_ids[u["number"]] = unit.id
        seen = set()
        for o in c["clos"]:
            code = o["code"] or "CLO?"
            while code in seen:
                code += "-DUP"
            seen.add(code)
            db.add(CLO(course_id=course.id, unit_id=unit_ids.get(o["unit"]), code=code, description=o["description"], bloom=o.get("bloom"), weight=o.get("weight")))
    v.status = "in_review"
    db.flush()
    from ..services import roadmap as roadmap_svc
    roadmap_svc.apply(db, v)  # semesters from the version's roadmap, if one was uploaded
    record(db, user, "outcomes.review_started", "curriculum_version", v.id, {"program_key": v.program_key})
    db.commit()
    return review(vid, db, user)


@router.get("/versions/{vid}")
def review(vid: int, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review"))):
    v = _version(db, vid)
    prog = _program(db, vid)
    courses = db.scalars(select(Course).where(Course.curriculum_version_id == vid).order_by(Course.code)).all()
    allowed = accessible_course_ids(db, user)
    issues = issues_with_acks(db, vid)
    return {
        "version": {"id": v.id, "program_key": v.program_key, "version_no": v.version_no, "status": v.status,
                    "approved_at": v.approved_at, "approved_by": v.approved_by},
        "program": {"id": prog.id, "code": prog.code, "name": prog.name},
        "plos": [{"id": p.id, "code": p.code, "description": p.description}
                 for p in db.scalars(select(PLO).where(PLO.program_id == prog.id).order_by(PLO.code))],
        "courses": [course_tree(db, c) for c in courses if allowed is None or c.id in allowed],
        "issues": issues,
        "can_approve": v.status == "in_review" and all(i["level"] != "error" and (i["level"] != "warning" or i["acknowledged"]) for i in issues),
    }


@router.get("/in-review")
def in_review(db: Session = Depends(get_db), _=Depends(require("outcomes:review"))):
    vs = db.scalars(select(CurriculumVersion).where(CurriculumVersion.status.in_(["in_review", "approved"]))
                    .order_by(CurriculumVersion.uploaded_at.desc()))
    return [{"id": v.id, "program_key": v.program_key, "version_no": v.version_no, "status": v.status, "title": v.title} for v in vs]


# ---- editing ------------------------------------------------------------
class ProgramIn(BaseModel):
    code: str | None = None
    name: str | None = None


class PloIn(BaseModel):
    code: str | None = None
    description: str | None = None


class CourseIn(BaseModel):
    code: str | None = None
    title: str | None = None
    credits: int | None = None
    semester: int | None = Field(None, ge=1, le=20)  # roadmap semester; null = not limited
    description: str | None = None
    prerequisites: list[str] | None = None


class UnitIn(BaseModel):
    number: int | None = None
    title: str | None = None


class CloIn(BaseModel):
    code: str | None = None
    description: str | None = None
    unit_id: int | None = None
    bloom: str | None = None
    weight: float | None = Field(None, ge=0, le=100)  # percent of the course, as the document states it


def _apply(obj, body: BaseModel, code_fields=("code",)) -> dict:
    changes = {}
    for k, val in body.model_dump(exclude_unset=True).items():
        if k in code_fields and isinstance(val, str):
            val = norm_code(val)
        if k == "prerequisites" and val is not None:
            val = [norm_code(x) for x in val if x and x.strip()]
        before = getattr(obj, k)
        if before != val:
            changes[k] = {"before": before, "after": val}
            setattr(obj, k, val)
    return changes


def _save(db, user, action, entity, obj_id, changes, course_id=None):
    record(db, user, action, entity, obj_id, changes, course_id=course_id)
    try:
        db.commit()
    except Exception as e:  # unique constraint etc.
        db.rollback()
        raise HTTPException(409, f"Could not save: {str(e.orig) if hasattr(e, 'orig') else e}")


@router.patch("/programs/{pid}")
def edit_program(pid: int, body: ProgramIn, db: Session = Depends(get_db), user: User = Depends(require("curriculum:manage"))):
    p = _get(db, Program, pid)
    _editable(db, p.curriculum_version_id)
    ch = _apply(p, body, code_fields=())
    _save(db, user, "outcomes.program.updated", "program", p.id, ch)
    return {"ok": True}


@router.post("/programs/{pid}/plos", status_code=201)
def add_plo(pid: int, body: PloIn, db: Session = Depends(get_db), user: User = Depends(require("curriculum:manage"))):
    p = _get(db, Program, pid)
    _editable(db, p.curriculum_version_id)
    plo = PLO(program_id=p.id, code=norm_code(body.code) or "PLO?", description=body.description or "")
    db.add(plo)
    db.flush()
    _save(db, user, "outcomes.plo.created", "plo", plo.id, body.model_dump())
    return {"id": plo.id}


@router.patch("/plos/{plo_id}")
def edit_plo(plo_id: int, body: PloIn, db: Session = Depends(get_db), user: User = Depends(require("curriculum:manage"))):
    plo = _get(db, PLO, plo_id)
    _editable(db, db.get(Program, plo.program_id).curriculum_version_id)
    _save(db, user, "outcomes.plo.updated", "plo", plo.id, _apply(plo, body))
    return {"ok": True}


@router.delete("/plos/{plo_id}")
def delete_plo(plo_id: int, db: Session = Depends(get_db), user: User = Depends(require("curriculum:manage"))):
    plo = _get(db, PLO, plo_id)
    _editable(db, db.get(Program, plo.program_id).curriculum_version_id)
    snap = {"code": plo.code, "description": plo.description}
    db.delete(plo)
    _save(db, user, "outcomes.plo.deleted", "plo", plo_id, snap)
    return {"ok": True}


@router.post("/versions/{vid}/courses", status_code=201)
def add_course(vid: int, body: CourseIn, db: Session = Depends(get_db), user: User = Depends(require("curriculum:manage"))):
    _editable(db, vid)
    prog = _program(db, vid)
    c = Course(program_id=prog.id, curriculum_version_id=vid, code=norm_code(body.code) or "NEW", title=body.title or "",
               credits=body.credits, semester=body.semester, description=body.description,
               prerequisites=[norm_code(x) for x in body.prerequisites or []], status="draft")
    db.add(c)
    db.flush()
    _save(db, user, "outcomes.course.created", "course", c.id, body.model_dump(), c.id)
    return {"id": c.id}


@router.patch("/courses/{cid}")
def edit_course(cid: int, body: CourseIn, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review"))):
    c = _scoped_course(db, user, cid, write=True)
    _editable(db, c.curriculum_version_id)
    _save(db, user, "outcomes.course.updated", "course", c.id, _apply(c, body), c.id)
    return course_tree(db, c)


@router.delete("/courses/{cid}")
def delete_course(cid: int, db: Session = Depends(get_db), user: User = Depends(require("curriculum:manage"))):
    c = _scoped_course(db, user, cid, write=True)
    _editable(db, c.curriculum_version_id)
    db.delete(c)
    _save(db, user, "outcomes.course.deleted", "course", cid, {"code": c.code}, cid)
    return {"ok": True}


@router.post("/courses/{cid}/units", status_code=201)
def add_unit(cid: int, body: UnitIn, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review"))):
    c = _scoped_course(db, user, cid, write=True)
    _editable(db, c.curriculum_version_id)
    nums = [u.number for u in db.scalars(select(Unit).where(Unit.course_id == c.id))]
    u = Unit(course_id=c.id, number=body.number or (max(nums, default=0) + 1), title=body.title or "")
    db.add(u)
    db.flush()
    _save(db, user, "outcomes.unit.created", "unit", u.id, body.model_dump(), c.id)
    return {"id": u.id}


@router.patch("/units/{uid}")
def edit_unit(uid: int, body: UnitIn, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review"))):
    u = _get(db, Unit, uid)
    c = _scoped_course(db, user, u.course_id, write=True)
    _editable(db, c.curriculum_version_id)
    _save(db, user, "outcomes.unit.updated", "unit", u.id, _apply(u, body, code_fields=()), c.id)
    return {"ok": True}


@router.delete("/units/{uid}")
def delete_unit(uid: int, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review"))):
    u = _get(db, Unit, uid)
    c = _scoped_course(db, user, u.course_id, write=True)
    _editable(db, c.curriculum_version_id)
    for o in db.scalars(select(CLO).where(CLO.unit_id == u.id)):
        o.unit_id = None
    db.delete(u)
    _save(db, user, "outcomes.unit.deleted", "unit", uid, {"number": u.number, "title": u.title}, c.id)
    return {"ok": True}


@router.post("/courses/{cid}/clos", status_code=201)
def add_clo(cid: int, body: CloIn, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review"))):
    c = _scoped_course(db, user, cid, write=True)
    _editable(db, c.curriculum_version_id)
    n = len(db.scalars(select(CLO).where(CLO.course_id == c.id)).all())
    o = CLO(course_id=c.id, code=norm_code(body.code) or f"CLO{n + 1}", description=body.description or "",
            unit_id=body.unit_id, bloom=body.bloom)
    db.add(o)
    db.flush()
    _save(db, user, "outcomes.clo.created", "clo", o.id, body.model_dump(), c.id)
    return {"id": o.id}


@router.patch("/clos/{oid}")
def edit_clo(oid: int, body: CloIn, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review"))):
    o = _get(db, CLO, oid)
    c = _scoped_course(db, user, o.course_id, write=True)
    _editable(db, c.curriculum_version_id)
    if body.unit_id is not None:
        u = db.get(Unit, body.unit_id)
        if not u or u.course_id != c.id:
            raise HTTPException(422, "Unit does not belong to this course")
    _save(db, user, "outcomes.clo.updated", "clo", o.id, _apply(o, body), c.id)
    return {"ok": True}


@router.delete("/clos/{oid}")
def delete_clo(oid: int, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review"))):
    o = _get(db, CLO, oid)
    c = _scoped_course(db, user, o.course_id, write=True)
    _editable(db, c.curriculum_version_id)
    db.delete(o)
    _save(db, user, "outcomes.clo.deleted", "clo", oid, {"code": o.code, "description": o.description}, c.id)
    return {"ok": True}


# ---- acknowledging warnings and approval --------------------------------
class AckIn(BaseModel):
    issue_key: str
    note: str


@router.post("/versions/{vid}/ack")
def acknowledge(vid: int, body: AckIn, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review"))):
    _editable(db, vid)
    issue = next((i for i in issues_with_acks(db, vid) if i["key"] == body.issue_key), None)
    if not issue:
        raise HTTPException(404, "Issue not found (it may already be fixed)")
    if issue["level"] == "error":
        raise HTTPException(409, "Errors must be corrected, not acknowledged")
    if len(body.note.strip()) < 5:
        raise HTTPException(422, "Give a short reason for accepting this warning")
    db.add(ReviewAck(curriculum_version_id=vid, issue_key=body.issue_key, message=issue["message"], note=body.note, by=user.id))
    _save(db, user, "outcomes.warning_acknowledged", "curriculum_version", vid, {"message": issue["message"], "note": body.note})
    return {"ok": True}


class AckAllIn(BaseModel):
    note: str


@router.post("/versions/{vid}/ack-all")
def acknowledge_all(vid: int, body: AckAllIn, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review"))):
    """Accept every open warning with one recorded reason (errors still have to be fixed)."""
    _editable(db, vid)
    if len(body.note.strip()) < 5:
        raise HTTPException(422, "Give a short reason for accepting the warnings")
    open_w = [i for i in issues_with_acks(db, vid) if i["level"] == "warning" and not i["acknowledged"]]
    for i in open_w:
        db.add(ReviewAck(curriculum_version_id=vid, issue_key=i["key"], message=i["message"], note=body.note, by=user.id))
    _save(db, user, "outcomes.warnings_acknowledged", "curriculum_version", vid, {"count": len(open_w), "note": body.note})
    return {"acknowledged": len(open_w)}


@router.post("/versions/{vid}/approve")
def approve(vid: int, db: Session = Depends(get_db), user: User = Depends(require("curriculum:manage"))):
    """Approve the reviewed outcomes. With automation on, linking CLOs to PLOs, activating the courses and drafting
    their questions then continue in the background - the same steps an upload runs when nothing needs a person."""
    from ..services import automation

    approve_version(vid, db, user)
    if automation.enabled():
        automation.continue_after_approval(vid, user.id)
    return review(vid, db, user)


def approve_version(vid: int, db: Session, user) -> None:
    v = _editable(db, vid)
    issues = issues_with_acks(db, vid)
    errors = [i["message"] for i in issues if i["level"] == "error"]
    open_warnings = [i["message"] for i in issues if i["level"] == "warning" and not i["acknowledged"]]
    if errors or open_warnings:
        raise HTTPException(409, {"message": "Resolve all errors and acknowledge or fix all warnings before approval",
                                  "errors": errors, "warnings": open_warnings})
    # earlier approved versions of the programme are superseded (active courses keep running)
    for old in db.scalars(select(CurriculumVersion).where(CurriculumVersion.program_key == v.program_key,
                                                          CurriculumVersion.status == "approved")):
        old.status = "superseded"
        for c in db.scalars(select(Course).where(Course.curriculum_version_id == old.id, Course.status != "active")):
            c.status = "superseded"
    for c in db.scalars(select(Course).where(Course.curriculum_version_id == vid)):
        c.status = "approved"
    v.status = "approved"
    v.approved_by = user.id
    v.approved_at = utcnow()
    record(db, user, "outcomes.approved", "curriculum_version", v.id, {"program_key": v.program_key, "version_no": v.version_no})
    db.commit()


# ---- read access used by later features ---------------------------------
@router.get("/courses")
def list_courses(status: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review", "reports:read", "learn"))):
    q = select(Course).order_by(Course.code)
    if status:
        q = q.where(Course.status == status)
    allowed = accessible_course_ids(db, user)
    codes = {p.id: p.code for p in db.scalars(select(Program))}  # department of each course (BSCS, BSSE, ...)
    return [{"id": c.id, "code": c.code, "title": c.title, "status": c.status, "credits": c.credits,
             "prerequisites": c.prerequisites, "curriculum_version_id": c.curriculum_version_id, "program": codes.get(c.program_id),
             "semester": c.semester}
            for c in db.scalars(q) if allowed is None or c.id in allowed]


@router.get("/courses/{cid}")
def get_course(cid: int, db: Session = Depends(get_db), user: User = Depends(require("outcomes:review", "reports:read", "learn"))):
    c = _scoped_course(db, user, cid)
    t = course_tree(db, c)
    t["plos"] = [{"id": p.id, "code": p.code, "description": p.description}
                 for p in db.scalars(select(PLO).where(PLO.program_id == c.program_id).order_by(PLO.code))]
    return t
