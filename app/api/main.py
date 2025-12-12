"""
FastAPI Application

This is the main FastAPI application that serves as the orchestration layer
between the CLI, GitHub API, and Devin API.

Usage:
    Run with: uvicorn app.api.main:app --reload
    API docs: http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Github Issues Automation with Devin",
    description="""
    REST API for automating GitHub issue management with Devin AI.
    
    ## Features
    
    * **List Issues** - Fetch and filter GitHub issues
    * **Scope Issues** - Use Devin to analyze issues and provide confidence scores (To-Do)
    * **Execute Issues** - Devin automatically implements and creates PRs (To-Do)
    * **Track Sessions** - Monitor all Devin sessions (To-Do)
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware (allows CLI to call API from localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from app.api.routes import router as api_router
app.include_router(api_router, prefix="/api/v1", tags=["issues"])


@app.get("/")
async def root():
    """
    Root endpoint.
    
    Returns basic information about the API.
    """
    return {
        "message": "Github Issues Automation with Devin",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns the health status of the API and its dependencies.
    """
    health_status = {
        "status": "healthy",
        "api": "operational",
        "github_token_configured": bool(settings.github_token and 
                                       settings.github_token != "your_github_token_here"),
        "devin_api_key_configured": bool(settings.devin_api_key and 
                                         settings.devin_api_key != "your_devin_api_key_here"),
    }
    
    return health_status


@app.on_event("startup")
async def startup_event():
    """
    Run when the API starts up.
    
    Performs initialization and validation.
    """
    logger.info("🚀 Starting Devin GitHub Issues Automation API")
    logger.info(f"📍 Orchestrator: {settings.orchestrator_host}:{settings.orchestrator_port}")
    logger.info(f"🔗 Devin API: {settings.devin_api_url}")
    
    # Validate configuration
    try:
        from app.config import validate_settings
        validate_settings()
        logger.info("✅ Configuration validated successfully")
    except ValueError as e:
        logger.warning(f"⚠️  Configuration warning: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Run when the API shuts down.
    
    Performs cleanup operations.
    """
    logger.info("👋 Shutting down Devin GitHub Issues Automation API")


if __name__ == "__main__":
    # This allows running with: python -m app.api.main
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host=settings.orchestrator_host,
        port=settings.orchestrator_port,
        reload=True
    )

