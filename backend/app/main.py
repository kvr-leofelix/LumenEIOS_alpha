from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.session import init_db, AsyncSessionLocal
from backend.app.api.v1.router import api_router
from backend.app.seed.seed_data import seed_database_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing LumenEIOS database tables...")
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_database_if_empty(session)
    logger.info("LumenEIOS Backend successfully started.")
    yield
    logger.info("LumenEIOS Backend shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Adaptive EdTech Ecosystem Backend aligned with NEP 2020 Competency Standards",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": "connected"
    }


@app.get("/ready", tags=["Health"])
async def readiness_check():
    return {"ready": True}


# Mount API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

