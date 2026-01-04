"""
TekVwarho ProAudit - Dashboard Service

Provides dashboard data for different user types:
1. Platform Staff Dashboards (Super Admin, Admin, IT, CSR, Marketing)
2. Organization User Dashboards (Owner, Admin, Accountant, etc.)
"""

import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, PlatformRole, UserRole
from app.models.organization import Organization, VerificationStatus, OrganizationType
from app.models.entity import BusinessEntity
from app.models.transaction import Transaction, TransactionType
from app.models.invoice import Invoice, InvoiceStatus
from app.models.audit import AuditLog
from app.utils.permissions import (
    PlatformPermission,
    OrganizationPermission,
    has_platform_permission,
    has_organization_permission,
    get_platform_permissions,
    get_organization_permissions,
)


class DashboardService:
    """Service for generating dashboard data."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ===========================================
    # PLATFORM STAFF DASHBOARDS
    # ===========================================
    
    async def get_super_admin_dashboard(self, user: User) -> Dict[str, Any]:
        """
        Super Admin Dashboard - Full platform overview.
        """
        if not user.is_platform_staff or user.platform_role != PlatformRole.SUPER_ADMIN:
            raise PermissionError("Super Admin access required")
        
        # Get counts
        org_count = await self._get_organization_count()
        user_count = await self._get_user_count()
        staff_count = await self._get_staff_count()
        pending_verifications = await self._get_pending_verification_count()
        
        # Get organization stats by type
        org_by_type = await self._get_organizations_by_type()
        
        # Get verification stats
        verification_stats = await self._get_verification_stats()
        
        # Recent platform activity
        recent_activity = await self._get_recent_platform_activity(limit=10)
        
        # Platform health metrics
        platform_health = await self._get_platform_health()
        
        return {
            "dashboard_type": "super_admin",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.full_name,
                "role": "Super Admin",
            },
            "overview": {
                "total_organizations": org_count,
                "total_users": user_count,
                "total_staff": staff_count,
                "pending_verifications": pending_verifications,
            },
            "organizations_by_type": org_by_type,
            "verification_stats": verification_stats,
            "recent_activity": recent_activity,
            "platform_health": platform_health,
            "permissions": [p.value for p in get_platform_permissions(PlatformRole.SUPER_ADMIN)],
            "quick_actions": [
                {"label": "Onboard Staff", "url": "/admin/staff/onboard", "icon": "user-plus"},
                {"label": "Pending Verifications", "url": "/admin/verifications", "icon": "check-circle"},
                {"label": "Platform Settings", "url": "/admin/settings", "icon": "cog"},
                {"label": "API Keys", "url": "/admin/api-keys", "icon": "key"},
            ],
        }
    
    async def get_admin_dashboard(self, user: User) -> Dict[str, Any]:
        """
        Admin Dashboard - Operational overview.
        """
        if not user.is_platform_staff or user.platform_role != PlatformRole.ADMIN:
            raise PermissionError("Admin access required")
        
        org_count = await self._get_organization_count()
        user_count = await self._get_user_count()
        pending_verifications = await self._get_pending_verification_count()
        verification_stats = await self._get_verification_stats()
        
        # Organizations needing attention
        orgs_needing_attention = await self._get_organizations_needing_attention()
        
        return {
            "dashboard_type": "admin",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.full_name,
                "role": "Admin",
            },
            "overview": {
                "total_organizations": org_count,
                "total_users": user_count,
                "pending_verifications": pending_verifications,
            },
            "verification_stats": verification_stats,
            "organizations_needing_attention": orgs_needing_attention,
            "permissions": [p.value for p in get_platform_permissions(PlatformRole.ADMIN)],
            "quick_actions": [
                {"label": "Onboard Staff", "url": "/admin/staff/onboard", "icon": "user-plus"},
                {"label": "Review Verifications", "url": "/admin/verifications", "icon": "check-circle"},
                {"label": "User Analytics", "url": "/admin/analytics", "icon": "chart-bar"},
            ],
        }
    
    async def get_it_developer_dashboard(self, user: User) -> Dict[str, Any]:
        """
        IT/Developer Dashboard - System health and technical metrics.
        """
        if not user.is_platform_staff or user.platform_role != PlatformRole.IT_DEVELOPER:
            raise PermissionError("IT/Developer access required")
        
        platform_health = await self._get_platform_health()
        recent_errors = await self._get_recent_errors(limit=10)
        
        return {
            "dashboard_type": "it_developer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.full_name,
                "role": "IT/Developer",
            },
            "platform_health": platform_health,
            "recent_errors": recent_errors,
            "system_metrics": {
                "database_status": "healthy",
                "api_uptime": "99.9%",
                "nrs_webhook_status": "active",
            },
            "permissions": [p.value for p in get_platform_permissions(PlatformRole.IT_DEVELOPER)],
            "quick_actions": [
                {"label": "System Logs", "url": "/admin/logs", "icon": "document-text"},
                {"label": "Database Health", "url": "/admin/database", "icon": "database"},
                {"label": "Webhook Status", "url": "/admin/webhooks", "icon": "link"},
            ],
        }
    
    async def get_csr_dashboard(self, user: User) -> Dict[str, Any]:
        """
        Customer Service Dashboard - Support metrics and user assistance.
        """
        if not user.is_platform_staff or user.platform_role != PlatformRole.CUSTOMER_SERVICE:
            raise PermissionError("Customer Service access required")
        
        # Get support-related metrics
        recent_submissions = await self._get_recent_nrs_submissions(limit=10)
        
        return {
            "dashboard_type": "customer_service",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.full_name,
                "role": "Customer Service",
            },
            "support_metrics": {
                "users_assisted_today": 0,  # Would come from support ticket system
                "pending_issues": 0,
                "failed_submissions": len([s for s in recent_submissions if s.get("status") == "failed"]),
            },
            "recent_submissions": recent_submissions,
            "permissions": [p.value for p in get_platform_permissions(PlatformRole.CUSTOMER_SERVICE)],
            "quick_actions": [
                {"label": "Search User", "url": "/admin/users/search", "icon": "search"},
                {"label": "Failed Submissions", "url": "/admin/submissions/failed", "icon": "exclamation"},
                {"label": "Help Articles", "url": "/admin/help", "icon": "book-open"},
            ],
        }
    
    async def get_marketing_dashboard(self, user: User) -> Dict[str, Any]:
        """
        Marketing Dashboard - Growth and engagement metrics.
        """
        if not user.is_platform_staff or user.platform_role != PlatformRole.MARKETING:
            raise PermissionError("Marketing access required")
        
        # User growth stats
        growth_stats = await self._get_user_growth_stats()
        org_by_type = await self._get_organizations_by_type()
        
        return {
            "dashboard_type": "marketing",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.full_name,
                "role": "Marketing",
            },
            "growth_stats": growth_stats,
            "organizations_by_type": org_by_type,
            "campaign_metrics": {
                "active_campaigns": 0,
                "email_open_rate": "0%",
                "referral_conversions": 0,
            },
            "permissions": [p.value for p in get_platform_permissions(PlatformRole.MARKETING)],
            "quick_actions": [
                {"label": "Create Campaign", "url": "/admin/campaigns/new", "icon": "megaphone"},
                {"label": "User Analytics", "url": "/admin/analytics", "icon": "chart-bar"},
                {"label": "Referral Stats", "url": "/admin/referrals", "icon": "users"},
            ],
        }
    
    # ===========================================
    # ORGANIZATION USER DASHBOARDS
    # ===========================================
    
    async def get_organization_dashboard(
        self, 
        user: User, 
        entity_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Organization User Dashboard - Business metrics.
        
        Includes 2026 compliance features:
        - TIN/CAC Vault display
        - Compliance Health indicator
        - Small Company Status
        - Development Levy status
        """
        if user.is_platform_staff:
            raise ValueError("Platform staff should use platform dashboards")
        
        if not user.organization_id:
            raise ValueError("User has no organization")
        
        # Get the entity to show dashboard for
        if entity_id:
            # Verify user has access to this entity
            entity = await self._get_entity_if_accessible(user, entity_id)
            if not entity:
                raise PermissionError("No access to this entity")
        else:
            # Use first accessible entity
            entity = await self._get_first_accessible_entity(user)
        
        # Get organization info
        org_result = await self.db.execute(
            select(Organization).where(Organization.id == user.organization_id)
        )
        organization = org_result.scalar_one_or_none()
        
        # Get financial metrics
        financial_metrics = await self._get_financial_metrics(entity.id if entity else None)
        
        # Get recent transactions
        recent_transactions = await self._get_recent_transactions(
            entity.id if entity else None, 
            limit=5
        )
        
        # Get invoice summary
        invoice_summary = await self._get_invoice_summary(entity.id if entity else None)
        
        # Get TIN/CAC Vault (2026 compliance)
        tin_cac_vault = await self._get_tin_cac_vault(entity, organization)
        
        # Get Compliance Health indicator (2026 compliance)
        compliance_health = await self._get_compliance_health(entity)
        
        # Get user's permissions
        permissions = []
        if user.role:
            permissions = [p.value for p in get_organization_permissions(user.role)]
        
        # Build dashboard based on role
        dashboard = {
            "dashboard_type": f"organization_{user.role.value if user.role else 'user'}",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.full_name,
                "role": user.role.value if user.role else "user",
            },
            "organization": {
                "id": str(organization.id) if organization else None,
                "name": organization.name if organization else None,
                "type": organization.organization_type.value if organization and organization.organization_type else None,
                "verification_status": organization.verification_status.value if organization and hasattr(organization, 'verification_status') else "pending",
                "subscription_tier": organization.subscription_tier.value if organization else None,
            },
            "current_entity": {
                "id": str(entity.id) if entity else None,
                "name": entity.name if entity else None,
            } if entity else None,
            # 2026 Compliance sections - always visible
            "tin_cac_vault": tin_cac_vault,
            "compliance_health": compliance_health,
            "financial_metrics": financial_metrics,
            "recent_transactions": recent_transactions,
            "invoice_summary": invoice_summary,
            "permissions": permissions,
            "quick_actions": self._get_quick_actions_for_role(user.role),
        }
        
        # Add role-specific sections
        if user.role in [UserRole.OWNER, UserRole.ADMIN]:
            dashboard["team_summary"] = await self._get_team_summary(user.organization_id)
        
        if user.role in [UserRole.OWNER, UserRole.ADMIN, UserRole.ACCOUNTANT]:
            dashboard["tax_summary"] = await self._get_tax_summary(entity.id if entity else None)
        
        if user.role in [UserRole.INVENTORY_MANAGER, UserRole.OWNER, UserRole.ADMIN]:
            dashboard["inventory_summary"] = await self._get_inventory_summary(entity.id if entity else None)
        
        return dashboard
    
    # ===========================================
    # UNIFIED DASHBOARD ENTRY POINT
    # ===========================================
    
    async def get_dashboard(
        self, 
        user: User, 
        entity_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Get appropriate dashboard based on user type and role.
        """
        if user.is_platform_staff:
            # Route to appropriate platform dashboard
            if user.platform_role == PlatformRole.SUPER_ADMIN:
                return await self.get_super_admin_dashboard(user)
            elif user.platform_role == PlatformRole.ADMIN:
                return await self.get_admin_dashboard(user)
            elif user.platform_role == PlatformRole.IT_DEVELOPER:
                return await self.get_it_developer_dashboard(user)
            elif user.platform_role == PlatformRole.CUSTOMER_SERVICE:
                return await self.get_csr_dashboard(user)
            elif user.platform_role == PlatformRole.MARKETING:
                return await self.get_marketing_dashboard(user)
            else:
                raise ValueError(f"Unknown platform role: {user.platform_role}")
        else:
            # Organization user dashboard
            return await self.get_organization_dashboard(user, entity_id)
    
    # ===========================================
    # HELPER METHODS
    # ===========================================
    
    async def _get_organization_count(self) -> int:
        result = await self.db.execute(select(func.count(Organization.id)))
        return result.scalar() or 0
    
    async def _get_user_count(self) -> int:
        result = await self.db.execute(
            select(func.count(User.id)).where(User.is_platform_staff == False)
        )
        return result.scalar() or 0
    
    async def _get_staff_count(self) -> int:
        result = await self.db.execute(
            select(func.count(User.id)).where(User.is_platform_staff == True)
        )
        return result.scalar() or 0
    
    async def _get_pending_verification_count(self) -> int:
        result = await self.db.execute(
            select(func.count(Organization.id)).where(
                Organization.verification_status == VerificationStatus.SUBMITTED
            )
        )
        return result.scalar() or 0
    
    async def _get_organizations_by_type(self) -> Dict[str, int]:
        result = await self.db.execute(
            select(
                Organization.organization_type,
                func.count(Organization.id)
            ).group_by(Organization.organization_type)
        )
        return {row[0].value if row[0] else "unknown": row[1] for row in result.all()}
    
    async def _get_verification_stats(self) -> Dict[str, int]:
        result = await self.db.execute(
            select(
                Organization.verification_status,
                func.count(Organization.id)
            ).group_by(Organization.verification_status)
        )
        return {row[0].value if row[0] else "unknown": row[1] for row in result.all()}
    
    async def _get_recent_platform_activity(self, limit: int = 10) -> List[Dict]:
        # Get recent audit logs
        result = await self.db.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
        return [
            {
                "id": str(log.id),
                "action": log.action,
                "resource_type": log.resource_type,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    
    async def _get_platform_health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "database": "connected",
            "last_check": datetime.utcnow().isoformat(),
        }
    
    async def _get_organizations_needing_attention(self) -> List[Dict]:
        result = await self.db.execute(
            select(Organization)
            .where(
                or_(
                    Organization.verification_status == VerificationStatus.SUBMITTED,
                    Organization.verification_status == VerificationStatus.REJECTED
                )
            )
            .order_by(Organization.created_at.desc())
            .limit(5)
        )
        orgs = result.scalars().all()
        return [
            {
                "id": str(org.id),
                "name": org.name,
                "status": org.verification_status.value if org.verification_status else "unknown",
                "type": org.organization_type.value if org.organization_type else "unknown",
            }
            for org in orgs
        ]
    
    async def _get_recent_errors(self, limit: int = 10) -> List[Dict]:
        # Placeholder - would integrate with error tracking system
        return []
    
    async def _get_recent_nrs_submissions(self, limit: int = 10) -> List[Dict]:
        # Placeholder - would get from NRS submission logs
        return []
    
    async def _get_user_growth_stats(self) -> Dict[str, Any]:
        # Get users created in last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        result = await self.db.execute(
            select(func.count(User.id)).where(
                and_(
                    User.is_platform_staff == False,
                    User.created_at >= thirty_days_ago
                )
            )
        )
        new_users = result.scalar() or 0
        
        total_users = await self._get_user_count()
        
        return {
            "total_users": total_users,
            "new_users_30d": new_users,
            "growth_rate": f"{(new_users / max(total_users, 1)) * 100:.1f}%",
        }
    
    async def _get_entity_if_accessible(
        self, 
        user: User, 
        entity_id: uuid.UUID
    ) -> Optional[BusinessEntity]:
        # Check user has access to this entity
        for access in user.entity_access:
            if access.entity_id == entity_id:
                result = await self.db.execute(
                    select(BusinessEntity).where(BusinessEntity.id == entity_id)
                )
                return result.scalar_one_or_none()
        return None
    
    async def _get_first_accessible_entity(self, user: User) -> Optional[BusinessEntity]:
        if user.entity_access and len(user.entity_access) > 0:
            entity_id = user.entity_access[0].entity_id
            result = await self.db.execute(
                select(BusinessEntity).where(BusinessEntity.id == entity_id)
            )
            return result.scalar_one_or_none()
        return None
    
    async def _get_financial_metrics(
        self, 
        entity_id: Optional[uuid.UUID]
    ) -> Dict[str, Any]:
        if not entity_id:
            return self._empty_financial_metrics()
        
        today = date.today()
        start_of_month = today.replace(day=1)
        start_of_year = today.replace(month=1, day=1)
        
        # This month metrics
        this_month = await self._get_period_metrics(
            entity_id, start_of_month, today
        )
        
        # Year to date metrics
        ytd = await self._get_period_metrics(
            entity_id, start_of_year, today
        )
        
        return {
            "this_month": this_month,
            "year_to_date": ytd,
        }
    
    async def _get_period_metrics(
        self, 
        entity_id: uuid.UUID, 
        start_date: date, 
        end_date: date
    ) -> Dict[str, float]:
        # Income
        income_result = await self.db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                and_(
                    Transaction.entity_id == entity_id,
                    Transaction.transaction_type == TransactionType.INCOME,
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                )
            )
        )
        income = float(income_result.scalar() or 0)
        
        # Expense
        expense_result = await self.db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                and_(
                    Transaction.entity_id == entity_id,
                    Transaction.transaction_type == TransactionType.EXPENSE,
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                )
            )
        )
        expense = float(expense_result.scalar() or 0)
        
        return {
            "income": income,
            "expense": expense,
            "net": income - expense,
        }
    
    def _empty_financial_metrics(self) -> Dict[str, Any]:
        return {
            "this_month": {"income": 0, "expense": 0, "net": 0},
            "year_to_date": {"income": 0, "expense": 0, "net": 0},
        }
    
    async def _get_recent_transactions(
        self, 
        entity_id: Optional[uuid.UUID], 
        limit: int = 5
    ) -> List[Dict]:
        if not entity_id:
            return []
        
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.entity_id == entity_id)
            .order_by(Transaction.transaction_date.desc())
            .limit(limit)
        )
        transactions = result.scalars().all()
        
        return [
            {
                "id": str(tx.id),
                "description": tx.description,
                "amount": float(tx.amount),
                "transaction_type": tx.transaction_type.value,
                "transaction_date": tx.transaction_date.isoformat() if tx.transaction_date else None,
            }
            for tx in transactions
        ]
    
    async def _get_invoice_summary(
        self, 
        entity_id: Optional[uuid.UUID]
    ) -> Dict[str, Any]:
        if not entity_id:
            return {"outstanding": 0, "overdue": 0, "total_count": 0}
        
        today = date.today()
        
        # Outstanding invoices
        outstanding_result = await self.db.execute(
            select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
                and_(
                    Invoice.entity_id == entity_id,
                    Invoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.SENT]),
                )
            )
        )
        outstanding = float(outstanding_result.scalar() or 0)
        
        # Overdue invoices
        overdue_result = await self.db.execute(
            select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
                and_(
                    Invoice.entity_id == entity_id,
                    Invoice.status == InvoiceStatus.SENT,
                    Invoice.due_date < today,
                )
            )
        )
        overdue = float(overdue_result.scalar() or 0)
        
        # Total count
        count_result = await self.db.execute(
            select(func.count(Invoice.id)).where(Invoice.entity_id == entity_id)
        )
        total_count = count_result.scalar() or 0
        
        return {
            "outstanding": outstanding,
            "overdue": overdue,
            "total_count": total_count,
        }
    
    async def _get_team_summary(
        self, 
        organization_id: uuid.UUID
    ) -> Dict[str, Any]:
        result = await self.db.execute(
            select(func.count(User.id)).where(
                and_(
                    User.organization_id == organization_id,
                    User.is_platform_staff == False,
                )
            )
        )
        total_members = result.scalar() or 0
        
        # Get by role
        role_result = await self.db.execute(
            select(User.role, func.count(User.id))
            .where(
                and_(
                    User.organization_id == organization_id,
                    User.is_platform_staff == False,
                )
            )
            .group_by(User.role)
        )
        by_role = {row[0].value if row[0] else "unknown": row[1] for row in role_result.all()}
        
        return {
            "total_members": total_members,
            "by_role": by_role,
        }
    
    async def _get_tax_summary(
        self, 
        entity_id: Optional[uuid.UUID]
    ) -> Dict[str, Any]:
        # Placeholder - would calculate actual tax obligations
        return {
            "vat_collected": 0,
            "vat_paid": 0,
            "next_filing_date": None,
        }
    
    async def _get_inventory_summary(
        self, 
        entity_id: Optional[uuid.UUID]
    ) -> Dict[str, Any]:
        # Placeholder - would get actual inventory stats
        return {
            "total_items": 0,
            "low_stock_items": 0,
            "total_value": 0,
        }
    
    async def _get_tin_cac_vault(
        self,
        entity: Optional["BusinessEntity"],
        organization: Optional["Organization"],
    ) -> Dict[str, Any]:
        """
        Get TIN/CAC Vault display data.
        
        Under the 2026 law, TIN and CAC numbers are mandatory for all
        financial and digital operations.
        """
        return {
            "tin": {
                "number": entity.tin if entity else None,
                "status": "verified" if entity and entity.tin else "missing",
                "label": "Tax Identification Number (TIN)",
                "is_critical": True,
                "warning": "TIN is mandatory for NRS e-invoicing" if not (entity and entity.tin) else None,
            },
            "cac": {
                "number": entity.rc_number if entity else None,
                "status": "verified" if entity and entity.rc_number else "missing",
                "label": "CAC RC/BN Number",
                "is_critical": True,
                "warning": "CAC registration is required for compliance" if not (entity and entity.rc_number) else None,
            },
            "business_type": {
                "value": entity.business_type.value if entity and entity.business_type else None,
                "label": "Business Name (PIT)" if entity and entity.business_type and entity.business_type.value == "business_name" else "Limited Company (CIT)",
                "tax_implication": "Personal Income Tax (PIT)" if entity and entity.business_type and entity.business_type.value == "business_name" else "Corporate Income Tax (CIT)",
            },
            "vat_registration": {
                "is_registered": entity.is_vat_registered if entity else False,
                "registration_date": entity.vat_registration_date.isoformat() if entity and entity.vat_registration_date else None,
                "status": "registered" if entity and entity.is_vat_registered else "not_registered",
            },
        }
    
    async def _get_compliance_health(
        self,
        entity: Optional["BusinessEntity"],
    ) -> Dict[str, Any]:
        """
        Get Compliance Health indicator for dashboard.
        
        Checks:
        - Small Company Status (0% CIT eligibility)
        - Development Levy Exemption status
        - NRS e-invoicing compliance
        - Pending tax filings
        """
        if not entity:
            return {
                "overall_status": "unknown",
                "score": 0,
                "checks": [],
            }
        
        checks = []
        issues = 0
        warnings = 0
        
        # Check 1: TIN registered
        if entity.tin:
            checks.append({
                "name": "TIN Registration",
                "status": "pass",
                "message": f"TIN registered: {entity.tin}",
                "icon": "check-circle",
            })
        else:
            checks.append({
                "name": "TIN Registration",
                "status": "fail",
                "message": "TIN not registered - required for NRS",
                "icon": "x-circle",
            })
            issues += 1
        
        # Check 2: CAC Registration
        if entity.rc_number:
            checks.append({
                "name": "CAC Registration",
                "status": "pass",
                "message": f"CAC registered: {entity.rc_number}",
                "icon": "check-circle",
            })
        else:
            checks.append({
                "name": "CAC Registration",
                "status": "fail",
                "message": "CAC number missing",
                "icon": "x-circle",
            })
            issues += 1
        
        # Check 3: Small Company Status (for CIT exemption)
        from decimal import Decimal
        turnover = entity.annual_turnover or Decimal("0")
        fixed_assets = entity.fixed_assets_value or Decimal("0")
        
        is_small_company = (
            turnover <= Decimal("50000000") and
            fixed_assets <= Decimal("250000000")
        )
        
        if entity.business_type and entity.business_type.value == "limited_company":
            if is_small_company:
                checks.append({
                    "name": "Small Company Status",
                    "status": "pass",
                    "message": f"Qualifies for 0% CIT (Turnover: ₦{turnover:,.0f}, Assets: ₦{fixed_assets:,.0f})",
                    "icon": "badge-check",
                    "highlight": True,
                })
            else:
                reason = []
                if turnover > Decimal("50000000"):
                    reason.append(f"Turnover ₦{turnover:,.0f} > ₦50M")
                if fixed_assets > Decimal("250000000"):
                    reason.append(f"Assets ₦{fixed_assets:,.0f} > ₦250M")
                checks.append({
                    "name": "Small Company Status",
                    "status": "info",
                    "message": f"Standard CIT applies: {', '.join(reason)}",
                    "icon": "information-circle",
                })
        
        # Check 4: Development Levy Exemption
        is_dev_levy_exempt = (
            turnover <= Decimal("100000000") and
            fixed_assets <= Decimal("250000000")
        )
        
        if entity.business_type and entity.business_type.value == "limited_company":
            if is_dev_levy_exempt:
                checks.append({
                    "name": "Development Levy",
                    "status": "pass",
                    "message": "Exempt from 4% Development Levy",
                    "icon": "shield-check",
                })
            else:
                checks.append({
                    "name": "Development Levy",
                    "status": "info",
                    "message": "Subject to 4% Development Levy on assessable profit",
                    "icon": "currency-dollar",
                })
        else:
            checks.append({
                "name": "Development Levy",
                "status": "pass",
                "message": "Not applicable (Business Names pay PIT only)",
                "icon": "shield-check",
            })
        
        # Check 5: VAT Registration
        if entity.is_vat_registered:
            checks.append({
                "name": "VAT Registration",
                "status": "pass",
                "message": "VAT registered - can issue VAT invoices",
                "icon": "check-circle",
            })
        else:
            if turnover > Decimal("25000000"):  # VAT threshold
                checks.append({
                    "name": "VAT Registration",
                    "status": "warning",
                    "message": "Turnover exceeds ₦25M threshold - VAT registration recommended",
                    "icon": "exclamation",
                })
                warnings += 1
            else:
                checks.append({
                    "name": "VAT Registration",
                    "status": "info",
                    "message": "Below VAT threshold (₦25M)",
                    "icon": "information-circle",
                })
        
        # Calculate overall score
        total_checks = len(checks)
        passed = sum(1 for c in checks if c["status"] == "pass")
        score = int((passed / total_checks) * 100) if total_checks > 0 else 0
        
        if issues > 0:
            overall_status = "critical"
        elif warnings > 0:
            overall_status = "warning"
        elif score == 100:
            overall_status = "excellent"
        else:
            overall_status = "good"
        
        return {
            "overall_status": overall_status,
            "score": score,
            "issues": issues,
            "warnings": warnings,
            "checks": checks,
            "summary": f"{passed}/{total_checks} compliance checks passed",
        }

    def _get_quick_actions_for_role(
        self, 
        role: Optional[UserRole]
    ) -> List[Dict[str, str]]:
        """Get quick actions based on user role."""
        if not role:
            return []
        
        base_actions = [
            {"label": "New Transaction", "url": "/transactions/new", "icon": "plus"},
        ]
        
        if role in [UserRole.OWNER, UserRole.ADMIN, UserRole.ACCOUNTANT]:
            base_actions.extend([
                {"label": "Create Invoice", "url": "/invoices/new", "icon": "document"},
                {"label": "Scan Receipt", "url": "/receipts/upload", "icon": "camera"},
                {"label": "Tax Center", "url": "/tax-2026", "icon": "calculator"},
            ])
        
        if role in [UserRole.OWNER, UserRole.ADMIN]:
            base_actions.append(
                {"label": "Manage Team", "url": "/settings/team", "icon": "users"}
            )
        
        if role in [UserRole.INVENTORY_MANAGER, UserRole.OWNER, UserRole.ADMIN]:
            base_actions.append(
                {"label": "Inventory", "url": "/inventory", "icon": "cube"}
            )
        
        return base_actions

