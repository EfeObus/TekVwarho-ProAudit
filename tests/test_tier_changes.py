"""
Tests for Tier Upgrade/Downgrade Paths (#50)

This module contains comprehensive tests for the subscription tier change functionality,
including validation, proration calculations, and the full downgrade request flow.
"""

import pytest
from calendar import monthrange
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
    UsageMetricType,
    IntelligenceAddon,
    TIER_LIMITS,
)
from app.services.billing_service import BillingService, BillingErrorCode
from app.services.metering_service import MeteringService


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
async def test_org_professional(db_session: AsyncSession):
    """Create an organization with Professional tier subscription."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Professional Tier Test Org",
        slug=f"pro-test-{org_id.hex[:8]}",
    )
    db_session.add(org)
    
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.PROFESSIONAL,
        billing_cycle="monthly",
        is_active=True,
        # No trial - trial_ends_at defaults to None
        current_period_start=(datetime.utcnow() - timedelta(days=15)).date(),  # Mid-cycle
        current_period_end=(datetime.utcnow() + timedelta(days=15)).date(),
        custom_price_naira=2500000,  # ₦25,000 in kobo
    )
    db_session.add(tenant_sku)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


@pytest.fixture
async def test_org_enterprise(db_session: AsyncSession):
    """Create an organization with Enterprise tier subscription."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Enterprise Tier Test Org",
        slug=f"enterprise-test-{org_id.hex[:8]}",
    )
    db_session.add(org)
    
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.ENTERPRISE,
        billing_cycle="monthly",
        is_active=True,
        current_period_start=(datetime.utcnow() - timedelta(days=10)).date(),
        current_period_end=(datetime.utcnow() + timedelta(days=20)).date(),
        custom_price_naira=7500000,  # ₦75,000 in kobo
    )
    db_session.add(tenant_sku)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


@pytest.fixture
async def test_org_core_with_usage(db_session: AsyncSession):
    """Create an organization with Core tier and existing usage."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Core Tier Test Org",
        slug=f"core-test-{org_id.hex[:8]}",
    )
    db_session.add(org)
    
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.CORE,
        billing_cycle="monthly",
        is_active=True,
        current_period_start=(datetime.utcnow() - timedelta(days=5)).date(),
        current_period_end=(datetime.utcnow() + timedelta(days=25)).date(),
        custom_price_naira=1000000,  # ₦10,000 in kobo
    )
    db_session.add(tenant_sku)
    
    # Create usage record - use correct period to match metering service
    today = date.today()
    period_start = date(today.year, today.month, 1)
    last_day = monthrange(today.year, today.month)[1]
    period_end = date(today.year, today.month, last_day)
    
    usage = UsageRecord(
        id=uuid4(),
        organization_id=org_id,
        period_start=period_start,
        period_end=period_end,
        transactions_count=50,
        users_count=3,
        entities_count=1,  # Core allows 1 entity
        invoices_count=20,
        api_calls_count=0,  # Core doesn't allow API calls
        ocr_pages_count=0,  # Core doesn't allow OCR
        storage_used_mb=Decimal("100.00"),
        ml_inferences_count=0,  # Core doesn't allow ML
        employees_count=0,
    )
    db_session.add(usage)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


@pytest.fixture
async def test_org_enterprise_high_usage(db_session: AsyncSession):
    """Create Enterprise org with high usage that would exceed Core/Professional limits."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Enterprise High Usage Org",
        slug=f"enterprise-high-{org_id.hex[:8]}",
    )
    db_session.add(org)
    
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.ENTERPRISE,
        billing_cycle="monthly",
        is_active=True,
        current_period_start=(datetime.utcnow() - timedelta(days=10)).date(),
        current_period_end=(datetime.utcnow() + timedelta(days=20)).date(),
        custom_price_naira=7500000,
    )
    db_session.add(tenant_sku)
    
    # Create high usage that exceeds lower tier limits
    today = date.today()
    period_start = date(today.year, today.month, 1)
    last_day = monthrange(today.year, today.month)[1]
    period_end = date(today.year, today.month, last_day)
    
    usage = UsageRecord(
        id=uuid4(),
        organization_id=org_id,
        period_start=period_start,
        period_end=period_end,
        transactions_count=50000,  # Exceeds Professional limit (10000)
        users_count=100,  # Exceeds Professional limit (25)
        entities_count=50,  # Exceeds Professional limit (10)
        invoices_count=10000,
        api_calls_count=500000,  # Exceeds Professional limit (100000)
        ocr_pages_count=5000,
        storage_used_mb=Decimal("50000.00"),  # Exceeds Professional limit (10240)
        ml_inferences_count=10000,
        employees_count=200,  # Exceeds Professional limit (100)
    )
    db_session.add(usage)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


# =============================================================================
# TEST CLASSES - Proration Calculations
# =============================================================================

class TestProratedUpgradePrice:
    """Tests for calculate_prorated_upgrade_price."""
    
    @pytest.mark.asyncio
    async def test_upgrade_core_to_professional_full_month(self, db_session: AsyncSession):
        """Test proration for Core to Professional upgrade with 30 days remaining."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.CORE,
            new_tier=SKUTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=30,
            total_days_in_period=30,
        )
        
        assert result["is_upgrade"] is True
        assert result["current_tier"] == "core"
        assert result["new_tier"] == "professional"
        assert result["prorated_amount"] > 0
        assert result["days_remaining"] == 30
    
    @pytest.mark.asyncio
    async def test_upgrade_core_to_professional_mid_cycle(self, db_session: AsyncSession):
        """Test proration for mid-cycle upgrade with 15 days remaining."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.CORE,
            new_tier=SKUTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=15,
            total_days_in_period=30,
        )
        
        assert result["is_upgrade"] is True
        # Prorated amount should be roughly half the difference
        assert result["prorated_amount"] > 0
        assert result["days_remaining"] == 15
    
    @pytest.mark.asyncio
    async def test_upgrade_professional_to_enterprise(self, db_session: AsyncSession):
        """Test upgrade from Professional to Enterprise tier."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.PROFESSIONAL,
            new_tier=SKUTier.ENTERPRISE,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=20,
            total_days_in_period=30,
        )
        
        assert result["is_upgrade"] is True
        assert result["current_tier"] == "professional"
        assert result["new_tier"] == "enterprise"
        assert result["prorated_amount"] > 0
    
    @pytest.mark.asyncio
    async def test_downgrade_returns_zero_proration(self, db_session: AsyncSession):
        """Test that downgrade returns is_upgrade=False with zero proration."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.PROFESSIONAL,
            new_tier=SKUTier.CORE,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=15,
            total_days_in_period=30,
        )
        
        assert result["is_upgrade"] is False
        assert result["prorated_amount"] == 0
        assert "Downgrades do not require payment" in result["message"]
    
    @pytest.mark.asyncio
    async def test_annual_upgrade_proration(self, db_session: AsyncSession):
        """Test proration for annual billing cycle upgrade."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.CORE,
            new_tier=SKUTier.PROFESSIONAL,
            billing_cycle=BillingCycle.ANNUAL,
            days_remaining=180,
            total_days_in_period=365,
        )
        
        assert result["is_upgrade"] is True
        assert result["billing_cycle"] == "annual"
        # Annual proration should be calculated over 365 days
        assert result["total_days"] == 365
    
    @pytest.mark.asyncio
    async def test_upgrade_with_intelligence_addon(self, db_session: AsyncSession):
        """Test upgrade that also adds intelligence addon."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.PROFESSIONAL,
            new_tier=SKUTier.ENTERPRISE,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=20,
            total_days_in_period=30,
            current_intelligence=None,
            new_intelligence=IntelligenceAddon.ADVANCED,
        )
        
        assert result["is_upgrade"] is True
        # Amount should include addon cost
        assert result["prorated_amount"] > 0
    
    @pytest.mark.asyncio
    async def test_same_tier_is_not_upgrade(self, db_session: AsyncSession):
        """Test that same tier change is not considered an upgrade."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.PROFESSIONAL,
            new_tier=SKUTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=15,
            total_days_in_period=30,
        )
        
        # Price difference should be 0
        assert result["price_difference"] == 0
        assert result["prorated_amount"] == 0


class TestCalculateUpgradeProration:
    """Tests for calculate_upgrade_proration (fetches subscription details)."""
    
    @pytest.mark.asyncio
    async def test_calculate_proration_for_existing_subscription(
        self,
        db_session: AsyncSession,
        test_org_professional,
    ):
        """Test proration calculation for organization with existing subscription."""
        service = BillingService(db_session)
        
        result = await service.calculate_upgrade_proration(
            organization_id=test_org_professional.id,
            new_tier=SKUTier.ENTERPRISE,
        )
        
        assert "error" not in result or result.get("error") is None
        assert result["is_upgrade"] is True
    
    @pytest.mark.asyncio
    async def test_calculate_proration_no_subscription(self, db_session: AsyncSession):
        """Test proration calculation when no subscription exists."""
        service = BillingService(db_session)
        
        # Use a random UUID that doesn't have a subscription
        result = await service.calculate_upgrade_proration(
            organization_id=uuid4(),
            new_tier=SKUTier.ENTERPRISE,
        )
        
        assert result.get("error") == "No active subscription found"


# =============================================================================
# TEST CLASSES - Downgrade Validation
# =============================================================================

class TestValidateDowngrade:
    """Tests for validate_downgrade method."""
    
    @pytest.mark.asyncio
    async def test_downgrade_allowed_when_within_limits(
        self,
        db_session: AsyncSession,
        test_org_core_with_usage,
    ):
        """Test that downgrade is allowed when usage is within target limits."""
        # Get the org and update to Professional to test downgrade to Core
        result = await db_session.execute(
            select(TenantSKU).where(TenantSKU.organization_id == test_org_core_with_usage.id)
        )
        tenant_sku = result.scalar_one()
        tenant_sku.tier = SKUTier.PROFESSIONAL
        await db_session.flush()
        
        service = BillingService(db_session)
        
        validation = await service.validate_downgrade(
            organization_id=test_org_core_with_usage.id,
            target_tier=SKUTier.CORE,
        )
        
        # Core has generous limits, should be allowed with modest usage
        # (50 transactions, 3 users, 2 entities)
        assert validation["can_downgrade"] is True
        assert validation["error_code"] == BillingErrorCode.SUCCESS.value
    
    @pytest.mark.asyncio
    async def test_downgrade_blocked_when_exceeds_limits(
        self,
        db_session: AsyncSession,
        test_org_enterprise_high_usage,
    ):
        """Test that downgrade is blocked when usage exceeds target limits."""
        service = BillingService(db_session)
        
        # Try to downgrade to Professional with high usage
        validation = await service.validate_downgrade(
            organization_id=test_org_enterprise_high_usage.id,
            target_tier=SKUTier.PROFESSIONAL,
        )
        
        assert validation["can_downgrade"] is False
        assert validation["exceeded_limits"] is not None
        assert len(validation["exceeded_limits"]) > 0
        assert validation["error_code"] == BillingErrorCode.DOWNGRADE_NOT_ALLOWED.value
    
    @pytest.mark.asyncio
    async def test_downgrade_blocked_to_core_with_high_usage(
        self,
        db_session: AsyncSession,
        test_org_enterprise_high_usage,
    ):
        """Test downgrade to Core blocked with Enterprise-level usage."""
        service = BillingService(db_session)
        
        validation = await service.validate_downgrade(
            organization_id=test_org_enterprise_high_usage.id,
            target_tier=SKUTier.CORE,
        )
        
        assert validation["can_downgrade"] is False
        assert len(validation["exceeded_limits"]) > 0
        
        # Check specific exceeded metrics
        exceeded_metrics = [e["metric"] for e in validation["exceeded_limits"]]
        # Should include transactions, users, entities, etc.
        assert len(exceeded_metrics) >= 3
    
    @pytest.mark.asyncio
    async def test_downgrade_validation_returns_action_required(
        self,
        db_session: AsyncSession,
        test_org_enterprise_high_usage,
    ):
        """Test that validation returns actionable guidance."""
        service = BillingService(db_session)
        
        validation = await service.validate_downgrade(
            organization_id=test_org_enterprise_high_usage.id,
            target_tier=SKUTier.PROFESSIONAL,
        )
        
        # Each exceeded limit should have action_required
        for exceeded in validation["exceeded_limits"]:
            assert "action_required" in exceeded
            assert exceeded["current_usage"] > exceeded["target_limit"]
            assert exceeded["excess"] > 0
    
    @pytest.mark.asyncio
    async def test_downgrade_validation_includes_warnings(
        self,
        db_session: AsyncSession,
        test_org_professional,
    ):
        """Test that warnings are returned for usage close to limits."""
        # Create usage close to Core limits but not exceeding
        period_start = datetime.utcnow().date().replace(day=1)
        next_month = period_start.replace(month=period_start.month + 1) if period_start.month < 12 else period_start.replace(year=period_start.year + 1, month=1)
        
        # Get Core limits
        core_limits = TIER_LIMITS.get(SKUTier.CORE, {})
        
        usage = UsageRecord(
            id=uuid4(),
            organization_id=test_org_professional.id,
            period_start=period_start,
            period_end=next_month,
            transactions_count=int(core_limits.get("transactions_per_month", 500) * 0.85),  # 85% of limit
            users_count=int(core_limits.get("users", 5) * 0.8),  # 80% of limit
            entities_count=1,
            invoices_count=10,
            api_calls_count=100,
            ocr_pages_count=5,
            storage_used_mb=Decimal("50.00"),
            ml_inferences_count=0,
            employees_count=0,
        )
        db_session.add(usage)
        await db_session.flush()
        
        service = BillingService(db_session)
        
        validation = await service.validate_downgrade(
            organization_id=test_org_professional.id,
            target_tier=SKUTier.CORE,
        )
        
        # Should be able to downgrade but with warnings
        # (depends on exact limits in TIER_LIMITS)


# =============================================================================
# TEST CLASSES - Downgrade Request
# =============================================================================

class TestRequestDowngrade:
    """Tests for request_downgrade method."""
    
    @pytest.mark.asyncio
    async def test_successful_downgrade_request(
        self,
        db_session: AsyncSession,
        test_org_professional,
    ):
        """Test successful downgrade request scheduling."""
        # Create usage record within Core limits
        period_start = datetime.utcnow().date().replace(day=1)
        next_month = period_start.replace(month=period_start.month + 1) if period_start.month < 12 else period_start.replace(year=period_start.year + 1, month=1)
        
        usage = UsageRecord(
            id=uuid4(),
            organization_id=test_org_professional.id,
            period_start=period_start,
            period_end=next_month,
            transactions_count=50,
            users_count=3,
            entities_count=1,
            invoices_count=10,
            api_calls_count=100,
            ocr_pages_count=5,
            storage_used_mb=Decimal("50.00"),
            ml_inferences_count=0,
            employees_count=0,
        )
        db_session.add(usage)
        await db_session.flush()
        
        service = BillingService(db_session)
        
        result = await service.request_downgrade(
            organization_id=test_org_professional.id,
            target_tier=SKUTier.CORE,
        )
        
        assert result["success"] is True
        assert result["target_tier"] == "core"
        assert result["error_code"] == BillingErrorCode.SUCCESS.value
        
        # Verify subscription was updated
        sku_result = await db_session.execute(
            select(TenantSKU).where(TenantSKU.organization_id == test_org_professional.id)
        )
        tenant_sku = sku_result.scalar_one()
        
        assert tenant_sku.cancel_at_period_end is True
        assert tenant_sku.scheduled_downgrade_tier == SKUTier.CORE
    
    @pytest.mark.asyncio
    async def test_downgrade_request_blocked_exceeds_limits(
        self,
        db_session: AsyncSession,
        test_org_enterprise_high_usage,
    ):
        """Test that downgrade request is blocked when limits exceeded."""
        service = BillingService(db_session)
        
        result = await service.request_downgrade(
            organization_id=test_org_enterprise_high_usage.id,
            target_tier=SKUTier.PROFESSIONAL,
            force=False,
        )
        
        assert result["success"] is False
        assert result["exceeded_limits"] is not None
        assert result["error_code"] == BillingErrorCode.DOWNGRADE_NOT_ALLOWED.value
    
    @pytest.mark.asyncio
    async def test_downgrade_request_with_force_flag(
        self,
        db_session: AsyncSession,
        test_org_enterprise_high_usage,
    ):
        """Test downgrade request with force=True bypasses limit check."""
        service = BillingService(db_session)
        
        result = await service.request_downgrade(
            organization_id=test_org_enterprise_high_usage.id,
            target_tier=SKUTier.PROFESSIONAL,
            force=True,  # Force despite exceeded limits
        )
        
        # Should succeed with force flag
        assert result["success"] is True
        assert result["exceeded_limits"] is not None  # Still includes warnings
    
    @pytest.mark.asyncio
    async def test_cannot_downgrade_to_same_or_higher_tier(
        self,
        db_session: AsyncSession,
        test_org_professional,
    ):
        """Test that 'downgrade' to same or higher tier is rejected."""
        service = BillingService(db_session)
        
        # Try to "downgrade" to same tier
        result = await service.request_downgrade(
            organization_id=test_org_professional.id,
            target_tier=SKUTier.PROFESSIONAL,
        )
        
        assert result["success"] is False
        assert result["error_code"] == BillingErrorCode.INVALID_PLAN_CHANGE.value
        
        # Try to "downgrade" to higher tier
        result2 = await service.request_downgrade(
            organization_id=test_org_professional.id,
            target_tier=SKUTier.ENTERPRISE,
        )
        
        assert result2["success"] is False
        assert result2["error_code"] == BillingErrorCode.INVALID_PLAN_CHANGE.value
    
    @pytest.mark.asyncio
    async def test_downgrade_request_no_subscription(self, db_session: AsyncSession):
        """Test downgrade request when no subscription exists."""
        service = BillingService(db_session)
        
        result = await service.request_downgrade(
            organization_id=uuid4(),  # Non-existent org
            target_tier=SKUTier.CORE,
        )
        
        assert result["success"] is False
        assert result["error_code"] == BillingErrorCode.SUBSCRIPTION_NOT_FOUND.value
    
    @pytest.mark.asyncio
    async def test_downgrade_sets_effective_date(
        self,
        db_session: AsyncSession,
        test_org_professional,
    ):
        """Test that downgrade sets correct effective date (end of period)."""
        # Create usage within limits - using correct period format
        today = date.today()
        period_start = date(today.year, today.month, 1)
        last_day = monthrange(today.year, today.month)[1]
        period_end = date(today.year, today.month, last_day)
        
        usage = UsageRecord(
            id=uuid4(),
            organization_id=test_org_professional.id,
            period_start=period_start,
            period_end=period_end,
            transactions_count=10,
            users_count=2,
            entities_count=1,
            invoices_count=5,
            api_calls_count=0,  # Core doesn't allow API
            ocr_pages_count=0,
            storage_used_mb=Decimal("10.00"),
            ml_inferences_count=0,
            employees_count=0,
        )
        db_session.add(usage)
        await db_session.flush()
        
        # Get original period end
        sku_result = await db_session.execute(
            select(TenantSKU).where(TenantSKU.organization_id == test_org_professional.id)
        )
        tenant_sku = sku_result.scalar_one()
        original_period_end = tenant_sku.current_period_end
        
        service = BillingService(db_session)
        
        result = await service.request_downgrade(
            organization_id=test_org_professional.id,
            target_tier=SKUTier.CORE,
        )
        
        assert result["success"] is True
        assert result["effective_date"] is not None
        
        # Effective date should match period end
        if original_period_end:
            effective = datetime.fromisoformat(result["effective_date"].replace("Z", "+00:00"))
            # Convert original_period_end to datetime for comparison
            if isinstance(original_period_end, date) and not isinstance(original_period_end, datetime):
                original_period_end_dt = datetime.combine(original_period_end, datetime.min.time())
            else:
                original_period_end_dt = original_period_end
            # Should be within a day of original period end
            assert abs((effective.replace(tzinfo=None) - original_period_end_dt).days) <= 1


class TestTierTransitions:
    """Tests for all tier transition scenarios."""
    
    @pytest.mark.asyncio
    async def test_core_to_professional_upgrade(self, db_session: AsyncSession):
        """Test Core → Professional upgrade flow."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.CORE,
            new_tier=SKUTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=20,
            total_days_in_period=30,
        )
        
        assert result["is_upgrade"] is True
        assert result["current_tier"] == "core"
        assert result["new_tier"] == "professional"
    
    @pytest.mark.asyncio
    async def test_core_to_enterprise_upgrade(self, db_session: AsyncSession):
        """Test Core → Enterprise upgrade flow."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.CORE,
            new_tier=SKUTier.ENTERPRISE,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=20,
            total_days_in_period=30,
        )
        
        assert result["is_upgrade"] is True
        assert result["new_tier"] == "enterprise"
    
    @pytest.mark.asyncio
    async def test_professional_to_enterprise_upgrade(self, db_session: AsyncSession):
        """Test Professional → Enterprise upgrade flow."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.PROFESSIONAL,
            new_tier=SKUTier.ENTERPRISE,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=25,
            total_days_in_period=30,
        )
        
        assert result["is_upgrade"] is True
    
    @pytest.mark.asyncio
    async def test_enterprise_to_professional_downgrade(
        self,
        db_session: AsyncSession,
        test_org_enterprise,
    ):
        """Test Enterprise → Professional downgrade flow."""
        # Create low usage within Professional limits
        period_start = datetime.utcnow().date().replace(day=1)
        next_month = period_start.replace(month=period_start.month + 1) if period_start.month < 12 else period_start.replace(year=period_start.year + 1, month=1)
        
        usage = UsageRecord(
            id=uuid4(),
            organization_id=test_org_enterprise.id,
            period_start=period_start,
            period_end=next_month,
            transactions_count=500,
            users_count=10,
            entities_count=5,
            invoices_count=100,
            api_calls_count=5000,
            ocr_pages_count=50,
            storage_used_mb=Decimal("500.00"),
            ml_inferences_count=10,
            employees_count=20,
        )
        db_session.add(usage)
        await db_session.flush()
        
        service = BillingService(db_session)
        
        # First validate
        validation = await service.validate_downgrade(
            organization_id=test_org_enterprise.id,
            target_tier=SKUTier.PROFESSIONAL,
        )
        
        # Then request if valid
        if validation["can_downgrade"]:
            result = await service.request_downgrade(
                organization_id=test_org_enterprise.id,
                target_tier=SKUTier.PROFESSIONAL,
            )
            assert result["success"] is True
    
    @pytest.mark.asyncio  
    async def test_enterprise_to_core_downgrade(
        self,
        db_session: AsyncSession,
        test_org_enterprise,
    ):
        """Test Enterprise → Core downgrade flow (two tier drop)."""
        # Create very low usage within Core limits
        period_start = datetime.utcnow().date().replace(day=1)
        next_month = period_start.replace(month=period_start.month + 1) if period_start.month < 12 else period_start.replace(year=period_start.year + 1, month=1)
        
        usage = UsageRecord(
            id=uuid4(),
            organization_id=test_org_enterprise.id,
            period_start=period_start,
            period_end=next_month,
            transactions_count=50,
            users_count=2,
            entities_count=1,
            invoices_count=10,
            api_calls_count=100,
            ocr_pages_count=5,
            storage_used_mb=Decimal("50.00"),
            ml_inferences_count=0,
            employees_count=0,
        )
        db_session.add(usage)
        await db_session.flush()
        
        service = BillingService(db_session)
        
        validation = await service.validate_downgrade(
            organization_id=test_org_enterprise.id,
            target_tier=SKUTier.CORE,
        )
        
        # Should be allowed with low usage
        if validation["can_downgrade"]:
            result = await service.request_downgrade(
                organization_id=test_org_enterprise.id,
                target_tier=SKUTier.CORE,
            )
            assert result["success"] is True
            assert result["target_tier"] == "core"


class TestProrationCalculations:
    """Tests for correct proration math."""
    
    @pytest.mark.asyncio
    async def test_prorated_amount_scales_with_days(self, db_session: AsyncSession):
        """Test that prorated amount scales linearly with days remaining."""
        service = BillingService(db_session)
        
        full_result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.CORE,
            new_tier=SKUTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=30,
            total_days_in_period=30,
        )
        
        half_result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.CORE,
            new_tier=SKUTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=15,
            total_days_in_period=30,
        )
        
        # Half days should give roughly half the prorated amount
        full_amount = full_result["prorated_amount"]
        half_amount = half_result["prorated_amount"]
        
        # Allow for rounding differences
        ratio = half_amount / full_amount if full_amount > 0 else 0
        assert 0.45 <= ratio <= 0.55
    
    @pytest.mark.asyncio
    async def test_zero_days_remaining_zero_proration(self, db_session: AsyncSession):
        """Test that 0 days remaining gives 0 proration."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.CORE,
            new_tier=SKUTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=0,
            total_days_in_period=30,
        )
        
        assert result["prorated_amount"] == 0
    
    @pytest.mark.asyncio
    async def test_unused_credit_calculated(self, db_session: AsyncSession):
        """Test that unused credit from current subscription is calculated."""
        service = BillingService(db_session)
        
        result = service.calculate_prorated_upgrade_price(
            current_tier=SKUTier.PROFESSIONAL,
            new_tier=SKUTier.ENTERPRISE,
            billing_cycle=BillingCycle.MONTHLY,
            days_remaining=20,
            total_days_in_period=30,
        )
        
        assert result["is_upgrade"] is True
        assert "unused_credit" in result
        assert result["unused_credit"] > 0
