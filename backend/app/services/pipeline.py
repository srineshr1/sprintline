"""Multi-agent lifecycle pipeline: draft → critic → plan → summarize.

Orchestrates agent functions (Groq when configured, else stubs). Callers decide
whether to persist/apply; pipeline never silently overwrites user-edited DB state.
"""

from __future__ import annotations

from typing import Any, Optional

from . import ai_agents, critic, evaluation


def run_backlog_pipeline(
    name: str,
    brief: str,
    goals: list[str],
    constraints: list[str],
    *,
    source_path: Optional[str] = None,
) -> dict[str, Any]:
    """Intake + backlog draft + critic quality pass.

    Returns epics (from backlog agent), critic report, pipeline rationale.
    When ``source_path`` is set, key repository files are packed and sent to the LLM.
    """
    draft = ai_agents.generate_backlog(
        name, brief, goals, constraints, source_path=source_path
    )
    flat_stories: list[dict[str, Any]] = []
    for i, epic in enumerate(draft.get("epics") or []):
        for j, st in enumerate(epic.get("stories") or []):
            s = dict(st)
            s.setdefault("id", f"draft-{i}-{j}")
            flat_stories.append(s)

    critique = critic.critique_backlog(flat_stories)
    eval_preview = evaluation.ac_coverage(flat_stories)
    invest_preview = evaluation.invest_scores(flat_stories)

    agent = draft.get("agent", "backlog")
    files_n = 0
    ctx = draft.get("codebase_context") or {}
    if isinstance(ctx, dict):
        files_n = int(ctx.get("file_count") or 0)

    pipeline_rationale = (
        f"[pipeline] {agent} drafted {len(draft.get('epics') or [])} epics / "
        f"{len(flat_stories)} stories"
        + (f" using {files_n} repo file(s)" if files_n else "")
        + f"; critic flagged {critique['summary']['errors']} errors, "
        f"{critique['summary']['warnings']} warnings; "
        f"AC coverage preview {eval_preview['coverage_pct']}%; "
        f"INVEST preview {invest_preview['average_pct']}%. "
        f"User must review before treating as final (human-in-the-loop)."
    )

    return {
        "epics": draft.get("epics") or [],
        "rationale": draft.get("rationale", ""),
        "agent": agent,
        "pipeline": {
            "steps": ["intake", "codebase_pack", "backlog_draft", "critic", "eval_preview"],
            "rationale": pipeline_rationale,
        },
        "critic": critique,
        "metrics_preview": {
            "ac_coverage": eval_preview,
            "invest_average_pct": invest_preview["average_pct"],
            "invest_rationale": invest_preview["rationale"],
        },
        "codebase_context": draft.get("codebase_context"),
        "llm_error": draft.get("llm_error"),
    }


def run_sprint_pipeline(
    stories: list[dict[str, Any]],
    capacity_points: int,
    sprint_name: str = "Sprint",
) -> dict[str, Any]:
    """Sprint selection + capacity critic."""
    plan = ai_agents.plan_sprint(stories, capacity_points, sprint_name)
    selected = plan.get("stories") or []
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
    story_critique = critic.critique_backlog(resolved)

    agent = plan.get("agent", "sprint")
    pipeline_rationale = (
        f"[pipeline] {agent} selected {len(plan.get('suggested_story_ids') or [])} "
        f"stories ({plan.get('total_points')}/{capacity_points} pts); "
        f"capacity critic: {cap_critique['summary'].get('errors', 0)} error(s); "
        f"selected-story critic: {story_critique['summary']['errors']} error(s), "
        f"{story_critique['summary']['warnings']} warning(s)."
    )

    merged_findings = list(cap_critique.get("findings") or [])
    merged_findings.extend(story_critique.get("findings") or [])

    return {
        "suggested_story_ids": plan.get("suggested_story_ids") or [],
        "total_points": plan.get("total_points") or 0,
        "rationale": plan.get("rationale", ""),
        "stories": resolved,
        "agent": agent,
        "pipeline": {
            "steps": ["llm_or_priority_select", "capacity_check", "critic"],
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
        "llm_error": plan.get("llm_error"),
    }


def run_standup_pipeline(
    stories: list[dict[str, Any]],
    project_name: str,
    recent_events: list[str] | None = None,
    sprints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Standup summary + board quality notes + optional sprint metrics snippet."""
    summary = ai_agents.standup_summary(stories, project_name, recent_events)
    board_critique = critic.critique_backlog(
        [s for s in stories if (s.get("status") or "") != "done"]
    )
    open_findings = [
        f
        for f in board_critique.get("findings") or []
        if f.get("severity") in ("error", "warning")
    ][:15]

    eval_bundle = evaluation.evaluate_project(stories, sprints)
    agent = summary.get("agent", "standup")

    pipeline_rationale = (
        f"[pipeline] {agent} drafted status from board; "
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
