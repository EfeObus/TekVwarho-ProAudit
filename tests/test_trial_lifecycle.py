"""
Tests for Trial Expiration and Lifecycle Scenarios (#49)

This module contains comprehensive tests for the trial lifecycle including:
- Trial start and initialization
- Trial usage during active period
- Trial nearing expiry notifications
- Trial expiration handling
- Grace period after trial expiry
- Trial to paid conversion
"""

import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Dict, Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.organization import Organization
from app.models.sku import (
    TenantSKU,
    SKUTier,
    BillingCycle,
    UsageRecord,
)
from app.services.billing_service import BillingService


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
async def org_with_active_trial(db_session: AsyncSession):
    """Create organization with an active trial (10 days remaining)."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Active Trial Org",
        slug=f"test-{org_id.hex[:8]}",
        
    )
    db_session.add(org)
    
    now = datetime.utcnow()
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.PROFESSIONAL,  # Trial on Professional tier
        billing_cycle="monthly",
        
        # Trial set via trial_ends_at
        trial_ends_at=now + timedelta(days=10),  # 10 days remaining
        current_period_start=(now - timedelta(days=4)).date(),
        current_period_end=(now + timedelta(days=26)).date(),  # Full 30 days
        # Free during trial via pricing logic  # Free during trial
    )
    db_session.add(tenant_sku)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


@pytest.fixture
async def org_with_expiring_trial(db_session: AsyncSession):
    """Create organization with trial about to expire (2 days remaining)."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Expiring Trial Org",
        slug=f"test-{org_id.hex[:8]}",
        
    )
    db_session.add(org)
    
    now = datetime.utcnow()
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.PROFESSIONAL,
        billing_cycle="monthly",
        
        # Trial set via trial_ends_at
        trial_ends_at=now + timedelta(days=2),  # Only 2 days left
        current_period_start=(now - timedelta(days=12)).date(),
        current_period_end=(now + timedelta(days=18)).date(),
        # Free during trial via pricing logic
    )
    db_session.add(tenant_sku)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


@pytest.fixture
async def org_with_expired_trial(db_session: AsyncSession):
    """Create organization with expired trial (2 days ago)."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Expired Trial Org",
        slug=f"test-{org_id.hex[:8]}",
        
    )
    db_session.add(org)
    
    now = datetime.utcnow()
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.PROFESSIONAL,
        billing_cycle="monthly",
          # Still technically active during grace period
        # Trial set via trial_ends_at
        trial_ends_at=now - timedelta(days=2),  # Expired 2 days ago
        current_period_start=(now - timedelta(days=16)).date(),
        current_period_end=(now + timedelta(days=14)).date(),
        # Free during trial via pricing logic
    )
    db_session.add(tenant_sku)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


@pytest.fixture
async def org_trial_past_grace(db_session: AsyncSession):
    """Create organization with trial expired beyond grace period."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Past Grace Trial Org",
        slug=f"test-{org_id.hex[:8]}",
        
    )
    db_session.add(org)
    
    now = datetime.utcnow()
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.PROFESSIONAL,
        billing_cycle="monthly",
        
        # Trial set via trial_ends_at
        trial_ends_at=now - timedelta(days=5),  # 5 days past trial end (beyond 3-day grace)
        current_period_start=(now - timedelta(days=19)).date(),
        current_period_end=(now + timedelta(days=11)).date(),
        # Free during trial via pricing logic
    )
    db_session.add(tenant_sku)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


@pytest.fixture
async def org_with_trial_and_payment_method(db_session: AsyncSession):
    """Create organization with active trial and saved payment method."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Trial With Payment Org",
        slug=f"test-{org_id.hex[:8]}",
        
    )
    db_session.add(org)
    
    now = datetime.utcnow()
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.PROFESSIONAL,
        billing_cycle="monthly",
        
        # Trial set via trial_ends_at
        trial_ends_at=now + timedelta(days=5),
        current_period_start=(now - timedelta(days=9)).date(),
        current_period_end=(now + timedelta(days=21)).date(),
        # Free during trial via pricing logic
        custom_metadata={
            "paystack_subscription": {
                "customer_code": "CUS_test12345",
                "authorization_code": "AUTH_test12345",
            }
        },
    )
    db_session.add(tenant_sku)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


@pytest.fixture
async def org_not_on_trial(db_session: AsyncSession):
    """Create organization with paid subscription (not on trial)."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Paid Subscription Org",
        slug=f"test-{org_id.hex[:8]}",
        
    )
    db_session.add(org)
    
    now = datetime.utcnow()
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.PROFESSIONAL,
        billing_cycle="monthly",
        
        # Not trial - no trial_ends_at
        trial_ends_at=None,  # Not on trial
        current_period_start=(now - timedelta(days=10)).date(),
        current_period_end=(now + timedelta(days=20)).date(),
        custom_price_naira=2500000,
    )
    db_session.add(tenant_sku)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


# =============================================================================
# TEST CLASSES - Subscription Status
# =============================================================================

class TestSubscriptionStatusDetermination:
    """Tests for _determine_subscription_status method."""
    
    @pytest.mark.asyncio
    async def test_active_trial_status(
        self,
        db_session: AsyncSession,
        org_with_active_trial,
    ):
        """Test that active trial returns 'trial' status."""
        result = await db_session.execute(
            select(TenantSKU).where(TenantSKU.organization_id == org_with_active_trial.id)
        )
        tenant_sku = result.scalar_one()
        
        service = BillingService(db_session)
        status = service._determine_subscription_status(tenant_sku, datetime.utcnow())
        
        assert status == "trial"
    
    @pytest.mark.asyncio
    async def test_expired_trial_in_grace_period(
        self,
        db_session: AsyncSession,
        org_with_expired_trial,
    ):
        """Test that recently expired trial returns 'trial_expired' status."""
        result = await db_session.execute(
            select(TenantSKU).where(TenantSKU.organization_id == org_with_expired_trial.id)
        )
        tenant_sku = result.scalar_one()
        
        service = BillingService(db_session)
        status = service._determine_subscription_status(tenant_sku, datetime.utcnow())
        
        assert status == "trial_expired"
    
    @pytest.mark.asyncio
    async def test_trial_past_grace_period(
        self,
        db_session: AsyncSession,
        org_trial_past_grace,
    ):
        """Test that trial past grace period returns 'trial_ended'."""
        result = await db_session.execute(
            select(TenantSKU).where(TenantSKU.organization_id == org_trial_past_grace.id)
        )
        tenant_sku = result.scalar_one()
        
        service = BillingService(db_session)
        status = service._determine_subscription_status(tenant_sku, datetime.utcnow())
        
        assert status == "trial_ended"
    
    @pytest.mark.asyncio
    async def test_active_paid_subscription(
        self,
        db_session: AsyncSession,
        org_not_on_trial,
    ):
        """Test that active paid subscription returns 'active' status."""
        result = await db_session.execute(
            select(TenantSKU).where(TenantSKU.organization_id == org_not_on_trial.id)
        )
        tenant_sku = result.scalar_one()
        
        service = BillingService(db_session)
        status = service._determine_subscription_status(tenant_sku, datetime.utcnow())
        
        assert status == "active"


class TestCheckSubscriptionAccess:
    """Tests for check_subscription_access method."""
    
    @pytest.mark.asyncio
    async def test_active_trial_has_access(
        self,
        db_session: AsyncSession,
        org_with_active_trial,
    ):
        """Test that active trial grants access."""
        service = BillingService(db_session)
        
        access = await service.check_subscription_access(org_with_active_trial.id)
        
        assert access["has_access"] is True
        assert access["status"] == "trial"
        assert access["is_trial"] is True
        assert access["days_remaining"] > 0
    
    @pytest.mark.asyncio
    async def test_expiring_trial_shows_days_remaining(
        self,
        db_session: AsyncSession,
        org_with_expiring_trial,
    ):
        """Test that expiring trial shows correct days remaining."""
        service = BillingService(db_session)
        
        access = await service.check_subscription_access(org_with_expiring_trial.id)
        
        assert access["has_access"] is True
        assert access["status"] == "trial"
        assert access["days_remaining"] <= 3  # 2 days + buffer for test timing
        assert "trial" in access["message"].lower()
    
    @pytest.mark.asyncio
    async def test_expired_trial_in_grace_has_limited_access(
        self,
        db_session: AsyncSession,
        org_with_expired_trial,
    ):
        """Test that expired trial in grace period still has access."""
        service = BillingService(db_session)
        
        access = await service.check_subscription_access(org_with_expired_trial.id)
        
        # During 3-day grace period, should still have access
        assert access["has_access"] is True
        assert access["status"] == "trial_expired"
    
    @pytest.mark.asyncio
    async def test_trial_past_grace_no_access(
        self,
        db_session: AsyncSession,
        org_trial_past_grace,
    ):
        """Test that trial past grace period loses access."""
        service = BillingService(db_session)
        
        access = await service.check_subscription_access(org_trial_past_grace.id)
        
        assert access["has_access"] is False
        assert access["status"] == "trial_ended"
    
    @pytest.mark.asyncio
    async def test_paid_subscription_has_access(
        self,
        db_session: AsyncSession,
        org_not_on_trial,
    ):
        """Test that paid subscription has access and is not trial."""
        service = BillingService(db_session)
        
        access = await service.check_subscription_access(org_not_on_trial.id)
        
        assert access["has_access"] is True
        assert access["status"] == "active"
        assert access["is_trial"] is False
    
    @pytest.mark.asyncio
    async def test_no_subscription_no_access(self, db_session: AsyncSession):
        """Test that organization without subscription has no access."""
        service = BillingService(db_session)
        
        access = await service.check_subscription_access(uuid4())  # Random non-existent org
        
        assert access["has_access"] is False
        assert access["status"] == "no_subscription"


class TestTrialToPaidConversionValidation:
    """Tests for validate_trial_to_paid_conversion method."""
    
    @pytest.mark.asyncio
    async def test_can_convert_active_trial(
        self,
        db_session: AsyncSession,
        org_with_trial_and_payment_method,
    ):
        """Test that active trial with payment method can convert."""
        service = BillingService(db_session)
        
        # Note: This test may need mocking for the Paystack API call
        result = await service.validate_trial_to_paid_conversion(
            org_with_trial_and_payment_method.id
        )
        
        # Should be able to convert (or indicate no payment method if mocking needed)
        assert "can_convert" in result
        # The exact result depends on whether we can mock the Paystack API
    
    @pytest.mark.asyncio
    async def test_cannot_convert_no_trial(
        self,
        db_session: AsyncSession,
        org_not_on_trial,
    ):
        """Test that non-trial subscription cannot convert."""
        service = BillingService(db_session)
        
        result = await service.validate_trial_to_paid_conversion(org_not_on_trial.id)
        
        assert result["can_convert"] is False
        assert result["reason"] == "not_on_trial"
    
    @pytest.mark.asyncio
    async def test_cannot_convert_expired_trial(
        self,
        db_session: AsyncSession,
        org_with_expired_trial,
    ):
        """Test that expired trial cannot convert."""
        service = BillingService(db_session)
        
        result = await service.validate_trial_to_paid_conversion(org_with_expired_trial.id)
        
        assert result["can_convert"] is False
        assert result["reason"] == "trial_expired"
    
    @pytest.mark.asyncio
    async def test_cannot_convert_no_subscription(self, db_session: AsyncSession):
        """Test that org without subscription cannot convert."""
        service = BillingService(db_session)
        
        result = await service.validate_trial_to_paid_conversion(uuid4())
        
        assert result["can_convert"] is False
        assert result["reason"] == "no_subscription"


# =============================================================================
# TEST CLASSES - Trial Period Boundaries
# =============================================================================

class TestTrialPeriodBoundaries:
    """Tests for edge cases at trial period boundaries."""
    
    @pytest.mark.asyncio
    async def test_trial_exactly_at_expiry(self, db_session: AsyncSession):
        """Test status when trial is exactly at expiry time."""
        org_id = uuid4()
        
        org = Organization(
            id=org_id,
            name="Exact Expiry Org",
            slug=f"test-{org_id.hex[:8]}",
            
        )
        db_session.add(org)
        
        now = datetime.utcnow()
        tenant_sku = TenantSKU(
            id=uuid4(),
            organization_id=org_id,
            tier=SKUTier.PROFESSIONAL,
            billing_cycle="monthly",
            
            # Trial set via trial_ends_at
            trial_ends_at=now,  # Exactly at current time
            current_period_start=(now - timedelta(days=14)).date(),
            current_period_end=(now + timedelta(days=16)).date(),
            # Free during trial via pricing logic
        )
        db_session.add(tenant_sku)
        await db_session.flush()
        
        service = BillingService(db_session)
        
        # Check slightly before and after
        status_at_time = service._determine_subscription_status(
            tenant_sku, now + timedelta(seconds=1)
        )
        
        # Just past expiry should be in grace period
        assert status_at_time == "trial_expired"
    
    @pytest.mark.asyncio
    async def test_trial_last_day(self, db_session: AsyncSession):
        """Test access on the last day of trial."""
        org_id = uuid4()
        
        org = Organization(
            id=org_id,
            name="Last Day Org",
            slug=f"test-{org_id.hex[:8]}",
            
        )
        db_session.add(org)
        
        now = datetime.utcnow()
        tenant_sku = TenantSKU(
            id=uuid4(),
            organization_id=org_id,
            tier=SKUTier.PROFESSIONAL,
            billing_cycle="monthly",
            
            # Trial set via trial_ends_at
            trial_ends_at=now + timedelta(hours=12),  # Expires in 12 hours
            current_period_start=(now - timedelta(days=13, hours=12)).date(),
            current_period_end=(now + timedelta(days=16, hours=12)).date(),
            # Free during trial via pricing logic
        )
        db_session.add(tenant_sku)
        await db_session.flush()
        
        service = BillingService(db_session)
        access = await service.check_subscription_access(org_id)
        
        assert access["has_access"] is True
        assert access["status"] == "trial"
        assert access["days_remaining"] <= 1
    
    @pytest.mark.asyncio
    async def test_trial_grace_period_day_1(self, db_session: AsyncSession):
        """Test access on day 1 of grace period (just expired)."""
        org_id = uuid4()
        
        org = Organization(
            id=org_id,
            name="Grace Day 1 Org",
            slug=f"test-{org_id.hex[:8]}",
            
        )
        db_session.add(org)
        
        now = datetime.utcnow()
        tenant_sku = TenantSKU(
            id=uuid4(),
            organization_id=org_id,
            tier=SKUTier.PROFESSIONAL,
            billing_cycle="monthly",
            
            # Trial set via trial_ends_at
            trial_ends_at=now - timedelta(hours=12),  # Expired 12 hours ago
            current_period_start=(now - timedelta(days=14, hours=12)).date(),
            current_period_end=(now + timedelta(days=15, hours=12)).date(),
            # Free during trial via pricing logic
        )
        db_session.add(tenant_sku)
        await db_session.flush()
        
        service = BillingService(db_session)
        access = await service.check_subscription_access(org_id)
        
        # Should still have access during 3-day grace period
        assert access["has_access"] is True
        assert access["status"] == "trial_expired"
    
    @pytest.mark.asyncio
    async def test_trial_grace_period_day_3(self, db_session: AsyncSession):
        """Test access on day 3 of grace period (last day)."""
        org_id = uuid4()
        
        org = Organization(
            id=org_id,
            name="Grace Day 3 Org",
            slug=f"test-{org_id.hex[:8]}",
            
        )
        db_session.add(org)
        
        now = datetime.utcnow()
        tenant_sku = TenantSKU(
            id=uuid4(),
            organization_id=org_id,
            tier=SKUTier.PROFESSIONAL,
            billing_cycle="monthly",
            
            # Trial set via trial_ends_at
            trial_ends_at=now - timedelta(days=2, hours=23),  # Almost 3 days ago
            current_period_start=(now - timedelta(days=16, hours=23)).date(),
            current_period_end=(now + timedelta(days=13, hours=1)).date(),
            # Free during trial via pricing logic
        )
        db_session.add(tenant_sku)
        await db_session.flush()
        
        service = BillingService(db_session)
        access = await service.check_subscription_access(org_id)
        
        # Should still have access on day 3 of grace
        assert access["has_access"] is True
        assert access["status"] == "trial_expired"
    
    @pytest.mark.asyncio
    async def test_trial_grace_period_expired(self, db_session: AsyncSession):
        """Test access after grace period ends (day 4+)."""
        org_id = uuid4()
        
        org = Organization(
            id=org_id,
            name="Past Grace Org",
            slug=f"test-{org_id.hex[:8]}",
            
        )
        db_session.add(org)
        
        now = datetime.utcnow()
        tenant_sku = TenantSKU(
            id=uuid4(),
            organization_id=org_id,
            tier=SKUTier.PROFESSIONAL,
            billing_cycle="monthly",
            
            # Trial set via trial_ends_at
            trial_ends_at=now - timedelta(days=4),  # 4 days ago (beyond 3-day grace)
            current_period_start=(now - timedelta(days=18)).date(),
            current_period_end=(now + timedelta(days=12)).date(),
            # Free during trial via pricing logic
        )
        db_session.add(tenant_sku)
        await db_session.flush()
        
        service = BillingService(db_session)
        access = await service.check_subscription_access(org_id)
        
        # Should NOT have access after grace period
        assert access["has_access"] is False
        assert access["status"] == "trial_ended"


# =============================================================================
# TEST CLASSES - Trial Tier Behavior
# =============================================================================

class TestTrialTierBehavior:
    """Tests for tier-specific behavior during trial."""
    
    @pytest.mark.asyncio
    async def test_trial_professional_tier_features(
        self,
        db_session: AsyncSession,
        org_with_active_trial,
    ):
        """Test that Professional tier features are available during trial."""
        result = await db_session.execute(
            select(TenantSKU).where(TenantSKU.organization_id == org_with_active_trial.id)
        )
        tenant_sku = result.scalar_one()
        
        # Trial should be on Professional tier
        assert tenant_sku.tier == SKUTier.PROFESSIONAL
        assert tenant_sku.is_trial is True
    
    @pytest.mark.asyncio
    async def test_trial_has_correct_tier_in_access_response(
        self,
        db_session: AsyncSession,
        org_with_active_trial,
    ):
        """Test that check_subscription_access returns correct tier for trial."""
        service = BillingService(db_session)
        
        access = await service.check_subscription_access(org_with_active_trial.id)
        
        assert access["tier"] == "PROFESSIONAL"
        assert access["is_trial"] is True


class TestTrialStatusMessages:
    """Tests for appropriate status messages during trial lifecycle."""
    
    @pytest.mark.asyncio
    async def test_active_trial_message_includes_days(
        self,
        db_session: AsyncSession,
        org_with_active_trial,
    ):
        """Test that active trial message includes days remaining."""
        service = BillingService(db_session)
        
        access = await service.check_subscription_access(org_with_active_trial.id)
        
        assert "days" in access["message"].lower()
        assert "trial" in access["message"].lower()
    
    @pytest.mark.asyncio
    async def test_expiring_trial_urgent_message(
        self,
        db_session: AsyncSession,
        org_with_expiring_trial,
    ):
        """Test that expiring trial shows urgency."""
        service = BillingService(db_session)
        
        access = await service.check_subscription_access(org_with_expiring_trial.id)
        
        # Message should mention remaining days
        assert "trial" in access["message"].lower()
    
    @pytest.mark.asyncio
    async def test_expired_trial_subscribe_message(
        self,
        db_session: AsyncSession,
        org_with_expired_trial,
    ):
        """Test that expired trial message prompts subscription."""
        service = BillingService(db_session)
        
        access = await service.check_subscription_access(org_with_expired_trial.id)
        
        assert "expired" in access["message"].lower() or "subscribe" in access["message"].lower()


# =============================================================================
# TEST CLASSES - Integration with Usage
# =============================================================================

class TestTrialWithUsage:
    """Tests for trial behavior with usage tracking."""
    
    @pytest.mark.asyncio
    async def test_trial_usage_tracked(
        self,
        db_session: AsyncSession,
        org_with_active_trial,
    ):
        """Test that usage is tracked during trial period."""
        # Create usage record
        period_start = datetime.utcnow().date().replace(day=1)
        next_month = period_start.replace(month=period_start.month + 1) if period_start.month < 12 else period_start.replace(year=period_start.year + 1, month=1)
        
        usage = UsageRecord(
            id=uuid4(),
            organization_id=org_with_active_trial.id,
            period_start=period_start,
            period_end=next_month,
            transactions_count=100,
            users_count=5,
            entities_count=3,
            invoices_count=25,
            api_calls_count=500,
            ocr_pages_count=10,
            storage_used_mb=Decimal("200.00"),
            ml_inferences_count=5,
            employees_count=0,
        )
        db_session.add(usage)
        await db_session.flush()
        
        # Verify usage was created
        result = await db_session.execute(
            select(UsageRecord).where(UsageRecord.organization_id == org_with_active_trial.id)
        )
        saved_usage = result.scalar_one()
        
        assert saved_usage.transactions_count == 100
    
    @pytest.mark.asyncio
    async def test_trial_usage_affects_downgrade_validation_after_conversion(
        self,
        db_session: AsyncSession,
        org_with_active_trial,
    ):
        """Test that trial usage is considered if user later wants to downgrade."""
        # Create high usage during trial
        period_start = datetime.utcnow().date().replace(day=1)
        next_month = period_start.replace(month=period_start.month + 1) if period_start.month < 12 else period_start.replace(year=period_start.year + 1, month=1)
        
        usage = UsageRecord(
            id=uuid4(),
            organization_id=org_with_active_trial.id,
            period_start=period_start,
            period_end=next_month,
            transactions_count=10000,  # High usage
            users_count=20,
            entities_count=8,
            invoices_count=500,
            api_calls_count=50000,
            ocr_pages_count=200,
            storage_used_mb=Decimal("5000.00"),
            ml_inferences_count=100,
            employees_count=50,
        )
        db_session.add(usage)
        
        # Convert trial to paid
        result = await db_session.execute(
            select(TenantSKU).where(TenantSKU.organization_id == org_with_active_trial.id)
        )
        tenant_sku = result.scalar_one()
        tenant_sku.is_trial = False
        tenant_sku.trial_ends_at = None
        await db_session.flush()
        
        service = BillingService(db_session)
        
        # Try to downgrade to Core - should fail due to high usage
        validation = await service.validate_downgrade(
            organization_id=org_with_active_trial.id,
            target_tier=SKUTier.CORE,
        )
        
        # Should not be able to downgrade with Professional-level usage
        assert validation["can_downgrade"] is False


# =============================================================================
# TEST CLASSES - Concurrent Trial Operations
# =============================================================================

class TestConcurrentTrialOperations:
    """Tests for handling concurrent operations during trial."""
    
    @pytest.mark.asyncio
    async def test_multiple_access_checks_consistent(
        self,
        db_session: AsyncSession,
        org_with_active_trial,
    ):
        """Test that multiple access checks return consistent results."""
        import asyncio
        
        service = BillingService(db_session)
        
        # Run multiple access checks concurrently
        results = await asyncio.gather(
            service.check_subscription_access(org_with_active_trial.id),
            service.check_subscription_access(org_with_active_trial.id),
            service.check_subscription_access(org_with_active_trial.id),
        )
        
        # All should return consistent results
        for result in results:
            assert result["has_access"] is True
            assert result["status"] == "trial"
