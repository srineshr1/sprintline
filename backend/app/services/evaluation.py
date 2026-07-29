"""Evaluation metrics for viva / report (pure functions).

Metrics (aligned with PROJECT.md §8):
- AC coverage: % stories with ≥1 acceptance criterion
- INVEST-style rubric score (0–1 average across stories)
- Sprint realism: planned / completed / remaining points
"""

from __future__ import annotations

import re
from typing import Any


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
            return [str(x).strip() for x in parsed if str(x).strip()] if isinstance(parsed, list) else []
        except Exception:
            return [ac.strip()] if ac.strip() else []
    return [str(a).strip() for a in ac if str(a).strip()]


def story_has_ac(story: dict[str, Any]) -> bool:
    return len(_ac_list(story)) >= 1


def ac_coverage(stories: list[dict[str, Any]]) -> dict[str, Any]:
    """% of stories that have at least one acceptance criterion."""
    n = len(stories)
    if n == 0:
        return {
            "total_stories": 0,
            "with_ac": 0,
            "without_ac": 0,
            "coverage_pct": 0.0,
            "rationale": "No stories in project; AC coverage is 0%.",
        }
    with_ac = sum(1 for s in stories if story_has_ac(s))
    pct = round(100.0 * with_ac / n, 2)
    return {
        "total_stories": n,
        "with_ac": with_ac,
        "without_ac": n - with_ac,
        "coverage_pct": pct,
        "rationale": (
            f"{with_ac}/{n} stories ({pct}%) have acceptance criteria. "
            f"Higher coverage improves testability and demo quality."
        ),
    }


def invest_score_story(story: dict[str, Any]) -> dict[str, Any]:
    """Simple INVEST-style checklist (0/1 per dimension, mean as score).

    I Independent — not scored deeply; heuristic: not blocked wording
    N Negotiable — has description or rationale (room to discuss)
    V Valuable — user-story form or clear value phrase
    E Estimable — points set and reasonable (1–13)
    S Small — points ≤ 8
    T Testable — has ≥2 AC or ≥1 AC with clear verbs
    """
    title = (story.get("title") or "").strip()
    desc = (story.get("description") or "").strip()
    rationale = (story.get("rationale") or "").strip()
    ac = _ac_list(story)
    try:
        points = int(story.get("points") if story.get("points") is not None else -1)
    except (TypeError, ValueError):
        points = -1

    checks: dict[str, bool] = {}

    # Independent (weak heuristic)
    blocked = bool(re.search(r"\bblocked\s+by\b|\bdepends\s+on\s+story\b", f"{title} {desc}", re.I))
    checks["independent"] = not blocked and bool(title)

    # Negotiable
    checks["negotiable"] = bool(desc or rationale or len(title) > 20)

    # Valuable
    checks["valuable"] = bool(
        _USER_STORY_RE.search(title)
        or _USER_STORY_RE.search(desc)
        or re.search(r"\bso that\b|\bvalue\b|\bstakeholder\b|\buser\b", f"{title} {desc}", re.I)
    )

    # Estimable
    checks["estimable"] = 1 <= points <= 13

    # Small
    checks["small"] = 0 < points <= 8

    # Testable
    checks["testable"] = len(ac) >= 2 or (len(ac) >= 1 and any(len(a) >= 10 for a in ac))

    dims = list(checks.values())
    score = round(sum(1 for v in dims if v) / len(dims), 4) if dims else 0.0

    return {
        "story_id": story.get("id"),
        "title": title[:80],
        "checks": checks,
        "score": score,
    }


def invest_scores(stories: list[dict[str, Any]]) -> dict[str, Any]:
    """Average INVEST-style score across stories."""
    if not stories:
        return {
            "story_count": 0,
            "average_score": 0.0,
            "average_pct": 0.0,
            "per_story": [],
            "dimension_pass_rates": {},
            "rationale": "No stories; INVEST average is 0.",
        }

    per = [invest_score_story(s) for s in stories]
    avg = round(sum(p["score"] for p in per) / len(per), 4)
    dims = ["independent", "negotiable", "valuable", "estimable", "small", "testable"]
    rates: dict[str, float] = {}
    for d in dims:
        rates[d] = round(
            100.0 * sum(1 for p in per if p["checks"].get(d)) / len(per),
            2,
        )

    return {
        "story_count": len(stories),
        "average_score": avg,
        "average_pct": round(avg * 100, 2),
        "per_story": per,
        "dimension_pass_rates": rates,
        "rationale": (
            f"INVEST-style average {avg:.2f} ({avg * 100:.1f}%) across {len(stories)} stories. "
            f"Dimension pass rates: "
            + ", ".join(f"{k}={v}%" for k, v in rates.items())
            + ". Rubric is a simple automated checklist for viva measurement, not a formal audit."
        ),
    }


def sprint_points_metrics(
    sprint: dict[str, Any],
    stories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Planned vs completed vs remaining points for a sprint.

    `sprint` may include items with nested story, or pass stories list + story_ids.
    """
    capacity = int(sprint.get("capacity_points") or 0)
    items = sprint.get("items") or []

    story_by_id: dict[Any, dict[str, Any]] = {}
    if stories:
        for s in stories:
            story_by_id[s.get("id")] = s

    planned_points = 0
    completed_points = 0
    remaining_points = 0
    in_progress_points = 0
    story_ids: list[Any] = []

    for item in items:
        st = item.get("story") if isinstance(item, dict) else None
        sid = item.get("story_id") if isinstance(item, dict) else None
        if st is None and sid is not None:
            st = story_by_id.get(sid)
        if st is None:
            continue
        story_ids.append(st.get("id", sid))
        pts = int(st.get("points") or 0)
        planned_points += pts
        status = (st.get("status") or "todo").lower()
        if status == "done":
            completed_points += pts
        elif status == "in_progress":
            in_progress_points += pts
            remaining_points += pts
        else:
            remaining_points += pts

    utilization = (
        round(100.0 * planned_points / capacity, 2) if capacity > 0 else 0.0
    )
    completion = (
        round(100.0 * completed_points / planned_points, 2)
        if planned_points > 0
        else 0.0
    )

    return {
        "sprint_id": sprint.get("id"),
        "sprint_name": sprint.get("name"),
        "capacity_points": capacity,
        "planned_points": planned_points,
        "completed_points": completed_points,
        "in_progress_points": in_progress_points,
        "remaining_points": remaining_points,
        "utilization_pct": utilization,
        "completion_pct": completion,
        "story_ids": story_ids,
        "story_count": len(story_ids),
        "rationale": (
            f"Sprint «{sprint.get('name', '?')}»: planned {planned_points}/{capacity} pts "
            f"({utilization}% capacity), completed {completed_points} pts "
            f"({completion}% of plan), remaining {remaining_points} pts."
        ),
    }


def evaluate_project(
    stories: list[dict[str, Any]],
    sprints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Full evaluation bundle for a project."""
    ac = ac_coverage(stories)
    invest = invest_scores(stories)
    sprint_metrics = [
        sprint_points_metrics(sp, stories) for sp in (sprints or [])
    ]

    # Status mix
    status_counts = {"todo": 0, "in_progress": 0, "done": 0, "other": 0}
    total_pts = 0
    done_pts = 0
    for s in stories:
        st = (s.get("status") or "todo").lower()
        if st in status_counts:
            status_counts[st] += 1
        else:
            status_counts["other"] += 1
        pts = int(s.get("points") or 0)
        total_pts += pts
        if st == "done":
            done_pts += pts

    overall_rationale = (
        f"Evaluation: AC coverage {ac['coverage_pct']}%; "
        f"INVEST avg {invest['average_pct']}%; "
        f"board {status_counts['done']} done / {status_counts['in_progress']} WIP / "
        f"{status_counts['todo']} todo; "
        f"points done {done_pts}/{total_pts}."
    )

    return {
        "ac_coverage": ac,
        "invest": {
            "story_count": invest["story_count"],
            "average_score": invest["average_score"],
            "average_pct": invest["average_pct"],
            "dimension_pass_rates": invest["dimension_pass_rates"],
            "rationale": invest["rationale"],
            # omit full per_story in compact view; included separately if needed
            "per_story": invest["per_story"],
        },
        "sprints": sprint_metrics,
        "board": {
            "status_counts": status_counts,
            "total_points": total_pts,
            "completed_points": done_pts,
            "completion_pct": (
                round(100.0 * done_pts / total_pts, 2) if total_pts else 0.0
            ),
        },
        "rationale": overall_rationale,
        "agent": "evaluation",
    }
