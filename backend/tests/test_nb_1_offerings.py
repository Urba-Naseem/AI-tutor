"""NB-1 Configure academic offerings and course assignments to faculty."""
from .helpers import approve_curriculum, as_role, login, make_user, setup_offering, start_review


def test_sections_only_for_approved_courses(client):
    _, h = as_role(client, "admin")
    rv = start_review(client, h)
    t = client.post("/api/offerings/terms", headers=h, json={"name": "T1", "start_date": "2026-01-01", "end_date": "2026-06-30"}).json()
    r = client.post("/api/offerings/sections", headers=h, json={"course_id": rv["courses"][0]["id"], "term_id": t["id"], "code": "A", "capacity": 10})
    assert r.status_code == 422


def test_term_dates_validated(client):
    _, h = as_role(client, "admin")
    assert client.post("/api/offerings/terms", headers=h, json={"name": "Bad", "start_date": "2026-06-01", "end_date": "2026-01-01"}).status_code == 422


def test_assigned_instructor_gets_course_scope(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    inst = make_user("instructor")
    ih = login(client, inst.email)
    assert client.get(f"/api/outcomes/courses/{courses['CS101']['id']}", headers=ih).status_code == 403
    setup_offering(client, h, courses["CS101"]["id"], inst)
    assert client.get(f"/api/outcomes/courses/{courses['CS101']['id']}", headers=ih).status_code == 200
    assert client.get(f"/api/outcomes/courses/{courses['CS201']['id']}", headers=ih).status_code == 403
    assert [c["code"] for c in client.get("/api/outcomes/courses", headers=ih).json()] == ["CS101"]


def test_only_one_primary_and_assistants_allowed(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    a, b = make_user("instructor"), make_user("instructor")
    s = setup_offering(client, h, courses["CS101"]["id"], a)
    assert client.post(f"/api/offerings/sections/{s['id']}/assign", headers=h, json={"instructor_id": b.id}).status_code == 409
    r = client.post(f"/api/offerings/sections/{s['id']}/assign", headers=h, json={"instructor_id": b.id, "role": "assistant"})
    assert r.status_code == 200 and len(r.json()["instructors"]) == 2


def test_instructor_leaves_mid_semester_handover(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    leaving, replacement = make_user("instructor"), make_user("instructor")
    s = setup_offering(client, h, courses["CS101"]["id"], leaving)
    lh = login(client, leaving.email)
    assert client.post(f"/api/offerings/sections/{s['id']}/reassign", headers=h, json={"new_instructor_id": replacement.id, "reason": ""}).status_code == 422
    r = client.post(f"/api/offerings/sections/{s['id']}/reassign", headers=h,
                    json={"new_instructor_id": replacement.id, "reason": "Resigned mid-semester"})
    assert r.status_code == 200
    sec = r.json()
    assert [i["instructor_id"] for i in sec["instructors"]] == [replacement.id]
    assert len(sec["history"]) == 2 and sec["history"][0]["end_reason"] == "Resigned mid-semester"
    # scope moves with the assignment
    assert client.get(f"/api/outcomes/courses/{courses['CS101']['id']}", headers=lh).status_code == 403
    rh = login(client, replacement.email)
    assert client.get(f"/api/outcomes/courses/{courses['CS101']['id']}", headers=rh).status_code == 200
    ev = client.get("/api/audit?action=offerings.instructor_reassigned", headers=h).json()["items"][0]
    assert ev["details"]["from"] == [leaving.id] and ev["details"]["reason"] == "Resigned mid-semester"


def test_unstaffed_sections_listed_after_assignment_ends(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    inst = make_user("instructor")
    s = setup_offering(client, h, courses["CS101"]["id"], inst)
    aid = s["instructors"][0]["id"]
    client.post(f"/api/offerings/assignments/{aid}/end", headers=h, json={"reason": "Medical leave"})
    assert [x["id"] for x in client.get("/api/offerings/unstaffed", headers=h).json()] == [s["id"]]


def test_prerequisites_maintained_with_validation(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    cs101, cs201 = courses["CS101"]["id"], courses["CS201"]["id"]
    r = client.put(f"/api/offerings/courses/{cs201}/prerequisites", headers=h, json={"prerequisites": ["CS101", "MATH110"], "reason": "Board decision 12"})
    assert r.status_code == 200 and r.json()["prerequisites"] == ["CS101", "MATH110"]
    assert client.put(f"/api/offerings/courses/{cs101}/prerequisites", headers=h, json={"prerequisites": ["CS201"], "reason": "test cycle"}).status_code == 422
    assert client.put(f"/api/offerings/courses/{cs101}/prerequisites", headers=h, json={"prerequisites": ["XX999"], "reason": "unknown"}).status_code == 422


def test_capacity_cannot_be_invalid(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    s = setup_offering(client, h, courses["CS101"]["id"])
    assert client.patch(f"/api/offerings/sections/{s['id']}", headers=h, json={"capacity": 5}).json()["capacity"] == 5


def test_non_admin_cannot_configure_offerings(client):
    _, h = as_role(client, "instructor")
    assert client.post("/api/offerings/terms", headers=h, json={"name": "X", "start_date": "2026-01-01", "end_date": "2026-02-01"}).status_code == 403
