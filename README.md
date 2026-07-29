# Sprintline

**Product name:** Sprintline  
**Official academic title:** AI-Enabled Intelligent Project Lifecycle Management System Using Generative AI and Agile Project Management  
**Stack:** React + TypeScript + Vite + Tailwind · FastAPI · SQLite  
**UI:** Light, dense workspace (Linear-inspired) — teal accent, IBM Plex Sans

Product brief: [PROJECT.md](./PROJECT.md)

## Submission docs (start here for report / viva)

| Document | Path |
|----------|------|
| Abstract | [docs/ABSTRACT.md](./docs/ABSTRACT.md) |
| Architecture | [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) |
| Demo script & how to run | [docs/DEMO_SCRIPT.md](./docs/DEMO_SCRIPT.md) |
| Evaluation methodology | [docs/EVALUATION.md](./docs/EVALUATION.md) |

## What makes this more than a thin UI

1. **Multi-agent pipeline** — backlog draft → critic → sprint plan → standup → evaluation (`backend/app/services/pipeline.py`).
2. **Critic agent** — flags missing AC, vague titles, large stories, capacity overload; never silently overwrites user edits.
3. **Evaluation layer** — AC coverage %, INVEST-style rubric, sprint planned vs done/remaining points (`GET .../ai/evaluate`).
4. **Explainability** — each agent returns structured data + rationale; UI surfaces both.
5. **Human-in-the-loop** — board + story editor are source of truth; AI apply is explicit.

## Features

| Feature | Status |
|---------|--------|
| Project workspace (brief, goals, constraints) | ✅ |
| AI backlog generator (epics → stories → AC → points + rationale) | ✅ pipeline + stub |
| Critic quality pass | ✅ |
| Sprint board (To-do / In progress / Done) | ✅ |
| Story editor | ✅ |
| AI sprint planner (capacity-aware + critic) | ✅ |
| AI standup / status summary | ✅ |
| Evaluation metrics (AC / INVEST / sprint pts) | ✅ |
| Export Markdown / JSON | ✅ |
| College docs package | ✅ |

AI agents use **deterministic stubs** that return structured JSON + rationale (offline demo). Swap internals for Groq/Ollama/OpenAI later without changing the REST contract.

## Quick start

### Prerequisites

- Python **3.11**
- Node.js 20+

### Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API docs: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/api/health  
- SQLite: `backend/data/app.db`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

- UI: http://127.0.0.1:5173  
- Vite proxies `/api` → backend.

### Tests

```bash
cd backend && source .venv/bin/activate && pytest -q
```

## Demo path (short)

1. Create project with brief → **Generate backlog** (pipeline + critic).  
2. Edit a story (human-in-the-loop).  
3. **AI sprint plan** → **Board** status moves.  
4. **Standup** → **Quality & metrics** (AC %, INVEST, sprint points).  
5. **Export** Markdown for the report appendix.

Full script: [docs/DEMO_SCRIPT.md](./docs/DEMO_SCRIPT.md).

## Repo layout

```
├── PROJECT.md
├── README.md
├── docs/                 # Abstract, architecture, demo, evaluation
├── backend/
│   ├── app/
│   │   ├── routers/      # projects, backlog, sprints, ai, export
│   │   └── services/     # ai_stub, critic, evaluation, pipeline, export
│   └── tests/            # pure logic + API e2e
└── frontend/src/         # pages, CriticPanel, MetricsPanel, board, editor
```

## Key API routes

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/projects` | Create workspace |
| POST | `/api/projects/{id}/ai/generate-backlog` | Draft + critic + metrics preview |
| POST | `/api/projects/{id}/ai/critique` | Critic only (no story mutation) |
| GET | `/api/projects/{id}/ai/evaluate` | AC / INVEST / sprint metrics |
| POST | `/api/projects/{id}/ai/plan-sprint` | Sprint scope + capacity critic |
| POST | `/api/projects/{id}/ai/standup` | Status summary |
| PATCH | `/api/projects/{id}/stories/{sid}` | User edit |
| GET | `/api/projects/{id}/export?format=markdown\|json` | Export |

## Non-goals (v1)

Full Jira replacement, multi-tenant RBAC, autonomous coding agents, mandatory paid LLM for demos.
