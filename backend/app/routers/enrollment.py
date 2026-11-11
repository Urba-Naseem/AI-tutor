"""US-2.4 - Enrol students in courses (semester roadmap, prerequisites, capacity, withdrawal history).

Roadmap limit: a student may enrol in courses of their CURRENT roadmap semester (the earliest semester of the
programme that still has a course they have not completed) and of earlier unfinished semesters, never in a later
semester. Courses with no semester are not limited. An administrator can override (with a reason)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.audit import record
from ..core.rbac import ensure_course_access, register_scope, require
from ..db import get_db, utcnow
from ..models.enrollment import Enrollment
from ..models.offerings import Section, Term
from ..models.outcomes import Course, Program
from ..models.user import User
from .offerings import course_instructors
from .registration import require_consent

router = APIRouter(prefix="/api/enrollment", tags=["enrollment"])


@register_scope("student")
def _student_courses(db: Session, user: User) -> set[int]:
    return {e.course_id for e in db.scalars(select(Enrollment).where(
        Enrollment.student_id == user.id, Enrollment.status.in_(["enrolled", "completed"])))}


class EnrollIn(BaseModel):
    section_id: int


class AdminEnrollIn(BaseModel):
    student_id: int
    section_id: int
    override_prerequisites: bool = False
    reason: str | None = None


class WithdrawIn(BaseModel):
    reason: str


def completed_codes(db: Session, student_id: int) -> set[str]:
    rows = db.execute(select(Course.code).join(Enrollment, Enrollment.course_id == Course.id)
                      .where(Enrollment.student_id == student_id, Enrollment.status == "completed")).all()
    return {r[0] for r in rows}


def roadmap(db: Session, student_id: int, program_id: int) -> dict:
    """The student's position in a programme's semester roadmap.
    Returns {"current": int | None, "courses": [{code, title, credits, semester, course_id}], "done": set}."""
    prog = db.get(Program, program_id)
    rows = db.execute(select(Course).join(Program, Program.id == Course.program_id)
                      .where(Program.code == prog.code, Course.status == "active", Course.semester.is_not(None))
                      .order_by(Course.semester, Course.code)).scalars().all()
    by_code: dict[str, Course] = {}
    for c in rows:  # the same course code can exist in several curriculum versions: keep the latest
        if c.code not in by_code or c.id > by_code[c.code].id:
            by_code[c.code] = c
    done = completed_codes(db, student_id)
    pending = [c.semester for c in by_code.values() if c.code not in done]
    return {"current": min(pending) if pending else None, "courses": list(by_code.values()), "done": done}


def roadmap_problem(db: Session, student_id: int, course: Course) -> str | None:
    if not course.semester:
        return None
    r = roadmap(db, student_id, course.program_id)
    cur = r["current"]
    if cur is None or course.semester <= cur:
        return None
    todo = sorted(c.code for c in r["courses"] if c.semester == cur and c.code not in r["done"])
    return (f"{course.code} is in Semester {course.semester} of the roadmap. You are in Semester {cur}: "
            f"complete {', '.join(todo)} first")


def seats_taken(db: Session, section_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.section_id == section_id,
                                                                       Enrollment.status == "enrolled"))


def check(db: Session, student: User, section: Section, override: bool = False) -> list[str]:
    """Return reasons the student cannot enrol (empty list = allowed)."""
    problems = []
    course = db.get(Course, section.course_id)
    term = db.get(Term, section.term_id)
    from ..services import departments

    if (dept := departments.same_department(db, student, course)):
        problems.append(dept)  # never overridable: departments keep their students separate
    if course.status != "active":
        problems.append(f"{course.code} is not active yet")
    if section.status != "open":
        problems.append("This section is closed")
    if term.end_date < date.today():
        problems.append(f"Term {term.name} has ended")
    if seats_taken(db, section.id) >= section.capacity:
        problems.append("This section is full")
    if db.scalar(select(Enrollment).where(Enrollment.student_id == student.id, Enrollment.course_id == course.id,
                                          Enrollment.status == "enrolled")):
        problems.append(f"Already enrolled in {course.code}")
    if db.scalar(select(Enrollment).where(Enrollment.student_id == student.id, Enrollment.course_id == course.id,
                                          Enrollment.status == "completed")):
        problems.append(f"{course.code} already completed")
    missing = [p for p in course.prerequisites if p not in completed_codes(db, student.id)]
    if missing and not override:
        problems.append(f"Missing prerequisite(s): {', '.join(missing)}")
    if not override and (sem := roadmap_problem(db, student.id, course)):
        problems.append(sem)
    return problems


def enr_out(db: Session, e: Enrollment) -> dict:
    s = db.get(Section, e.section_id)
    c = db.get(Course, e.course_id)
    t = db.get(Term, s.term_id)
    return {"id": e.id, "status": e.status, "course": {"id": c.id, "code": c.code, "title": c.title},
            "section": {"id": s.id, "code": s.code}, "term": t.name, "enrolled_at": e.enrolled_at,
            "withdrawn_at": e.withdrawn_at, "withdraw_reason": e.withdraw_reason, "completed_at": e.completed_at,
            "prerequisite_override": e.prerequisite_override, "override_reason": e.override_reason}


def _enrol(db, student: User, section: Section, actor: User, override=False, reason=None) -> Enrollment:
    problems = check(db, student, section, override)
    if problems:
        record(db, actor, "enrollment.refused", "section", section.id, {"student_id": student.id, "problems": problems},
               course_id=section.course_id)
        db.commit()
        raise HTTPException(409, {"message": "Enrolment not possible", "problems": problems})
    e = Enrollment(student_id=student.id, section_id=section.id, course_id=section.course_id, enrolled_by=actor.id,
                   prerequisite_override=override, override_reason=reason)
    db.add(e)
    db.flush()
    record(db, actor, "enrollment.enrolled", "enrollment", e.id,
           {"student_id": student.id, "section_id": section.id, "override": override, "reason": reason},
           course_id=section.course_id)
    return e


@router.get("/catalog")
def catalog(db: Session = Depends(get_db), user: User = Depends(require("enroll:self"))):
    from ..services import departments

    done = completed_codes(db, user.id)
    mine = departments.program_of(db, user)
    db.commit()  # keep an inferred department
    out = []
    q = select(Course).join(Program, Program.id == Course.program_id).where(Course.status == "active", Program.code == (mine or "__none__"))
    for c in db.scalars(q.order_by(Course.code)):
        sections = []
        for s in db.scalars(select(Section).where(Section.course_id == c.id, Section.status == "open")):
            t = db.get(Term, s.term_id)
            if t.end_date < date.today():
                continue
            teachers = [u.full_name for u in course_instructors(db, c.id)]
            sections.append({"id": s.id, "code": s.code, "term": t.name, "capacity": s.capacity,
                             "seats_left": s.capacity - seats_taken(db, s.id), "instructors": teachers,
                             "problems": check(db, user, s)})
        out.append({"id": c.id, "code": c.code, "title": c.title, "credits": c.credits, "description": c.description,
                    "semester": c.semester, "roadmap_problem": roadmap_problem(db, user.id, c),
                    "prerequisites": [{"code": p, "met": p in done} for p in c.prerequisites], "sections": sections})
    return out


@router.get("/roadmap")
def my_roadmap(db: Session = Depends(get_db), user: User = Depends(require("enroll:self"))):
    """The student's semester roadmap per programme: each course marked completed / enrolled / open / locked."""
    mine = {e.course_id: e.status for e in db.scalars(select(Enrollment).where(Enrollment.student_id == user.id))}
    enrolled_codes = {db.get(Course, cid).code for cid, st in mine.items() if st == "enrolled"}
    # only the student's own department's roadmap
    from ..services import departments

    dept = departments.program_of(db, user)
    db.commit()  # keep an inferred department
    codes = {dept} if dept else set()
    out = []
    for code in sorted(codes):
        prog = db.scalar(select(Program).join(Course, Course.program_id == Program.id)
                         .where(Program.code == code, Course.status == "active").order_by(Program.id.desc()).limit(1))
        if not prog:
            continue
        r = roadmap(db, user.id, prog.id)
        if not r["courses"]:
            continue
        semesters: dict[int, list] = {}
        for c in r["courses"]:
            status = ("completed" if c.code in r["done"] else "enrolled" if c.code in enrolled_codes
                      else "locked" if r["current"] is not None and c.semester > r["current"] else "open")
            semesters.setdefault(c.semester, []).append({
                "course_id": c.id, "code": c.code, "title": c.title, "credits": c.credits, "status": status,
                "prerequisites": [{"code": p, "met": p in r["done"]} for p in c.prerequisites]})
        # Roadmap-only courses (in the study plan but without CLOs in the curriculum): shown for information,
        # never counted for the limit (the app cannot track them).
        from ..models.curriculum import RoadmapEntry
        vids = sorted({c.curriculum_version_id for c in r["courses"]}, reverse=True)
        for vid in vids:
            extra = db.scalars(select(RoadmapEntry).where(RoadmapEntry.curriculum_version_id == vid,
                                                          RoadmapEntry.course_code.is_(None))
                               .order_by(RoadmapEntry.semester, RoadmapEntry.position)).all()
            if extra or db.scalar(select(RoadmapEntry.id).where(RoadmapEntry.curriculum_version_id == vid).limit(1)):
                for e in extra:
                    semesters.setdefault(e.semester, []).append({
                        "course_id": None, "code": None, "title": e.name, "credits": e.credits, "status": "not_tracked",
                        "prerequisites": []})
                break
        out.append({"program": {"code": prog.code, "name": prog.name}, "current_semester": r["current"],
                    "semesters": [{"number": n, "courses": cs} for n, cs in sorted(semesters.items())]})
    return out


@router.post("", status_code=201)
def enrol_self(body: EnrollIn, db: Session = Depends(get_db), user: User = Depends(require("enroll:self")),
               _c: User = Depends(require_consent)):
    s = db.get(Section, body.section_id)
    if not s:
        raise HTTPException(404, "Section not found")
    e = _enrol(db, user, s, user)
    db.commit()
    return enr_out(db, e)


@router.post("/admin", status_code=201)
def enrol_admin(body: AdminEnrollIn, db: Session = Depends(get_db), user: User = Depends(require("enrollment:manage"))):
    s = db.get(Section, body.section_id)
    student = db.get(User, body.student_id)
    if not s or not student or student.role != "student":
        raise HTTPException(404, "Section or student not found")
    if body.override_prerequisites and len((body.reason or "").strip()) < 5:
        raise HTTPException(422, "A reason is required to override prerequisites")
    e = _enrol(db, student, s, user, body.override_prerequisites, body.reason)
    db.commit()
    return enr_out(db, e)


@router.get("/mine")
def mine(db: Session = Depends(get_db), user: User = Depends(require("enroll:self"))):
    rows = db.scalars(select(Enrollment).where(Enrollment.student_id == user.id).order_by(Enrollment.enrolled_at.desc()))
    return [enr_out(db, e) for e in rows]


@router.post("/{eid}/withdraw")
def withdraw(eid: int, body: WithdrawIn, db: Session = Depends(get_db), user: User = Depends(require("enroll:self", "enrollment:manage"))):
    e = db.get(Enrollment, eid)
    if not e or (user.role == "student" and e.student_id != user.id):
        raise HTTPException(404, "Enrolment not found")
    if e.status != "enrolled":
        raise HTTPException(409, f"Enrolment is already {e.status}")
    if len(body.reason.strip()) < 3:
        raise HTTPException(422, "Please give a reason")
    e.status, e.withdrawn_at, e.withdraw_reason = "withdrawn", utcnow(), body.reason
    record(db, user, "enrollment.withdrawn", "enrollment", e.id, {"reason": body.reason, "student_id": e.student_id},
           course_id=e.course_id)
    db.commit()
    return enr_out(db, e)


@router.post("/{eid}/complete")
def complete(eid: int, db: Session = Depends(get_db), user: User = Depends(require("enrollment:manage"))):
    e = db.get(Enrollment, eid)
    if not e or e.status != "enrolled":
        raise HTTPException(409, "Only current enrolments can be completed")
    e.status, e.completed_at = "completed", utcnow()
    record(db, user, "enrollment.completed", "enrollment", e.id, {"student_id": e.student_id}, course_id=e.course_id)
    db.commit()
    return enr_out(db, e)


@router.get("/student/{sid}")
def student_history(sid: int, db: Session = Depends(get_db), _=Depends(require("enrollment:manage"))):
    return [enr_out(db, e) for e in db.scalars(select(Enrollment).where(Enrollment.student_id == sid).order_by(Enrollment.id))]


@router.get("/course/{cid}/roster")
def roster(cid: int, include_history: bool = False, db: Session = Depends(get_db), user: User = Depends(require("reports:read"))):
    ensure_course_access(db, user, cid)
    q = select(Enrollment).where(Enrollment.course_id == cid)
    if not include_history:
        q = q.where(Enrollment.status == "enrolled")
    out = []
    for e in db.scalars(q.order_by(Enrollment.enrolled_at)):
        st = db.get(User, e.student_id)
        out.append({**enr_out(db, e), "student": {"id": st.id, "name": st.full_name, "student_number": st.student_number}})
    return out
