"""Departments (CS and SE): each curriculum is a department with its own courses and roadmap; students choose one at
registration, see and enrol only in their own department's courses, and only an admin can move them."""
from .helpers import (SAMPLE_MD, activate_course, as_role, approve_curriculum, login, make_user, setup_offering,
                      upload_curriculum)

SE_MD = (SAMPLE_MD.decode("utf-8").replace("# Program: BSCS - Bachelor of Science in Computer Science",
                                            "# Program: BSSE - Bachelor of Science in Software Engineering")
         .replace("CS101 - Introduction to Programming", "SE101 - Introduction to Software Engineering").replace("CS101", "SE101")).encode("utf-8")


def two_departments(client):
    """BSCS (approved via the helper) and BSSE (uploaded and approved), one active course with a section in each."""
    _, ah = as_role(client, "admin")
    cs = approve_curriculum(client, ah)
    v = upload_curriculum(client, ah, SE_MD)
    rv = client.post(f"/api/outcomes/versions/{v['id']}/start-review", headers=ah).json()
    m = next(c for c in rv["courses"] if c["code"] == "MATH110")
    clo2 = next(o for o in m["clos"] if o["code"] == "CLO2")
    client.patch(f"/api/outcomes/clos/{clo2['id']}", headers=ah, json={"description": "Construct direct proofs and proofs by contradiction."})
    ap = client.post(f"/api/outcomes/versions/{v['id']}/approve", headers=ah)
    assert ap.status_code == 200, ap.text
    se = {c["code"]: c for c in ap.json()["courses"]}
    out = {"ah": ah}
    for key, course in (("cs", cs["CS101"]), ("se", se["SE101"])):
        inst = make_user("instructor")
        sec = setup_offering(client, ah, course["id"], inst)
        activate_course(client, login(client, inst.email), course["id"])
        out[key] = {"course": course, "section": sec}
    return out


def register(client, code, n):
    consent = client.get("/api/auth/consent").json()
    return client.post("/api/auth/register", json={
        "student_number": f"21-{code}-{n:03d}", "full_name": "New Student", "email": f"new{code}{n}@university.edu",
        "password": "Str0ng!Passw0rd#2026", "consent": True, "consent_version": consent["version"], "program_code": code})


def test_registration_offers_departments_and_requires_one(client):
    two_departments(client)
    progs = client.get("/api/auth/programs").json()
    assert [p["code"] for p in progs] == ["BSCS", "BSSE"] and progs[1]["name"].endswith("Software Engineering")
    assert register(client, "BSSE", 1).status_code == 201
    bad = register(client, "XX", 2)
    assert bad.status_code == 422 and "department" in bad.text


def test_students_see_and_enrol_only_in_their_department(client):
    d = two_departments(client)
    cs_student = make_user("student")
    se_student = make_user("student")
    from app.db import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    db.get(User, cs_student.id).program_code = "BSCS"
    db.get(User, se_student.id).program_code = "BSSE"
    db.commit()
    db.close()
    ch, sh = login(client, cs_student.email), login(client, se_student.email)
    assert {c["code"] for c in client.get("/api/enrollment/catalog", headers=ch).json()} == {"CS101"}
    assert {c["code"] for c in client.get("/api/enrollment/catalog", headers=sh).json()} == {"SE101"}
    r = client.post("/api/enrollment", headers=sh, json={"section_id": d["cs"]["section"]["id"]})
    assert r.status_code == 409 and "belongs to the" in r.text and "Computer Science" in r.text
    assert client.post("/api/enrollment", headers=sh, json={"section_id": d["se"]["section"]["id"]}).status_code == 201
    # roadmaps are separate too
    road = client.get("/api/enrollment/roadmap", headers=sh).json()
    assert all(r["program"]["code"] == "BSSE" for r in road)  # never the CS roadmap (this sample has no semester plan)
    # an admin cannot override the department either
    r = client.post("/api/enrollment/admin", headers=d["ah"], json={"student_id": cs_student.id, "section_id": d["se"]["section"]["id"],
                                                                     "override_prerequisites": True, "reason": "Testing override"})
    assert r.status_code == 409 and "belongs to the" in r.text


def test_only_admin_moves_a_student_with_a_reason(client):
    d = two_departments(client)
    assert register(client, "BSCS", 7).status_code == 201
    ah = d["ah"]
    u = next(x for x in client.get("/api/users?program=BSCS", headers=ah).json() if x["student_number"] == "21-BSCS-007")
    assert u["program_code"] == "BSCS"
    assert client.patch(f"/api/users/{u['id']}", headers=ah, json={"program_code": "BSSE"}).status_code == 422  # no reason
    r = client.patch(f"/api/users/{u['id']}", headers=ah, json={"program_code": "BSSE", "reason": "Changed degree in week 2"})
    assert r.status_code == 200 and r.json()["program_code"] == "BSSE"
    ev = client.get("/api/audit?action=user.updated", headers=ah).json()["items"][0]
    assert ev["details"]["program_code"] == ["BSCS", "BSSE"] and ev["details"]["reason"] == "Changed degree in week 2"
    # students cannot change their own department (no endpoint accepts it from them)
    sh = login(client, make_user("student").email)
    assert client.patch(f"/api/users/{u['id']}", headers=sh, json={"program_code": "BSCS"}).status_code == 403


def test_single_department_backfills_existing_students(client):
    _, ah = as_role(client, "admin")
    courses = approve_curriculum(client, ah)
    inst = make_user("instructor")
    sec = setup_offering(client, ah, courses["CS101"]["id"], inst)
    activate_course(client, login(client, inst.email), courses["CS101"]["id"])
    old = make_user("student")  # created before departments: no program_code
    sh = login(client, old.email)
    assert {c["code"] for c in client.get("/api/enrollment/catalog", headers=sh).json()} == {"CS101"}
    assert client.post("/api/enrollment", headers=sh, json={"section_id": sec["id"]}).status_code == 201


def test_existing_student_gets_department_from_their_enrolments(client):
    """A student from before departments, already enrolled in a CS course, is placed in CS once SE exists too."""
    _, ah = as_role(client, "admin")
    cs = approve_curriculum(client, ah)
    inst = make_user("instructor")
    sec = setup_offering(client, ah, cs["CS101"]["id"], inst)
    activate_course(client, login(client, inst.email), cs["CS101"]["id"])
    old = make_user("student")
    sh = login(client, old.email)
    assert client.post("/api/enrollment", headers=sh, json={"section_id": sec["id"]}).status_code == 201
    from app.db import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    db.get(User, old.id).program_code = None  # as if registered before departments existed
    db.commit()
    db.close()
    # now a second department appears
    v = upload_curriculum(client, ah, SE_MD)
    rv = client.post(f"/api/outcomes/versions/{v['id']}/start-review", headers=ah).json()
    m = next(c for c in rv["courses"] if c["code"] == "MATH110")
    clo2 = next(o for o in m["clos"] if o["code"] == "CLO2")
    client.patch(f"/api/outcomes/clos/{clo2['id']}", headers=ah, json={"description": "Construct direct proofs and proofs by contradiction."})
    assert client.post(f"/api/outcomes/versions/{v['id']}/approve", headers=ah).status_code == 200
    client.get("/api/enrollment/roadmap", headers=sh)
    db = SessionLocal()
    assert db.get(User, old.id).program_code == "BSCS"
    db.close()
    # a student with no enrolments stays unassigned (admin decides)
    new = make_user("student")
    db = SessionLocal()
    db.get(User, new.id).program_code = None
    db.commit()
    db.close()
    assert client.get("/api/enrollment/catalog", headers=login(client, new.email)).json() == []


def test_sections_for_a_whole_semester(client):
    _, ah = as_role(client, "admin")
    from .test_roadmap import ROADMAP

    v = upload_curriculum(client, ah, SAMPLE_MD + ROADMAP)
    rv = client.post(f"/api/outcomes/versions/{v['id']}/start-review", headers=ah).json()
    m = next(c for c in rv["courses"] if c["code"] == "MATH110")
    clo2 = next(o for o in m["clos"] if o["code"] == "CLO2")
    client.patch(f"/api/outcomes/clos/{clo2['id']}", headers=ah, json={"description": "Construct direct proofs and proofs by contradiction."})
    assert client.post(f"/api/outcomes/versions/{v['id']}/approve", headers=ah).status_code == 200
    term = client.post("/api/offerings/terms", headers=ah, json={"name": "Fall 2026", "start_date": "2026-01-01", "end_date": "2027-12-31"}).json()
    body = {"program_code": "BSCS", "semester": 1, "term_id": term["id"], "code": "A", "capacity": 35}
    r = client.post("/api/offerings/sections/semester", headers=ah, json=body)
    assert r.status_code == 201
    made = r.json()["created"]
    assert [s["course"]["code"] for s in made] == ["CS101"] and made[0]["capacity"] == 35 and made[0]["needs_instructor"]
    again = client.post("/api/offerings/sections/semester", headers=ah, json=body).json()
    assert again["created"] == [] and again["skipped"] == ["CS101"]
    assert client.post("/api/offerings/sections/semester", headers=ah, json={**body, "semester": 9}).status_code == 422
    # instructors cannot create offerings
    ih = login(client, make_user("instructor").email)
    assert client.post("/api/offerings/sections/semester", headers=ih, json=body).status_code == 403
