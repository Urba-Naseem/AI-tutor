"""US-2.4 Enroll students in courses."""
from .helpers import activate_course, active_course_with_student, approve_curriculum, as_role, login, make_user, setup_offering


def test_student_enrols_and_gains_course_scope(client):
    ctx = active_course_with_student(client)
    cid = ctx["course"]["id"]
    assert client.get(f"/api/outcomes/courses/{cid}", headers=ctx["sh"]).status_code == 200
    assert client.get(f"/api/outcomes/courses/{ctx['courses']['CS201']['id']}", headers=ctx["sh"]).status_code == 403
    mine = client.get("/api/enrollment/mine", headers=ctx["sh"]).json()
    assert mine[0]["status"] == "enrolled" and mine[0]["course"]["code"] == "CS101"


def test_only_active_courses(client):
    _, ah = as_role(client, "admin")
    courses = approve_curriculum(client, ah)
    s = setup_offering(client, ah, courses["CS101"]["id"])
    _, sh = as_role(client, "student")
    r = client.post("/api/enrollment", headers=sh, json={"section_id": s["id"]})
    assert r.status_code == 409 and "not active" in r.json()["detail"]["problems"][0]


def test_capacity_enforced(client):
    ctx = active_course_with_student(client, capacity=1)
    _, sh2 = as_role(client, "student")
    r = client.post("/api/enrollment", headers=sh2, json={"section_id": ctx["section"]["id"]})
    assert r.status_code == 409 and "full" in str(r.json())


def test_prerequisites_checked_and_admin_override(client):
    ctx = active_course_with_student(client)
    ah = ctx["ah"]
    cs201 = ctx["courses"]["CS201"]["id"]
    s2 = setup_offering(client, ah, cs201, ctx["inst"])
    activate_course(client, ctx["ih"], cs201)
    r = client.post("/api/enrollment", headers=ctx["sh"], json={"section_id": s2["id"]})
    assert r.status_code == 409 and "Missing prerequisite(s): CS101" in str(r.json())
    # completing CS101 satisfies the prerequisite
    eid = client.get("/api/enrollment/mine", headers=ctx["sh"]).json()[0]["id"]
    client.post(f"/api/enrollment/{eid}/complete", headers=ah)
    assert client.post("/api/enrollment", headers=ctx["sh"], json={"section_id": s2["id"]}).status_code == 201
    # override for another student requires a reason
    other = make_user("student")
    assert client.post("/api/enrollment/admin", headers=ah, json={"student_id": other.id, "section_id": s2["id"], "override_prerequisites": True}).status_code == 422
    r = client.post("/api/enrollment/admin", headers=ah, json={"student_id": other.id, "section_id": s2["id"], "override_prerequisites": True, "reason": "Transfer credit"})
    assert r.status_code == 201 and r.json()["prerequisite_override"] is True


def test_catalog_shows_prerequisite_status_and_seats(client):
    ctx = active_course_with_student(client)
    cat = {c["code"]: c for c in client.get("/api/enrollment/catalog", headers=ctx["sh"]).json()}
    cs101 = cat["CS101"]
    assert cs101["sections"][0]["seats_left"] == 29 and "Already enrolled in CS101" in cs101["sections"][0]["problems"]


def test_withdrawal_keeps_history_and_allows_reenrol(client):
    ctx = active_course_with_student(client)
    sh = ctx["sh"]
    eid = client.get("/api/enrollment/mine", headers=sh).json()[0]["id"]
    assert client.post(f"/api/enrollment/{eid}/withdraw", headers=sh, json={"reason": "Timetable clash"}).json()["status"] == "withdrawn"
    assert client.get(f"/api/outcomes/courses/{ctx['course']['id']}", headers=sh).status_code == 403
    assert client.post("/api/enrollment", headers=sh, json={"section_id": ctx["section"]["id"]}).status_code == 201
    hist = client.get("/api/enrollment/mine", headers=sh).json()
    assert [h["status"] for h in hist] == ["enrolled", "withdrawn"] and hist[1]["withdraw_reason"] == "Timetable clash"


def test_consent_required_to_enrol(client):
    ctx = active_course_with_student(client)
    st = make_user("student")
    sh = login(client, st.email)
    client.post("/api/auth/my-consent/withdraw", headers=sh)
    assert client.post("/api/enrollment", headers=sh, json={"section_id": ctx["section"]["id"]}).status_code == 403


def test_roster_scoped_to_instructor(client):
    ctx = active_course_with_student(client)
    roster = client.get(f"/api/enrollment/course/{ctx['course']['id']}/roster", headers=ctx["ih"]).json()
    assert roster[0]["student"]["id"] == ctx["student"].id
    other = make_user("instructor")
    assert client.get(f"/api/enrollment/course/{ctx['course']['id']}/roster", headers=login(client, other.email)).status_code == 403
