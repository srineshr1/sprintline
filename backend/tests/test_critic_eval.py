"""Unit tests for critic + evaluation pure logic (real shipped functions)."""

from app.services import critic, evaluation, pipeline


def _good_story(**overrides):
    base = {
        "id": 1,
        "title": "As a student, I want to RSVP to events so that organizers know attendance",
        "description": "RSVP flow with confirmation email.",
        "acceptance_criteria": [
            "User can RSVP from event detail page",
            "Organizer sees updated count",
            "Confirmation email is sent",
        ],
        "points": 5,
        "priority": "high",
        "status": "todo",
        "rationale": "Core user value for the campus events brief.",
    }
    base.update(overrides)
    return base


def test_critique_missing_ac_is_error():
    findings = critic.critique_story(
        _good_story(acceptance_criteria=[], title="As a user I want login so that I can access")
    )
    codes = {f["code"] for f in findings}
    assert "missing_ac" in codes
    assert any(f["severity"] == "error" for f in findings if f["code"] == "missing_ac")


def test_critique_empty_title_is_error():
    findings = critic.critique_story(_good_story(title=""))
    assert any(f["code"] == "empty_title" and f["severity"] == "error" for f in findings)


def test_critique_good_story_has_no_errors():
    findings = critic.critique_story(_good_story())
    errors = [f for f in findings if f["severity"] == "error"]
    assert errors == []


def test_critique_vague_and_large_story():
    findings = critic.critique_story(
        {
            "id": 9,
            "title": "Fix stuff",
            "description": "",
            "acceptance_criteria": ["ok"],
            "points": 21,
            "priority": "medium",
        }
    )
    codes = {f["code"] for f in findings}
    assert "vague_title" in codes or "title_too_short" in codes
    assert "large_story" in codes
    assert "thin_ac" in codes


def test_capacity_overload_flagged():
    stories = [_good_story(id=1, points=8), _good_story(id=2, points=8)]
    report = critic.critique_sprint_capacity(stories, capacity_points=10, total_points=16)
    assert any(f["code"] == "capacity_overload" for f in report["findings"])
    assert report["summary"]["errors"] >= 1


def test_capacity_ok_no_overload():
    stories = [_good_story(id=1, points=5)]
    report = critic.critique_sprint_capacity(stories, capacity_points=20, total_points=5)
    assert not any(f["code"] == "capacity_overload" for f in report["findings"])


def test_ac_coverage_changes_with_input():
    good = _good_story(id=1)
    bad = _good_story(id=2, acceptance_criteria=[])
    cov_all = evaluation.ac_coverage([good, good])
    cov_mixed = evaluation.ac_coverage([good, bad])
    cov_none = evaluation.ac_coverage([bad, bad])
    assert cov_all["coverage_pct"] == 100.0
    assert cov_mixed["coverage_pct"] == 50.0
    assert cov_none["coverage_pct"] == 0.0
    assert cov_mixed["with_ac"] == 1
    assert cov_none["without_ac"] == 2


def test_invest_score_higher_for_good_story():
    good = evaluation.invest_score_story(_good_story())
    weak = evaluation.invest_score_story(
        {
            "id": 3,
            "title": "x",
            "description": "",
            "acceptance_criteria": [],
            "points": 0,
            "priority": "medium",
        }
    )
    assert good["score"] > weak["score"]
    assert good["checks"]["testable"] is True
    assert weak["checks"]["testable"] is False
    assert good["checks"]["estimable"] is True


def test_sprint_points_metrics_planned_done_remaining():
    stories = [
        _good_story(id=1, points=5, status="done"),
        _good_story(id=2, points=3, status="in_progress"),
        _good_story(id=3, points=8, status="todo"),
    ]
    sprint = {
        "id": 1,
        "name": "Sprint 1",
        "capacity_points": 20,
        "items": [
            {"story_id": 1, "story": stories[0]},
            {"story_id": 2, "story": stories[1]},
            {"story_id": 3, "story": stories[2]},
        ],
    }
    m = evaluation.sprint_points_metrics(sprint)
    assert m["planned_points"] == 16
    assert m["completed_points"] == 5
    assert m["remaining_points"] == 11  # 3 + 8
    assert m["in_progress_points"] == 3
    assert m["capacity_points"] == 20
    assert m["utilization_pct"] == 80.0


def test_backlog_pipeline_returns_critic_and_metrics():
    out = pipeline.run_backlog_pipeline(
        "Campus Events",
        "Students discover events and RSVP",
        ["Ship MVP"],
        ["Team of 3"],
    )
    assert out["epics"]
    assert out["rationale"]
    assert out["critic"]["findings"] is not None
    assert "summary" in out["critic"]
    assert out["pipeline"]["steps"]
    assert "ac_coverage" in out["metrics_preview"]
    assert out["metrics_preview"]["ac_coverage"]["coverage_pct"] >= 0


def test_sprint_pipeline_respects_capacity():
    stories = [
        _good_story(id=i, points=5, priority="high" if i < 3 else "low")
        for i in range(1, 8)
    ]
    out = pipeline.run_sprint_pipeline(stories, capacity_points=12, sprint_name="S1")
    assert out["total_points"] <= 12
    assert out["critic"]["summary"]["capacity_points"] == 12
    assert "pipeline" in out


def test_evaluation_bundle():
    stories = [
        _good_story(id=1, status="done", points=5),
        _good_story(id=2, acceptance_criteria=[], status="todo", points=3),
    ]
    sprints = [
        {
            "id": 1,
            "name": "S1",
            "capacity_points": 10,
            "items": [
                {"story_id": 1, "story": stories[0]},
                {"story_id": 2, "story": stories[1]},
            ],
        }
    ]
    bundle = evaluation.evaluate_project(stories, sprints)
    assert bundle["ac_coverage"]["coverage_pct"] == 50.0
    assert bundle["invest"]["average_score"] > 0
    assert len(bundle["sprints"]) == 1
    assert bundle["sprints"][0]["completed_points"] == 5
    assert bundle["board"]["status_counts"]["done"] == 1
