"""NB-1 - Configure academic offerings and course assignments to faculty.

Covers terms, sections (capacity), instructor assignment, prerequisite
maintenance, and the mid-semester hand-over when an instructor leaves:
the old assignment is ended with a reason (kept as history) and the new
instructor takes over the course scope - pending reviews and escalations are
routed by *current* assignment, so they move automatically.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..core.audit import record
from ..core.rbac import register_scope, require
from ..db import get_db
from ..models.offerings import InstructorAssignment, Section, Term
from ..models.outcomes import Course
from ..models.user import User
from ..services import departments
from ..services.curriculum_parser import norm_code

router = APIRouter(prefix="/api/offerings", tags=["offerings"])


def active_assignments(db: Session, today: date | None = None):
    today = today or date.today()
    return select(InstructorAssignment).where(
        InstructorAssignment.start_date <= today,
        or_(InstructorAssignment.end_date.is_(None), InstructorAssignment.end_date > today),
    )


@register_scope("instructor")
def _instructor_courses(db: Session, user: User) -> set[int]:
    q = active_assignments(db).where(InstructorAssignment.instructor_id == user.id)
    section_ids = [a.section_id for a in db.scalars(q)]
    if not section_ids:
        return set()
    return {s.course_id for s in db.scalars(select(Section).where(Section.id.in_(section_ids)))}


def course_instructors(db: Session, course_id: int) -> list[User]:
    """Instructors currently responsible for a course (used to route reviews/escalations)."""
    sids = [s.id for s in db.scalars(select(Section).where(Section.course_id == course_id))]
    if not sids:
        return []
    ids = {a.instructor_id for a in db.scalars(active_assignments(db).where(InstructorAssignment.section_id.in_(sids)))}
    return list(db.scalars(select(User).where(User.id.in_(ids)))) if ids else []


# ---- schemas -------------------------------------------------------------
class TermIn(BaseModel):
    name: str
    start_date: date
    end_date: date


class SectionIn(BaseModel):
    course_id: int
    term_id: int
    code: str
    capacity: int


class SemesterSectionsIn(BaseModel):
    program_code: str
    semester: int
    term_id: int
    code: str = "A"
    capacity: int = 40


class SectionPatch(BaseModel):
    capacity: int | None = None
    status: str | None = None


class AssignIn(BaseModel):
    instructor_id: int
    role: str = "primary"
    start_date: date | None = None


class ReassignIn(BaseModel):
    new_instructor_id: int
    reason: str
    effective_date: date | None = None


class EndIn(BaseModel):
    reason: str
    end_date: date | None = None


class PrereqIn(BaseModel):
    prerequisites: list[str]
    reason: str


def _assignment_out(db, a: InstructorAssignment) -> dict:
    u = db.get(User, a.instructor_id)
    return {"id": a.id, "instructor_id": a.instructor_id, "instructor_name": u.full_name if u else None, "role": a.role,
            "start_date": a.start_date, "end_date": a.end_date, "end_reason": a.end_reason,
            "active": a.end_date is None or a.end_date > date.today()}


def section_out(db: Session, s: Section) -> dict:
    from ..models.offerings import Term

    c = db.get(Course, s.course_id)
    t = db.get(Term, s.term_id)
    hist = db.scalars(select(InstructorAssignment).where(InstructorAssignment.section_id == s.id)
                      .order_by(InstructorAssignment.start_date, InstructorAssignment.id)).all()
    enrolled = 0
    try:
        from ..models.enrollment import Enrollment

        enrolled = len(db.scalars(select(Enrollment).where(Enrollment.section_id == s.id, Enrollment.status == "enrolled")).all())
    except ImportError:
        pass
    current = [_assignment_out(db, a) for a in hist if a.end_date is None or a.end_date > date.today()]
    return {"id": s.id, "code": s.code, "capacity": s.capacity, "status": s.status, "enrolled": enrolled,
            "course": {"id": c.id, "code": c.code, "title": c.title, "status": c.status, "program": departments.course_program(db, c)},
            "term": {"id": t.id, "name": t.name, "start_date": t.start_date, "end_date": t.end_date},
            "instructors": current, "history": [_assignment_out(db, a) for a in hist],
            "needs_instructor": not any(a["role"] == "primary" for a in current)}


def _instructor(db, uid) -> User:
    u = db.get(User, uid)
    if not u or u.role != "instructor" or not u.is_active:
        raise HTTPException(422, "Choose an active instructor account")
    return u


# ---- terms -----------------------------------------------------------------
@router.get("/terms")
def list_terms(db: Session = Depends(get_db), _=Depends(require("offerings:manage", "learn", "console:view"))):
    return [{"id": t.id, "name": t.name, "start_date": t.start_date, "end_date": t.end_date}
            for t in db.scalars(select(Term).order_by(Term.start_date.desc()))]


@router.post("/terms", status_code=201)
def create_term(body: TermIn, db: Session = Depends(get_db), user: User = Depends(require("offerings:manage"))):
    if body.end_date <= body.start_date:
        raise HTTPException(422, "Term must end after it starts")
    if db.scalar(select(Term).where(Term.name == body.name)):
        raise HTTPException(409, "A term with this name exists")
    t = Term(**body.model_dump())
    db.add(t)
    db.flush()
    record(db, user, "offerings.term_created", "term", t.id, body.model_dump())
    db.commit()
    return {"id": t.id}


# ---- sections --------------------------------------------------------------
@router.get("/sections")
def list_sections(course_id: int | None = None, term_id: int | None = None, db: Session = Depends(get_db),
                  _=Depends(require("offerings:manage"))):
    q = select(Section).order_by(Section.id)
    if course_id:
        q = q.where(Section.course_id == course_id)
    if term_id:
        q = q.where(Section.term_id == term_id)
    return [section_out(db, s) for s in db.scalars(q)]


@router.get("/my-sections")
def my_sections(db: Session = Depends(get_db), user: User = Depends(require("console:view"))):
    q = active_assignments(db).where(InstructorAssignment.instructor_id == user.id)
    sids = [a.section_id for a in db.scalars(q)]
    return [section_out(db, s) for s in db.scalars(select(Section).where(Section.id.in_(sids)))] if sids else []


@router.post("/sections", status_code=201)
def create_section(body: SectionIn, db: Session = Depends(get_db), user: User = Depends(require("offerings:manage"))):
    c = db.get(Course, body.course_id)
    if not c or c.status not in ("approved", "active"):
        raise HTTPException(422, "Sections can only be offered for approved courses")
    if not db.get(Term, body.term_id):
        raise HTTPException(422, "Unknown term")
    if body.capacity < 1:
        raise HTTPException(422, "Capacity must be at least 1")
    if db.scalar(select(Section).where(Section.course_id == c.id, Section.term_id == body.term_id, Section.code == body.code)):
        raise HTTPException(409, "Section code already used for this course and term")
    s = Section(**body.model_dump())
    db.add(s)
    db.flush()
    record(db, user, "offerings.section_created", "section", s.id, body.model_dump(), course_id=c.id)
    db.commit()
    return section_out(db, s)


@router.post("/sections/semester", status_code=201)
def create_semester_sections(body: SemesterSectionsIn, db: Session = Depends(get_db), user: User = Depends(require("offerings:manage"))):
    """One section (same code and capacity) for every approved course of a department's semester in a term.
    Courses that already have a section with that code in the term are skipped. Instructors are assigned afterwards."""
    from ..models.outcomes import Program

    if not db.get(Term, body.term_id):
        raise HTTPException(422, "Unknown term")
    if body.capacity < 1:
        raise HTTPException(422, "Capacity must be at least 1")
    if not body.code.strip():
        raise HTTPException(422, "Give a section code")
    courses = db.scalars(select(Course).join(Program, Program.id == Course.program_id)
                         .where(Program.code == body.program_code, Course.semester == body.semester,
                                Course.status.in_(("approved", "active"))).order_by(Course.code)).all()
    if not courses:
        raise HTTPException(422, f"No approved {body.program_code} courses in semester {body.semester}")
    created, skipped = [], []
    for c in courses:
        if db.scalar(select(Section).where(Section.course_id == c.id, Section.term_id == body.term_id, Section.code == body.code.strip())):
            skipped.append(c.code)
            continue
        s = Section(course_id=c.id, term_id=body.term_id, code=body.code.strip(), capacity=body.capacity)
        db.add(s)
        db.flush()
        record(db, user, "offerings.section_created", "section", s.id,
               {"course_id": c.id, "term_id": body.term_id, "code": s.code, "capacity": s.capacity, "bulk_semester": body.semester},
               course_id=c.id)
        created.append(s)
    db.commit()
    return {"created": [section_out(db, s) for s in created], "skipped": skipped}


@router.patch("/sections/{sid}")
def patch_section(sid: int, body: SectionPatch, db: Session = Depends(get_db), user: User = Depends(require("offerings:manage"))):
    s = db.get(Section, sid)
    if not s:
        raise HTTPException(404, "Section not found")
    out = section_out(db, s)
    if body.capacity is not None:
        if body.capacity < out["enrolled"]:
            raise HTTPException(409, f"{out['enrolled']} students are enrolled; capacity cannot go below that")
        s.capacity = body.capacity
    if body.status is not None:
        if body.status not in ("open", "closed"):
            raise HTTPException(422, "Status must be open or closed")
        s.status = body.status
    record(db, user, "offerings.section_updated", "section", s.id, body.model_dump(exclude_unset=True), course_id=s.course_id)
    db.commit()
    return section_out(db, s)


# ---- instructor assignment ------------------------------------------------
@router.post("/sections/{sid}/assign")
def assign(sid: int, body: AssignIn, db: Session = Depends(get_db), user: User = Depends(require("offerings:manage"))):
    s = db.get(Section, sid)
    if not s:
        raise HTTPException(404, "Section not found")
    _instructor(db, body.instructor_id)
    if body.role not in ("primary", "assistant"):
        raise HTTPException(422, "Role must be primary or assistant")
    current = db.scalars(active_assignments(db).where(InstructorAssignment.section_id == sid)).all()
    if body.role == "primary" and any(a.role == "primary" for a in current):
        raise HTTPException(409, "Section already has a primary instructor - use reassign to hand over")
    if any(a.instructor_id == body.instructor_id for a in current):
        raise HTTPException(409, "Instructor is already assigned to this section")
    a = InstructorAssignment(section_id=sid, instructor_id=body.instructor_id, role=body.role,
                             start_date=body.start_date or date.today(), assigned_by=user.id)
    db.add(a)
    db.flush()
    record(db, user, "offerings.instructor_assigned", "section", sid,
           {"instructor_id": body.instructor_id, "role": body.role}, course_id=s.course_id)
    db.commit()
    return section_out(db, s)


@router.post("/sections/{sid}/reassign")
def reassign(sid: int, body: ReassignIn, db: Session = Depends(get_db), user: User = Depends(require("offerings:manage"))):
    """Mid-semester hand-over: end the current primary assignment and start the new one."""
    s = db.get(Section, sid)
    if not s:
        raise HTTPException(404, "Section not found")
    if len(body.reason.strip()) < 5:
        raise HTTPException(422, "A reason is required for a hand-over")
    _instructor(db, body.new_instructor_id)
    eff = body.effective_date or date.today()
    current = db.scalars(active_assignments(db).where(InstructorAssignment.section_id == sid,
                                                      InstructorAssignment.role == "primary")).all()
    previous = []
    for a in current:
        if a.instructor_id == body.new_instructor_id:
            raise HTTPException(409, "That instructor is already the primary instructor")
        a.end_date = eff
        a.end_reason = body.reason
        previous.append(a.instructor_id)
    db.add(InstructorAssignment(section_id=sid, instructor_id=body.new_instructor_id, role="primary",
                                start_date=eff, assigned_by=user.id))
    record(db, user, "offerings.instructor_reassigned", "section", sid,
           {"from": previous, "to": body.new_instructor_id, "reason": body.reason, "effective": eff}, course_id=s.course_id)
    db.commit()
    return section_out(db, s)


@router.post("/assignments/{aid}/end")
def end_assignment(aid: int, body: EndIn, db: Session = Depends(get_db), user: User = Depends(require("offerings:manage"))):
    a = db.get(InstructorAssignment, aid)
    if not a:
        raise HTTPException(404, "Assignment not found")
    if a.end_date and a.end_date <= date.today():
        raise HTTPException(409, "Assignment already ended")
    a.end_date = body.end_date or date.today()
    a.end_reason = body.reason
    s = db.get(Section, a.section_id)
    record(db, user, "offerings.assignment_ended", "section", a.section_id,
           {"instructor_id": a.instructor_id, "reason": body.reason}, course_id=s.course_id)
    db.commit()
    return section_out(db, s)


@router.get("/unstaffed")
def unstaffed(db: Session = Depends(get_db), _=Depends(require("offerings:manage"))):
    """Sections that lost their primary instructor (e.g. after someone left)."""
    return [o for o in (section_out(db, s) for s in db.scalars(select(Section).where(Section.status == "open"))) if o["needs_instructor"]]


# ---- prerequisites -------------------------------------------------------------
def _has_cycle(db: Session, start_code: str, prereqs: list[str]) -> bool:
    by_code: dict[str, list[str]] = {}
    for c in db.scalars(select(Course).where(Course.status.in_(["approved", "active", "draft"]))):
        by_code.setdefault(c.code, []).extend(c.prerequisites)
    by_code[start_code] = prereqs
    stack, seen = list(prereqs), set()
    while stack:
        code = stack.pop()
        if code == start_code:
            return True
        if code in seen:
            continue
        seen.add(code)
        stack.extend(by_code.get(code, []))
    return False


@router.put("/courses/{cid}/prerequisites")
def set_prerequisites(cid: int, body: PrereqIn, db: Session = Depends(get_db), user: User = Depends(require("offerings:manage"))):
    c = db.get(Course, cid)
    if not c:
        raise HTTPException(404, "Course not found")
    if len(body.reason.strip()) < 5:
        raise HTTPException(422, "A reason is required")
    codes = sorted({norm_code(x) for x in body.prerequisites if x and x.strip()})
    if c.code in codes:
        raise HTTPException(422, "A course cannot be its own prerequisite")
    known = {x.code for x in db.scalars(select(Course))}
    unknown = [x for x in codes if x not in known]
    if unknown:
        raise HTTPException(422, f"Unknown course code(s): {', '.join(unknown)}")
    if _has_cycle(db, c.code, codes):
        raise HTTPException(422, "This would create a circular prerequisite chain")
    before = c.prerequisites
    c.prerequisites = codes
    record(db, user, "offerings.prerequisites_changed", "course", c.id,
           {"before": before, "after": codes, "reason": body.reason}, course_id=c.id)
    db.commit()
    return {"id": c.id, "code": c.code, "prerequisites": c.prerequisites}
