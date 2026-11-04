import io
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_upload_valid_csv():
    csv_content = b"course_code,title,credit_hours\nCS101,Intro to CS,3\nCS102,Data Structures,4"
    response = client.post(
        "/api/v1/curriculum/upload",
        data={
            "program": "BS Computer Science",
            "department": "Computer Science",
            "cohort": "2024-2028",
            "term": "Fall 2024",
            "user_id": "1"
        },
        files={"file": ("curriculum.csv", csv_content, "text/csv")}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "checksum" in data

def test_reject_empty_file():
    response = client.post(
        "/api/v1/curriculum/upload",
        data={
            "program": "BS CS",
            "department": "CS",
            "cohort": "2024",
            "term": "Fall",
            "user_id": "1"
        },
        files={"file": ("empty.pdf", b"", "application/pdf")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_reject_invalid_extension():
    response = client.post(
        "/api/v1/curriculum/upload",
        data={
            "program": "BS CS",
            "department": "CS",
            "cohort": "2024",
            "term": "Fall",
            "user_id": "1"
        },
        files={"file": ("executable.exe", b"binary content", "application/octet-stream")}
    )
    assert response.status_code == 400
    assert "extension" in response.json()["detail"].lower()

def test_reject_oversized_file():
    oversized_data = b"0" * (21 * 1024 * 1024)  # 21 MB
    response = client.post(
        "/api/v1/curriculum/upload",
        data={
            "program": "BS CS",
            "department": "CS",
            "cohort": "2024",
            "term": "Fall",
            "user_id": "1"
        },
        files={"file": ("large.csv", oversized_data, "text/csv")}
    )
    assert response.status_code == 400
    assert "exceeds" in response.json()["detail"].lower()