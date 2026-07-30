from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, SessionLocal, engine, run_migrations
from .routers import ai, backlog, export, import_projects, projects, sprints
from .services.seed import seed_if_empty

Base.metadata.create_all(bind=engine)
# Patch in columns added after the first release (no-op on a fresh DB).
run_migrations()

# Demo seed when DB has no projects (first boot / wiped data)
try:
    _db = SessionLocal()
    seed_if_empty(_db)
finally:
    _db.close()

app = FastAPI(
    title="Sprintline API",
    description="Agile workspace API: projects, backlog, sprints, export",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(backlog.router)
app.include_router(sprints.router)
app.include_router(ai.router)
app.include_router(export.router)
app.include_router(import_projects.router)


@app.get("/api/health")
def health():
    ai = get_settings().ai_status()
    return {
        "status": "ok",
        "service": "ai-project-lifecycle",
        "ai": ai,
    }
