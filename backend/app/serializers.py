"""Helpers to convert ORM rows ↔ API dicts (JSON fields stored as strings)."""

from __future__ import annotations

import json
from typing import Any

from . import models


def _loads_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _loads_dict(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def project_to_dict(p: models.Project) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "brief": p.brief or "",
        "goals": _loads_list(p.goals),
        "constraints": _loads_list(p.constraints),
        "source_path": p.source_path,
        "created_at": p.created_at,
    }


def story_to_dict(s: models.Story) -> dict[str, Any]:
    return {
        "id": s.id,
        "epic_id": s.epic_id,
        "title": s.title,
        "description": s.description or "",
        "acceptance_criteria": _loads_list(s.acceptance_criteria),
        "points": s.points,
        "priority": s.priority,
        "status": s.status,
        "rationale": s.rationale or "",
        "order": s.order,
    }


def epic_to_dict(e: models.Epic, include_stories: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": e.id,
        "project_id": e.project_id,
        "title": e.title,
        "description": e.description or "",
        "order": e.order,
        "stories": [],
    }
    if include_stories:
        stories = sorted(e.stories or [], key=lambda x: (x.order, x.id))
        data["stories"] = [story_to_dict(s) for s in stories]
    return data


def sprint_item_to_dict(item: models.SprintItem, include_story: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": item.id,
        "sprint_id": item.sprint_id,
        "story_id": item.story_id,
        "story": None,
    }
    if include_story and item.story is not None:
        data["story"] = story_to_dict(item.story)
    return data


def sprint_to_dict(sp: models.Sprint, include_items: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": sp.id,
        "project_id": sp.project_id,
        "name": sp.name,
        "goal": sp.goal or "",
        "start": sp.start,
        "end": sp.end,
        "capacity_points": sp.capacity_points,
        "status": sp.status,
        "items": [],
    }
    if include_items:
        data["items"] = [sprint_item_to_dict(i) for i in (sp.items or [])]
    return data


def activity_to_dict(a: models.Activity) -> dict[str, Any]:
    return {
        "id": a.id,
        "project_id": a.project_id,
        "type": a.type,
        "payload": _loads_dict(a.payload),
        "created_at": a.created_at,
    }


def dumps(obj: Any) -> str:
    return json.dumps(obj)
