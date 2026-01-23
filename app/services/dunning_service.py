"""
TekVwarho ProAudit - Dunning Management Service

Manages the dunning process for failed payments.
Implements escalation rules and retry schedules.

Dunning Levels:
1. Initial (Day 0): First failure notification
2. Warning (Day 3): First reminder
3. Urgent (Day 7): Urgent notice
4. Final (Day 14): Final warning before suspension
5. Suspended (Day 21): Account suspended

Retry Schedule:
- Day 1: First retry
- Day 3: Second retry
- Day 5: Third retry
- Day 7: Fourth retry (escalate to urgent)
- Day 10: Fifth retry
- Day 14: Sixth retry (final notice)
- Day 21: Account suspension
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from sqlalchemy import select, and_, or_, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory

logger = logging.getLogger(__name__)


class DunningLevel(str, Enum):
    """Dunning escalation levels."""
    INITIAL = "initial"
    WARNING = "warning"
    URGENT = "urgent"
    FINAL = "final"
    SUSPENDED = "suspended"


@dataclass
class DunningRecord:
    """Dunning status for an organization."""
    organization_id: uuid.UUID
    level: DunningLevel
    amount_naira: int
    first_failure_at: datetime
    last_retry_at: Optional[datetime]
    retry_count: int
    next_retry_at: Optional[datetime]
    days_until_suspension: int
    notes: Optional[str]


# Dunning schedule configuration
DUNNING_SCHEDULE = {
    # (days_since_failure, retry_count) -> action
    (0, 0): {"action": "notify", "level": DunningLevel.INITIAL},
    (1, 1): {"action": "retry", "level": DunningLevel.INITIAL},
    (3, 2): {"action": "retry", "level": DunningLevel.WARNING},
    (5, 3): {"action": "retry", "level": DunningLevel.WARNING},
    (7, 4): {"action": "retry", "level": DunningLevel.URGENT},
    (10, 5): {"action": "retry", "level": DunningLevel.URGENT},
    (14, 6): {"action": "retry", "level": DunningLevel.FINAL},
    (21, 7): {"action": "suspend", "level": DunningLevel.SUSPENDED},
}

# Grace period before suspension (days)
GRACE_PERIOD_DAYS = 21

# Maximum retry attempts
MAX_RETRY_ATTEMPTS = 6


class DunningService:
    """Service for managing payment dunning and collections."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def record_payment_failure(
        self,
        organization_id: uuid.UUID,
        reason: str,
        amount_naira: int,
        transaction_reference: Optional[str] = None,
    ) -> DunningRecord:
        """
        Record a payment failure and initiate dunning process.
        
        Args:
            organization_id: The organization with failed payment
            reason: Reason for payment failure
            amount_naira: Amount that failed to process
            transaction_reference: Optional payment transaction reference
            
        Returns:
            DunningRecord with current dunning status
        """
        from app.models.sku import TenantSKU
        
        now = datetime.utcnow()
        
        # Get or create dunning record in tenant_sku metadata
        result = await self.db.execute(
            select(TenantSKU).where(TenantSKU.organization_id == organization_id)
        )
        tenant_sku = result.scalar_one_or_none()
        
        if not tenant_sku:
            raise ValueError(f"No TenantSKU found for organization {organization_id}")
        
        # Initialize or update dunning metadata
        dunning_data = tenant_sku.custom_metadata or {}
        if "dunning" not in dunning_data:
            dunning_data["dunning"] = {
                "first_failure_at": now.isoformat(),
                "last_retry_at": None,
                "retry_count": 0,
                "level": DunningLevel.INITIAL.value,
                "amount_naira": amount_naira,
                "failure_reasons": [reason],
                "transaction_references": [transaction_reference] if transaction_reference else [],
            }
        else:
            # Update existing dunning record
            dunning_data["dunning"]["retry_count"] += 1
            dunning_data["dunning"]["last_retry_at"] = now.isoformat()
            if reason not in dunning_data["dunning"].get("failure_reasons", []):
                dunning_data["dunning"]["failure_reasons"].append(reason)
            if transaction_reference:
                refs = dunning_data["dunning"].get("transaction_references", [])
                if transaction_reference not in refs:
                    refs.append(transaction_reference)
                    dunning_data["dunning"]["transaction_references"] = refs
        
        tenant_sku.custom_metadata = dunning_data
        await self.db.flush()
        
        logger.info(f"Recorded payment failure for org {organization_id}: {reason}")
        
        return self._create_dunning_record(tenant_sku)
    
    async def get_dunning_status(
        self,
        organization_id: uuid.UUID,
    ) -> Optional[DunningRecord]:
        """Get current dunning status for an organization."""
        from app.models.sku import TenantSKU
        
        result = await self.db.execute(
            select(TenantSKU).where(TenantSKU.organization_id == organization_id)
        )
        tenant_sku = result.scalar_one_or_none()
        
        if not tenant_sku:
            return None
        
        dunning_data = (tenant_sku.custom_metadata or {}).get("dunning")
        if not dunning_data:
            return None
        
        return self._create_dunning_record(tenant_sku)
    
    async def get_active_dunning_records(self) -> List[DunningRecord]:
        """Get all organizations currently in dunning."""
        from app.models.sku import TenantSKU
        
        result = await self.db.execute(
            select(TenantSKU)
            .where(TenantSKU.is_active == True)
            .where(TenantSKU.custom_metadata != None)
        )
        tenant_skus = result.scalars().all()
        
        records = []
        for tenant_sku in tenant_skus:
            dunning_data = (tenant_sku.custom_metadata or {}).get("dunning")
            if dunning_data and dunning_data.get("level") != DunningLevel.SUSPENDED.value:
                records.append(self._create_dunning_record(tenant_sku))
        
        return records
    
    async def should_retry_payment(
        self,
        organization_id: uuid.UUID,
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if payment should be retried and what action to take.
        
        Returns:
            Tuple of (should_retry, action) where action is one of:
            - "retry": Attempt payment retry
            - "escalate": Escalate dunning level
            - "suspend": Suspend account
            - None: No action needed
        """
        from app.models.sku import TenantSKU
        
        result = await self.db.execute(
            select(TenantSKU).where(TenantSKU.organization_id == organization_id)
        )
        tenant_sku = result.scalar_one_or_none()
        
        if not tenant_sku:
            return False, None
        
        dunning_data = (tenant_sku.custom_metadata or {}).get("dunning")
        if not dunning_data:
            return False, None
        
        now = datetime.utcnow()
        first_failure = datetime.fromisoformat(dunning_data["first_failure_at"])
        last_retry = dunning_data.get("last_retry_at")
        if last_retry:
            last_retry = datetime.fromisoformat(last_retry)
        
        days_since_failure = (now - first_failure).days
        retry_count = dunning_data.get("retry_count", 0)
        current_level = DunningLevel(dunning_data.get("level", DunningLevel.INITIAL.value))
        
        # Check if already suspended
        if current_level == DunningLevel.SUSPENDED:
            return False, None
        
        # Check if max retries reached
        if retry_count >= MAX_RETRY_ATTEMPTS:
            if days_since_failure >= GRACE_PERIOD_DAYS:
                return True, "suspend"
            return False, None
        
        # Determine next action based on schedule
        next_action = None
        for (days, retries), action_info in sorted(DUNNING_SCHEDULE.items()):
            if days_since_failure >= days and retry_count < retries:
                next_action = action_info["action"]
                break
        
        if next_action == "suspend":
            return True, "suspend"
        elif next_action == "retry":
            # Check if enough time has passed since last retry (minimum 24 hours)
            if last_retry:
                hours_since_retry = (now - last_retry).total_seconds() / 3600
                if hours_since_retry < 24:
                    return False, None
            return True, "retry"
        elif next_action == "notify":
            return True, "escalate"
        
        return False, None
    
    async def record_retry_attempt(
        self,
        organization_id: uuid.UUID,
        success: bool = False,
    ) -> None:
        """Record a payment retry attempt."""
        from app.models.sku import TenantSKU
        
        now = datetime.utcnow()
        
        result = await self.db.execute(
            select(TenantSKU).where(TenantSKU.organization_id == organization_id)
        )
        tenant_sku = result.scalar_one_or_none()
        
        if not tenant_sku:
            return
        
        dunning_data = tenant_sku.custom_metadata or {}
        if "dunning" in dunning_data:
            dunning_data["dunning"]["last_retry_at"] = now.isoformat()
            dunning_data["dunning"]["retry_count"] = dunning_data["dunning"].get("retry_count", 0) + 1
            
            if success:
                # Clear dunning on successful payment
                del dunning_data["dunning"]
                logger.info(f"Payment recovered for org {organization_id}, cleared dunning")
            
            tenant_sku.custom_metadata = dunning_data
            await self.db.flush()
    
    async def escalate_dunning_level(
        self,
        organization_id: uuid.UUID,
    ) -> DunningLevel:
        """Escalate the dunning level for an organization."""
        from app.models.sku import TenantSKU
        
        result = await self.db.execute(
            select(TenantSKU).where(TenantSKU.organization_id == organization_id)
        )
        tenant_sku = result.scalar_one_or_none()
        
        if not tenant_sku:
            raise ValueError(f"No TenantSKU found for organization {organization_id}")
        
        dunning_data = tenant_sku.custom_metadata or {}
        if "dunning" not in dunning_data:
            raise ValueError(f"No dunning record for organization {organization_id}")
        
        current_level = DunningLevel(dunning_data["dunning"].get("level", DunningLevel.INITIAL.value))
        
        # Escalation order
        escalation_order = [
            DunningLevel.INITIAL,
            DunningLevel.WARNING,
            DunningLevel.URGENT,
            DunningLevel.FINAL,
            DunningLevel.SUSPENDED,
        ]
        
        current_index = escalation_order.index(current_level)
        if current_index < len(escalation_order) - 1:
            new_level = escalation_order[current_index + 1]
            dunning_data["dunning"]["level"] = new_level.value
            dunning_data["dunning"]["escalated_at"] = datetime.utcnow().isoformat()
            tenant_sku.custom_metadata = dunning_data
            await self.db.flush()
            
            logger.info(f"Escalated dunning for org {organization_id}: {current_level.value} -> {new_level.value}")
            return new_level
        
        return current_level
    
    async def clear_dunning(
        self,
        organization_id: uuid.UUID,
        reason: str = "Payment received",
    ) -> None:
        """Clear dunning status after successful payment."""
        from app.models.sku import TenantSKU
        
        result = await self.db.execute(
            select(TenantSKU).where(TenantSKU.organization_id == organization_id)
        )
        tenant_sku = result.scalar_one_or_none()
        
        if not tenant_sku:
            return
        
        dunning_data = tenant_sku.custom_metadata or {}
        if "dunning" in dunning_data:
            # Archive dunning record
            dunning_data["dunning_history"] = dunning_data.get("dunning_history", [])
            dunning_data["dunning_history"].append({
                **dunning_data["dunning"],
                "cleared_at": datetime.utcnow().isoformat(),
                "cleared_reason": reason,
            })
            del dunning_data["dunning"]
            
            tenant_sku.custom_metadata = dunning_data
            
            # Reactivate if suspended
            if tenant_sku.suspended_at:
                tenant_sku.suspended_at = None
                tenant_sku.suspension_reason = None
                tenant_sku.is_active = True
            
            await self.db.flush()
            logger.info(f"Cleared dunning for org {organization_id}: {reason}")
    
    async def get_dunning_summary(self) -> Dict[str, Any]:
        """Get summary of all dunning activity."""
        from app.models.sku import TenantSKU
        
        result = await self.db.execute(
            select(TenantSKU).where(TenantSKU.custom_metadata != None)
        )
        tenant_skus = result.scalars().all()
        
        summary = {
            "total_in_dunning": 0,
            "by_level": {
                DunningLevel.INITIAL.value: 0,
                DunningLevel.WARNING.value: 0,
                DunningLevel.URGENT.value: 0,
                DunningLevel.FINAL.value: 0,
                DunningLevel.SUSPENDED.value: 0,
            },
            "total_amount_at_risk": 0,
            "average_days_in_dunning": 0,
        }
        
        total_days = 0
        for tenant_sku in tenant_skus:
            dunning_data = (tenant_sku.custom_metadata or {}).get("dunning")
            if dunning_data:
                level = dunning_data.get("level", DunningLevel.INITIAL.value)
                summary["total_in_dunning"] += 1
                summary["by_level"][level] = summary["by_level"].get(level, 0) + 1
                summary["total_amount_at_risk"] += dunning_data.get("amount_naira", 0)
                
                first_failure = datetime.fromisoformat(dunning_data["first_failure_at"])
                days = (datetime.utcnow() - first_failure).days
                total_days += days
        
        if summary["total_in_dunning"] > 0:
            summary["average_days_in_dunning"] = total_days / summary["total_in_dunning"]
        
        return summary
    
    def _create_dunning_record(self, tenant_sku) -> DunningRecord:
        """Create DunningRecord from TenantSKU."""
        dunning_data = (tenant_sku.custom_metadata or {}).get("dunning", {})
        
        first_failure = datetime.fromisoformat(dunning_data.get("first_failure_at", datetime.utcnow().isoformat()))
        days_elapsed = (datetime.utcnow() - first_failure).days
        days_until_suspension = max(0, GRACE_PERIOD_DAYS - days_elapsed)
        
        last_retry = dunning_data.get("last_retry_at")
        if last_retry:
            last_retry = datetime.fromisoformat(last_retry)
        
        return DunningRecord(
            organization_id=tenant_sku.organization_id,
            level=DunningLevel(dunning_data.get("level", DunningLevel.INITIAL.value)),
            amount_naira=dunning_data.get("amount_naira", 0),
            first_failure_at=first_failure,
            last_retry_at=last_retry,
            retry_count=dunning_data.get("retry_count", 0),
            next_retry_at=None,  # Calculated on demand
            days_until_suspension=days_until_suspension,
            notes="; ".join(dunning_data.get("failure_reasons", [])),
        )
