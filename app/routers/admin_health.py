"""
Admin Health Router - Platform Health Metrics for Super Admin.

Provides endpoints for monitoring platform health, performance metrics,
system status, and operational dashboards.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.dependencies import require_super_admin
from app.models.user import User
from app.services.admin_health_service import AdminHealthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/health", tags=["Admin - Platform Health"])


def json_response(data: dict) -> dict:
    """Standardized JSON response wrapper."""
    return {"success": True, **data}


@router.get("")
async def get_dashboard_summary(
    current_user: User = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get dashboard summary with key platform metrics.
    
    Returns a combined view of platform status, quick stats,
    security alerts, and resource utilization.
    
    - **Requires**: Super Admin role
    """
    service = AdminHealthService(db)
    summary = await service.get_dashboard_summary()
    
    logger.info(f"Admin {current_user.email} accessed platform dashboard summary")
    
    return json_response({"dashboard": summary})


@router.get("/overview")
async def get_platform_overview(
    current_user: User = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get platform overview with user and organization statistics.
    
    Returns counts and breakdowns for:
    - Users (total, active, new today/week)
    - Organizations (total, active, by verification status)
    - Platform staff
    - Recent activity metrics
    
    - **Requires**: Super Admin role
    """
    service = AdminHealthService(db)
    overview = await service.get_platform_overview()
    
    logger.info(f"Admin {current_user.email} accessed platform overview")
    
    return json_response({"overview": overview})


@router.get("/system")
async def get_system_health(
    current_user: User = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get system health metrics including server resources.
    
    Returns:
    - Overall health status (healthy/degraded/critical)
    - CPU, memory, and disk usage
    - Database connection status and latency
    - System information
    
    - **Requires**: Super Admin role
    """
    service = AdminHealthService(db)
    health = await service.get_system_health()
    
    logger.info(f"Admin {current_user.email} accessed system health metrics")
    
    return json_response({"health": health})


@router.get("/trends")
async def get_activity_trends(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get activity trends over time.
    
    Returns:
    - Daily activity counts (events, unique users)
    - Hourly distribution for today
    - User growth trend
    - Organization growth trend
    
    - **days**: Number of days to analyze (1-365, default 30)
    - **Requires**: Super Admin role
    """
    service = AdminHealthService(db)
    trends = await service.get_activity_trends(days=days)
    
    logger.info(f"Admin {current_user.email} accessed activity trends for {days} days")
    
    return json_response({"trends": trends})


@router.get("/organizations")
async def get_organization_health_summary(
    current_user: User = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get health summary across all organizations.
    
    Returns:
    - Top organizations by user count
    - Organization details (name, status, user count)
    - Activity summary (active vs inactive this week)
    
    - **Requires**: Super Admin role
    """
    service = AdminHealthService(db)
    org_health = await service.get_organization_health_summary()
    
    logger.info(f"Admin {current_user.email} accessed organization health summary")
    
    return json_response({"organization_health": org_health})


@router.get("/security")
async def get_security_metrics(
    current_user: User = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get security-related metrics.
    
    Returns:
    - Login security (successful/failed logins, failure rate)
    - Password security (resets, users requiring reset)
    - User verification status
    - Security anomalies
    
    - **Requires**: Super Admin role
    """
    service = AdminHealthService(db)
    security = await service.get_security_metrics()
    
    logger.info(f"Admin {current_user.email} accessed security metrics")
    
    return json_response({"security": security})


@router.get("/feature-usage")
async def get_feature_usage_metrics(
    current_user: User = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get feature usage metrics based on audit log actions.
    
    Returns:
    - Most used actions in the last 7 days
    - Entity type usage breakdown
    
    - **Requires**: Super Admin role
    """
    service = AdminHealthService(db)
    usage = await service.get_feature_usage_metrics()
    
    logger.info(f"Admin {current_user.email} accessed feature usage metrics")
    
    return json_response({"feature_usage": usage})
