"""API happy-path tests for multi-agent lifecycle + evaluation."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_e2e_pipeline_critic_metrics_export():
    r = client.post(
        "/api/projects",
        json={
            "name": "Demo Campus Events",
            "brief": "Students discover campus events, RSVP, and get reminders.",
            "goals": ["Ship MVP in 8 weeks"],
            "constraints": ["Team of 3"],
        },
    )
    assert r.status_code == 201
    project = r.json()
    pid = project["id"]

    # Backlog via multi-agent pipeline
    r = client.post(
        f"/api/projects/{pid}/ai/generate-backlog",
        json={"replace": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["epics"]) >= 3
    assert body["rationale"]
    assert body.get("pipeline") is not None
    assert "steps" in body["pipeline"]
    assert body.get("critic") is not None
    assert "findings" in body["critic"]
    assert "summary" in body["critic"]
    assert body.get("metrics_preview") is not None
    assert "ac_coverage" in body["metrics_preview"]

    stories = client.get(f"/api/projects/{pid}/stories").json()
    assert len(stories) >= 5
    sid = stories[0]["id"]

    # User edit is source of truth
    r = client.patch(
        f"/api/projects/{pid}/stories/{sid}",
        json={
            "status": "in_progress",
            "points": 5,
            "title": "As a developer, I want a scaffold so that the team can start",
            "acceptance_criteria": ["Repo exists", "Health returns 200"],
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"
    assert r.json()["points"] == 5

    # Critic on persisted data
    r = client.post(f"/api/projects/{pid}/ai/critique")
    assert r.status_code == 200
    critique = r.json()
    assert "findings" in critique
    assert "summary" in critique
    assert critique["agent"] == "critic"
    assert critique["rationale"]

    # Evaluation metrics
    r = client.get(f"/api/projects/{pid}/ai/evaluate")
    assert r.status_code == 200
    metrics = r.json()
    assert "ac_coverage" in metrics
    assert metrics["ac_coverage"]["total_stories"] == len(stories)
    assert 0 <= metrics["ac_coverage"]["coverage_pct"] <= 100
    assert "invest" in metrics
    assert "average_score" in metrics["invest"]
    assert "board" in metrics
    assert metrics["rationale"]

    # Sprint plan with critic
    r = client.post(
        f"/api/projects/{pid}/sprints",
        json={"name": "Sprint 1", "capacity_points": 15, "goal": "First slice"},
    )
    assert r.status_code == 201
    sprint_id = r.json()["id"]

    r = client.post(
        f"/api/projects/{pid}/ai/plan-sprint",
        json={"sprint_id": sprint_id, "apply": True},
    )
    assert r.status_code == 200
    plan = r.json()
    assert plan["total_points"] <= 15
    assert plan["rationale"]
    assert plan.get("pipeline") is not None
    assert plan.get("critic") is not None

    # Standup with metrics snapshot
    r = client.post(f"/api/projects/{pid}/ai/standup")
    assert r.status_code == 200
    standup = r.json()
    assert "Standup" in standup["summary"]
    assert standup.get("pipeline") is not None
    assert standup.get("metrics_snapshot") is not None

    # Evaluation after sprint assignment includes sprint metrics
    r = client.get(f"/api/projects/{pid}/ai/evaluate")
    assert r.status_code == 200
    metrics2 = r.json()
    assert isinstance(metrics2["sprints"], list)
    assert len(metrics2["sprints"]) >= 1
    spm = metrics2["sprints"][0]
    assert "planned_points" in spm
    assert "completed_points" in spm
    assert "remaining_points" in spm

    r = client.get(f"/api/projects/{pid}/export?format=markdown")
    assert r.status_code == 200
    assert "Demo Campus Events" in r.text

    import json

    r = client.get(f"/api/projects/{pid}/export?format=json")
    assert r.status_code == 200
    payload = json.loads(r.text)
    assert payload["project"]["name"] == "Demo Campus Events"
    assert len(payload["epics"]) >= 1


def test_user_edit_not_silently_overwritten_on_critique():
    r = client.post(
        "/api/projects",
        json={"name": "Edit Guard", "brief": "Test human-in-the-loop"},
    )
    pid = r.json()["id"]
    client.post(
        f"/api/projects/{pid}/ai/generate-backlog",
        json={"replace": True},
    )
    stories = client.get(f"/api/projects/{pid}/stories").json()
    sid = stories[0]["id"]
    custom = "USER CUSTOM TITLE THAT MUST REMAIN"
    client.patch(
        f"/api/projects/{pid}/stories/{sid}",
        json={"title": custom, "acceptance_criteria": ["User wrote this AC"]},
    )
    # Critique must not change story
    client.post(f"/api/projects/{pid}/ai/critique")
    after = client.get(f"/api/projects/{pid}/stories/{sid}").json()
    assert after["title"] == custom
    assert after["acceptance_criteria"] == ["User wrote this AC"]
