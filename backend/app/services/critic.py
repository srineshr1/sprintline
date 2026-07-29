"""Critic agent: quality pass over backlog / sprint proposals.

Pure functions over plain dicts — no DB, no HTTP. Flags weak stories so humans
can improve AI drafts without silent overwrite of user edits.
"""

from __future__ import annotations

import re
from typing import Any


# Vague title signals (lowercased token match)
_VAGUE_TOKENS = {
    "stuff",
    "things",
    "handle",
    "fix",
    "update",
    "improve",
    "work",
    "misc",
    "various",
    "do",
    "make",
    "something",
    "etc",
}

_USER_STORY_RE = re.compile(
    r"as\s+a\s+.+\s+i\s+want\s+.+\s+so\s+that\s+.+",
    re.IGNORECASE | re.DOTALL,
)


def _ac_list(story: dict[str, Any]) -> list[str]:
    ac = story.get("acceptance_criteria") or []
    if isinstance(ac, str):
        try:
            import json

            parsed = json.loads(ac)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return [ac] if ac.strip() else []
    return list(ac) if isinstance(ac, list) else []


def critique_story(story: dict[str, Any]) -> list[dict[str, Any]]:
    """Return list of finding dicts for one story.

    Each finding: {code, severity, message, story_id?, field?}
    severity: error | warning | info
    """
    findings: list[dict[str, Any]] = []
    sid = story.get("id")
    title = (story.get("title") or "").strip()
    desc = (story.get("description") or "").strip()
    ac = [str(a).strip() for a in _ac_list(story) if str(a).strip()]
    points = story.get("points")
    priority = (story.get("priority") or "").lower()

    if not title:
        findings.append(
            {
                "code": "empty_title",
                "severity": "error",
                "message": "Story title is empty.",
                "story_id": sid,
                "field": "title",
            }
        )
    else:
        if len(title) < 12:
            findings.append(
                {
                    "code": "title_too_short",
                    "severity": "warning",
                    "message": f"Title is very short ({len(title)} chars); may be too vague.",
                    "story_id": sid,
                    "field": "title",
                }
            )
        tokens = set(re.findall(r"[a-zA-Z]+", title.lower()))
        if tokens & _VAGUE_TOKENS and len(tokens) <= 5:
            findings.append(
                {
                    "code": "vague_title",
                    "severity": "warning",
                    "message": "Title uses vague language without a clear outcome.",
                    "story_id": sid,
                    "field": "title",
                }
            )
        if not _USER_STORY_RE.search(title) and not _USER_STORY_RE.search(desc):
            findings.append(
                {
                    "code": "not_user_story_form",
                    "severity": "info",
                    "message": "Consider INVEST user-story form: As a … I want … so that …",
                    "story_id": sid,
                    "field": "title",
                }
            )

    if not ac:
        findings.append(
            {
                "code": "missing_ac",
                "severity": "error",
                "message": "No acceptance criteria — story is not testable.",
                "story_id": sid,
                "field": "acceptance_criteria",
            }
        )
    elif len(ac) < 2:
        findings.append(
            {
                "code": "thin_ac",
                "severity": "warning",
                "message": "Only one acceptance criterion; prefer 2–5 verifiable checks.",
                "story_id": sid,
                "field": "acceptance_criteria",
            }
        )

    if points is None:
        findings.append(
            {
                "code": "missing_points",
                "severity": "warning",
                "message": "Story points not set.",
                "story_id": sid,
                "field": "points",
            }
        )
    else:
        try:
            pts = int(points)
            if pts <= 0:
                findings.append(
                    {
                        "code": "invalid_points",
                        "severity": "warning",
                        "message": "Points should be a positive estimate.",
                        "story_id": sid,
                        "field": "points",
                    }
                )
            if pts > 13:
                findings.append(
                    {
                        "code": "large_story",
                        "severity": "warning",
                        "message": f"Large story ({pts} pts) — consider splitting (INVEST: small).",
                        "story_id": sid,
                        "field": "points",
                    }
                )
        except (TypeError, ValueError):
            findings.append(
                {
                    "code": "invalid_points",
                    "severity": "warning",
                    "message": "Points value is not a number.",
                    "story_id": sid,
                    "field": "points",
                }
            )

    if priority and priority not in ("high", "medium", "low"):
        findings.append(
            {
                "code": "unknown_priority",
                "severity": "info",
                "message": f"Unusual priority value: {priority}",
                "story_id": sid,
                "field": "priority",
            }
        )

    if not desc and title:
        findings.append(
            {
                "code": "missing_description",
                "severity": "info",
                "message": "No description beyond the title.",
                "story_id": sid,
                "field": "description",
            }
        )

    return findings


def critique_backlog(stories: list[dict[str, Any]]) -> dict[str, Any]:
    """Critique a full backlog of stories. Returns aggregated report."""
    all_findings: list[dict[str, Any]] = []
    by_story: dict[Any, list[dict[str, Any]]] = {}

    for s in stories:
        f = critique_story(s)
        all_findings.extend(f)
        key = s.get("id", id(s))
        by_story[key] = f

    errors = sum(1 for x in all_findings if x["severity"] == "error")
    warnings = sum(1 for x in all_findings if x["severity"] == "warning")
    infos = sum(1 for x in all_findings if x["severity"] == "info")

    stories_with_issues = sum(1 for f in by_story.values() if f)
    clean = len(stories) - stories_with_issues

    rationale = (
        f"Critic reviewed {len(stories)} stories: {errors} error(s), "
        f"{warnings} warning(s), {infos} info flag(s). "
        f"{clean}/{len(stories)} stories clean. "
        f"Common checks: empty title, missing AC, vague wording, oversized points. "
        f"Findings are advisory — user edits remain the source of truth."
    )

    return {
        "findings": all_findings,
        "summary": {
            "story_count": len(stories),
            "stories_with_findings": stories_with_issues,
            "clean_stories": clean,
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
        },
        "rationale": rationale,
        "agent": "critic",
    }


def critique_sprint_capacity(
    selected_stories: list[dict[str, Any]],
    capacity_points: int,
    total_points: int | None = None,
) -> dict[str, Any]:
    """Flag capacity overload / underload for a proposed sprint scope."""
    findings: list[dict[str, Any]] = []
    pts = (
        total_points
        if total_points is not None
        else sum(int(s.get("points") or 0) for s in selected_stories)
    )
    cap = int(capacity_points)

    if pts > cap:
        findings.append(
            {
                "code": "capacity_overload",
                "severity": "error",
                "message": f"Planned {pts} pts exceeds capacity {cap} pts.",
                "story_id": None,
                "field": "capacity",
            }
        )
    elif cap > 0 and pts == 0 and selected_stories == []:
        findings.append(
            {
                "code": "empty_sprint",
                "severity": "warning",
                "message": "Sprint plan selected no stories.",
                "story_id": None,
                "field": "capacity",
            }
        )
    elif cap > 0 and pts < cap * 0.4:
        findings.append(
            {
                "code": "capacity_underload",
                "severity": "info",
                "message": f"Only {pts}/{cap} pts planned ({100 * pts // cap}% of capacity).",
                "story_id": None,
                "field": "capacity",
            }
        )

    # Per-story quality inside sprint
    for s in selected_stories:
        for f in critique_story(s):
            if f["severity"] in ("error", "warning"):
                findings.append(f)

    errors = sum(1 for x in findings if x["severity"] == "error")
    warnings = sum(1 for x in findings if x["severity"] == "warning")
    rationale = (
        f"Sprint critic: {pts}/{cap} points planned across {len(selected_stories)} stories. "
        f"{errors} error(s), {warnings} warning(s). "
        f"Capacity and story quality checks only; no silent reassignment."
    )
    return {
        "findings": findings,
        "summary": {
            "planned_points": pts,
            "capacity_points": cap,
            "story_count": len(selected_stories),
            "errors": errors,
            "warnings": warnings,
        },
        "rationale": rationale,
        "agent": "critic",
    }
