"""US-2.3 Secure login and account recovery."""
import re
from datetime import timedelta

from app.db import SessionLocal, utcnow
from app.models.user import User
from app.services.email import list_outbox

from .helpers import PASSWORD, login, make_user


def test_login_returns_token_and_sets_httponly_refresh_cookie(client):
    u = make_user("admin")
    r = client.post("/api/auth/login", json={"email": u.email, "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "admin"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == u.email


def test_password_is_hashed_not_stored():
    u = make_user("admin")
    assert u.password_hash.startswith("$argon2") and PASSWORD not in u.password_hash


def test_wrong_password_is_generic_and_unknown_user_same_message(client):
    u = make_user("admin")
    a = client.post("/api/auth/login", json={"email": u.email, "password": "nope"})
    b = client.post("/api/auth/login", json={"email": "ghost@university.edu", "password": "nope"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_lockout_after_repeated_failures(client):
    u = make_user("admin")
    for _ in range(5):
        client.post("/api/auth/login", json={"email": u.email, "password": "wrong"})
    r = client.post("/api/auth/login", json={"email": u.email, "password": PASSWORD})
    assert r.status_code == 423


def test_ip_throttling(client):
    for i in range(20):
        client.post("/api/auth/login", json={"email": f"x{i}@university.edu", "password": "wrong"})
    r = client.post("/api/auth/login", json={"email": "x@university.edu", "password": "wrong"})
    assert r.status_code == 429


def test_refresh_rotates_and_reuse_revokes_family(client):
    u = make_user("admin")
    client.post("/api/auth/login", json={"email": u.email, "password": PASSWORD})
    old = client.cookies.get("aitutor_refresh")
    r1 = client.post("/api/auth/refresh")
    assert r1.status_code == 200
    assert client.cookies.get("aitutor_refresh") != old
    # replay the old (rotated) token -> everything in the family is revoked
    client.cookies.clear()
    r2 = client.post("/api/auth/refresh", cookies={"aitutor_refresh": old})
    assert r2.status_code == 401
    r3 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r1.json()['access_token']}"})
    assert r3.status_code == 401


def test_logout_revokes_session(client):
    u = make_user("admin")
    h = login(client, u.email)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_password_reset_flow_single_use_and_expiry(client):
    u = make_user("admin")
    r = client.post("/api/auth/forgot-password", json={"email": u.email})
    assert r.status_code == 200
    body = list_outbox()[0]["body"]
    token = re.search(r"token=([\w-]+)", body).group(1)
    weak = client.post("/api/auth/reset-password", json={"token": token, "new_password": "short"})
    assert weak.status_code == 422
    ok = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewPassw0rd99"})
    assert ok.status_code == 200
    again = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewPassw0rd99"})
    assert again.status_code == 400
    login(client, u.email, "NewPassw0rd99")


def test_forgot_password_does_not_reveal_accounts(client):
    r = client.post("/api/auth/forgot-password", json={"email": "nobody@university.edu"})
    assert r.status_code == 200


def test_expired_reset_token_rejected(client):
    u = make_user("admin")
    client.post("/api/auth/forgot-password", json={"email": u.email})
    token = re.search(r"token=([\w-]+)", list_outbox()[0]["body"]).group(1)
    from app.models.user import OneTimeToken

    db = SessionLocal()
    for t in db.query(OneTimeToken).all():
        t.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    db.close()
    r = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewPassw0rd99"})
    assert r.status_code == 400


def test_unverified_student_cannot_login(client):
    u = make_user("student", verified=False)
    r = client.post("/api/auth/login", json={"email": u.email, "password": PASSWORD})
    assert r.status_code == 403


def test_personal_data_encrypted_in_users_table(client):
    make_user("admin", email="secret.person@university.edu", name="Secret Person")
    db = SessionLocal()
    raw = db.execute(__import__("sqlalchemy").text("select email, full_name from users")).first()
    assert "secret" not in raw[0].lower() and "Secret" not in raw[1]
    assert db.query(User).first().email == "secret.person@university.edu"
    db.close()
