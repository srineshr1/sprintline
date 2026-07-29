# Architecture Overview

**Product theme:** GenAI Agile Copilot — generative AI agents aligned with Agile project lifecycle management (brief → backlog → sprint → status → evaluation), with human-in-the-loop control and measurable quality metrics.

## 1. Problem

| Pain | Gap in existing tools |
|------|------------------------|
| Vague brief → backlog is manual and slow | Trackers store tickets; they do not generate INVEST-quality stories |
| AI chat drafts are unstructured | No epics/stories/AC schema or persistence |
| No measurement of AI draft quality | No critic or AC/INVEST metrics for evaluation |
| Sprint over-commitment | No capacity-aware proposal + explainability |

## 2. Approach

**Propose → critique → human edit → apply → measure.**

```
Brief / goals / constraints
        │
        ▼
┌───────────────────┐
│  Intake + Backlog │  structured epics, stories, AC, points, rationale
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Critic agent     │  missing AC, vague titles, large stories, …
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  User review      │  story editor (source of truth)
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Sprint agent     │  priority + capacity selection
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Capacity critic  │  overload / underload flags
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Board + Standup  │  status updates → summary agent
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Evaluation       │  AC %, INVEST rubric, sprint pts
└───────────────────┘
```

## 3. Agents

| Agent | Role | Output |
|-------|------|--------|
| **Backlog (draft)** | Brief → epics/stories/AC/points/priority | JSON + rationale |
| **Critic** | Quality pass on stories / sprint scope | Findings (`code`, `severity`, `message`) + rationale |
| **Sprint** | Select incomplete high-priority stories up to capacity | Story IDs, total points, rationale |
| **Standup / summarizer** | Board columns → narrative status | Markdown-ish summary + blockers |
| **Evaluation** | Metrics for report/viva | AC coverage, INVEST scores, sprint planned/done/remaining |

Orchestration lives in `backend/app/services/pipeline.py`. Pure rules for critic and metrics are in `critic.py` and `evaluation.py` so they are unit-tested without mocking the business logic.

## 4. Data model

```
Project → Epic → Story
Project → Sprint → SprintItem → Story
Project → Activity (audit log of AI/user events)
```

Stories store: title, description, acceptance_criteria[], points, priority, status (`todo` | `in_progress` | `done`), rationale (AI “why”).

SQLite file: `backend/data/app.db`.

## 5. API surface (selected)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/projects` | Create workspace |
| POST | `/api/projects/{id}/ai/generate-backlog` | Pipeline: draft + critic + metrics preview |
| POST | `/api/projects/{id}/ai/critique` | Critic only (no write to stories) |
| GET | `/api/projects/{id}/ai/evaluate` | AC / INVEST / sprint metrics |
| POST | `/api/projects/{id}/ai/plan-sprint` | Sprint plan + capacity critic (`apply` optional) |
| POST | `/api/projects/{id}/ai/standup` | Standup + open-work critic + metrics snapshot |
| PATCH | `/api/projects/{id}/stories/{sid}` | User edit (source of truth) |
| GET | `/api/projects/{id}/export?format=markdown\|json` | Report export |

## 6. UI

React SPA with tabs: Overview · Backlog (+ story editor) · Board · Sprints · **Quality & metrics** · Export.  
Critic findings and evaluation panels surface agent output without replacing the board.

## 7. Design principles

1. **Structured state over chat** — board/DB is truth.  
2. **Human-in-the-loop** — AI proposes; apply is explicit; critique never mutates titles/AC.  
3. **Explainability** — every agent returns a short rationale.  
4. **Measurable** — metrics endpoints support evaluation section of the report.  
5. **Offline demo** — deterministic stubs; LLM can replace stub internals later without API rewrite.

## 8. Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | React, TypeScript, Vite, Tailwind |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| DB | SQLite |
| Tests | pytest (pure agent logic + API e2e) |
