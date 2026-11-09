"""US-1.1 - Upload and version curriculum (administrators)."""
import hashlib
import logging
import re
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.audit import record
from ..core.crypto import read_encrypted_file, store_encrypted_file
from ..config import get_settings
from ..core.rbac import require
from ..db import get_db
from ..models.curriculum import CurriculumVersion
from ..models.user import User
from ..services import automation
from ..services import progress
from ..services import unit_planner
from ..services import roadmap as roadmap_svc
from ..services import curriculum_parser as cp
from ..services.extraction import MIME, extract_markdown, validate_upload

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


def parse_curriculum(db: Session, user: User, markdown: str, run_id: str | None = None) -> tuple[dict, str, list[dict]]:
    """AI extraction that does not depend on the document's layout. Returns (parsed, parser, notes).

    1. compress the text (no padding, page headers/footers or image placeholders),
    2. cut it into parts BY SIZE (course headings are only preferred cut points; a part that starts inside a course
       is told which course it continues) - so documents without code-style headings work the same way,
    3. read the programme + PLOs and all parts in parallel, strict schemas, temperature 0; the PLO codes found in
       the text go first in every prompt (shared prefix),
    4. merge what the parts returned (the same course read from two parts becomes one),
    5. a failed part is retried in two halves; everything that was read is kept, and a part that still cannot be
       read is named in a warning,
    6. only if nothing could be read: the rule-based template parser.
    """
    import threading

    from ..config import get_settings
    from ..services import ai_gateway, llm, text_prep
    from ..services.ai_gateway import AIUnavailable, call_json_many
    from ..services.schemas import CoursesOut, CurriculumOut, HeadOut

    notes: list[dict] = []
    text = text_prep.compress(markdown)
    parts = text_prep.windows(text, get_settings().curriculum_part_chars)
    hint = text_prep.course_count_hint(text)  # progress only; None when the document has no code-style headings
    head, _ = text_prep.split_courses(text)
    head_text = head if head != text and cp.plo_codes(head) else text[:60_000]  # PLOs may be anywhere
    plos = cp.plo_codes(head_text) or cp.plo_codes(text)
    budget = get_settings().gemini_background_timeout_seconds  # background job: wait out rate limits, don't fail
    progress.update(run_id, stage="extracting", courses_total=hint, courses_done=0,
                    message=(f"Found {hint} courses - extracting their CLOs and the programme's PLOs" if hint else
                             f"Extracting courses, CLOs and PLOs ({len(parts)} part(s))"))
    lock, seen = threading.Lock(), {"parts": 0, "courses": 0}

    def counted(i, res):
        if isinstance(res, Exception) or jobs[i]["purpose"] != "curriculum.parse.courses":
            return
        n = len(ai_gateway.as_list(llm.parse_json(res.text), "courses"))
        with lock:
            seen["parts"] += 1
            seen["courses"] += n
        progress.add_courses(run_id, n)
        if not hint:
            progress.update(run_id, message=f"Extracting courses - {seen['parts']} of {len(parts)} parts read, "
                                            f"{seen['courses']} courses found so far")

    def course_job(part):
        body, context = part
        return {"purpose": "curriculum.parse.courses", "prompt": cp.courses_prompt(plos, body, context),
                "system": cp.SYSTEM, "schema": CoursesOut, "max_output_tokens": 16384, "budget": budget}

    head_job = {"purpose": "curriculum.parse.head", "prompt": cp.head_prompt(head_text), "system": cp.SYSTEM,
                "schema": HeadOut, "max_output_tokens": 8192, "budget": budget}
    try:
        if len(parts) <= 1:  # a short document: one call for everything
            data = ai_gateway.call_json(db, user, "curriculum.parse", cp.full_prompt(text), cp.SYSTEM,
                                        schema=CurriculumOut, budget=budget)
        else:
            jobs = [head_job] + [course_job(p) for p in parts]
            results = call_json_many(db, user, jobs, on_done=counted)
            head_res, courses, failed = results[0], [], []
            for p, r in zip(parts, results[1:]):
                if isinstance(r, AIUnavailable):
                    failed.append(p)
                else:
                    courses += r["courses"]
            if failed or isinstance(head_res, AIUnavailable):  # second chance: failed parts in two halves (+ PLOs)
                progress.update(run_id, message=f"Retrying {len(failed)} part(s) that timed out, in smaller pieces"
                                if failed else "Retrying the programme's PLOs")
                halves = [(h, c or ctx) for body, ctx in failed
                          for h, c in text_prep.windows(body, max(200, len(body) // 2 + 1))]
                jobs = ([head_job] if isinstance(head_res, AIUnavailable) else []) + [course_job(h) for h in halves]
                retry = call_json_many(db, user, jobs, on_done=counted)
                if isinstance(head_res, AIUnavailable):
                    head_res, retry = retry[0], retry[1:]
                still = [h for h, r in zip(halves, retry) if isinstance(r, AIUnavailable)]
                courses += [x for r in retry if not isinstance(r, AIUnavailable) for x in r["courses"]]
                if still:
                    labels = [text_prep.part_label(b, c) for b, c in still]
                    notes.append({"level": "warning", "path": "parser",
                                  "message": f"The AI could not read {len(still)} part(s) of the document (it timed out "
                                             f"twice), starting with: {'; '.join(labels)}. Upload again later to try "
                                             "once more, or add the missing courses in Outcome review."})
            if isinstance(head_res, AIUnavailable) or not courses:
                raise AIUnavailable(str(head_res) if isinstance(head_res, AIUnavailable) else "no course could be read")
            data = {"program": head_res["program"], "plos": head_res["plos"],
                    "courses": text_prep.merge_courses(courses)}
        parsed, parser = cp.normalise(cp.from_schema(data)), "gemini"
        if not parsed["courses"]:
            raise AIUnavailable("model found no courses")
    except AIUnavailable as e:
        notes = [n for n in notes if n["path"] != "parser"]
        parsed, parser = cp.normalise(cp.heuristic_parse(markdown)), "template"
        notes.append({"level": "info", "path": "parser",
                      "message": f"AI parser unavailable ({str(e)[:120]}); used the rule-based template parser"})
    return parsed, parser, notes


def version_out(v: CurriculumVersion, full: bool = False) -> dict:
    resolved = v.status in ("approved", "superseded")
    d = {
        "id": v.id, "program_key": v.program_key, "version_no": v.version_no, "title": v.title,
        "filename": v.filename, "size_bytes": v.size_bytes, "status": v.status, "parser": v.parser,
        "extraction_engine": v.extraction_engine, "uploaded_by": v.uploaded_by, "uploaded_at": v.uploaded_at,
        "approved_at": v.approved_at, "sha256": v.sha256,
        "summary": {
            "courses": len(v.parsed.get("courses", [])), "plos": len(v.parsed.get("plos", [])),
            "clos": sum(len(c.get("clos", [])) for c in v.parsed.get("courses", [])),
            # counts are OPEN issues: an approved version passed the approval gate (no errors, warnings resolved),
            # so the issues saved at upload time are history, not problems
            "errors": 0 if resolved else sum(1 for w in v.warnings if w["level"] == "error"),
            "warnings": 0 if resolved else sum(1 for w in v.warnings if w["level"] == "warning"),
            "found_at_upload": len(v.warnings),
        },
        "issues_resolved": resolved,
    }
    if full:
        d.update(parsed=v.parsed, warnings=v.warnings, extracted_markdown=v.extracted_markdown, notes=v.notes)
    return d


@router.get("/upload-progress/{run_id}")
def upload_progress(run_id: str, user: User = Depends(require("curriculum:manage"))):
    """Live progress of an upload started with this `upload_id` by the same user (404 if unknown or finished long ago).
    When finished it also carries `result` (what the upload returns) or `error` (a plain-language reason)."""
    p = progress.get(run_id, user.id)
    if p is None:
        raise HTTPException(404, "No upload in progress with this id")
    return p


@router.post("/upload", status_code=201)
async def upload(
    file: UploadFile = File(...),
    roadmap: UploadFile | None = File(None),  # optional semester roadmap (study plan): PDF, XLSX, MD, TXT, DOCX
    program_key: str | None = Form(None),
    title: str | None = Form(None),
    upload_id: str | None = Form(None),  # client-chosen id to poll /upload-progress/{id} while this runs
    db: Session = Depends(get_db),
    user: User = Depends(require("curriculum:manage")),
):
    from starlette.concurrency import run_in_threadpool

    data = await file.read()
    roadmap_data = await roadmap.read() if roadmap is not None and roadmap.filename else None
    roadmap_name = roadmap.filename if roadmap_data is not None else None
    if progress.valid_id(upload_id):
        # Background job: the upload keeps going while the person uses other pages (or closes this one); the page
        # follows it through /upload-progress/{upload_id} and picks up the result when it is done.
        validate_upload(file.filename, data)  # obvious problems are reported straight away
        if roadmap_data is not None:
            try:
                roadmap_svc.validate(roadmap_name, roadmap_data)
            except roadmap_svc.RoadmapError as e:
                raise HTTPException(422, str(e))
        progress.start(upload_id, user.id, "Reading the document")
        args = (user.id, file.filename, data, roadmap_name, roadmap_data, program_key, title, upload_id)
        if get_settings().app_env == "test":
            _upload_background(*args)  # deterministic under tests
        else:
            threading.Thread(target=_upload_background, args=args, daemon=True, name=f"upload-{upload_id[:8]}").start()
        return JSONResponse({"upload_id": upload_id, "status": "started"}, status_code=202)
    # Without an id the call waits for the result (API clients, tests). The slow part runs in a worker thread: on
    # the event loop it blocked every other request until the upload finished.
    return await run_in_threadpool(_upload, db, user, file.filename, data, roadmap_name, roadmap_data, program_key, title, None)


def _upload_background(user_id: int, filename: str, data: bytes, roadmap_name: str | None, roadmap_data: bytes | None,
                       program_key: str | None, title: str | None, run_id: str) -> None:
    from fastapi.encoders import jsonable_encoder

    from ..db import SessionLocal

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        out = _upload_steps(db, user, filename, data, roadmap_name, roadmap_data, program_key, title, run_id)
        progress.update(run_id, stage="done", done=True, message="Finished", result=jsonable_encoder(out))
    except HTTPException as e:
        db.rollback()
        d = e.detail
        msg = d.get("message", str(d)) if isinstance(d, dict) else str(d)
        progress.update(run_id, stage="failed", done=True, message="The upload stopped", error=msg)
    except Exception:  # never crash the server; say what to do instead of showing a stack trace
        log.exception("Curriculum upload %s failed", run_id)
        db.rollback()
        progress.update(run_id, stage="failed", done=True, message="The upload stopped",
                        error="Something went wrong while processing the file. Try again; if it keeps happening, "
                              "the server log has the details.")
    finally:
        db.close()


def _upload(db: Session, user: User, filename: str, data: bytes, roadmap_name: str | None, roadmap_data: bytes | None,
            program_key: str | None, title: str | None, run_id: str | None) -> dict:
    progress.start(run_id, user.id, "Reading the document")
    try:
        out = _upload_steps(db, user, filename, data, roadmap_name, roadmap_data, program_key, title, run_id)
    except Exception:
        progress.update(run_id, stage="failed", done=True, message="The upload stopped - see the message on the page")
        raise
    progress.update(run_id, stage="done", done=True, message="Finished")
    return out


def _upload_steps(db: Session, user: User, filename: str, data: bytes, roadmap_name: str | None, roadmap_data: bytes | None,
                  program_key: str | None, title: str | None, run_id: str | None) -> dict:
    ext = validate_upload(filename, data)
    if roadmap_data is not None:
        try:
            roadmap_svc.validate(roadmap_name, roadmap_data)
        except roadmap_svc.RoadmapError as e:
            raise HTTPException(422, str(e))
    digest = hashlib.sha256(data).hexdigest()
    markdown, engine = extract_markdown(filename, data)
    if len(markdown.strip()) < 50:
        raise HTTPException(422, "Almost no text could be extracted - is this a scanned image? Upload a text-based file.")
    parsed, parser, notes = parse_curriculum(db, user, markdown, run_id)
    # documents without units: group each course's CLOs into a few units in teaching order (AI, even-split fallback)
    if any(c.get("auto_unit") and len(c.get("clos", [])) >= unit_planner.MIN_CLOS for c in parsed["courses"]):
        progress.update(run_id, stage="units", message="The document has no units - grouping the CLOs into units")
        unit_planner.propose(db, user, parsed, use_ai=parser == "gemini")
    n_courses = len(parsed["courses"])
    progress.update(run_id, stage="checking", courses_total=n_courses, courses_done=n_courses,
                    message=f"Extracted {n_courses} courses, {sum(len(c['clos']) for c in parsed['courses'])} CLOs and "
                            f"{len(parsed['plos'])} PLOs - checking them against the document")
    warnings = notes + cp.check_structure(parsed, markdown)

    key = (program_key or parsed["program"].get("code") or Path(filename).stem).strip().upper()
    key = re.sub(r"[^A-Z0-9-]+", "-", key)[:40]
    dup = db.scalar(select(CurriculumVersion).where(
        CurriculumVersion.program_key == key, CurriculumVersion.sha256 == digest,
        CurriculumVersion.status != "discarded"))
    if dup:
        raise HTTPException(409, f"This exact file is already version {dup.version_no} of {key}")
    version_no = (db.scalar(select(func.max(CurriculumVersion.version_no)).where(CurriculumVersion.program_key == key)) or 0) + 1

    v = CurriculumVersion(
        program_key=key, version_no=version_no,
        title=title or parsed["program"].get("name") or filename,
        filename=filename, mime=MIME[ext], size_bytes=len(data), sha256=digest,
        file_ref=store_encrypted_file(data, filename), status="preview",
        extraction_engine=engine, extracted_markdown=markdown, parser=parser, parsed=parsed,
        warnings=warnings, uploaded_by=user.id,
    )
    db.add(v)
    db.flush()
    record(db, user, "curriculum.uploaded", "curriculum_version", v.id,
           {"program_key": key, "version_no": version_no, "filename": filename, "sha256": digest,
            "parser": parser, "engine": engine})
    db.commit()
    road = None
    if roadmap_data is not None:
        progress.update(run_id, stage="roadmap", message="Reading the semester roadmap")
        try:
            road = roadmap_svc.import_file(db, user, v, roadmap_name, roadmap_data)
            db.commit()
        except roadmap_svc.RoadmapError as e:
            db.rollback()
            road = {"error": str(e)}
    else:
        # No separate roadmap file: look for a study plan inside the curriculum document itself. A recognisable
        # "Semester 1 ... / Semester 2 ..." list is read directly; any other layout that mentions semesters, terms
        # or years is read by the AI from those passages.
        entries, engine = roadmap_svc.embedded_entries(markdown), "document"
        if not entries and (passages := roadmap_svc.roadmap_passages(markdown)):
            progress.update(run_id, stage="roadmap", message="Looking for a semester roadmap in the document")
            try:
                entries, engine = roadmap_svc.rows_to_entries(roadmap_svc.ai_reader(db, user)(passages)), "document-ai"
            except Exception:  # noqa: BLE001 - best effort: a curriculum without a roadmap is fine
                entries = []
            if len({e.semester for e in entries}) < 2:
                entries = []
        if entries:
            progress.update(run_id, stage="roadmap", message="Reading the semester roadmap in the document")
            road = roadmap_svc.import_entries(db, user, v, entries, f"{filename} (roadmap in the document)", engine)
            db.commit()
    if not automation.enabled():
        return {**version_out(v, full=True), "roadmap": road}
    # Automation: review -> approve -> map -> activate, then write and publish each live course's questions.
    progress.update(run_id, stage="setup", message="Approving the curriculum")

    def course_step(i, n, code):
        progress.update(run_id, step=i, steps=n, message=f"Linking CLOs to PLOs and activating courses - {code} ({i} of {n})")

    result = automation.run_curriculum(db, user, v.id, on_course=course_step)
    for c in result["courses"]:
        if c["status"] == "active":
            c["preparing_questions"] = automation.prepare_course_async(c["id"], user.id)
    db.refresh(v)
    return {**version_out(v, full=True), "automation": result, "roadmap": road}


# ---- semester roadmap (study plan) ------------------------------------------------------
class RoadmapMatchIn(BaseModel):
    id: int
    course_code: str | None = None


class RoadmapEditIn(BaseModel):
    entries: list[RoadmapMatchIn]


@router.get("/versions/{vid}/roadmap")
def get_roadmap(vid: int, db: Session = Depends(get_db), _=Depends(require("curriculum:manage", "outcomes:review"))):
    v = db.get(CurriculumVersion, vid)
    if not v:
        raise HTTPException(404, "Version not found")
    return roadmap_svc.out(db, v)


@router.post("/versions/{vid}/roadmap")
async def upload_roadmap(vid: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                         user: User = Depends(require("curriculum:manage"))):
    """Add or replace the semester roadmap of a version (also for approved / active curricula: semesters are not outcomes)."""
    v = db.get(CurriculumVersion, vid)
    if not v or v.status == "discarded":
        raise HTTPException(404, "Version not found")
    data = await file.read()
    try:
        res = roadmap_svc.import_file(db, user, v, file.filename, data)
    except roadmap_svc.RoadmapError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return res


@router.put("/versions/{vid}/roadmap")
def edit_roadmap(vid: int, body: RoadmapEditIn, db: Session = Depends(get_db), user: User = Depends(require("curriculum:manage"))):
    """Correct which curriculum course a roadmap row is (or set None for a roadmap-only course)."""
    from ..models.curriculum import RoadmapEntry

    v = db.get(CurriculumVersion, vid)
    if not v:
        raise HTTPException(404, "Version not found")
    codes = {c for c, _ in roadmap_svc.version_courses(db, v)}
    rows = {r.id: r for r in db.scalars(select(RoadmapEntry).where(RoadmapEntry.curriculum_version_id == vid))}
    wanted = [c.course_code for c in body.entries if c.course_code]
    if len(wanted) != len(set(wanted)):
        raise HTTPException(422, "Each curriculum course can be placed in the roadmap only once")
    changed = 0
    for item in body.entries:
        r = rows.get(item.id)
        if not r:
            raise HTTPException(404, f"Roadmap row {item.id} not found")
        code = item.course_code.strip().upper() if item.course_code else None
        if code and code not in codes:
            raise HTTPException(422, f"{code} is not a course of this curriculum")
        if r.course_code != code:
            r.course_code, r.matched_by, r.match_score, changed = code, "manual" if code else "none", None, changed + 1
    others = {r.course_code for r in rows.values() if r.course_code}
    if len([r for r in rows.values() if r.course_code]) != len(others):
        raise HTTPException(422, "Each curriculum course can be placed in the roadmap only once")
    roadmap_svc.apply(db, v)
    record(db, user, "curriculum.roadmap_edited", "curriculum_version", v.id, {"changed": changed})
    db.commit()
    return roadmap_svc.out(db, v)


@router.get("/versions")
def list_versions(program_key: str | None = None, db: Session = Depends(get_db), _=Depends(require("curriculum:manage", "outcomes:review"))):
    q = select(CurriculumVersion).order_by(CurriculumVersion.program_key, CurriculumVersion.version_no.desc())
    if program_key:
        q = q.where(CurriculumVersion.program_key == program_key)
    return [version_out(v) for v in db.scalars(q)]


@router.get("/versions/{vid}")
def get_version(vid: int, db: Session = Depends(get_db), _=Depends(require("curriculum:manage", "outcomes:review"))):
    v = db.get(CurriculumVersion, vid)
    if not v:
        raise HTTPException(404, "Version not found")
    return version_out(v, full=True)


@router.get("/versions/{vid}/file")
def download_file(vid: int, db: Session = Depends(get_db), user: User = Depends(require("curriculum:manage"))):
    v = db.get(CurriculumVersion, vid)
    if not v:
        raise HTTPException(404, "Version not found")
    record(db, user, "curriculum.downloaded", "curriculum_version", v.id, {})
    db.commit()
    return Response(read_encrypted_file(v.file_ref), media_type=v.mime,
                    headers={"Content-Disposition": f'attachment; filename="{v.filename}"'})


@router.post("/versions/{vid}/discard")
def discard(vid: int, db: Session = Depends(get_db), user: User = Depends(require("curriculum:manage"))):
    v = db.get(CurriculumVersion, vid)
    if not v:
        raise HTTPException(404, "Version not found")
    if v.status != "preview":
        raise HTTPException(409, "Only a preview can be discarded; reviewed versions are retained")
    v.status = "discarded"
    record(db, user, "curriculum.discarded", "curriculum_version", v.id, {})
    db.commit()
    return version_out(v)
