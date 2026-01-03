"""
TekVwarho ProAudit - FastAPI Application Entry Point

This is the main entry point for the FastAPI application.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Handles startup and shutdown events.
    """
    # Startup
    print(f"🚀 Starting {settings.app_name}...")
    print(f"📊 Environment: {settings.app_env}")
    print(f"🔗 Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    
    # Initialize database (dev only - use migrations in production)
    if settings.is_development:
        await init_db()
        print("✅ Database tables initialized")
    
    yield
    
    # Shutdown
    print(f"🛑 Shutting down {settings.app_name}...")
    await close_db()
    print("✅ Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Nigeria's Premier Tax Compliance & Business Management Platform for the 2026 Tax Reform Era",
    version="0.1.0",
    docs_url="/api/docs" if settings.is_development else None,
    redoc_url="/api/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")


# ===========================================
# API ROUTES
# ===========================================

@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
        "environment": settings.app_env,
        "api_docs": "/api/docs" if settings.is_development else "disabled",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database": "connected",
    }


@app.get("/api/v1")
async def api_root():
    """API v1 root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name} API v1",
        "endpoints": {
            "auth": "/api/v1/auth",
            "entities": "/api/v1/entities",
            "transactions": "/api/v1/entities/{entity_id}/transactions",
            "invoices": "/api/v1/entities/{entity_id}/invoices",
            "vendors": "/api/v1/entities/{entity_id}/vendors",
            "reports": "/api/v1/entities/{entity_id}/reports",
        }
    }


# ===========================================
# INCLUDE ROUTERS
# ===========================================

from app.routers import (
    auth, entities, categories, vendors, customers, 
    transactions, invoices, tax, inventory, receipts,
    reports, audit, views, tax_2026,
)

# View Routes (HTML pages)
app.include_router(views.router, tags=["Views"])

# Authentication
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])

# Business Entities
app.include_router(entities.router, prefix="/api/v1/entities", tags=["Business Entities"])

# Entity Sub-resources (nested under entities)
app.include_router(categories.router, prefix="/api/v1/entities", tags=["Categories"])
app.include_router(vendors.router, prefix="/api/v1/entities", tags=["Vendors"])
app.include_router(customers.router, prefix="/api/v1/entities", tags=["Customers"])
app.include_router(transactions.router, prefix="/api/v1/entities", tags=["Transactions"])
app.include_router(invoices.router, prefix="/api/v1/entities", tags=["Invoices"])
app.include_router(inventory.router, prefix="/api/v1/entities", tags=["Inventory"])
app.include_router(receipts.router, prefix="/api/v1/entities", tags=["Receipts & Files"])
app.include_router(reports.router, prefix="/api/v1/entities", tags=["Reports & Dashboard"])
app.include_router(audit.router, prefix="/api/v1/entities", tags=["Audit Trail"])

# Tax Management
app.include_router(tax.router, prefix="/api/v1/tax", tags=["Tax Management"])

# 2026 Tax Reform APIs
app.include_router(tax_2026.router, prefix="/api/v1/tax-2026", tags=["2026 Tax Reform"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5120,
        reload=settings.is_development,
    )
