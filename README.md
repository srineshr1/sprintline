# Sprintline

**Product name:** Sprintline  
**Official academic title:** AI-Enabled Intelligent Project Lifecycle Management System Using Generative AI and Agile Project Management  
**Stack:** React + TypeScript + Vite + Tailwind · FastAPI · SQLite  
**UI:** Dense workspace (Linear-inspired) — teal accent, IBM Plex Sans, light + dark themes

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
| Dark mode (system-aware, light/dark/system toggle) | ✅ |
| Auto-import projects + todos from a local folder | ✅ |
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

AI agents use **Groq** when `GROQ_API_KEY` is set in `backend/.env` (packs real project files for import + backlog generation). Without a key they fall back to **deterministic stubs** so the app still demos offline.

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

### Environment variables

Copy `backend/.env.example` → `backend/.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROQ_API_KEY` | — | Enables real AI (Groq). Required for true LLM backlog / import analysis. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Chat model id on Groq. |
| `SPRINTLINE_AI_MODE` | `auto` | `auto` (Groq if key set), `groq`, or `stub` (force offline). |
| `PROJECTS_ROOT` | repo's parent directory | Folder scanned by **Import from folder**. Scanning is confined to it. |
| `PROJECTS_ROOTS` | — | Extra allowed roots, `:`-separated (e.g. `/work/a:/work/b`). |
| `SPRINTLINE_DB_PATH` | `backend/data/app.db` | Redirect the SQLite file. The test suite sets this so runs don't touch your dev data. |

```bash
# backend/.env
GROQ_API_KEY=gsk_...
PROJECTS_ROOT=~/Projects
```

```bash
PROJECTS_ROOT=~/Projects uvicorn app.main:app --reload --port 8000
```

**Import + AI:** Scan packs README, package manifests, and key source files (skips `.env`, `node_modules`, binaries) and sends them to Groq. The UI lists every file path that was included. **Generate backlog** on an imported project re-reads that `source_path` the same way.

Paths outside the allowed roots are rejected (400), including `..` traversal
and symlinks pointing out of the root.

### Import from a projects folder

**Projects → Import from folder → Scan**, review the preview, tick the folders
you want, then **Import**. Nothing is written until you apply.

Per folder, the scanner infers:

- **name** — folder name, humanized (`my_cool-app` → "My Cool App")
- **brief** — intro prose of `README.md` / `PROJECT.md` / `brief.md` / `description.md`
- **goals / constraints** — bullets under those headings (or "Non-goals")
- **stories** — from `TODO.md` / `TODOS.md` / `BACKLOG.md` / `TASKS.md`
  (`##` headings become epics), `todos.json` / `backlog.json` / `tasks.json`,
  or a plain `.todo` file

Checklist state maps `- [ ]` → *To do*, `- [~]` → *In progress*, `- [x]` →
*Done*. A trailing `(5)` sets points and `[high]` sets priority; defaults are 3
points / medium.

Re-importing is safe: a folder is keyed by its path, so a second import
**re-syncs** it — only todos that aren't already stories get added, and your
edits, points and statuses are left alone.

### Theme

The sun/moon button (sidebar footer, and the mobile top bar) cycles
**light → dark → system**. The choice persists in `localStorage`; `system`
follows `prefers-color-scheme` live. A dot on the button means "following
system".

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
│   │   ├── routers/      # projects, backlog, sprints, ai, export, import
│   │   └── services/     # ai_stub, critic, evaluation, pipeline, export, importer
│   └── tests/            # pure logic + API e2e + import scanner
└── frontend/src/         # pages, board (FLIP moves), import dialog, theming
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
| GET | `/api/import/roots` | Allowed scan roots |
| POST | `/api/import/scan` | Dry-run preview of a projects folder |
| POST | `/api/import/apply` | Create / re-sync projects from folders |

## Non-goals (v1)

Full Jira replacement, multi-tenant RBAC, autonomous coding agents, mandatory paid LLM for demos.
