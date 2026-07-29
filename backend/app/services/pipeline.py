"""Multi-agent lifecycle pipeline: draft → critic → plan → summarize.

Orchestrates pure agent functions. Callers decide whether to persist/apply;
pipeline never silently overwrites user-edited DB state.
"""

from __future__ import annotations

from typing import Any

from . import ai_stub, critic, evaluation


def run_backlog_pipeline(
    name: str,
    brief: str,
    goals: list[str],
    constraints: list[str],
) -> dict[str, Any]:
    """Intake + backlog draft + critic quality pass.

    Returns epics (from backlog agent), critic report, pipeline rationale.
    """
    draft = ai_stub.generate_backlog(name, brief, goals, constraints)
    flat_stories: list[dict[str, Any]] = []
    for i, epic in enumerate(draft.get("epics") or []):
        for j, st in enumerate(epic.get("stories") or []):
            # Temporary synthetic ids for critic before DB assign
            s = dict(st)
            s.setdefault("id", f"draft-{i}-{j}")
            flat_stories.append(s)

    critique = critic.critique_backlog(flat_stories)
    eval_preview = evaluation.ac_coverage(flat_stories)
    invest_preview = evaluation.invest_scores(flat_stories)

    pipeline_rationale = (
        f"[pipeline] backlog_stub drafted {len(draft.get('epics') or [])} epics / "
        f"{len(flat_stories)} stories; critic flagged "
        f"{critique['summary']['errors']} errors, "
        f"{critique['summary']['warnings']} warnings; "
        f"AC coverage preview {eval_preview['coverage_pct']}%; "
        f"INVEST preview {invest_preview['average_pct']}%. "
        f"User must review before treating as final (human-in-the-loop)."
    )

    return {
        "epics": draft.get("epics") or [],
        "rationale": draft.get("rationale", ""),
        "agent": draft.get("agent", "backlog_stub"),
        "pipeline": {
            "steps": ["intake", "backlog_draft", "critic", "eval_preview"],
            "rationale": pipeline_rationale,
        },
        "critic": critique,
        "metrics_preview": {
            "ac_coverage": eval_preview,
            "invest_average_pct": invest_preview["average_pct"],
            "invest_rationale": invest_preview["rationale"],
        },
    }


def run_sprint_pipeline(
    stories: list[dict[str, Any]],
    capacity_points: int,
    sprint_name: str = "Sprint",
) -> dict[str, Any]:
    """Sprint selection + capacity critic."""
    plan = ai_stub.plan_sprint(stories, capacity_points, sprint_name)
    selected = plan.get("stories") or []
    # If stories in plan lack full fields, resolve from input by id
    by_id = {s.get("id"): s for s in stories}
    resolved = []
    for s in selected:
        full = by_id.get(s.get("id"), s)
        resolved.append(full)

    cap_critique = critic.critique_sprint_capacity(
        resolved,
        capacity_points,
        total_points=plan.get("total_points"),
    )

    # Also soft-critique backlog quality for selected items
    story_critique = critic.critique_backlog(resolved)

    pipeline_rationale = (
        f"[pipeline] sprint_stub selected {len(plan.get('suggested_story_ids') or [])} "
        f"stories ({plan.get('total_points')}/{capacity_points} pts); "
        f"capacity critic: {cap_critique['summary'].get('errors', 0)} error(s); "
        f"selected-story critic: {story_critique['summary']['errors']} error(s), "
        f"{story_critique['summary']['warnings']} warning(s)."
    )

    # Merge findings (capacity first)
    merged_findings = list(cap_critique.get("findings") or [])
    # Avoid double-counting capacity-only codes from story pass
    merged_findings.extend(story_critique.get("findings") or [])

    return {
        "suggested_story_ids": plan.get("suggested_story_ids") or [],
        "total_points": plan.get("total_points") or 0,
        "rationale": plan.get("rationale", ""),
        "stories": resolved,
        "agent": plan.get("agent", "sprint_stub"),
        "pipeline": {
            "steps": ["priority_select", "capacity_check", "critic"],
            "rationale": pipeline_rationale,
        },
        "critic": {
            "findings": merged_findings,
            "summary": {
                "planned_points": plan.get("total_points") or 0,
                "capacity_points": capacity_points,
                "errors": sum(1 for f in merged_findings if f.get("severity") == "error"),
                "warnings": sum(
                    1 for f in merged_findings if f.get("severity") == "warning"
                ),
            },
            "rationale": cap_critique.get("rationale", "")
            + " "
            + story_critique.get("rationale", ""),
            "agent": "critic",
        },
    }


def run_standup_pipeline(
    stories: list[dict[str, Any]],
    project_name: str,
    recent_events: list[str] | None = None,
    sprints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Standup summary + board quality notes + optional sprint metrics snippet."""
    summary = ai_stub.standup_summary(stories, project_name, recent_events)
    board_critique = critic.critique_backlog(
        [s for s in stories if (s.get("status") or "") != "done"]
    )
    # Only surface errors/warnings for open work
    open_findings = [
        f
        for f in board_critique.get("findings") or []
        if f.get("severity") in ("error", "warning")
    ][:15]

    eval_bundle = evaluation.evaluate_project(stories, sprints)

    pipeline_rationale = (
        f"[pipeline] standup_stub drafted status from board; "
        f"{len(open_findings)} open quality flag(s) on incomplete work; "
        f"eval AC {eval_bundle['ac_coverage']['coverage_pct']}% / "
        f"INVEST {eval_bundle['invest']['average_pct']}%."
    )

    return {
        **summary,
        "pipeline": {
            "steps": ["board_scan", "summarize", "critic_open_work", "metrics_snapshot"],
            "rationale": pipeline_rationale,
        },
        "critic": {
            "findings": open_findings,
            "summary": {
                "open_errors": sum(1 for f in open_findings if f["severity"] == "error"),
                "open_warnings": sum(
                    1 for f in open_findings if f["severity"] == "warning"
                ),
            },
            "rationale": (
                "Open (non-done) stories re-checked for missing AC / vague titles during standup."
            ),
            "agent": "critic",
        },
        "metrics_snapshot": {
            "ac_coverage_pct": eval_bundle["ac_coverage"]["coverage_pct"],
            "invest_average_pct": eval_bundle["invest"]["average_pct"],
            "board": eval_bundle["board"],
        },
    }


def run_critic_only(stories: list[dict[str, Any]]) -> dict[str, Any]:
    """Standalone critic endpoint body."""
    return critic.critique_backlog(stories)


def run_evaluation(
    stories: list[dict[str, Any]],
    sprints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Standalone evaluation endpoint body."""
    return evaluation.evaluate_project(stories, sprints)
