import os
import uuid
import hashlib
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.curriculum import CurriculumDocument
from app.services.curriculum_validator import CurriculumValidator
from app.services.audit_service import log_audit_event  # For US-3.1

router = APIRouter(prefix="/api/v1/curriculum", tags=["Curriculum"])

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads", "curriculums")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def generate_preview_text(file_bytes: bytes, filename: str) -> str:
    """Generates a brief text preview of uploaded files (US-1.1)."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".csv":
        lines = file_bytes.decode("utf-8", errors="ignore").splitlines()
        return "\n".join(lines[:10])  # First 10 lines
    elif ext == ".pdf":
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        if len(reader.pages) > 0:
            return reader.pages[0].extract_text()[:1000]  # First 1000 chars of page 1
    return "Preview unavailable for this file type."

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_curriculum(
    request: Request,
    program: str = Form(...),
    department: str = Form(...),
    cohort: str = Form(...),
    term: str = Form(...),
    user_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    contents = await file.read()
    
    # 1. Run multi-layer security & integrity validation
    CurriculumValidator.validate_file(file.filename, contents, file.content_type)
    
    # 2. Compute SHA-256 hash
    checksum = hashlib.sha256(contents).hexdigest()
    
    # 3. Determine next version number for this (program, department, cohort, term) tuple
    latest_version = db.query(func.max(CurriculumDocument.version)).filter(
        CurriculumDocument.program == program,
        CurriculumDocument.department == department,
        CurriculumDocument.cohort == cohort,
        CurriculumDocument.term == term
    ).scalar() or 0
    
    new_version = latest_version + 1
    
    # 4. Save file to disk with unique naming convention
    unique_filename = f"{checksum}_{uuid.uuid4().hex[:8]}{os.path.splitext(file.filename)[1]}"
    saved_path = os.path.join(UPLOAD_DIR, unique_filename)
    with open(saved_path, "wb") as f:
        f.write(contents)
        
    # 5. Save metadata to database
    doc_record = CurriculumDocument(
        program=program,
        department=department,
        cohort=cohort,
        term=term,
        version=new_version,
        filename=file.filename,
        file_path=saved_path,
        sha256_checksum=checksum,
        file_size_bytes=len(contents),
        uploaded_by=user_id
    )
    db.add(doc_record)
    db.commit()
    db.refresh(doc_record)
    
    # 6. Generate extraction preview (US-1.1)
    preview_snippet = generate_preview_text(contents, file.filename)
    
    # 7. Log attributable audit event (US-3.1)
    log_audit_event(
        db=db,
        user_id=user_id,
        action="CURRICULUM_UPLOADED",
        resource_type="curriculum_document",
        resource_id=doc_record.id,
        details={
            "filename": file.filename,
            "version": new_version,
            "checksum": checksum,
            "program": program,
            "term": term
        },
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    
    return {
        "status": "success",
        "message": f"Document version {new_version} uploaded successfully",
        "document_id": doc_record.id,
        "version": new_version,
        "filename": doc_record.filename,
        "checksum": checksum,
        "extraction_preview": preview_snippet
    }