"""US-1.2 Review and approve parsed outcomes."""
from .helpers import approve_curriculum, as_role, start_review


def test_start_review_materialises_structure(client):
    _, h = as_role(client, "admin")
    rv = start_review(client, h)
    assert rv["version"]["status"] == "in_review"
    assert len(rv["plos"]) == 4 and [c["code"] for c in rv["courses"]] == ["CS101", "CS201", "MATH110"]
    cs101 = rv["courses"][0]
    assert len(cs101["units"]) == 3 and len(cs101["clos"]) == 5 and all(o["unit_id"] for o in cs101["clos"])


def test_ambiguous_items_flagged_and_block_approval(client):
    _, h = as_role(client, "admin")
    rv = start_review(client, h)
    flagged = [i for i in rv["issues"] if i["level"] == "warning"]
    assert any("MATH110 CLO2" in i["message"] for i in flagged)
    assert rv["can_approve"] is False
    r = client.post(f"/api/outcomes/versions/{rv['version']['id']}/approve", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["warnings"]


def test_correcting_missing_unit_assignment_clears_error(client):
    _, h = as_role(client, "admin")
    rv = start_review(client, h)
    vid = rv["version"]["id"]
    cs201 = next(c for c in rv["courses"] if c["code"] == "CS201")
    clo = cs201["clos"][0]
    # deleting the unit leaves its CLO without a unit -> blocking error
    client.delete(f"/api/outcomes/units/{cs201['units'][0]['id']}", headers=h)
    issues = client.get(f"/api/outcomes/versions/{vid}", headers=h).json()["issues"]
    assert any(i["level"] == "error" and "CS201 CLO1 is not assigned" in i["message"] for i in issues)
    new_unit = client.post(f"/api/outcomes/courses/{cs201['id']}/units", headers=h, json={"number": 1, "title": "Algorithm Analysis"}).json()
    client.patch(f"/api/outcomes/clos/{clo['id']}", headers=h, json={"unit_id": new_unit["id"]})
    issues = client.get(f"/api/outcomes/versions/{vid}", headers=h).json()["issues"]
    assert not any("CS201 CLO1 is not assigned" in i["message"] for i in issues)


def test_add_missing_course_plo_and_clo(client):
    _, h = as_role(client, "admin")
    rv = start_review(client, h)
    vid = rv["version"]["id"]
    assert client.post(f"/api/outcomes/programs/{rv['program']['id']}/plos", headers=h, json={"code": "plo 5", "description": "Work effectively in teams on computing projects."}).status_code == 201
    cid = client.post(f"/api/outcomes/versions/{vid}/courses", headers=h, json={"code": "cs 301", "title": "Databases", "credits": 3}).json()["id"]
    issues = client.get(f"/api/outcomes/versions/{vid}", headers=h).json()["issues"]
    assert any("CS301 has no CLOs" in i["message"] for i in issues)
    uid = client.post(f"/api/outcomes/courses/{cid}/units", headers=h, json={"title": "Relational model"}).json()["id"]
    client.post(f"/api/outcomes/courses/{cid}/clos", headers=h, json={"description": "Design normalised relational schemas for a domain.", "unit_id": uid})
    data = client.get(f"/api/outcomes/versions/{vid}", headers=h).json()
    assert any(p["code"] == "PLO5" for p in data["plos"])
    assert not any("CS301" in i["message"] and i["level"] == "error" for i in data["issues"])


def test_acknowledge_warning_requires_reason_then_approve(client):
    _, h = as_role(client, "admin")
    rv = start_review(client, h)
    vid = rv["version"]["id"]
    w = next(i for i in rv["issues"] if i["level"] == "warning")
    assert client.post(f"/api/outcomes/versions/{vid}/ack", headers=h, json={"issue_key": w["key"], "note": ""}).status_code == 422
    assert client.post(f"/api/outcomes/versions/{vid}/ack", headers=h, json={"issue_key": w["key"], "note": "Confirmed with programme lead"}).status_code == 200
    r = client.post(f"/api/outcomes/versions/{vid}/approve", headers=h)
    assert r.status_code == 200 and r.json()["version"]["status"] == "approved"
    assert all(c["status"] == "approved" for c in r.json()["courses"])


def test_approved_version_is_locked_and_audited(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    clo = courses["CS101"]["clos"][0]
    assert client.patch(f"/api/outcomes/clos/{clo['id']}", headers=h, json={"description": "changed after approval"}).status_code == 409
    acts = [e["action"] for e in client.get("/api/audit?action=outcomes", headers=h).json()["items"]]
    assert {"outcomes.review_started", "outcomes.clo.updated", "outcomes.approved"} <= set(acts)


def test_edit_audit_records_before_and_after(client):
    _, h = as_role(client, "admin")
    rv = start_review(client, h)
    c = rv["courses"][0]
    client.patch(f"/api/outcomes/courses/{c['id']}", headers=h, json={"title": "Programming I"})
    ev = client.get("/api/audit?action=outcomes.course.updated", headers=h).json()["items"][0]
    assert ev["details"]["title"] == {"before": "Introduction to Programming", "after": "Programming I"}


def test_new_version_supersedes_previous_approval(client):
    from .helpers import SAMPLE_MD, upload_curriculum

    _, h = as_role(client, "admin")
    approve_curriculum(client, h)
    v2 = upload_curriculum(client, h, SAMPLE_MD.replace(b"Proofs.", b"Construct direct proofs for simple mathematical statements."))
    client.post(f"/api/outcomes/versions/{v2['id']}/start-review", headers=h)
    r = client.post(f"/api/outcomes/versions/{v2['id']}/approve", headers=h)
    assert r.status_code == 200, r.text
    statuses = {v["version_no"]: v["status"] for v in client.get("/api/curriculum/versions", headers=h).json()}
    assert statuses == {2: "approved", 1: "superseded"}


def test_students_cannot_edit_outcomes(client):
    _, ah = as_role(client, "admin")
    rv = start_review(client, ah)
    _, sh = as_role(client, "student")
    assert client.patch(f"/api/outcomes/courses/{rv['courses'][0]['id']}", headers=sh, json={"title": "x"}).status_code == 403


NO_UNITS = b"""# Program: BSSE - Bachelor of Software Engineering

## Programme Learning Outcomes
- PLO1: Apply software engineering principles to design reliable systems.
- PLO2: Communicate technical decisions clearly to stakeholders.

## Course: SE101 - Software Construction
Credits: 3
Prerequisites: None

### Course Learning Outcomes
- CLO1: Write well-structured programs using appropriate design principles.
- CLO2: Test programs systematically using unit testing frameworks.
"""


def test_curriculum_without_units_is_reviewable(client):
    _, h = as_role(client, "admin")
    r = client.post("/api/curriculum/upload", headers=h, files={"file": ("bsse.md", NO_UNITS)})
    assert r.status_code == 201 and r.json()["summary"]["errors"] == 0
    rv = client.post(f"/api/outcomes/versions/{r.json()['id']}/start-review", headers=h).json()
    se = rv["courses"][0]
    assert se["units"][0]["title"] == "Course content" and all(o["unit_id"] for o in se["clos"])
    vid = rv["version"]["id"]
    # a document without any units: one information note, nothing to accept
    assert any("lists no units" in i["message"] and i["level"] == "info" for i in rv["issues"])
    assert client.post(f"/api/outcomes/versions/{vid}/ack-all", headers=h, json={"note": "No"}).status_code == 422
    assert client.post(f"/api/outcomes/versions/{vid}/ack-all", headers=h, json={"note": "Units added later by faculty"}).status_code == 200
    assert client.post(f"/api/outcomes/versions/{vid}/approve", headers=h).status_code == 200
