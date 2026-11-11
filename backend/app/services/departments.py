"""Departments (degree programmes such as BSCS and BSSE).

* A department is a programme code from an uploaded curriculum: every curriculum upload (BSCS, BSSE, ...) brings
  its own courses, PLOs and semester roadmap, and the same pipeline (review, mappings, topics, paths) runs for each.
* Every student belongs to one department (User.program_code), chosen at registration; only an admin can change it
  (with a reason, audited). Students see and enrol only in their own department's courses and roadmap - enforced
  here on the server, not only in the UI.
* Students registered before departments existed get the only department automatically while there is just one;
  once there are several, an admin assigns them.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.outcomes import Course, Program
from ..models.user import User

LIVE = ("approved", "active")  # course statuses that make a programme a real department


def programs(db: Session) -> list[dict]:
    """Departments students can belong to: programme codes with approved or active courses (latest name wins)."""
    rows = db.execute(select(Program.code, Program.name, Program.id).join(Course, Course.program_id == Program.id)
                      .where(Course.status.in_(LIVE)).order_by(Program.id)).all()
    out: dict[str, dict] = {}
    for code, name, _pid in rows:
        out[code] = {"code": code, "name": name}
    return sorted(out.values(), key=lambda p: p["code"])


def name_of(db: Session, code: str | None) -> str | None:
    if not code:
        return None
    return db.scalar(select(Program.name).where(Program.code == code).order_by(Program.id.desc()).limit(1)) or code


def valid(db: Session, code: str | None) -> bool:
    return bool(code) and any(p["code"] == code for p in programs(db))


def program_of(db: Session, user: User) -> str | None:
    """The student's department. Students from before departments existed are filled in automatically: the only
    department while there is one, otherwise the department of the courses they are already enrolled in (when all
    their enrolments are in one department). Anyone else waits for an admin."""
    if user.program_code or user.role != "student":
        return user.program_code
    ps = programs(db)
    guess = ps[0]["code"] if len(ps) == 1 else None
    if guess is None:
        from ..models.enrollment import Enrollment

        codes = set(db.scalars(select(Program.code).join(Course, Course.program_id == Program.id)
                               .join(Enrollment, Enrollment.course_id == Course.id).where(Enrollment.student_id == user.id)))
        guess = codes.pop() if len(codes) == 1 else None
    if guess:
        user.program_code = guess
        from ..core.audit import record

        record(db, None, "user.department_inferred", "user", user.id, {"program_code": guess})
        db.flush()
    return user.program_code


def course_program(db: Session, course: Course) -> str | None:
    p = db.get(Program, course.program_id)
    return p.code if p else None


def same_department(db: Session, student: User, course: Course) -> str | None:
    """None when the student may take this course, else the reason (shown to the student)."""
    mine = program_of(db, student)
    theirs = course_program(db, course)
    if mine is None:
        return "Your department is not set yet - ask an administrator to assign you to CS or SE"
    if theirs != mine:
        return f"{course.code} belongs to the {name_of(db, theirs)} department, not yours ({name_of(db, mine)})"
    return None
