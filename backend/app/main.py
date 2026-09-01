from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.db_migrations import ensure_schema
from app.routers import activities_export, azure_devops, calendar_exceptions, collaborator_absences, collaborators, dashboard, imports, inconsistencies_report
from app.routers import settings as settings_router
from app.services.azure_devops_config import migrate_env_to_db_if_needed
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
        migrate_env_to_db_if_needed(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Painel de Aderência de Atividades", version="1.0.0", lifespan=lifespan)

origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(collaborators.router, prefix="/api")
app.include_router(collaborator_absences.router, prefix="/api")
app.include_router(calendar_exceptions.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(azure_devops.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(activities_export.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(inconsistencies_report.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
