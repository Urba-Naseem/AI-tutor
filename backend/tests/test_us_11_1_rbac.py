"""US-11.1 Manage roles and scopes (server-side authorization)."""
import pytest

from app.core import rbac
from app.db import SessionLocal

from .helpers import as_role, login, make_user


@pytest.mark.parametrize("role", ["student", "instructor", "exam_staff"])
def test_non_admins_cannot_manage_users(client, role):
    _, h = as_role(client, role)
    assert client.get("/api/users", headers=h).status_code == 403
    r = client.post("/api/users", headers=h, json={"email": "x@university.edu", "full_name": "X", "role": "admin", "password": "Passw0rd!2026"})
    assert r.status_code == 403


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/api/users").status_code == 401


def test_admin_creates_users_in_each_role(client):
    _, h = as_role(client, "admin")
    for role in ("student", "instructor", "admin", "exam_staff"):
        r = client.post("/api/users", headers=h, json={"email": f"new.{role}@university.edu", "full_name": role, "role": role, "password": "Passw0rd!2026"})
        assert r.status_code == 201, r.text
    assert client.post("/api/users", headers=h, json={"email": "z@university.edu", "full_name": "z", "role": "superuser", "password": "Passw0rd!2026"}).status_code == 422
    assert len(client.get("/api/users", headers=h).json()) == 5


def test_role_change_revokes_existing_sessions(client):
    _, h = as_role(client, "admin")
    target = make_user("instructor")
    th = login(client, target.email)
    assert client.get("/api/auth/me", headers=th).status_code == 200
    client.patch(f"/api/users/{target.id}", headers=h, json={"role": "student"})
    assert client.get("/api/auth/me", headers=th).status_code == 401


def test_admin_cannot_demote_self(client):
    admin, h = as_role(client, "admin")
    assert client.patch(f"/api/users/{admin.id}", headers=h, json={"role": "student"}).status_code == 400


def test_me_lists_permissions_per_role(client):
    _, h = as_role(client, "exam_staff")
    perms = client.get("/api/auth/me", headers=h).json()["permissions"]
    assert "audit:read" in perms and "users:manage" not in perms


def test_course_scope_providers():
    db = SessionLocal()
    inst = make_user("instructor")
    student = make_user("student")
    admin = make_user("admin")
    staff = make_user("exam_staff")
    fn = rbac.register_scope("instructor", lambda d, u: {7} if u.id == inst.id else set())
    try:
        assert rbac.accessible_course_ids(db, admin) is None
        assert rbac.accessible_course_ids(db, inst) == {7}
        assert rbac.accessible_course_ids(db, student) == set()
        rbac.ensure_course_access(db, inst, 7)
        with pytest.raises(Exception):
            rbac.ensure_course_access(db, inst, 8)
        rbac.ensure_course_access(db, staff, 8)  # read is fine
        with pytest.raises(Exception):
            rbac.ensure_course_access(db, staff, 8, write=True)
    finally:
        rbac.SCOPE_PROVIDERS["instructor"].remove(fn)
        db.close()
