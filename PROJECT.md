# AI-Enabled Intelligent Project Lifecycle Management System

**Faculty:** Dr. B. Sandhya, Prof.  
**Theme:** Generative AI + Agile Project Management  
**Status:** Major-project build — multi-agent pipeline, critic, evaluation metrics, docs  
**Owner:** Srinesh R

---

## 1. One-liner

An AI-assisted platform that manages the **full software project lifecycle** (idea → backlog → sprints → docs → delivery) using **generative AI agents** aligned with **Agile** practices, with human control and explainable suggestions.

---

## 2. Problem

Teams lose time on:

- Turning vague requirements into backlog items
- Writing user stories, acceptance criteria, and estimates
- Keeping docs (PRD, sprint notes, retros) in sync with reality
- Tracking risk, blockers, and progress without constant manual updates

Existing tools (Jira, Linear, Notion) are strong on **tracking**, weak on **intelligent generation + lifecycle guidance**. Pure ChatGPT is strong on **text**, weak on **structured project state**.

---

## 3. Goal

Build a system that:

1. Accepts a project brief (text / upload)
2. Generates a structured Agile plan (epics → stories → tasks)
3. Supports sprint planning and day-to-day updates
4. Uses GenAI agents for drafting, prioritization hints, and status summaries
5. Keeps artifacts explainable (why this priority? why this estimate?)
6. Stays human-in-the-loop (AI proposes; user accepts/edits)

**Non-goals (v1):** full Jira replacement, multi-org enterprise RBAC, autonomous coding agents that write production repos end-to-end.

---

## 4. Core features (MVP → stretch)

### MVP (must ship)

| # | Feature | Notes |
|---|---------|--------|
| 1 | Project workspace | Create project, brief, goals, constraints |
| 2 | AI backlog generator | Epics, user stories, AC, rough story points |
| 3 | Sprint board | To-do / In progress / Done (Kanban) |
| 4 | Story editor | Edit AI output; version of truth is user data |
| 5 | AI sprint planner | Suggest sprint scope from capacity + priority |
| 6 | AI standup / status summary | From board + recent changes |
| 7 | Explainability | Short “why” for AI suggestions (priority, scope) |
| 8 | Export | Markdown / JSON of backlog + sprint report |

### Stretch (if time)

- Risk / dependency detector
- Retro generator from sprint history
- Multi-agent pipeline (Planner, Writer, Critic, Scrum Master)
- Import from GitHub issues / Linear CSV
- Role-based views (PM vs developer)
- RAG over uploaded PRD/spec PDFs

---

## 5. Suggested architecture

```
┌─────────────────────────────────────────────────┐
│  Web UI (React + TypeScript + Vite)             │
│  Board · Stories · AI chat panel · Reports      │
└──────────────────────┬──────────────────────────┘
                       │ REST / WebSocket
┌──────────────────────▼──────────────────────────┐
│  API (FastAPI or Node)                          │
│  Projects · Stories · Sprints · Auth            │
│  Agent orchestrator (propose → review → apply)  │
└──────────┬───────────────────────┬──────────────┘
           │                       │
    ┌──────▼──────┐         ┌──────▼──────┐
    │  DB         │         │  LLM        │
    │  Postgres / │         │  Groq /     │
    │  Supabase / │         │  Ollama /   │
    │  SQLite     │         │  OpenAI API │
    └─────────────┘         └─────────────┘
```

**Agent sketch (keep simple first):**

1. **Intake agent** — brief → structured project model  
2. **Backlog agent** — epics / stories / AC  
3. **Sprint agent** — capacity-aware selection  
4. **Summarizer agent** — standup / weekly report  
5. **Critic (optional)** — flags vague stories, missing AC, overload  

All agents return **JSON + short rationale**, never silent writes without user confirm (MVP).

---

## 6. Tech stack (aligned to existing skills)

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | React, TypeScript, Vite, Tailwind | Same as Kairo / Boards |
| State | Zustand or React Query | Familiar |
| Backend | FastAPI (Python) or Node | FastAPI if agents + JSON schemas |
| DB | Supabase / Postgres / SQLite | Supabase if auth needed quick |
| LLM | Groq (fast) + optional Ollama local | Already used in Kairo |
| Structured output | JSON schema / tool calling | Reliable backlog objects |
| Tests | Vitest + pytest | Don’t skip |

---

## 7. Data model (draft)

```
Project
  id, name, brief, goals[], constraints[], created_at

Epic
  id, project_id, title, description, order

Story
  id, epic_id, title, description, acceptance_criteria[]
  points, priority, status, rationale (AI why)

Sprint
  id, project_id, name, start, end, capacity_points, goal

SprintItem
  sprint_id, story_id

Activity / Event (optional)
  project_id, type, payload, created_at
```

---

## 8. Evaluation (for report / viva)

Measure something concrete:

- **Time saved:** minutes to produce backlog (AI-assisted vs manual)
- **Quality checklist:** % stories with AC, INVEST-ish score (simple rubric)
- **Edit rate:** how much user changes AI output (lower = better drafts)
- **Sprint realism:** planned points vs completed (over 1–2 mock sprints)
- **User study (n=3–5 classmates):** SUS or 1–5 usefulness scores

---

## 9. Semester milestones

| Phase | Weeks (approx) | Outcome |
|-------|----------------|---------|
| **M0** | 1 | Proposal approved, stack locked, repo ready |
| **M1** | 2–3 | Auth + project CRUD + empty board |
| **M2** | 4–5 | AI backlog generation + story editor |
| **M3** | 6–7 | Sprints + AI sprint plan + status summary |
| **M4** | 8 | Explainability + export + polish UI |
| **M5** | 9–10 | Eval, report, demo video, viva slides |

---

## 10. Title variants (for registration)

1. AI-Enabled Intelligent Project Lifecycle Management System Using Generative AI and Agile Project Management *(official list title)*  
2. GenAI Agile Copilot: Lifecycle Management from Brief to Sprint Delivery *(shorter demo name)*  

Use **(1)** in forms; **(2)** on slides if allowed.

---

## 11. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| LLM garbage backlog | Strict JSON schema + critic pass + user edit |
| Scope creep to “Jira 2.0” | MVP table is law; freeze features before M4 |
| API cost | Groq free tier / Ollama offline for demos |
| Looks like a chatbot wrapper | Persist structured state; board is source of truth |
| Faculty wants more “research” | Add multi-agent critic + eval metrics + ablation (with/without critic) |

---

## 12. Next actions (start here)

- [ ] Confirm with Dr. B. Sandhya that this topic is allotted
- [x] Create git repo (`ai-project-lifecycle`)
- [x] Scaffold frontend + backend
- [x] Define JSON schema for Story / Epic / Sprint
- [x] Implement “brief → backlog” happy path end-to-end
- [ ] Write 1-page abstract for department form

---

## 13. Notes / log

| Date | Note |
|------|------|
| 2026-07-27 | Topic chosen from CSE Allied list (Sandhya). Robot house-scan idea parked. Project folder created. |
| 2026-07-29 | MVP monorepo: FastAPI+SQLite, React+Vite board, AI stubs (backlog/sprint/standup), export. E2E demo OK. |
| 2026-07-29 | Elevated: multi-agent pipeline, critic, AC/INVEST/sprint metrics API+UI, docs/ submission package. |

---

## 14. References (fill as you go)

- Agile / Scrum Guide  
- INVEST criteria for user stories  
- Papers / blogs on LLM agents for software engineering (add citations later)  
- Groq / chosen LLM provider docs  

---

*Continue from this file: update status, checkboxes, milestones, and architecture as decisions firm up.*
