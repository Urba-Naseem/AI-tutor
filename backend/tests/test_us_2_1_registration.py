"""US-2.1 Register and verify students."""
import re

from app.services.email import list_outbox

from .helpers import login

GOOD = {"student_number": "BSCS-2026-001", "full_name": "Ayesha Khan", "email": "ayesha.khan@university.edu",
        "password": "Learning2026", "consent": True, "consent_version": "2026-1"}


def reg(client, **over):
    return client.post("/api/auth/register", json={**GOOD, **over})


def verify_link():
    return re.search(r"token=([\w-]+)", list_outbox()[0]["body"]).group(1)


def test_register_verify_then_login(client):
    assert reg(client).status_code == 201
    r = client.post("/api/auth/login", json={"email": GOOD["email"], "password": GOOD["password"]})
    assert r.status_code == 403  # not verified yet
    assert client.post("/api/auth/verify-email", json={"token": verify_link()}).status_code == 200
    h = login(client, GOOD["email"], GOOD["password"])
    me = client.get("/api/auth/me", headers=h).json()
    assert me["role"] == "student" and me["student_number"] == "BSCS-2026-001"


def test_institutional_domain_required(client):
    assert reg(client, email="ayesha@gmail.com").status_code == 422
    assert reg(client, email="ayesha@student.university.edu", student_number="S-9999").status_code == 201


def test_unique_email_and_student_number(client):
    reg(client)
    assert reg(client, student_number="OTHER-1").status_code == 409
    assert reg(client, email="other@university.edu").status_code == 409
    assert reg(client, email="AYESHA.KHAN@University.edu", student_number="OTHER-2").status_code == 409


def test_consent_required_and_recorded(client):
    assert reg(client, consent=False).status_code == 422
    assert reg(client, consent_version="old").status_code == 422
    reg(client)
    client.post("/api/auth/verify-email", json={"token": verify_link()})
    h = login(client, GOOD["email"], GOOD["password"])
    c = client.get("/api/auth/my-consent", headers=h).json()
    assert c["consented"] is True and c["history"][0]["version"] == "2026-1"


def test_withdraw_and_reaccept_consent(client):
    reg(client)
    client.post("/api/auth/verify-email", json={"token": verify_link()})
    h = login(client, GOOD["email"], GOOD["password"])
    client.post("/api/auth/my-consent/withdraw", headers=h)
    assert client.get("/api/auth/my-consent", headers=h).json()["consented"] is False
    client.post("/api/auth/my-consent/accept", headers=h, json={"consent_version": "2026-1"})
    c = client.get("/api/auth/my-consent", headers=h).json()
    assert c["consented"] is True and len(c["history"]) == 2 and c["history"][1]["withdrawn_at"]


def test_verification_link_single_use(client):
    reg(client)
    tok = verify_link()
    assert client.post("/api/auth/verify-email", json={"token": tok}).status_code == 200
    assert client.post("/api/auth/verify-email", json={"token": tok}).status_code == 400


def test_weak_password_and_bad_student_number(client):
    assert reg(client, password="short").status_code == 422
    assert reg(client, student_number="!!").status_code == 422


def test_consent_text_available(client):
    r = client.get("/api/auth/consent").json()
    assert r["version"] == "2026-1" and "Gemini" in r["text"]
