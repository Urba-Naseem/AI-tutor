import io
import os
import csv
import hashlib
import zipfile
from fastapi import UploadFile, HTTPException, status
from pypdf import PdfReader
from pypdf.errors import PdfReadError
import logging

# Suppress minor PDF parsing warnings in terminal
logging.getLogger("pypdf").setLevel(logging.ERROR)

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB Limit
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".csv"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/csv",
    "application/csv",
    "text/plain"
}

class CurriculumValidator:

    @staticmethod
    async def validate_and_process_file(file: UploadFile) -> tuple[bytes, str, str]:
        """
        Validates file size, extension, MIME type, corruption, passwords, and macros.
        Returns: (file_bytes, sha256_checksum, detected_mime_type)
        """
        filename = file.filename or ""
        file_ext = os.path.splitext(filename)[1].lower()

        # 1. Extension Validation
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file extension '{file_ext}'. Only PDF, DOCX, and CSV files are allowed."
            )

        # 2. Read File Bytes
        content = await file.read()
        file_size = len(content)

        # 3. Empty File Validation
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes)."
            )

        # 4. File Size Validation (Max 20 MB)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size ({file_size / (1024 * 1024):.2f} MB) exceeds maximum allowed limit of 20 MB."
            )

        # 5. MIME Type Validation
        content_type = file.content_type or "application/octet-stream"
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid MIME type '{content_type}' for format {file_ext.upper()}."
            )

        # 6. Deep Content Inspection (Corrupted, Encrypted, or Macro Detection)
        if file_ext == ".pdf":
            CurriculumValidator._inspect_pdf(content)
        elif file_ext == ".docx":
            CurriculumValidator._inspect_docx(content)
        elif file_ext == ".csv":
            CurriculumValidator._inspect_csv(content)

        # 7. Compute SHA-256 Checksum
        checksum = hashlib.sha256(content).hexdigest()

        return content, checksum, content_type

    @staticmethod
    def _inspect_pdf(content: bytes):
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PDF document is password-protected or encrypted."
                )
            # Trigger page parsing to catch internal stream corruption
            _ = len(reader.pages)
        except PdfReadError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded PDF file is corrupted or unreadable."
            )

    @staticmethod
    def _inspect_docx(content: bytes):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                namelist = zf.namelist()

                # Check for password-protected / encrypted DOCX
                if "EncryptedPackage" in namelist or "EncryptionInfo" in namelist:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="DOCX document is password-protected or encrypted."
                    )

                # Check for macros (vbaProject.bin)
                if any("vbaProject.bin" in name for name in namelist):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Macro-containing DOCX files are strictly prohibited."
                    )
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded DOCX file is corrupted or not a valid OpenXML package."
            )

    @staticmethod
    def _inspect_csv(content: bytes):
        try:
            decoded = content.decode("utf-8")
            reader = csv.reader(io.StringIO(decoded))
            rows = list(reader)
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CSV file contains no valid data or rows."
                )
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file encoding is invalid. File must be UTF-8 encoded text."
            )