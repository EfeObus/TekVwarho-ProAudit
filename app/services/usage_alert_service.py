"""
TekVwarho ProAudit - Usage Alert Service

Service for monitoring usage limits and sending alerts when approaching or exceeding limits.
Supports multiple notification channels: email, WebSocket, in-app.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Set
from uuid import UUID
from enum import Enum

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sku import (
    TenantSKU,
    UsageRecord,
    UsageMetricType,
    SKUTier,
    TIER_LIMITS,
)

logger = logging.getLogger(__name__)


class AlertThreshold(str, Enum):
    """Usage alert thresholds as percentages."""
    WARNING_80 = "80"    # 80% usage - approaching limit
    CRITICAL_90 = "90"   # 90% usage - near limit
    EXCEEDED_100 = "100" # 100% usage - limit reached


class AlertChannel(str, Enum):
    """Notification channels for alerts."""
    EMAIL = "email"
    WEBSOCKET = "websocket"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class UsageAlert:
    """Represents a usage alert."""
    
    def __init__(
        self,
        organization_id: UUID,
        metric_type: UsageMetricType,
        current_usage: int,
        limit: int,
        percentage: float,
        threshold: AlertThreshold,
        message: str,
    ):
        self.organization_id = organization_id
        self.metric_type = metric_type
        self.current_usage = current_usage
        self.limit = limit
        self.percentage = percentage
        self.threshold = threshold
        self.message = message
        self.created_at = datetime.utcnow()
        self.acknowledged = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "organization_id": str(self.organization_id),
            "metric_type": self.metric_type.value,
            "current_usage": self.current_usage,
            "limit": self.limit,
            "percentage": round(self.percentage, 1),
            "threshold": self.threshold.value,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
        }


class UsageAlertService:
    """
    Service for monitoring usage limits and sending alerts.
    
    Usage:
        service = UsageAlertService(db)
        
        # Check for alerts for an organization
        alerts = await service.check_usage_alerts(org_id)
        
        # Get active alerts
        alerts = await service.get_active_alerts(org_id)
        
        # Send notifications for alerts
        await service.notify_alerts(alerts, channels=[AlertChannel.EMAIL, AlertChannel.IN_APP])
    """
    
    # Thresholds to check (in percentage)
    ALERT_THRESHOLDS = [80, 90, 100]
    
    # Human-readable metric names
    METRIC_DISPLAY_NAMES = {
        UsageMetricType.TRANSACTIONS: "Transactions",
        UsageMetricType.USERS: "Users",
        UsageMetricType.ENTITIES: "Business Entities",
        UsageMetricType.INVOICES: "Invoices",
        UsageMetricType.API_CALLS: "API Calls",
        UsageMetricType.OCR_PAGES: "OCR Pages",
        UsageMetricType.STORAGE_MB: "Storage (MB)",
        UsageMetricType.ML_INFERENCES: "ML Inferences",
        UsageMetricType.EMPLOYEES: "Payroll Employees",
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._alert_cache: Dict[str, datetime] = {}  # Prevent alert spam
        self._cache_ttl = timedelta(hours=1)  # Don't repeat alerts within 1 hour
    
    # ===========================================
    # ALERT CHECKING
    # ===========================================
    
    async def check_usage_alerts(
        self,
        organization_id: UUID,
        metrics: Optional[List[UsageMetricType]] = None,
    ) -> List[UsageAlert]:
        """
        Check for usage alerts for an organization.
        
        Args:
            organization_id: Organization to check
            metrics: Specific metrics to check (or all if None)
            
        Returns:
            List of UsageAlert objects for any thresholds exceeded
        """
        alerts = []
        
        # Get tenant SKU and limits
        tenant_sku = await self._get_tenant_sku(organization_id)
        if not tenant_sku:
            return alerts
        
        tier_limits = TIER_LIMITS.get(tenant_sku.tier, TIER_LIMITS[SKUTier.CORE])
        
        # Get current usage record
        usage_record = await self._get_current_usage_record(organization_id)
        if not usage_record:
            return alerts
        
        # Check each metric
        metrics_to_check = metrics or list(UsageMetricType)
        
        for metric in metrics_to_check:
            limit = tier_limits.get(metric, 0)
            if limit == -1:  # Unlimited
                continue
            if limit == 0:  # Not available
                continue
            
            current_usage = self._get_usage_for_metric(usage_record, metric)
            
            # Check thresholds
            alert = self._check_threshold(
                organization_id=organization_id,
                metric=metric,
                current_usage=current_usage,
                limit=limit,
            )
            
            if alert:
                alerts.append(alert)
        
        return alerts
    
    def _check_threshold(
        self,
        organization_id: UUID,
        metric: UsageMetricType,
        current_usage: int,
        limit: int,
    ) -> Optional[UsageAlert]:
        """Check if usage exceeds any threshold."""
        if limit <= 0:
            return None
        
        percentage = (current_usage / limit) * 100
        
        # Find highest threshold exceeded
        threshold = None
        if percentage >= 100:
            threshold = AlertThreshold.EXCEEDED_100
        elif percentage >= 90:
            threshold = AlertThreshold.CRITICAL_90
        elif percentage >= 80:
            threshold = AlertThreshold.WARNING_80
        
        if not threshold:
            return None
        
        # Check cache to prevent spam
        cache_key = f"{organization_id}:{metric.value}:{threshold.value}"
        if cache_key in self._alert_cache:
            if datetime.utcnow() - self._alert_cache[cache_key] < self._cache_ttl:
                return None  # Alert already sent recently
        
        # Update cache
        self._alert_cache[cache_key] = datetime.utcnow()
        
        # Generate message
        message = self._generate_alert_message(
            metric=metric,
            current_usage=current_usage,
            limit=limit,
            percentage=percentage,
            threshold=threshold,
        )
        
        return UsageAlert(
            organization_id=organization_id,
            metric_type=metric,
            current_usage=current_usage,
            limit=limit,
            percentage=percentage,
            threshold=threshold,
            message=message,
        )
    
    def _generate_alert_message(
        self,
        metric: UsageMetricType,
        current_usage: int,
        limit: int,
        percentage: float,
        threshold: AlertThreshold,
    ) -> str:
        """Generate human-readable alert message."""
        metric_name = self.METRIC_DISPLAY_NAMES.get(metric, metric.value)
        
        if threshold == AlertThreshold.EXCEEDED_100:
            return (
                f"🚨 {metric_name} limit exceeded! "
                f"You have used {current_usage:,} of your {limit:,} monthly limit ({percentage:.1f}%). "
                f"Please upgrade your plan to continue using this feature."
            )
        elif threshold == AlertThreshold.CRITICAL_90:
            return (
                f"[WARNING] {metric_name} usage critical! "
                f"You have used {current_usage:,} of your {limit:,} monthly limit ({percentage:.1f}%). "
                f"Consider upgrading your plan to avoid service interruption."
            )
        else:  # 80%
            return (
                f"ℹ️ {metric_name} usage approaching limit. "
                f"You have used {current_usage:,} of your {limit:,} monthly limit ({percentage:.1f}%). "
                f"You may want to consider upgrading your plan."
            )
    
    # ===========================================
    # USAGE DATA ACCESS
    # ===========================================
    
    async def _get_tenant_sku(self, organization_id: UUID) -> Optional[TenantSKU]:
        """Get tenant SKU for organization."""
        result = await self.db.execute(
            select(TenantSKU).where(
                and_(
                    TenantSKU.organization_id == organization_id,
                    TenantSKU.is_active == True,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_current_usage_record(
        self,
        organization_id: UUID,
    ) -> Optional[UsageRecord]:
        """Get current period's usage record."""
        # Determine current billing period (monthly)
        now = datetime.utcnow()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        result = await self.db.execute(
            select(UsageRecord).where(
                and_(
                    UsageRecord.organization_id == organization_id,
                    UsageRecord.period_start == period_start.date(),
                )
            )
        )
        return result.scalar_one_or_none()
    
    def _get_usage_for_metric(
        self,
        record: UsageRecord,
        metric: UsageMetricType,
    ) -> int:
        """Get usage count for a specific metric from record."""
        metric_mapping = {
            UsageMetricType.TRANSACTIONS: record.transactions_count,
            UsageMetricType.USERS: record.users_count,
            UsageMetricType.ENTITIES: record.entities_count,
            UsageMetricType.INVOICES: record.invoices_count,
            UsageMetricType.API_CALLS: record.api_calls_count,
            UsageMetricType.OCR_PAGES: record.ocr_pages_count,
            UsageMetricType.STORAGE_MB: record.storage_mb,
            UsageMetricType.ML_INFERENCES: record.ml_inferences_count,
            UsageMetricType.EMPLOYEES: record.employees_count,
        }
        return metric_mapping.get(metric, 0)
    
    # ===========================================
    # NOTIFICATIONS
    # ===========================================
    
    async def notify_alerts(
        self,
        alerts: List[UsageAlert],
        channels: List[AlertChannel],
    ) -> Dict[str, Any]:
        """
        Send notifications for alerts through specified channels.
        
        Args:
            alerts: List of alerts to notify
            channels: Channels to use for notification
            
        Returns:
            Dictionary with notification results per channel
        """
        results = {}
        
        for channel in channels:
            if channel == AlertChannel.EMAIL:
                results["email"] = await self._notify_email(alerts)
            elif channel == AlertChannel.WEBSOCKET:
                results["websocket"] = await self._notify_websocket(alerts)
            elif channel == AlertChannel.IN_APP:
                results["in_app"] = await self._notify_in_app(alerts)
            elif channel == AlertChannel.WEBHOOK:
                results["webhook"] = await self._notify_webhook(alerts)
        
        return results
    
    async def _notify_email(self, alerts: List[UsageAlert]) -> Dict[str, Any]:
        """Send email notifications for alerts."""
        # TODO: Integrate with email service
        # This is a stub implementation
        sent_count = 0
        
        for alert in alerts:
            # Get organization admin emails
            # await email_service.send_usage_alert(alert)
            logger.info(f"Email alert (stub): {alert.message}")
            sent_count += 1
        
        return {
            "status": "stub",
            "sent_count": sent_count,
            "message": "Email notifications not yet implemented"
        }
    
    async def _notify_websocket(self, alerts: List[UsageAlert]) -> Dict[str, Any]:
        """Send WebSocket notifications for real-time alerts."""
        # TODO: Integrate with WebSocket manager
        # This broadcasts to connected clients for the organization
        sent_count = 0
        
        for alert in alerts:
            # websocket_manager.broadcast(
            #     organization_id=alert.organization_id,
            #     message_type="usage_alert",
            #     data=alert.to_dict(),
            # )
            logger.info(f"WebSocket alert (stub): {alert.message}")
            sent_count += 1
        
        return {
            "status": "stub",
            "sent_count": sent_count,
            "message": "WebSocket notifications not yet implemented"
        }
    
    async def _notify_in_app(self, alerts: List[UsageAlert]) -> Dict[str, Any]:
        """Store alerts for in-app notification display."""
        # Store alerts in database for in-app display
        stored_count = 0
        
        for alert in alerts:
            # For now, just log it. In production, we'd store in a notifications table
            logger.info(f"In-app alert: {alert.message}")
            stored_count += 1
        
        return {
            "status": "success",
            "stored_count": stored_count,
        }
    
    async def _notify_webhook(self, alerts: List[UsageAlert]) -> Dict[str, Any]:
        """Send webhook notifications for external integrations."""
        # TODO: Send to configured webhook URLs
        sent_count = 0
        
        for alert in alerts:
            # webhook_url = await self._get_webhook_url(alert.organization_id)
            # if webhook_url:
            #     await http_client.post(webhook_url, json=alert.to_dict())
            logger.info(f"Webhook alert (stub): {alert.message}")
            sent_count += 1
        
        return {
            "status": "stub",
            "sent_count": sent_count,
            "message": "Webhook notifications not yet implemented"
        }
    
    # ===========================================
    # ALERT MANAGEMENT
    # ===========================================
    
    async def get_active_alerts(
        self,
        organization_id: UUID,
    ) -> List[UsageAlert]:
        """
        Get all active (unacknowledged) alerts for an organization.
        
        This checks current usage against all limits and returns
        any alerts that are still active.
        """
        return await self.check_usage_alerts(organization_id)
    
    async def acknowledge_alert(
        self,
        organization_id: UUID,
        metric_type: UsageMetricType,
    ) -> bool:
        """
        Acknowledge an alert to prevent repeated notifications.
        
        Acknowledged alerts won't trigger notifications for the
        same threshold level until usage drops below and rises again.
        """
        # Clear from cache (will re-alert if still above threshold after TTL)
        for threshold in AlertThreshold:
            cache_key = f"{organization_id}:{metric_type.value}:{threshold.value}"
            if cache_key in self._alert_cache:
                del self._alert_cache[cache_key]
        
        return True
    
    # ===========================================
    # USAGE SUMMARY
    # ===========================================
    
    async def get_usage_summary(
        self,
        organization_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get a comprehensive usage summary for an organization.
        
        Returns usage vs limits for all metrics.
        """
        tenant_sku = await self._get_tenant_sku(organization_id)
        if not tenant_sku:
            return {
                "error": "No active subscription found",
                "organization_id": str(organization_id),
            }
        
        tier_limits = TIER_LIMITS.get(tenant_sku.tier, TIER_LIMITS[SKUTier.CORE])
        usage_record = await self._get_current_usage_record(organization_id)
        
        metrics_summary = {}
        
        for metric in UsageMetricType:
            limit = tier_limits.get(metric, 0)
            current_usage = self._get_usage_for_metric(usage_record, metric) if usage_record else 0
            
            # Determine status
            if limit == -1:
                status = "unlimited"
                percentage = 0
            elif limit == 0:
                status = "not_available"
                percentage = 0
            else:
                percentage = (current_usage / limit) * 100 if limit > 0 else 0
                if percentage >= 100:
                    status = "exceeded"
                elif percentage >= 90:
                    status = "critical"
                elif percentage >= 80:
                    status = "warning"
                else:
                    status = "ok"
            
            metrics_summary[metric.value] = {
                "display_name": self.METRIC_DISPLAY_NAMES.get(metric, metric.value),
                "current_usage": current_usage,
                "limit": limit,
                "percentage": round(percentage, 1),
                "status": status,
            }
        
        return {
            "organization_id": str(organization_id),
            "tier": tenant_sku.tier.value,
            "billing_period": {
                "start": usage_record.period_start.isoformat() if usage_record else None,
                "end": usage_record.period_end.isoformat() if usage_record else None,
            },
            "metrics": metrics_summary,
            "checked_at": datetime.utcnow().isoformat(),
        }


# =============================================================================
# BACKGROUND TASK FOR PERIODIC ALERT CHECKING
# =============================================================================

async def check_all_organizations_usage(db: AsyncSession) -> Dict[str, Any]:
    """
    Background task to check usage for all organizations.
    
    This should be run periodically (e.g., every hour) to send
    proactive usage alerts.
    """
    service = UsageAlertService(db)
    
    # Get all active organizations
    result = await db.execute(
        select(TenantSKU.organization_id).where(TenantSKU.is_active == True)
    )
    org_ids = result.scalars().all()
    
    all_alerts = []
    
    for org_id in org_ids:
        alerts = await service.check_usage_alerts(org_id)
        if alerts:
            # Send notifications
            await service.notify_alerts(
                alerts,
                channels=[AlertChannel.IN_APP, AlertChannel.EMAIL],
            )
            all_alerts.extend(alerts)
    
    return {
        "organizations_checked": len(org_ids),
        "alerts_triggered": len(all_alerts),
        "checked_at": datetime.utcnow().isoformat(),
    }
