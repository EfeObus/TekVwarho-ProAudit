"""
TekVwarho ProAudit - FastAPI Application Entry Point

This is the main entry point for the FastAPI application.
"""

import logging
import traceback
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import init_db, close_db, async_session_factory
from app.utils.error_handling import (
    AppException,
    setup_exception_handlers,
    ErrorTrackingMiddleware,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def seed_super_admin():
    """
    Seed the hardcoded Super Admin user on startup.
    This ensures there's always a Super Admin account available.
    """
    from app.services.staff_management_service import StaffManagementService
    
    async with async_session_factory() as session:
        service = StaffManagementService(session)
        try:
            super_admin = await service.get_or_create_super_admin()
            logger.info(f"Super Admin ready: {super_admin.email}")
        except Exception as e:
            logger.warning(f"Could not seed Super Admin: {e}")


async def seed_platform_test_entity():
    """
    Seed the platform test organization and entity on startup.
    This provides a demo business for platform staff to use when testing features.
    """
    from app.services.staff_management_service import StaffManagementService
    
    async with async_session_factory() as session:
        service = StaffManagementService(session)
        try:
            demo_entity = await service.get_or_create_platform_test_entity()
            logger.info(f"Platform Test Entity ready: {demo_entity.name}")
        except Exception as e:
            logger.warning(f"Could not seed Test Entity: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name}...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    
    # Initialize database (dev only - use migrations in production)
    if settings.is_development:
        await init_db()
        logger.info("Database tables initialized")
    
    # Seed Super Admin
    try:
        await seed_super_admin()
    except Exception as e:
        logger.warning(f"Super Admin seeding skipped: {e}")
    
    # Seed Platform Test Entity for staff testing
    try:
        await seed_platform_test_entity()
    except Exception as e:
        logger.warning(f"Test Entity seeding skipped: {e}")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}...")
    await close_db()
    logger.info("Database connections closed")


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

# Setup Security Middleware (NDPA/NITDA Compliance)
from app.middleware.security import setup_security_middleware
setup_security_middleware(
    app=app,
    development_mode=settings.is_development,
    geo_fencing_enabled=not settings.is_development,  # Disable geo-fencing in dev
    rate_limiting_enabled=True,  # Always enable, but relaxed in dev
    csrf_enabled=True,  # Always enable CSRF
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")


# ===========================================
# GLOBAL ERROR HANDLERS
# ===========================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTP exceptions with consistent error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "http_error"
            }
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors with detailed field info."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": 422,
                "message": "Validation error",
                "type": "validation_error",
                "details": errors
            }
        }
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": 422,
                "message": "Data validation error",
                "type": "validation_error",
                "details": errors
            }
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle value errors (business logic errors)."""
    logger.warning(f"ValueError: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": {
                "code": 400,
                "message": str(exc),
                "type": "value_error"
            }
        }
    )


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError) -> JSONResponse:
    """Handle permission errors."""
    logger.warning(f"PermissionError: {exc}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "success": False,
            "error": {
                "code": 403,
                "message": str(exc) or "Permission denied",
                "type": "permission_error"
            }
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions."""
    # Log the full traceback for debugging
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    
    # Return generic error in production, detailed in development
    if settings.is_development:
        message = f"{type(exc).__name__}: {str(exc)}"
    else:
        message = "An unexpected error occurred. Please try again later."
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": 500,
                "message": message,
                "type": "internal_error"
            }
        }
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions with standardized format."""
    logger.error(
        f"AppException: {exc.code.value} - {exc.message}",
        extra={"code": exc.code.value, "path": request.url.path}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.to_dict()
        }
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle SQLAlchemy database errors."""
    from sqlalchemy.exc import IntegrityError, OperationalError, DataError
    
    error_message = "A database error occurred"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_type = "database_error"
    
    if isinstance(exc, IntegrityError):
        error_str = str(exc.orig).lower() if exc.orig else ""
        if "unique" in error_str or "duplicate" in error_str:
            error_message = "A record with this value already exists"
            status_code = status.HTTP_409_CONFLICT
            error_type = "duplicate_entry"
        elif "foreign key" in error_str:
            error_message = "Referenced record does not exist"
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            error_type = "foreign_key_violation"
        else:
            error_message = "Data integrity constraint violated"
            error_type = "integrity_error"
    elif isinstance(exc, OperationalError):
        error_message = "Database connection or operation failed"
        error_type = "connection_error"
    elif isinstance(exc, DataError):
        error_message = "Invalid data format for database field"
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        error_type = "data_error"
    
    logger.error(f"SQLAlchemyError ({error_type}): {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": status_code,
                "message": error_message,
                "type": error_type
            }
        }
    )


# ===========================================
# API ROUTES
# ===========================================

@app.get("/api")
async def api_info():
    """API information endpoint."""
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
            "staff": "/api/v1/staff",
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
    reports, audit, views, tax_2026, staff, organization_users,
    fixed_assets, sales, dashboard, payroll, payroll_views,
    # New routers added
    notifications, self_assessment, organization_settings,
    bulk_operations, exports, search_analytics,
    # 2026 Tax Reform Advanced Features
    advanced_accounting,
    # Business Intelligence (BIK, NIBSS, Growth Radar, Inventory)
    business_intelligence,
    # World-Class Forensic Audit (Benford's Law, Z-Score, NRS Gap, WORM)
    forensic_audit,
    # Enterprise Advanced Audit (Explainability, Replay, Confidence, Attestation, Export, Behavioral)
    advanced_audit,
    # Advanced Audit System (Immutable Evidence, Reproducible Runs, Human-Readable Findings)
    audit_system,
    # Advanced Payroll (Compliance, Impact Preview, Exceptions, Decision Logs, YTD, CTC)
    payroll_advanced,
    # NRS Integration (Invoice Reporting, TIN Validation, Disputes)
    nrs,
    # Bank Reconciliation
    bank_reconciliation,
    # Expense Claims
    expense_claims,
    # Machine Learning & AI (OCR, Forecasting, NLP, Neural Networks)
    ml_ai,
)

# View Routes (HTML pages)
app.include_router(views.router, tags=["Views"])

# Authentication
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])

# Platform Staff Management (RBAC)
app.include_router(staff.router, prefix="/api/v1", tags=["Staff Management"])

# Organization User Management
app.include_router(organization_users.router, prefix="/api/v1", tags=["Organization Users"])

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
app.include_router(sales.router, prefix="/api/v1/entities", tags=["Sales Recording"])

# Tax Management
app.include_router(tax.router, prefix="/api/v1/tax", tags=["Tax Management"])

# 2026 Tax Reform APIs
app.include_router(tax_2026.router, prefix="/api/v1/tax-2026", tags=["2026 Tax Reform"])

# Fixed Asset Register (2026)
app.include_router(fixed_assets.router, tags=["Fixed Assets"])

# World-Class Dashboards (NTAA 2025)
app.include_router(dashboard.router, tags=["Dashboard"])

# Notifications
app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"])

# Self-Assessment & Tax Returns
app.include_router(self_assessment.router, tags=["Self-Assessment"])

# Organization Settings
app.include_router(organization_settings.router, tags=["Organization Settings"])

# Bulk Operations (Import/Export)
app.include_router(bulk_operations.router, tags=["Bulk Operations"])

# Export & Download
app.include_router(exports.router, tags=["Export & Download"])

# Search & Analytics
app.include_router(search_analytics.router, tags=["Search & Analytics"])

# Payroll System (Nigerian Compliance)
app.include_router(payroll.router, prefix="/api/v1/payroll", tags=["Payroll"])

# Payroll HTML Views
app.include_router(payroll_views.router, tags=["Payroll Views"])

# Advanced Payroll (Compliance Status, Impact Preview, Exceptions, Decision Logs, YTD, CTC, What-If)
app.include_router(payroll_advanced.router, prefix="/api/v1/payroll/advanced", tags=["Advanced Payroll"])

# 2026 Tax Reform Advanced Features (3-Way Matching, WHT Vault, Approvals, AI)
app.include_router(advanced_accounting.router, tags=["Advanced Accounting"])

# Business Intelligence (BIK Automator, NIBSS Pension, Growth Radar, Inventory Management)
app.include_router(business_intelligence.router, tags=["Business Intelligence"])

# World-Class Forensic Audit (Benford's Law, Z-Score Anomaly, NRS Gap, WORM Storage)
app.include_router(forensic_audit.router, prefix="/api/v1/entities", tags=["Forensic Audit"])

# Enterprise Advanced Audit (Explainability, Replay, Confidence, Attestation, Export, Behavioral Analytics)
app.include_router(advanced_audit.router, prefix="/api/v1/entities", tags=["Advanced Audit"])

# Advanced Audit System (Immutable Evidence, Reproducible Runs, Auditor Read-Only, Human-Readable Findings)
app.include_router(audit_system.router, tags=["Audit System"])

# NRS Integration (Invoice Reporting System - 2026 Compliance)
app.include_router(nrs.router, prefix="/api/v1", tags=["NRS Integration"])

# Bank Reconciliation
app.include_router(bank_reconciliation.router, prefix="/api/v1/entities", tags=["Bank Reconciliation"])

# Expense Claims
app.include_router(expense_claims.router, prefix="/api/v1/entities", tags=["Expense Claims"])

# Machine Learning & AI (OCR, Cash Flow Forecasting, Growth Prediction, NLP, Neural Networks)
app.include_router(ml_ai.router, prefix="/api/v1/ml", tags=["Machine Learning & AI"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5120,
        reload=settings.is_development,
    )
