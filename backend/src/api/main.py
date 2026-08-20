from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import get_settings
from ..core.database import init_db
from .routes import comparisons, evaluations, providers

settings = get_settings()

app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(evaluations.router, prefix="/api/v1/evaluations", tags=["evaluations"])
app.include_router(comparisons.router, prefix="/api/v1/comparisons", tags=["comparisons"])
app.include_router(providers.router, prefix="/api/v1/providers", tags=["providers"])


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.api_version}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to EvalForge API",
        "docs": "/docs",
        "health": "/health"
    }
