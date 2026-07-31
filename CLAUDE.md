# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Sprintline** — academic major project (official title: "AI-Enabled Intelligent Project Lifecycle Management System Using Generative AI and Agile Project Management"). An Agile workspace where GenAI agents draft backlog, sprint plans, and standups from a project brief, with a critic pass, explainability, and measurable quality metrics. See `PROJECT.md` for the full brief and `docs/ARCHITECTURE.md` for the design writeup (useful background for report/viva content, not just code).

Monorepo: `backend/` (FastAPI + SQLite) and `frontend/` (React + TypeScript + Vite + Tailwind).

## Commands

### Backend (from `backend/`)

```bash
python3.11 -m venv .venv && source .venv/bin/activate   # first time
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000                # dev server
pytest -q                                                 # all tests
pytest tests/test_api.py::test_name -q                    # single test
```

- API docs: http://127.0.0.1:8000/docs
- SQLite file: `backend/data/app.db` (gitignored)
- Tests redirect the DB via `SPRINTLINE_DB_PATH` and force `SPRINTLINE_AI_MODE=stub` in `tests/conftest.py` — never touches dev data or calls Groq.

### Frontend (from `frontend/`)

```bash
npm install
npm run dev        # Vite dev server on :5173, proxies /api to backend
npm run build       # tsc -b && vite build
npm run lint         # oxlint
```

No frontend test runner is configured.

## Architecture

**Flow:** brief → backlog draft (LLM or stub) → critic → human edit (source of truth) → sprint plan → capacity critic → board → standup → evaluation metrics. This propose-critique-edit-apply loop is the core design principle: AI never silently overwrites user-edited story data, and critique endpoints never mutate stories.

**Orchestration lives in `backend/app/services/pipeline.py`.** It composes three independently-testable layers:
- `ai_agents.py` (real, Groq-backed) / `ai_stub.py` (deterministic offline fallback) — same function signatures, so `pipeline.py` calls whichever is active without branching logic itself. `llm.py` wraps the Groq OpenAI-compatible client (`chat_json`/`chat_text`), including 429 handling that distinguishes short per-minute waits (retried inline) from daily token-limit errors (surfaced to the user, not retried).
- `critic.py` — pure rule-based quality checks (missing AC, vague titles, oversized stories, capacity overload). No LLM calls, fully unit-testable.
- `evaluation.py` — pure metrics (AC coverage %, INVEST rubric, sprint planned/done/remaining points). Also no LLM calls.

Keeping critic/evaluation as pure functions (vs. LLM calls) is deliberate — it's what makes them unit-testable and what the report's "evaluation" section measures.

**AI mode is decided centrally in `config.py`** (`Settings.use_llm()`): `SPRINTLINE_AI_MODE=auto|groq|stub` plus whether `GROQ_API_KEY` is set. Two model tiers exist by design — `GROQ_MODEL` (quality: backlog/sprint/standup) and `GROQ_IMPORT_MODEL` (cheap: bulk import enrich) — to avoid burning free-tier daily limits on folder scans.

**Import from folder** (`services/importer.py`, `routers/import_projects.py`) is a separate concern from the AI pipeline: scanning a local folder for README/TODO/backlog files to seed a project is always free (heuristic, no LLM). Only when a user explicitly selects folders for "AI enrich" does it call the cheap import model, with results cached on disk under `backend/data/ai_cache/` (`ai_cache.py`) so repeat scans don't re-spend tokens. Scanning is sandboxed to `PROJECTS_ROOT`/`PROJECTS_ROOTS` — path traversal and symlink escapes are rejected with 400. Re-importing the same folder path re-syncs (adds new todos, doesn't touch existing story edits/status).

**Data model:** `Project → Epic → Story`, `Project → Sprint → SprintItem → Story`, plus an `Activity` audit log. Stories carry `acceptance_criteria[]`, `points`, `priority`, `status`, and a `rationale` field (the AI's "why", surfaced in the UI rather than hidden). Schema changes to an existing SQLite file go through `database.py`'s `_ADDITIVE_COLUMNS` + `run_migrations()` (plain idempotent DDL, no Alembic — this is a demo-scale app, keep it that way unless asked otherwise).

**Routers** (`app/routers/`) are thin: `projects`, `backlog`, `sprints`, `ai` (pipeline endpoints: generate-backlog, critique, evaluate, plan-sprint, standup), `export` (Markdown/JSON), `import_projects`. Business logic belongs in `services/`, not routers.

**Frontend structure:** `pages/` (HomePage, ProjectPage) hold routing-level state; `components/` are presentational (`SprintBoard` does FLIP-animated drag moves via `lib/flip.ts`; `CriticPanel`/`MetricsPanel`/`RationalePanel` surface agent output). `api.ts` is the single fetch client, `types.ts` the shared TS types mirroring backend Pydantic schemas. Theme (`ThemeProvider`/`ThemeToggle`) is a light/dark/system cycle persisted to `localStorage`.

## Conventions

- Never persist AI output without an explicit user "apply" step — this is a stated non-negotiable in `docs/ARCHITECTURE.md`, not just a suggestion.
- Every agent function returns structured JSON plus a short `rationale` string; preserve this shape when touching `ai_agents.py`/`ai_stub.py`.
- `.env` files are gitignored; only `.env.example` is committed. Required var for real AI: `GROQ_API_KEY` (get one at https://console.groq.com).
