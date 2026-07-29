# Demo Script & How to Run

**Product:** GenAI Agile Copilot (AI-enabled Agile project lifecycle).  
**Shows:** multi-agent pipeline, human-in-the-loop story editing, critic findings, and evaluation metrics (AC coverage, INVEST rubric, sprint points).

## Prerequisites

- **Python 3.11** (recommended; create venv under `backend/.venv`)
- **Node.js 20+**
- Ports **8000** (API) and **5173** (UI) free

## Start backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API docs: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/api/health  

## Start frontend

```bash
cd frontend
npm install
npm run dev
```

- UI: http://127.0.0.1:5173  
- Vite proxies `/api` → `http://127.0.0.1:8000`

## Automated tests

```bash
cd backend
source .venv/bin/activate
pytest -q
```

## Viva walkthrough (≈8–10 minutes)

### 1. Create project workspace (1 min)

1. Open the UI → **New project**.  
2. Name: `Campus Events App`.  
3. Brief: *Students discover campus events, RSVP, and get reminders. Admin moderation.*  
4. Goals (one per line): `Ship MVP in 8 weeks` / `Demo for viva`.  
5. Constraints: `Team of 3` / `SQLite only`.  
6. Create workspace.

### 2. Multi-agent backlog generation (2 min)

1. Click **Generate backlog**.  
2. Point out **pipeline rationale** (steps: intake → backlog draft → critic → eval preview).  
3. Open **Backlog** tab: epics and stories with AC, points, priority, AI rationale.  
4. Show **critic findings** (advisory quality flags).

### 3. Human-in-the-loop edit (1 min)

1. Select a story → **Story editor**.  
2. Change title or AC → **Save**.  
3. State: *user data is source of truth; re-running critic does not overwrite edits.*

### 4. Sprint planning + capacity critic (2 min)

1. **AI sprint plan** (apply).  
2. **Sprints** tab: selected stories within capacity.  
3. Show critic/pipeline notes on capacity and story quality.

### 5. Board + standup (1–2 min)

1. **Board** → move a card To-do → In progress → Done.  
2. **Standup** → drafted summary from live board status.

### 6. Evaluation metrics (2 min)

1. **Quality & metrics** tab → **Refresh metrics**.  
2. Report:  
   - **AC coverage %**  
   - **INVEST average** + dimension pass rates  
   - **Sprint planned / done / remaining points**  
3. Tie to report section “Evaluation methodology”.

### 7. Export (1 min)

1. **Export** → download Markdown (report appendix) or JSON (structured dump).

## API-only demo (optional)

```bash
BASE=http://127.0.0.1:8000/api
# create → generate-backlog → critique → evaluate → plan-sprint → standup → export
```

See interactive docs at `/docs` for request bodies.
