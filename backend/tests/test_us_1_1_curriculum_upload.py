"""US-1.1 Upload and version curriculum."""
from pathlib import Path

import pytest

from app.services.extraction import docling_available

from .helpers import as_role

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"
MD = (SAMPLES / "BSCS_curriculum.md").read_bytes()


def upload(client, h, data=MD, name="BSCS_curriculum.md", **form):
    return client.post("/api/curriculum/upload", headers=h, files={"file": (name, data)}, data=form)


def test_only_admins_upload(client):
    _, h = as_role(client, "instructor")
    assert upload(client, h).status_code == 403


def test_upload_returns_extraction_preview(client):
    _, h = as_role(client, "admin")
    r = upload(client, h)
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["status"] == "preview" and v["version_no"] == 1 and v["program_key"] == "BSCS"
    assert "Introduction to Programming" in v["extracted_markdown"]
    assert [c["code"] for c in v["parsed"]["courses"]] == ["CS101", "CS201", "MATH110"]
    assert {k: v["summary"][k] for k in ("courses", "plos", "clos", "errors", "warnings")} == {"courses": 3, "plos": 4, "clos": 12, "errors": 0, "warnings": 1}
    assert v["issues_resolved"] is False and v["summary"]["found_at_upload"] >= 1
    # offline mode -> rule-based parser is used and this is stated
    assert v["parser"] == "template" and any(w["level"] == "info" for w in v["warnings"])


@pytest.mark.parametrize("name,data,code", [
    ("evil.exe", b"MZ....", 422),
    ("fake.pdf", b"not a pdf at all", 422),
    ("empty.md", b"", 422),
    ("binary.txt", b"\xff\xfe\x00bad", 422),
    ("tiny.md", b"hello", 422),
])
def test_upload_validation(client, name, data, code):
    _, h = as_role(client, "admin")
    assert upload(client, h, data, name).status_code == code


def test_too_large_upload_rejected(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    _, h = as_role(client, "admin")
    assert upload(client, h).status_code == 413


def test_new_upload_creates_new_version_and_keeps_earlier(client):
    _, h = as_role(client, "admin")
    upload(client, h)
    assert upload(client, h).status_code == 409  # identical file is not re-versioned
    r2 = upload(client, h, MD + b"\nRevised 2027.\n")
    assert r2.json()["version_no"] == 2
    versions = client.get("/api/curriculum/versions?program_key=BSCS", headers=h).json()
    assert [v["version_no"] for v in versions] == [2, 1]


def test_original_file_stored_encrypted_and_downloadable(client):
    _, h = as_role(client, "admin")
    vid = upload(client, h).json()["id"]
    r = client.get(f"/api/curriculum/versions/{vid}/file", headers=h)
    assert r.content == MD


def test_discard_only_previews(client):
    _, h = as_role(client, "admin")
    vid = upload(client, h).json()["id"]
    assert client.post(f"/api/curriculum/versions/{vid}/discard", headers=h).json()["status"] == "discarded"
    assert client.post(f"/api/curriculum/versions/{vid}/discard", headers=h).status_code == 409


def test_upload_is_audited(client):
    _, h = as_role(client, "admin")
    upload(client, h)
    acts = [e["action"] for e in client.get("/api/audit?action=curriculum", headers=h).json()["items"]]
    assert "curriculum.uploaded" in acts


def test_gemini_parser_used_when_available(client, monkeypatch):
    from app.services import ai_gateway

    fake = {"program": {"code": "BSCS", "name": "BS CS"}, "plos": [{"code": "PLO1", "description": "Apply computing knowledge to problems"}],
            "courses": [{"code": "CS101", "title": "Intro", "credits": 3, "units": [{"number": 1, "title": "Basics", "clos": ["CLO1"]}],
                         "clos": [{"code": "CLO1", "description": "Explain variables and types in Python", "unit": 1}]}]}
    monkeypatch.setattr(ai_gateway, "call_json", lambda *a, **k: fake)
    _, h = as_role(client, "admin")
    v = upload(client, h).json()
    assert v["parser"] == "gemini" and v["summary"]["courses"] == 1


@pytest.mark.skipif(not docling_available(), reason="docling not installed")
def test_docx_extracted_with_docling(client):
    _, h = as_role(client, "admin")
    r = upload(client, h, (SAMPLES / "BSCS_curriculum.docx").read_bytes(), "BSCS_curriculum.docx")
    assert r.status_code == 201, r.text
    assert r.json()["extraction_engine"] == "docling" and r.json()["summary"]["clos"] == 12


def test_approved_version_shows_no_open_issues(client):
    """Issues saved at upload are history once the version passes the approval gate (which needs zero errors)."""
    from .helpers import approve_curriculum

    _, ah = as_role(client, "admin")
    approve_curriculum(client, ah)
    v = client.get("/api/curriculum/versions", headers=ah).json()[0]
    assert v["status"] == "approved" and v["issues_resolved"] is True
    assert v["summary"]["errors"] == 0 and v["summary"]["warnings"] == 0 and v["summary"]["found_at_upload"] >= 1
