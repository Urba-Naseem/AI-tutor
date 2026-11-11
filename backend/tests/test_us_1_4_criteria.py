"""US-1.4 Configure attainment criteria."""
import time

from app.db import utcnow

from .helpers import approve_curriculum, as_role


def eff(client, h, course_id, at=None):
    url = f"/api/criteria/effective/course/{course_id}" + (f"?at={at.isoformat()}" if at else "")
    return {c["clo_code"]: c for c in client.get(url, headers=h).json()["clos"]}


def test_default_is_60_percent(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    e = eff(client, h, courses["CS101"]["id"])
    assert all(c["threshold"] == 60.0 and c["scope_key"] == "global" for c in e.values())


def test_scoped_overrides_most_specific_wins(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    cs101 = courses["CS101"]
    prog_id = client.get(f"/api/outcomes/courses/{cs101['id']}", headers=h).json()["program_id"]
    assert client.post("/api/criteria", headers=h, json={"scope_type": "program", "ref_id": prog_id, "threshold": 65, "reason": "Programme policy"}).status_code == 201
    client.post("/api/criteria", headers=h, json={"scope_type": "course", "ref_id": cs101["id"], "threshold": 70, "reason": "Core course"})
    clo3 = next(o for o in cs101["clos"] if o["code"] == "CLO3")
    client.post("/api/criteria", headers=h, json={"scope_type": "clo", "ref_id": clo3["id"], "threshold": 80, "reason": "Critical skill"})
    e = eff(client, h, cs101["id"])
    assert e["CLO3"]["threshold"] == 80 and e["CLO3"]["scope_key"] == "clo:CS101/CLO3"
    assert e["CLO1"]["threshold"] == 70 and e["CLO1"]["scope_key"] == "course:CS101"
    assert eff(client, h, courses["CS201"]["id"])["CLO1"]["threshold"] == 65
    chain = e["CLO3"]["chain"]
    assert [c["level"] for c in chain] == ["clo", "course", "program", "global"]


def test_changes_are_versioned_and_reproducible_at_past_time(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    cid = courses["CS101"]["id"]
    client.post("/api/criteria", headers=h, json={"scope_type": "course", "ref_id": cid, "threshold": 70, "reason": "v1 policy"})
    time.sleep(0.01)
    moment = utcnow()
    time.sleep(0.01)
    client.post("/api/criteria", headers=h, json={"scope_type": "course", "ref_id": cid, "threshold": 75, "reason": "v2 policy"})
    assert eff(client, h, cid)["CLO1"]["threshold"] == 75
    past = eff(client, h, cid, moment)["CLO1"]
    assert past["threshold"] == 70 and past["version_no"] == 1
    hist = [r for r in client.get("/api/criteria", headers=h).json()["history"] if r["scope_key"] == "course:CS101"]
    assert [r["version_no"] for r in hist] == [2, 1] and hist[1]["superseded_at"]


def test_removing_override_falls_back_but_keeps_history(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    cid = courses["CS101"]["id"]
    client.post("/api/criteria", headers=h, json={"scope_type": "course", "ref_id": cid, "threshold": 70, "reason": "temporary"})
    assert client.post(f"/api/criteria/remove/course/{cid}", headers=h, json={"reason": "policy withdrawn"}).status_code == 200
    assert eff(client, h, cid)["CLO1"]["threshold"] == 60
    assert len([r for r in client.get("/api/criteria", headers=h).json()["history"] if r["scope_key"] == "course:CS101"]) == 2


def test_global_default_can_change_but_not_be_removed(client):
    _, h = as_role(client, "admin")
    courses = approve_curriculum(client, h)
    client.post("/api/criteria", headers=h, json={"scope_type": "global", "threshold": 55, "reason": "Senate decision"})
    assert eff(client, h, courses["CS101"]["id"])["CLO1"]["threshold"] == 55
    assert client.post("/api/criteria/remove/global/0", headers=h, json={"reason": "x"}).status_code == 409


def test_validation_reason_and_range(client):
    _, h = as_role(client, "admin")
    assert client.post("/api/criteria", headers=h, json={"scope_type": "global", "threshold": 150, "reason": "too high"}).status_code == 422
    assert client.post("/api/criteria", headers=h, json={"scope_type": "global", "threshold": 50, "reason": ""}).status_code == 422


def test_changes_audited_and_restricted(client):
    _, h = as_role(client, "admin")
    client.post("/api/criteria", headers=h, json={"scope_type": "global", "threshold": 62, "reason": "Board vote"})
    ev = client.get("/api/audit?action=criteria.changed", headers=h).json()["items"][0]
    assert ev["details"]["before"] == 60 and ev["details"]["after"] == 62
    _, ih = as_role(client, "instructor")
    assert client.post("/api/criteria", headers=ih, json={"scope_type": "global", "threshold": 50, "reason": "nope nope"}).status_code == 403
