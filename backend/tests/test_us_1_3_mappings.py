"""US-1.3 Approve CLO-PLO mappings."""
from app.services import llm

from .helpers import activate_course, approve_curriculum, as_role, instructor_for, login, make_user, setup_offering, start_review


def test_activation_blocked_when_mapping_incomplete(client):
    _, ah = as_role(client, "admin")
    courses = approve_curriculum(client, ah)
    cid = courses["MATH110"]["id"]  # the document gives no mappings for this course
    _, h = instructor_for(client, ah, cid)
    r = client.post(f"/api/courses/{cid}/activate", headers=h)
    assert r.status_code == 409 and "CLO1, CLO2, CLO3" in r.json()["detail"]["blockers"][0]
    cov = client.get(f"/api/mappings/course/{cid}", headers=h).json()
    assert cov["complete"] is False and cov["unmapped_clos"] == ["CLO1", "CLO2", "CLO3"]


def test_document_mappings_are_suggestions_until_approved(client):
    _, ah = as_role(client, "admin")
    courses = approve_curriculum(client, ah)
    cid = courses["CS101"]["id"]
    _, h = instructor_for(client, ah, cid)
    cov = client.post(f"/api/mappings/course/{cid}/import-document", headers=h).json()
    assert len(cov["mappings"]) == 6 and all(m["status"] == "suggested" for m in cov["mappings"])
    assert cov["unmapped_clos"] == ["CLO1", "CLO2", "CLO3", "CLO4", "CLO5"]
    assert client.post(f"/api/courses/{cid}/activate", headers=h).status_code == 409


def test_full_coverage_allows_activation_and_locks(client):
    _, ah = as_role(client, "admin")
    courses = approve_curriculum(client, ah)
    cid = courses["CS101"]["id"]
    _, h = instructor_for(client, ah, cid)
    cov = activate_course(client, h, cid)
    assert cov["course"]["status"] == "active"
    assert client.post(f"/api/mappings/course/{cid}/suggest", headers=h).status_code == 409
    assert "PLO4" in cov["uncovered_plos"]  # reported for the programme roll-up


def test_ai_suggestions_offline_are_routed_for_review(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    cid = courses["MATH110"]["id"]
    inst = make_user("instructor")
    setup_offering(client, h, cid, inst)
    ih = login(client, inst.email)
    r = client.post(f"/api/mappings/course/{cid}/suggest", headers=ih).json()
    assert r["origin"] == "offline" and r["suggested"] >= 1
    tasks = client.get("/api/reviews?kind=mapping", headers=ih).json()
    assert len(tasks) == r["suggested"]


def test_ai_suggestions_live(client, monkeypatch):
    _, ah = as_role(client, "admin")
    courses = approve_curriculum(client, ah)
    cid = courses["MATH110"]["id"]
    _, h = instructor_for(client, ah, cid)
    monkeypatch.setattr(llm, "generate", lambda *a, **k: llm.LLMResult(
        '{"mappings":[{"clo":"CLO1","plo":"PLO1","strength":3,"rationale":"logic underpins computing"}]}', "gemini-test", 1, 1, 1))
    r = client.post(f"/api/mappings/course/{cid}/suggest", headers=h).json()
    assert r["origin"] == "ai" and r["mappings"][0]["rationale"] == "logic underpins computing"
    mid = r["mappings"][0]["id"]
    r = client.post(f"/api/mappings/{mid}/decide", headers=h, json={"decision": "approve", "strength": 2}).json()
    assert r["mappings"][0]["status"] == "approved" and r["mappings"][0]["strength"] == 2
    assert client.get("/api/reviews?kind=mapping", headers=h).json() == []


def test_cannot_map_before_outcomes_approved(client):
    _, ah = as_role(client, "admin")
    rv = start_review(client, ah)
    # no section (so no instructor) can exist before approval, and an admin cannot map at all: mappings are
    # instructor work
    assert client.post(f"/api/mappings/course/{rv['courses'][0]['id']}/import-document", headers=ah).status_code == 403


def test_program_rollup(client):
    _, ah = as_role(client, "admin")
    courses = approve_curriculum(client, ah)
    _, h = instructor_for(client, ah, courses["CS101"]["id"])
    activate_course(client, h, courses["CS101"]["id"])
    pid = client.get(f"/api/outcomes/courses/{courses['CS101']['id']}", headers=h).json()["program_id"]
    roll = {r["plo"]: r for r in client.get(f"/api/mappings/program/{pid}/rollup", headers=h).json()}
    assert {c["clo"] for c in roll["PLO1"]["contributions"]} == {"CLO1", "CLO2"}
    assert roll["PLO4"]["contributions"] == []
