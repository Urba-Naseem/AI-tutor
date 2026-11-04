import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.curriculum import CurriculumDocument
from app.services.curriculum_validator import CurriculumValidator
from app.services.audit_service import AuditService

router = APIRouter()

STORAGE_DIR = "uploads/curriculums"

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_scheme_of_studies(
    background_tasks: BackgroundTasks,
    program: str = Form(..., description="e.g., BS Computer Science"),
    department: str = Form(..., description="e.g., Computer Science"),
    cohort: str = Form(..., description="e.g., 2024-2028"),
    term: str = Form(..., description="e.g., Fall 2024"),
    user_id: str = Form("1", description="Uploader User ID"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    filename = file.filename or "unknown"

    # 1. Full Inspection & Validation
    file_bytes, sha256_checksum, mime_type = await CurriculumValidator.validate_and_process_file(file)

    # 2. Persist Raw File Unchanged to Storage
    os.makedirs(STORAGE_DIR, exist_ok=True)
    file_ext = os.path.splitext(filename)[1].lower()
    stored_filename = f"{sha256_checksum}_{uuid.uuid4().hex[:8]}{file_ext}"
    saved_path = os.path.join(STORAGE_DIR, stored_filename)

    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    # 3. Calculate Document Version (US-1.1)
    latest_doc = db.query(CurriculumDocument).filter(
        CurriculumDocument.program == program,
        CurriculumDocument.department == department,
        CurriculumDocument.cohort == cohort,
        CurriculumDocument.term == term
    ).order_by(CurriculumDocument.version.desc()).first()

    current_version = (latest_doc.version + 1) if (latest_doc and getattr(latest_doc, 'version', None)) else 1

    # 4. Store Metadata in Database
    doc_record = CurriculumDocument(
        program=program,
        department=department,
        cohort=cohort,
        term=term,
        version=current_version,
        original_filename=filename,
        stored_filename=stored_filename,
        file_path=saved_path,
        mime_type=mime_type,
        file_size_bytes=len(file_bytes),
        sha256_checksum=sha256_checksum,
        uploaded_by=str(user_id)
    )
    db.add(doc_record)
    db.commit()
    db.refresh(doc_record)

    # 5. Emit Audit Event (US-3.1)
    AuditService.emit_event_async(
        background_tasks,
        event_type="CURRICULUM_UPLOADED",
        user_id=str(user_id),
        resource_type="curriculum_document",
        resource_id=str(doc_record.id),
        details={
            "document_id": doc_record.id,
            "version": current_version,
            "program": program,
            "department": department,
            "cohort": cohort,
            "term": term,
            "filename": filename,
            "checksum": sha256_checksum,
            "file_size_bytes": len(file_bytes),
            "mime_type": mime_type
        }
    )

    return {
        "status": "success",
        "message": f"Scheme of studies uploaded successfully (Version {current_version})",
        "document_id": doc_record.id,
        "version": current_version,
        "filename": filename,
        "checksum": sha256_checksum,
        "metadata": {
            "program": program,
            "department": department,
            "cohort": cohort,
            "term": term
        }
    }