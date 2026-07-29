"""Deterministic AI agent stubs for the MVP demo.

These return structured backlog / sprint / standup artifacts with explainable
rationale. Swap for real LLM calls (Groq / Ollama / OpenAI) later without
changing the API contract.
"""

from __future__ import annotations

import re
from typing import Any


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    stop = {
        "that",
        "this",
        "with",
        "from",
        "have",
        "will",
        "should",
        "would",
        "about",
        "using",
        "project",
        "system",
        "application",
        "build",
        "create",
        "users",
        "user",
    }
    seen: list[str] = []
    for w in words:
        if w not in stop and w not in seen:
            seen.append(w)
        if len(seen) >= 8:
            break
    return seen or ["core", "feature", "platform"]


def generate_backlog(
    name: str,
    brief: str,
    goals: list[str],
    constraints: list[str],
) -> dict[str, Any]:
    """Produce epics + stories from project brief (stub)."""
    kws = _keywords(f"{name} {brief} {' '.join(goals)}")
    domain = kws[0].title() if kws else "Product"

    epics: list[dict[str, Any]] = [
        {
            "title": f"Foundation & {domain} Setup",
            "description": f"Core infrastructure and project scaffolding for {name}.",
            "order": 0,
            "stories": [
                {
                    "title": f"As a developer, I want a project scaffold so that we can start building {name}",
                    "description": "Initialize repo, tooling, and basic config.",
                    "acceptance_criteria": [
                        "Repository structure exists with frontend and backend",
                        "Local run instructions work on a clean machine",
                        "Health check endpoint returns 200",
                    ],
                    "points": 3,
                    "priority": "high",
                    "status": "todo",
                    "rationale": "Foundational work unblocks all other delivery; high priority by dependency.",
                    "order": 0,
                },
                {
                    "title": "As a PM, I want project CRUD so that I can manage workspace metadata",
                    "description": "Create, read, update project brief, goals, and constraints.",
                    "acceptance_criteria": [
                        "User can create a project with name and brief",
                        "Goals and constraints are editable lists",
                        "Project list shows all workspaces",
                    ],
                    "points": 5,
                    "priority": "high",
                    "status": "todo",
                    "rationale": "Project workspace is MVP feature #1; required before backlog generation.",
                    "order": 1,
                },
                {
                    "title": "As a user, I want data persisted so that work survives reloads",
                    "description": "SQLite (or equivalent) persistence for projects, stories, sprints.",
                    "acceptance_criteria": [
                        "All entities survive server restart",
                        "Cascade delete works for project → epics → stories",
                    ],
                    "points": 3,
                    "priority": "high",
                    "status": "todo",
                    "rationale": "Without persistence the board is not source of truth (PROJECT.md risk).",
                    "order": 2,
                },
            ],
        },
        {
            "title": "AI-Assisted Planning",
            "description": "Generate backlog, sprint scope, and status summaries with rationale.",
            "order": 1,
            "stories": [
                {
                    "title": "As a PM, I want AI backlog generation so that a brief becomes epics and stories",
                    "description": "Intake brief → structured epics, user stories, AC, points.",
                    "acceptance_criteria": [
                        "POST generate returns epics with nested stories",
                        "Each story has AC, points, priority, and rationale",
                        "User can regenerate or keep edits (human-in-the-loop)",
                    ],
                    "points": 8,
                    "priority": "high",
                    "status": "todo",
                    "rationale": f"Core differentiator vs Jira tracking; keywords from brief: {', '.join(kws[:4])}.",
                    "order": 0,
                },
                {
                    "title": "As a Scrum Master, I want sprint planning suggestions so that scope fits capacity",
                    "description": "Select high-priority stories up to capacity points.",
                    "acceptance_criteria": [
                        "Suggestion respects capacity_points",
                        "Priority ordering is explained in rationale",
                        "User confirms before apply",
                    ],
                    "points": 5,
                    "priority": "medium",
                    "status": "todo",
                    "rationale": "Capacity-aware selection reduces over-commitment; explainability required.",
                    "order": 1,
                },
                {
                    "title": "As a team, I want standup summaries so that status is drafted automatically",
                    "description": "Summarize board columns and recent activity.",
                    "acceptance_criteria": [
                        "Summary lists done / in progress / todo",
                        "Flags potential blockers when many items stay todo",
                        "Short narrative suitable for paste into chat",
                    ],
                    "points": 3,
                    "priority": "medium",
                    "status": "todo",
                    "rationale": "Reduces manual status writing; grounded in board state not free-form chat.",
                    "order": 2,
                },
            ],
        },
        {
            "title": "Board & Delivery UX",
            "description": "Kanban board, story editor, and export for demos and reports.",
            "order": 2,
            "stories": [
                {
                    "title": "As a developer, I want a Kanban board so that I can move stories across status",
                    "description": "Columns: To-do / In progress / Done.",
                    "acceptance_criteria": [
                        "Stories appear in correct column by status",
                        "Drag or click updates status via API",
                        "Points visible on cards",
                    ],
                    "points": 5,
                    "priority": "high",
                    "status": "todo",
                    "rationale": "Board is source of truth for sprint tracking (MVP #3).",
                    "order": 0,
                },
                {
                    "title": "As a PM, I want a story editor so that AI drafts can be corrected",
                    "description": "Edit title, description, AC, points, priority, rationale.",
                    "acceptance_criteria": [
                        "All story fields are editable",
                        "Save persists immediately",
                        "Rationale remains visible for explainability",
                    ],
                    "points": 5,
                    "priority": "high",
                    "status": "todo",
                    "rationale": "User data is version of truth; AI proposes only (MVP #4).",
                    "order": 1,
                },
                {
                    "title": "As a stakeholder, I want Markdown/JSON export so that I can share backlog reports",
                    "description": "Export full backlog and optional sprint report.",
                    "acceptance_criteria": [
                        "JSON export is valid and complete",
                        "Markdown is readable for viva / report",
                        "Filename includes project name",
                    ],
                    "points": 3,
                    "priority": "medium",
                    "status": "todo",
                    "rationale": "Supports evaluation artifacts and demo handoff (MVP #8).",
                    "order": 2,
                },
            ],
        },
    ]

    # Goal-driven extra epic if goals provided
    if goals:
        goal_stories = []
        for i, g in enumerate(goals[:3]):
            goal_stories.append(
                {
                    "title": f"As a stakeholder, I want progress on: {g}",
                    "description": f"Deliverable aligned to stated goal: {g}",
                    "acceptance_criteria": [
                        f"Goal '{g}' is reflected in at least one demoable feature",
                        "Acceptance can be verified in a walkthrough",
                    ],
                    "points": 5 if i == 0 else 3,
                    "priority": "high" if i == 0 else "medium",
                    "status": "todo",
                    "rationale": f"Derived directly from project goal #{i + 1}.",
                    "order": i,
                }
            )
        epics.append(
            {
                "title": "Goal Alignment",
                "description": "Stories mapped from explicit project goals.",
                "order": 3,
                "stories": goal_stories,
            }
        )

    # Constraint note baked into rationale
    constraint_note = (
        f" Constraints considered: {'; '.join(constraints)}."
        if constraints
        else ""
    )

    rationale = (
        f"Generated a structured Agile backlog for «{name}» from the project brief. "
        f"Key themes extracted: {', '.join(kws[:5])}. "
        f"Organized into {len(epics)} epics with INVEST-oriented user stories, "
        f"acceptance criteria, rough Fibonacci-ish points, and priority. "
        f"This is a stub agent — replace with LLM for production drafts.{constraint_note}"
    )

    return {"epics": epics, "rationale": rationale, "agent": "backlog_stub"}


def plan_sprint(
    stories: list[dict[str, Any]],
    capacity_points: int,
    sprint_name: str = "Sprint",
) -> dict[str, Any]:
    """Pick high-priority incomplete stories up to capacity."""
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    candidates = [
        s
        for s in stories
        if s.get("status") != "done"
    ]
    candidates.sort(
        key=lambda s: (
            priority_rank.get(s.get("priority", "medium"), 1),
            s.get("order", 0),
            s.get("id", 0),
        )
    )

    selected: list[dict[str, Any]] = []
    total = 0
    for s in candidates:
        pts = int(s.get("points") or 0)
        if total + pts <= capacity_points:
            selected.append(s)
            total += pts

    ids = [s["id"] for s in selected]
    titles = [s["title"][:60] for s in selected]
    rationale = (
        f"Suggested {len(selected)} stories ({total}/{capacity_points} pts) for {sprint_name}. "
        f"Selection order: high priority first, then medium/low; skip done items; "
        f"stop when capacity would be exceeded. "
        f"Stories: {'; '.join(titles) if titles else '(none — raise capacity or add backlog)'}."
    )
    return {
        "suggested_story_ids": ids,
        "total_points": total,
        "rationale": rationale,
        "stories": selected,
        "agent": "sprint_stub",
    }


def standup_summary(
    stories: list[dict[str, Any]],
    project_name: str,
    recent_events: list[str] | None = None,
) -> dict[str, Any]:
    """Draft standup from board columns."""
    done = [s["title"] for s in stories if s.get("status") == "done"]
    wip = [s["title"] for s in stories if s.get("status") == "in_progress"]
    todo = [s["title"] for s in stories if s.get("status") == "todo"]

    blockers: list[str] = []
    if len(wip) == 0 and len(todo) > 5:
        blockers.append("No work in progress while many items remain in To-do — start pull?")
    if len(wip) > 4:
        blockers.append(f"High WIP ({len(wip)} items) — consider finishing before starting more.")

    lines = [
        f"### Standup — {project_name}",
        "",
        f"**Done ({len(done)}):** " + ("; ".join(t[:50] for t in done[:5]) or "—"),
        f"**In progress ({len(wip)}):** " + ("; ".join(t[:50] for t in wip[:5]) or "—"),
        f"**To-do remaining ({len(todo)}):** {len(todo)} items in backlog/board.",
    ]
    if blockers:
        lines.append("**Watchouts:** " + " ".join(blockers))
    if recent_events:
        lines.append("**Recent:** " + "; ".join(recent_events[:5]))

    summary = "\n".join(lines)
    rationale = (
        "Summarized from live board status counts only (no LLM hallucination of work). "
        "Blockers are heuristic flags on WIP and idle backlog."
    )
    return {
        "summary": summary,
        "done": done,
        "in_progress": wip,
        "todo": todo,
        "blockers": blockers,
        "rationale": rationale,
        "agent": "standup_stub",
    }
