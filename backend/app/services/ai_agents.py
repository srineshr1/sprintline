"""Real Groq-backed agents with automatic stub fallback.

Public API mirrors ``ai_stub`` so ``pipeline`` can call either path.
Each function returns the same shape as the stubs, plus optional
``codebase_context`` metadata for the UI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from ..config import get_settings
from . import ai_stub, codebase
from .llm import LLMError, chat_json, model_label


def _normalize_priority(raw: Any) -> str:
    s = str(raw or "medium").strip().lower()
    if s in ("high", "urgent", "critical", "p0", "p1"):
        return "high"
    if s in ("low", "p3", "nice"):
        return "low"
    return "medium"


def _normalize_points(raw: Any) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return 3
    allowed = {1, 2, 3, 5, 8, 13, 21}
    if n in allowed:
        return n
    # snap to nearest Fibonacci-ish
    return min(allowed, key=lambda x: abs(x - max(1, n)))


def _normalize_status(raw: Any) -> str:
    s = str(raw or "todo").strip().lower().replace("-", "_").replace(" ", "_")
    if s in ("done", "complete", "completed"):
        return "done"
    if s in ("in_progress", "inprogress", "wip", "doing"):
        return "in_progress"
    return "todo"


def _coerce_epics(data: dict[str, Any]) -> list[dict[str, Any]]:
    epics_in = data.get("epics") or []
    if not isinstance(epics_in, list):
        return []
    epics: list[dict[str, Any]] = []
    for i, ep in enumerate(epics_in[:12]):
        if not isinstance(ep, dict):
            continue
        title = str(ep.get("title") or f"Epic {i + 1}").strip()[:280]
        stories_out: list[dict[str, Any]] = []
        for j, st in enumerate((ep.get("stories") or [])[:40]):
            if not isinstance(st, dict):
                continue
            st_title = str(st.get("title") or "").strip()
            if not st_title:
                continue
            ac = st.get("acceptance_criteria") or []
            if isinstance(ac, str):
                ac = [ac] if ac.strip() else []
            if not isinstance(ac, list):
                ac = []
            ac = [str(x).strip() for x in ac if str(x).strip()][:8]
            stories_out.append(
                {
                    "title": st_title[:380],
                    "description": str(st.get("description") or "")[:800],
                    "acceptance_criteria": ac,
                    "points": _normalize_points(st.get("points", 3)),
                    "priority": _normalize_priority(st.get("priority")),
                    "status": _normalize_status(st.get("status")),
                    "rationale": str(st.get("rationale") or "")[:600],
                    "order": j,
                }
            )
        if not stories_out:
            continue
        epics.append(
            {
                "title": title,
                "description": str(ep.get("description") or "")[:600],
                "order": i,
                "stories": stories_out,
            }
        )
    return epics


def generate_backlog(
    name: str,
    brief: str,
    goals: list[str],
    constraints: list[str],
    *,
    source_path: Optional[str] = None,
) -> dict[str, Any]:
    """Draft epics/stories from brief + optional real codebase files via Groq."""
    settings = get_settings()
    ctx = None
    ctx_summary = None
    if source_path:
        ctx = codebase.collect_project_context(
            source_path, max_files=16, max_total_chars=16_000
        )
        ctx_summary = codebase.context_summary(ctx)

    if not settings.use_llm():
        draft = ai_stub.generate_backlog(name, brief, goals, constraints)
        if ctx_summary:
            draft["codebase_context"] = ctx_summary
            draft["rationale"] = (
                draft.get("rationale", "")
                + " (LLM offline — stub used; codebase was available but not sent.)"
            )
        return draft

    code_block = codebase.format_context_for_prompt(ctx) if ctx else "(No source_path linked.)"

    system = (
        "You are an expert Agile product manager and tech lead. "
        "Produce a realistic, INVEST-friendly backlog grounded in the project brief "
        "AND the actual repository files when provided. "
        "Do not invent secrets. Prefer concrete, testable acceptance criteria. "
        "Respond with JSON only."
    )
    user = f"""Project name: {name}

Brief:
{brief or '(empty)'}

Goals:
{json.dumps(goals or [], indent=2)}

Constraints:
{json.dumps(constraints or [], indent=2)}

Repository context (file tree + selected sources — use this heavily):
{code_block}

Return JSON with this shape:
{{
  "epics": [
    {{
      "title": string,
      "description": string,
      "stories": [
        {{
          "title": "As a <role>, I want <capability> so that <benefit>",
          "description": string,
          "acceptance_criteria": [string, ...],
          "points": 1|2|3|5|8|13,
          "priority": "high"|"medium"|"low",
          "status": "todo",
          "rationale": "why this story, citing files/features when possible"
        }}
      ]
    }}
  ],
  "rationale": "overall explanation of how you used the brief and codebase"
}}

Rules:
- 2–4 epics, 6–14 stories total
- Stories must reflect real modules/files when codebase is present
- Every story needs 2–4 acceptance criteria
- Fibonacci points only
"""

    try:
        data = chat_json(system=system, user=user, temperature=0.35, max_tokens=3500)
        epics = _coerce_epics(data)
        if not epics:
            raise LLMError("Model returned no usable epics")
        rationale = str(data.get("rationale") or "").strip() or (
            f"Groq ({model_label()}) drafted the backlog from brief"
            + (" and repository files." if ctx and ctx.get("exists") else ".")
        )
        return {
            "epics": epics,
            "rationale": rationale,
            "agent": model_label(),
            "codebase_context": ctx_summary,
        }
    except LLMError as exc:
        draft = ai_stub.generate_backlog(name, brief, goals, constraints)
        draft["agent"] = "backlog_stub"
        draft["rationale"] = (
            f"Groq unavailable ({exc}); fell back to stub. " + draft.get("rationale", "")
        )
        if ctx_summary:
            draft["codebase_context"] = ctx_summary
        draft["llm_error"] = str(exc)
        return draft


def plan_sprint(
    stories: list[dict[str, Any]],
    capacity_points: int,
    sprint_name: str = "Sprint",
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.use_llm():
        return ai_stub.plan_sprint(stories, capacity_points, sprint_name)

    # Compact story list for the model
    slim = [
        {
            "id": s.get("id"),
            "title": s.get("title"),
            "points": s.get("points"),
            "priority": s.get("priority"),
            "status": s.get("status"),
            "description": (s.get("description") or "")[:200],
        }
        for s in stories
        if s.get("status") != "done"
    ]

    system = (
        "You are an experienced Scrum Master. Select a sprint backlog that fits "
        "capacity, prioritises high-value/high-priority work, and avoids "
        "overloading. JSON only."
    )
    user = f"""Sprint name: {sprint_name}
Capacity points: {capacity_points}

Open stories (JSON):
{json.dumps(slim, indent=2)}

Return:
{{
  "suggested_story_ids": [int, ...],  // subset of given ids, order = planned sequence
  "total_points": int,                // sum of selected story points
  "rationale": string                 // explain trade-offs, dependencies, capacity
}}

Rules:
- total_points MUST be <= capacity_points
- Prefer high priority; do not select done items
- Only use ids from the list
- If nothing fits, return empty list and explain
"""

    try:
        data = chat_json(system=system, user=user, temperature=0.2, max_tokens=2000)
        valid_ids = {s.get("id") for s in stories}
        by_id = {s.get("id"): s for s in stories}
        selected_ids: list[int] = []
        total = 0
        for raw_id in data.get("suggested_story_ids") or []:
            try:
                sid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if sid not in valid_ids or sid in selected_ids:
                continue
            st = by_id[sid]
            pts = int(st.get("points") or 0)
            if total + pts > capacity_points:
                continue
            selected_ids.append(sid)
            total += pts
        # If model overshot empty, fall back to greedy stub selection
        if not selected_ids and slim:
            fallback = ai_stub.plan_sprint(stories, capacity_points, sprint_name)
            fallback["rationale"] = (
                "Groq returned no valid ids; used capacity packing. "
                + str(data.get("rationale") or "")
            )
            fallback["agent"] = model_label() + "+capacity_pack"
            return fallback

        selected = [by_id[i] for i in selected_ids]
        return {
            "suggested_story_ids": selected_ids,
            "total_points": total,
            "rationale": str(data.get("rationale") or "").strip()
            or f"Selected {len(selected_ids)} stories ({total}/{capacity_points} pts).",
            "stories": selected,
            "agent": model_label(),
        }
    except LLMError as exc:
        plan = ai_stub.plan_sprint(stories, capacity_points, sprint_name)
        plan["rationale"] = f"Groq unavailable ({exc}); stub plan. " + plan.get(
            "rationale", ""
        )
        plan["llm_error"] = str(exc)
        return plan


def standup_summary(
    stories: list[dict[str, Any]],
    project_name: str,
    recent_events: list[str] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    # Always compute ground-truth board lists
    base = ai_stub.standup_summary(stories, project_name, recent_events)
    if not settings.use_llm():
        return base

    board = {
        "done": base["done"][:12],
        "in_progress": base["in_progress"][:12],
        "todo_count": len(base["todo"]),
        "todo_sample": base["todo"][:8],
        "blockers_heuristic": base["blockers"],
        "recent_events": recent_events or [],
    }
    system = (
        "You are a helpful engineering manager writing a crisp daily standup. "
        "Stay factual: only mention work present in the board data. JSON only."
    )
    user = f"""Project: {project_name}

Board snapshot:
{json.dumps(board, indent=2)}

Return:
{{
  "summary": "markdown standup notes (## headings ok)",
  "blockers": [string, ...],
  "rationale": "how you read the board"
}}
"""
    try:
        data = chat_json(system=system, user=user, temperature=0.4, max_tokens=1500)
        summary = str(data.get("summary") or "").strip() or base["summary"]
        blockers = data.get("blockers")
        if not isinstance(blockers, list):
            blockers = base["blockers"]
        blockers = [str(b).strip() for b in blockers if str(b).strip()][:8]
        return {
            "summary": summary,
            "done": base["done"],
            "in_progress": base["in_progress"],
            "todo": base["todo"],
            "blockers": blockers,
            "rationale": str(data.get("rationale") or "").strip()
            or f"Standup drafted by {model_label()} from live board state.",
            "agent": model_label(),
        }
    except LLMError as exc:
        base["rationale"] = f"Groq unavailable ({exc}); heuristic standup. " + base.get(
            "rationale", ""
        )
        base["llm_error"] = str(exc)
        return base


def analyze_project_folder(
    folder_path: str | Path,
    *,
    heuristic: Optional[dict[str, Any]] = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Token-frugal import analysis: compact card + cheap model + disk cache.

    Merges with optional heuristic scan (README/TODO parser) so checklist
    items are never lost. Does **not** dump full source trees into the prompt.
    """
    from . import ai_cache

    path = Path(folder_path)
    settings = get_settings()
    import_model = settings.groq_import_model

    # Compact card only (README/manifests + shallow tree) — ~1–2k tokens.
    ctx = codebase.collect_compact_card(path)
    ctx_summary = codebase.context_summary(ctx)

    if not settings.use_llm() or not ctx.get("exists"):
        return {
            "ok": False,
            "agent": "none",
            "codebase_context": ctx_summary,
            "error": "LLM off or path missing",
            "cached": False,
        }

    heuristic = heuristic or {}
    ckey = ai_cache.cache_key(path, import_model, mode="import_compact_v2")
    if use_cache:
        hit = ai_cache.get(ckey)
        if hit and hit.get("ok"):
            hit = dict(hit)
            hit["cached"] = True
            hit["codebase_context"] = ctx_summary
            # Still merge latest heuristic todos (may have changed titles only)
            if heuristic.get("epics") and hit.get("epics"):
                hit["epics"] = _merge_epics(heuristic["epics"], hit["epics"])
                flat = [s for e in hit["epics"] for s in e.get("stories") or []]
                hit["story_count"] = len(flat)
                hit["epic_count"] = len(hit["epics"])
            return hit

    system = (
        "You analyze software project folders for an Agile import tool. "
        "You only see a compact card (tree + README/manifests), not full source. "
        "Infer purpose, goals, constraints, tech stack, and a short realistic backlog. "
        "JSON only. Be concise."
    )
    user = f"""Folder: {path.name}

Heuristic (may be incomplete):
{json.dumps({
    'name': heuristic.get('name'),
    'brief': (heuristic.get('brief') or '')[:500],
    'goals': (heuristic.get('goals') or [])[:6],
    'constraints': (heuristic.get('constraints') or [])[:6],
    'story_count': heuristic.get('story_count'),
    'sample_titles': (heuristic.get('sample_titles') or [])[:6],
    'story_sources': heuristic.get('story_sources'),
}, indent=2)}

Compact repository card:
{codebase.format_context_for_prompt(ctx, max_chars=5_000)}

Return JSON:
{{
  "name": "product name",
  "brief": "2-4 sentences",
  "goals": ["..."],
  "constraints": ["..."],
  "analysis": "1-2 sentences maturity/purpose",
  "tech_stack": ["..."],
  "epics": [
    {{
      "title": string,
      "stories": [
        {{
          "title": string,
          "description": string,
          "points": 1|2|3|5|8,
          "priority": "high"|"medium"|"low",
          "status": "todo",
          "rationale": string
        }}
      ]
    }}
  ],
  "rationale": "short"
}}

Rules:
- Keep/merge heuristic checklist stories
- Max 3 epics, 10 stories total
- Prefer concrete work over filler
"""

    try:
        data = chat_json(
            system=system,
            user=user,
            temperature=0.25,
            max_tokens=1800,
            model=import_model,
            retries=1,
        )
        epics = _coerce_epics(data)
        if heuristic.get("epics"):
            epics = _merge_epics(heuristic["epics"], epics)
        # Cap after merge
        total_stories = 0
        capped: list[dict[str, Any]] = []
        for ep in epics:
            room = 10 - total_stories
            if room <= 0:
                break
            stories = (ep.get("stories") or [])[:room]
            if not stories:
                continue
            capped.append({**ep, "stories": stories})
            total_stories += len(stories)
        epics = capped

        name = str(data.get("name") or heuristic.get("name") or path.name).strip()
        brief = str(data.get("brief") or heuristic.get("brief") or "").strip()
        goals = data.get("goals") if isinstance(data.get("goals"), list) else []
        goals = [str(g).strip() for g in goals if str(g).strip()][:12]
        if not goals:
            goals = list(heuristic.get("goals") or [])
        constraints = (
            data.get("constraints") if isinstance(data.get("constraints"), list) else []
        )
        constraints = [str(c).strip() for c in constraints if str(c).strip()][:12]
        if not constraints:
            constraints = list(heuristic.get("constraints") or [])

        flat = [s for e in epics for s in e.get("stories") or []]
        result = {
            "ok": True,
            "agent": model_label(import_model),
            "name": name[:200],
            "brief": brief[:1200],
            "goals": goals,
            "constraints": constraints,
            "epics": epics,
            "analysis": str(data.get("analysis") or "").strip()[:800],
            "tech_stack": [
                str(t).strip()
                for t in (data.get("tech_stack") or [])
                if str(t).strip()
            ][:12],
            "rationale": str(data.get("rationale") or "").strip()[:600],
            "codebase_context": ctx_summary,
            "story_count": len(flat),
            "epic_count": len(epics),
            "cached": False,
        }
        if use_cache:
            # Don't store codebase_context bodies-heavy; summary is fine
            to_store = {k: v for k, v in result.items() if k != "codebase_context"}
            ai_cache.put(ckey, to_store)
        return result
    except LLMError as exc:
        return {
            "ok": False,
            "agent": "none",
            "error": str(exc),
            "codebase_context": ctx_summary,
            "cached": False,
        }


def _merge_epics(
    base: list[dict[str, Any]], extra: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Union stories by loose title key; keep base order, append new from extra."""
    import re

    def key(t: str) -> str:
        return re.sub(r"\W+", " ", (t or "").lower()).strip()

    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    def add_epic(ep: dict[str, Any]) -> None:
        title = str(ep.get("title") or "Backlog")
        stories = []
        for st in ep.get("stories") or []:
            k = key(st.get("title") or "")
            if not k or k in seen:
                continue
            seen.add(k)
            stories.append(st)
        if stories:
            out.append(
                {
                    "title": title,
                    "description": ep.get("description") or "",
                    "stories": stories,
                }
            )

    for ep in base:
        add_epic(ep)
    for ep in extra:
        # try fold into existing epic with same title
        et = key(ep.get("title") or "")
        matched = False
        for existing in out:
            if key(existing["title"]) == et:
                for st in ep.get("stories") or []:
                    k = key(st.get("title") or "")
                    if not k or k in seen:
                        continue
                    seen.add(k)
                    existing["stories"].append(st)
                matched = True
                break
        if not matched:
            add_epic(ep)
    return out[:8]
