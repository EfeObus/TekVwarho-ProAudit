"""
Platform Health Service for Super Admin.

Provides comprehensive health metrics, system status, and operational dashboards
for platform administrators to monitor system health and performance.
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID
import os
import sys
import platform
import psutil

from sqlalchemy import select, func, and_, or_, desc, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.organization import Organization
from app.models.audit_consolidated import AuditLog


class AdminHealthService:
    """Service for platform health monitoring and metrics."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_platform_overview(self) -> Dict[str, Any]:
        """Get high-level platform overview metrics."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # User counts
        total_users_result = await self.db.execute(
            select(func.count(User.id))
        )
        total_users = total_users_result.scalar() or 0
        
        active_users_result = await self.db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        active_users = active_users_result.scalar() or 0
        
        # New users today
        new_users_today_result = await self.db.execute(
            select(func.count(User.id)).where(
                func.date(User.created_at) == today
            )
        )
        new_users_today = new_users_today_result.scalar() or 0
        
        # New users this week
        new_users_week_result = await self.db.execute(
            select(func.count(User.id)).where(
                func.date(User.created_at) >= week_ago
            )
        )
        new_users_week = new_users_week_result.scalar() or 0
        
        # Organization counts
        total_orgs_result = await self.db.execute(
            select(func.count(Organization.id))
        )
        total_orgs = total_orgs_result.scalar() or 0
        
        # Active orgs = not emergency suspended
        active_orgs_result = await self.db.execute(
            select(func.count(Organization.id)).where(
                Organization.is_emergency_suspended == False
            )
        )
        active_orgs = active_orgs_result.scalar() or 0
        
        # Organizations by verification status
        org_verification_result = await self.db.execute(
            select(
                Organization.verification_status,
                func.count(Organization.id)
            ).group_by(Organization.verification_status)
        )
        verification_breakdown = {
            str(row[0]): row[1] for row in org_verification_result.all()
        }
        
        # Platform staff count
        platform_staff_result = await self.db.execute(
            select(func.count(User.id)).where(User.is_platform_staff == True)
        )
        platform_staff_count = platform_staff_result.scalar() or 0
        
        # Active platform staff
        active_platform_staff_result = await self.db.execute(
            select(func.count(User.id)).where(
                and_(
                    User.is_platform_staff == True,
                    User.is_active == True
                )
            )
        )
        active_platform_staff = active_platform_staff_result.scalar() or 0
        
        # Recent activity (audit logs in last 24h)
        activity_24h_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.created_at >= datetime.utcnow() - timedelta(hours=24)
            )
        )
        activity_24h = activity_24h_result.scalar() or 0
        
        # Unique active users in last 24h
        active_24h_result = await self.db.execute(
            select(func.count(func.distinct(AuditLog.user_id))).where(
                AuditLog.created_at >= datetime.utcnow() - timedelta(hours=24)
            )
        )
        unique_active_24h = active_24h_result.scalar() or 0
        
        return {
            "users": {
                "total": total_users,
                "active": active_users,
                "inactive": total_users - active_users,
                "new_today": new_users_today,
                "new_this_week": new_users_week,
            },
            "organizations": {
                "total": total_orgs,
                "active": active_orgs,
                "inactive": total_orgs - active_orgs,
                "verification_status": verification_breakdown,
            },
            "platform_staff": {
                "total": platform_staff_count,
                "active": active_platform_staff,
            },
            "activity": {
                "last_24h_events": activity_24h,
                "unique_active_users_24h": unique_active_24h,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics including server resources."""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        
        # Disk usage
        disk = psutil.disk_usage('/')
        
        # Database connection test
        db_healthy = True
        db_latency = 0.0
        try:
            start = datetime.utcnow()
            await self.db.execute(text("SELECT 1"))
            db_latency = (datetime.utcnow() - start).total_seconds() * 1000  # ms
        except Exception as e:
            db_healthy = False
        
        # Python and system info
        system_info = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
        }
        
        # Calculate health status
        health_issues = []
        if cpu_percent > 90:
            health_issues.append("High CPU usage")
        if memory.percent > 90:
            health_issues.append("High memory usage")
        if disk.percent > 90:
            health_issues.append("Low disk space")
        if not db_healthy:
            health_issues.append("Database connection issue")
        elif db_latency > 100:  # ms
            health_issues.append("High database latency")
        
        overall_status = "healthy" if not health_issues else "degraded"
        if not db_healthy or cpu_percent > 95 or memory.percent > 95:
            overall_status = "critical"
        
        return {
            "status": overall_status,
            "issues": health_issues,
            "resources": {
                "cpu": {
                    "usage_percent": cpu_percent,
                    "core_count": psutil.cpu_count(),
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "usage_percent": memory.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "usage_percent": disk.percent,
                },
            },
            "database": {
                "connected": db_healthy,
                "latency_ms": round(db_latency, 2),
            },
            "system": system_info,
            "checked_at": datetime.utcnow().isoformat(),
        }
    
    async def get_activity_trends(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get activity trends over time."""
        start_date = date.today() - timedelta(days=days)
        
        # Daily activity counts
        daily_activity_result = await self.db.execute(
            select(
                func.date(AuditLog.created_at).label("date"),
                func.count(AuditLog.id).label("events"),
                func.count(func.distinct(AuditLog.user_id)).label("unique_users"),
            ).where(
                func.date(AuditLog.created_at) >= start_date
            ).group_by(
                func.date(AuditLog.created_at)
            ).order_by(
                func.date(AuditLog.created_at)
            )
        )
        daily_activity = [
            {
                "date": str(row.date),
                "events": row.events,
                "unique_users": row.unique_users,
            }
            for row in daily_activity_result.all()
        ]
        
        # Hourly distribution (for today)
        today = date.today()
        hourly_result = await self.db.execute(
            select(
                func.extract('hour', AuditLog.created_at).label("hour"),
                func.count(AuditLog.id).label("events"),
            ).where(
                func.date(AuditLog.created_at) == today
            ).group_by(
                func.extract('hour', AuditLog.created_at)
            ).order_by(
                func.extract('hour', AuditLog.created_at)
            )
        )
        hourly_distribution = [
            {
                "hour": int(row.hour),
                "events": row.events,
            }
            for row in hourly_result.all()
        ]
        
        # User growth trend
        user_growth_result = await self.db.execute(
            select(
                func.date(User.created_at).label("date"),
                func.count(User.id).label("new_users"),
            ).where(
                func.date(User.created_at) >= start_date
            ).group_by(
                func.date(User.created_at)
            ).order_by(
                func.date(User.created_at)
            )
        )
        user_growth = [
            {
                "date": str(row.date),
                "new_users": row.new_users,
            }
            for row in user_growth_result.all()
        ]
        
        # Organization growth trend
        org_growth_result = await self.db.execute(
            select(
                func.date(Organization.created_at).label("date"),
                func.count(Organization.id).label("new_orgs"),
            ).where(
                func.date(Organization.created_at) >= start_date
            ).group_by(
                func.date(Organization.created_at)
            ).order_by(
                func.date(Organization.created_at)
            )
        )
        org_growth = [
            {
                "date": str(row.date),
                "new_orgs": row.new_orgs,
            }
            for row in org_growth_result.all()
        ]
        
        return {
            "period_days": days,
            "daily_activity": daily_activity,
            "hourly_distribution_today": hourly_distribution,
            "user_growth": user_growth,
            "organization_growth": org_growth,
        }
    
    async def get_organization_health_summary(self) -> Dict[str, Any]:
        """Get health summary across all organizations."""
        # Get all organizations with their user counts
        org_stats_result = await self.db.execute(
            select(
                Organization.id,
                Organization.name,
                Organization.is_emergency_suspended,
                Organization.verification_status,
                Organization.created_at,
                func.count(User.id).label("user_count"),
            ).outerjoin(
                User, User.organization_id == Organization.id
            ).group_by(
                Organization.id,
                Organization.name,
                Organization.is_emergency_suspended,
                Organization.verification_status,
                Organization.created_at,
            ).order_by(
                desc(func.count(User.id))
            )
        )
        
        org_stats = []
        for row in org_stats_result.all():
            org_stats.append({
                "id": str(row.id),
                "name": row.name,
                "is_active": not row.is_emergency_suspended,  # Active if not suspended
                "verification_status": str(row.verification_status) if row.verification_status else "pending",
                "user_count": row.user_count,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })
        
        # Organizations with recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_org_ids_result = await self.db.execute(
            select(func.distinct(AuditLog.organization_id)).where(
                and_(
                    AuditLog.created_at >= week_ago,
                    AuditLog.organization_id.isnot(None)
                )
            )
        )
        active_org_ids = {row[0] for row in active_org_ids_result.all()}
        
        # Count by activity status
        active_count = len(active_org_ids)
        total_count = len(org_stats)
        
        return {
            "organizations": org_stats[:50],  # Top 50 by user count
            "summary": {
                "total": total_count,
                "active_this_week": active_count,
                "inactive_this_week": total_count - active_count,
            },
        }
    
    async def get_security_metrics(self) -> Dict[str, Any]:
        """Get security-related metrics."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        
        # Failed login attempts today
        failed_logins_today_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                and_(
                    AuditLog.action == "login_failed",
                    func.date(AuditLog.created_at) == today
                )
            )
        )
        failed_logins_today = failed_logins_today_result.scalar() or 0
        
        # Failed login attempts this week
        failed_logins_week_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                and_(
                    AuditLog.action == "login_failed",
                    func.date(AuditLog.created_at) >= week_ago
                )
            )
        )
        failed_logins_week = failed_logins_week_result.scalar() or 0
        
        # Successful logins today
        successful_logins_today_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                and_(
                    AuditLog.action == "login",
                    func.date(AuditLog.created_at) == today
                )
            )
        )
        successful_logins_today = successful_logins_today_result.scalar() or 0
        
        # Unique IP addresses with failed logins this week
        failed_login_ips_result = await self.db.execute(
            select(func.count(func.distinct(AuditLog.ip_address))).where(
                and_(
                    AuditLog.action == "login_failed",
                    func.date(AuditLog.created_at) >= week_ago,
                    AuditLog.ip_address.isnot(None)
                )
            )
        )
        unique_failed_ips = failed_login_ips_result.scalar() or 0
        
        # Users with password reset
        password_resets_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                and_(
                    or_(
                        AuditLog.action.ilike("%password_reset%"),
                        AuditLog.action.ilike("%reset_password%")
                    ),
                    func.date(AuditLog.created_at) >= week_ago
                )
            )
        )
        password_resets_week = password_resets_result.scalar() or 0
        
        # Unverified users
        unverified_users_result = await self.db.execute(
            select(func.count(User.id)).where(User.is_verified == False)
        )
        unverified_users = unverified_users_result.scalar() or 0
        
        # Users requiring password reset
        must_reset_result = await self.db.execute(
            select(func.count(User.id)).where(User.must_reset_password == True)
        )
        must_reset_count = must_reset_result.scalar() or 0
        
        # Calculate login failure rate
        total_login_attempts_today = successful_logins_today + failed_logins_today
        failure_rate = 0.0
        if total_login_attempts_today > 0:
            failure_rate = round((failed_logins_today / total_login_attempts_today) * 100, 2)
        
        return {
            "login_security": {
                "successful_logins_today": successful_logins_today,
                "failed_logins_today": failed_logins_today,
                "failed_logins_this_week": failed_logins_week,
                "failure_rate_today_percent": failure_rate,
                "unique_failed_ips_this_week": unique_failed_ips,
            },
            "password_security": {
                "password_resets_this_week": password_resets_week,
                "users_requiring_password_reset": must_reset_count,
            },
            "user_verification": {
                "unverified_users": unverified_users,
            },
            "checked_at": datetime.utcnow().isoformat(),
        }
    
    async def get_feature_usage_metrics(self) -> Dict[str, Any]:
        """Get feature usage metrics based on audit log actions."""
        week_ago = date.today() - timedelta(days=7)
        
        # Count actions by type for the last week
        action_counts_result = await self.db.execute(
            select(
                AuditLog.action,
                func.count(AuditLog.id).label("count")
            ).where(
                func.date(AuditLog.created_at) >= week_ago
            ).group_by(
                AuditLog.action
            ).order_by(
                desc(func.count(AuditLog.id))
            ).limit(30)
        )
        
        action_usage = [
            {
                "action": row.action,
                "count": row.count,
            }
            for row in action_counts_result.all()
        ]
        
        # Entity type usage
        entity_usage_result = await self.db.execute(
            select(
                AuditLog.target_entity_type,
                func.count(AuditLog.id).label("count")
            ).where(
                and_(
                    func.date(AuditLog.created_at) >= week_ago,
                    AuditLog.target_entity_type.isnot(None)
                )
            ).group_by(
                AuditLog.target_entity_type
            ).order_by(
                desc(func.count(AuditLog.id))
            )
        )
        
        entity_usage = [
            {
                "entity_type": row.target_entity_type,
                "count": row.count,
            }
            for row in entity_usage_result.all()
        ]
        
        return {
            "period": "last_7_days",
            "action_usage": action_usage,
            "entity_usage": entity_usage,
        }
    
    async def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get a combined dashboard summary with key metrics."""
        overview = await self.get_platform_overview()
        health = await self.get_system_health()
        security = await self.get_security_metrics()
        
        return {
            "platform_status": health["status"],
            "health_issues": health["issues"],
            "quick_stats": {
                "total_users": overview["users"]["total"],
                "active_users": overview["users"]["active"],
                "total_organizations": overview["organizations"]["total"],
                "active_organizations": overview["organizations"]["active"],
                "platform_staff": overview["platform_staff"]["total"],
                "events_last_24h": overview["activity"]["last_24h_events"],
                "active_users_24h": overview["activity"]["unique_active_users_24h"],
            },
            "security_alerts": {
                "failed_logins_today": security["login_security"]["failed_logins_today"],
                "failure_rate_percent": security["login_security"]["failure_rate_today_percent"],
                "unverified_users": security["user_verification"]["unverified_users"],
            },
            "resources": {
                "cpu_percent": health["resources"]["cpu"]["usage_percent"],
                "memory_percent": health["resources"]["memory"]["usage_percent"],
                "disk_percent": health["resources"]["disk"]["usage_percent"],
                "db_latency_ms": health["database"]["latency_ms"],
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
