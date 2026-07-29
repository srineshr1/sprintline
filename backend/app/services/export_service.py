"""Export project backlog and sprints as Markdown or JSON."""

from __future__ import annotations

import json
import re
from typing import Any


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "project"


def export_json(payload: dict[str, Any]) -> tuple[str, str]:
    content = json.dumps(payload, indent=2, default=str)
    filename = f"{_slug(payload.get('project', {}).get('name', 'project'))}-export.json"
    return content, filename


def export_markdown(payload: dict[str, Any]) -> tuple[str, str]:
    p = payload.get("project", {})
    lines: list[str] = [
        f"# {p.get('name', 'Project')}",
        "",
        "## Brief",
        "",
        p.get("brief") or "_(empty)_",
        "",
    ]
    goals = p.get("goals") or []
    if goals:
        lines += ["## Goals", ""]
        for g in goals:
            lines.append(f"- {g}")
        lines.append("")

    constraints = p.get("constraints") or []
    if constraints:
        lines += ["## Constraints", ""]
        for c in constraints:
            lines.append(f"- {c}")
        lines.append("")

    lines += ["## Backlog", ""]
    for epic in payload.get("epics", []):
        lines.append(f"### Epic: {epic.get('title')}")
        if epic.get("description"):
            lines.append("")
            lines.append(epic["description"])
        lines.append("")
        for s in epic.get("stories") or []:
            lines.append(f"#### [{s.get('status', 'todo')}] {s.get('title')} ({s.get('points', 0)} pts, {s.get('priority', 'medium')})")
            if s.get("description"):
                lines.append("")
                lines.append(s["description"])
            ac = s.get("acceptance_criteria") or []
            if ac:
                lines.append("")
                lines.append("**Acceptance criteria**")
                for a in ac:
                    lines.append(f"- [ ] {a}")
            if s.get("rationale"):
                lines.append("")
                lines.append(f"> **Why:** {s['rationale']}")
            lines.append("")

    sprints = payload.get("sprints") or []
    if sprints:
        lines += ["## Sprints", ""]
        for sp in sprints:
            lines.append(f"### {sp.get('name')} ({sp.get('status')})")
            if sp.get("goal"):
                lines.append(f"**Goal:** {sp['goal']}")
            lines.append(f"**Capacity:** {sp.get('capacity_points')} pts")
            lines.append("")
            for item in sp.get("items") or []:
                st = item.get("story") or {}
                title = st.get("title") or f"story#{item.get('story_id')}"
                status = st.get("status", "?")
                points = st.get("points", "?")
                lines.append(f"- [{status}] {title} ({points} pts)")
            lines.append("")

    content = "\n".join(lines)
    filename = f"{_slug(p.get('name', 'project'))}-export.md"
    return content, filename
