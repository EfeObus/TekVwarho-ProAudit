"""
Tests for Concurrent Usage Recording (#51)

This module contains comprehensive tests for concurrent usage recording
to ensure data integrity under high-concurrency scenarios.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.organization import Organization
from app.models.sku import (
    TenantSKU,
    SKUTier,
    BillingCycle,
    UsageRecord,
    UsageEvent,
    UsageMetricType,
)
from app.services.metering_service import MeteringService


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
async def metering_org(db_session: AsyncSession):
    """Create organization for metering tests."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Metering Test Org",
        slug=f"test-{org_id.hex[:8]}",
        
    )
    db_session.add(org)
    
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.PROFESSIONAL,
        billing_cycle=BillingCycle.MONTHLY,
        
        is_trial=False,
        current_period_start=datetime.utcnow() - timedelta(days=10),
        current_period_end=datetime.utcnow() + timedelta(days=20),
        price_ngn=2500000,
    )
    db_session.add(tenant_sku)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


@pytest.fixture
async def multiple_orgs(db_session: AsyncSession):
    """Create multiple organizations for concurrent testing."""
    orgs = []
    
    for i in range(5):
        org_id = uuid4()
        org = Organization(
            id=org_id,
            name=f"Concurrent Test Org {i}",
            email=f"concurrent{i}@example.com",
            
        )
        db_session.add(org)
        
        tenant_sku = TenantSKU(
            id=uuid4(),
            organization_id=org_id,
            tier=SKUTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            
            is_trial=False,
            current_period_start=datetime.utcnow() - timedelta(days=5),
            current_period_end=datetime.utcnow() + timedelta(days=25),
            price_ngn=2500000,
        )
        db_session.add(tenant_sku)
        orgs.append(org)
    
    await db_session.flush()
    for org in orgs:
        await db_session.refresh(org)
    
    return orgs


# =============================================================================
# TEST CLASSES - Basic Concurrency
# =============================================================================

class TestConcurrentRecordEvent:
    """Tests for concurrent record_event calls."""
    
    @pytest.mark.asyncio
    async def test_concurrent_transaction_recording(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test concurrent recording of transactions."""
        service = MeteringService(db_session)
        num_concurrent = 10
        
        # Create concurrent record_event calls
        tasks = [
            service.record_event(
                organization_id=metering_org.id,
                metric_type=UsageMetricType.TRANSACTIONS,
                quantity=1,
                resource_type="transaction",
                resource_id=f"TXN_{i}_{uuid4().hex[:8]}",
            )
            for i in range(num_concurrent)
        ]
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check no exceptions
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Got exceptions: {exceptions}"
        
        # Check all events were recorded
        successful = [r for r in results if isinstance(r, UsageEvent)]
        assert len(successful) == num_concurrent
    
    @pytest.mark.asyncio
    async def test_concurrent_api_call_recording(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test concurrent recording of API calls."""
        service = MeteringService(db_session)
        num_concurrent = 20
        
        tasks = [
            service.record_api_call(
                organization_id=metering_org.id,
                user_id=None,
                endpoint=f"/api/v1/endpoint{i}",
            )
            for i in range(num_concurrent)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Got exceptions: {exceptions}"
    
    @pytest.mark.asyncio
    async def test_concurrent_mixed_metrics(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test concurrent recording of different metric types."""
        service = MeteringService(db_session)
        
        tasks = []
        
        # Add transactions
        for i in range(5):
            tasks.append(service.record_transaction(
                organization_id=metering_org.id,
                entity_id=uuid4(),
                transaction_id=f"TXN_{i}",
            ))
        
        # Add invoices
        for i in range(5):
            tasks.append(service.record_invoice(
                organization_id=metering_org.id,
                entity_id=uuid4(),
                invoice_id=f"INV_{i}",
            ))
        
        # Add OCR pages
        for i in range(3):
            tasks.append(service.record_ocr_pages(
                organization_id=metering_org.id,
                pages=5,
                document_id=f"DOC_{i}",
            ))
        
        # Add ML inferences
        for i in range(3):
            tasks.append(service.record_ml_inference(
                organization_id=metering_org.id,
                model_type=f"model_v{i}",
            ))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0


class TestConcurrentUsageAggregation:
    """Tests for concurrent usage aggregation consistency."""
    
    @pytest.mark.asyncio
    async def test_usage_count_accuracy_after_concurrent_writes(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test that usage count is accurate after concurrent writes."""
        service = MeteringService(db_session)
        num_events = 25
        
        # Record events concurrently
        tasks = [
            service.record_event(
                organization_id=metering_org.id,
                metric_type=UsageMetricType.TRANSACTIONS,
                quantity=1,
            )
            for _ in range(num_events)
        ]
        
        await asyncio.gather(*tasks)
        await db_session.commit()
        
        # Check the aggregated count
        current_usage = await service.get_current_usage(
            organization_id=metering_org.id,
            metric=UsageMetricType.TRANSACTIONS,
        )
        
        # Usage should match number of events
        assert current_usage == num_events
    
    @pytest.mark.asyncio
    async def test_batch_quantity_recording(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test concurrent recording with varying quantities."""
        service = MeteringService(db_session)
        
        quantities = [1, 5, 10, 2, 3]  # Total = 21
        expected_total = sum(quantities)
        
        tasks = [
            service.record_event(
                organization_id=metering_org.id,
                metric_type=UsageMetricType.OCR_PAGES,
                quantity=q,
            )
            for q in quantities
        ]
        
        await asyncio.gather(*tasks)
        await db_session.commit()
        
        current_usage = await service.get_current_usage(
            organization_id=metering_org.id,
            metric=UsageMetricType.OCR_PAGES,
        )
        
        assert current_usage == expected_total


class TestConcurrentMultipleOrganizations:
    """Tests for concurrent recording across multiple organizations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_recording_different_orgs(
        self,
        db_session: AsyncSession,
        multiple_orgs,
    ):
        """Test concurrent recording across different organizations."""
        service = MeteringService(db_session)
        
        tasks = []
        for org in multiple_orgs:
            # Each org records 5 transactions concurrently
            for i in range(5):
                tasks.append(service.record_transaction(
                    organization_id=org.id,
                    entity_id=uuid4(),
                    transaction_id=f"TXN_{org.id}_{i}",
                ))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0
        
        # Verify each org has correct count
        await db_session.commit()
        
        for org in multiple_orgs:
            usage = await service.get_current_usage(
                organization_id=org.id,
                metric=UsageMetricType.TRANSACTIONS,
            )
            assert usage == 5, f"Org {org.id} has {usage} transactions, expected 5"
    
    @pytest.mark.asyncio
    async def test_organization_isolation(
        self,
        db_session: AsyncSession,
        multiple_orgs,
    ):
        """Test that concurrent recording is isolated between organizations."""
        service = MeteringService(db_session)
        
        # Record different amounts per organization
        org_quantities = {
            multiple_orgs[0].id: 10,
            multiple_orgs[1].id: 20,
            multiple_orgs[2].id: 15,
            multiple_orgs[3].id: 5,
            multiple_orgs[4].id: 8,
        }
        
        tasks = []
        for org_id, qty in org_quantities.items():
            for _ in range(qty):
                tasks.append(service.record_event(
                    organization_id=org_id,
                    metric_type=UsageMetricType.INVOICES,
                    quantity=1,
                ))
        
        await asyncio.gather(*tasks)
        await db_session.commit()
        
        # Verify isolation
        for org in multiple_orgs:
            usage = await service.get_current_usage(
                organization_id=org.id,
                metric=UsageMetricType.INVOICES,
            )
            expected = org_quantities[org.id]
            assert usage == expected, f"Org {org.id}: got {usage}, expected {expected}"


class TestConcurrentStorageUpdates:
    """Tests for concurrent storage usage updates (absolute values)."""
    
    @pytest.mark.asyncio
    async def test_concurrent_storage_updates(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test concurrent storage updates (should use last value)."""
        service = MeteringService(db_session)
        
        # Multiple concurrent storage updates
        tasks = [
            service.update_storage_usage(metering_org.id, Decimal("100.00")),
            service.update_storage_usage(metering_org.id, Decimal("200.00")),
            service.update_storage_usage(metering_org.id, Decimal("150.00")),
        ]
        
        await asyncio.gather(*tasks)
        await db_session.commit()
        
        # Storage is absolute, not cumulative - verify record exists
        usage = await service.get_current_usage(
            organization_id=metering_org.id,
            metric=UsageMetricType.STORAGE_MB,
        )
        
        # Should be one of the values (last write wins for absolute)
        assert usage in [100, 150, 200]
    
    @pytest.mark.asyncio
    async def test_concurrent_user_count_updates(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test concurrent user count updates (absolute values)."""
        service = MeteringService(db_session)
        
        final_count = 15
        
        # Multiple updates, last should win
        tasks = [
            service.update_user_count(metering_org.id, 5),
            service.update_user_count(metering_org.id, 10),
            service.update_user_count(metering_org.id, final_count),
        ]
        
        await asyncio.gather(*tasks)
        await db_session.commit()
        
        usage = await service.get_current_usage(
            organization_id=metering_org.id,
            metric=UsageMetricType.USERS,
        )
        
        # Should be one of the values
        assert usage in [5, 10, 15]


class TestConcurrentGetUsage:
    """Tests for concurrent get_usage operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_get_current_usage(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test concurrent read operations."""
        service = MeteringService(db_session)
        
        # First record some usage
        for _ in range(5):
            await service.record_transaction(
                organization_id=metering_org.id,
                entity_id=uuid4(),
            )
        await db_session.commit()
        
        # Concurrent reads
        tasks = [
            service.get_current_usage(metering_org.id, UsageMetricType.TRANSACTIONS)
            for _ in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All reads should return same value
        assert all(r == 5 for r in results)
    
    @pytest.mark.asyncio
    async def test_concurrent_get_all_usage(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test concurrent get_all_current_usage calls."""
        service = MeteringService(db_session)
        
        # Record diverse usage
        await service.record_transaction(metering_org.id, uuid4())
        await service.record_invoice(metering_org.id, uuid4())
        await service.record_api_call(metering_org.id)
        await db_session.commit()
        
        # Concurrent reads
        tasks = [
            service.get_all_current_usage(metering_org.id)
            for _ in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should return consistent dict
        first_result = results[0]
        for r in results[1:]:
            assert r == first_result


class TestConcurrentReadWrite:
    """Tests for concurrent read and write operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_reads_during_writes(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test reading while writing concurrently."""
        service = MeteringService(db_session)
        
        async def write_events():
            for _ in range(5):
                await service.record_event(
                    organization_id=metering_org.id,
                    metric_type=UsageMetricType.API_CALLS,
                    quantity=1,
                )
                await asyncio.sleep(0.01)  # Small delay between writes
        
        async def read_usage():
            results = []
            for _ in range(10):
                usage = await service.get_current_usage(
                    metering_org.id,
                    UsageMetricType.API_CALLS,
                )
                results.append(usage)
                await asyncio.sleep(0.005)
            return results
        
        # Run both concurrently
        write_task = asyncio.create_task(write_events())
        read_task = asyncio.create_task(read_usage())
        
        await asyncio.gather(write_task, read_task)
        
        # Reads should not fail during writes
        read_results = read_task.result()
        assert len(read_results) == 10


class TestConcurrentHighVolume:
    """Tests for high-volume concurrent operations."""
    
    @pytest.mark.asyncio
    async def test_high_volume_concurrent_recording(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test recording 100 events concurrently."""
        service = MeteringService(db_session)
        num_events = 100
        
        tasks = [
            service.record_event(
                organization_id=metering_org.id,
                metric_type=UsageMetricType.API_CALLS,
                quantity=1,
            )
            for _ in range(num_events)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes and failures
        successes = [r for r in results if isinstance(r, UsageEvent)]
        failures = [r for r in results if isinstance(r, Exception)]
        
        # All should succeed
        assert len(failures) == 0, f"Got {len(failures)} failures: {failures[:3]}"
        assert len(successes) == num_events
    
    @pytest.mark.asyncio
    async def test_burst_traffic_handling(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test handling burst traffic pattern."""
        service = MeteringService(db_session)
        
        # Simulate burst: 50 events in rapid succession
        burst_size = 50
        
        async def burst_record():
            tasks = [
                service.record_event(
                    organization_id=metering_org.id,
                    metric_type=UsageMetricType.TRANSACTIONS,
                    quantity=1,
                )
                for _ in range(burst_size)
            ]
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        # Execute burst
        results = await burst_record()
        
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(failures) == 0
        
        await db_session.commit()
        
        # Verify count
        usage = await service.get_current_usage(
            metering_org.id,
            UsageMetricType.TRANSACTIONS,
        )
        assert usage == burst_size


class TestConcurrentEventMetadata:
    """Tests for concurrent events with metadata."""
    
    @pytest.mark.asyncio
    async def test_concurrent_events_with_different_metadata(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test concurrent events with unique metadata."""
        service = MeteringService(db_session)
        
        tasks = [
            service.record_event(
                organization_id=metering_org.id,
                metric_type=UsageMetricType.ML_INFERENCES,
                quantity=1,
                metadata={"model": f"model_v{i}", "batch_id": str(uuid4())},
            )
            for i in range(20)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0
        
        # Verify all events have unique resource_ids/metadata
        events = [r for r in results if isinstance(r, UsageEvent)]
        assert len(events) == 20
    
    @pytest.mark.asyncio
    async def test_concurrent_events_with_resource_ids(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test concurrent events with unique resource IDs."""
        service = MeteringService(db_session)
        
        resource_ids = [f"RESOURCE_{uuid4().hex[:8]}" for _ in range(30)]
        
        tasks = [
            service.record_event(
                organization_id=metering_org.id,
                metric_type=UsageMetricType.TRANSACTIONS,
                quantity=1,
                resource_type="test_resource",
                resource_id=rid,
            )
            for rid in resource_ids
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successes = [r for r in results if isinstance(r, UsageEvent)]
        assert len(successes) == 30
        
        # Verify all resource IDs are recorded
        recorded_ids = {e.resource_id for e in successes}
        assert recorded_ids == set(resource_ids)


class TestConcurrentErrorScenarios:
    """Tests for error handling in concurrent scenarios."""
    
    @pytest.mark.asyncio
    async def test_invalid_org_in_concurrent_batch(
        self,
        db_session: AsyncSession,
        metering_org,
    ):
        """Test handling of invalid org ID mixed with valid ones."""
        service = MeteringService(db_session)
        
        invalid_org_id = uuid4()  # Non-existent
        
        tasks = [
            # Valid org
            service.record_event(
                organization_id=metering_org.id,
                metric_type=UsageMetricType.TRANSACTIONS,
                quantity=1,
            ),
            # Invalid org - may or may not fail depending on FK constraints
            service.record_event(
                organization_id=invalid_org_id,
                metric_type=UsageMetricType.TRANSACTIONS,
                quantity=1,
            ),
            # Valid org
            service.record_event(
                organization_id=metering_org.id,
                metric_type=UsageMetricType.TRANSACTIONS,
                quantity=1,
            ),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # At least the valid org events should succeed
        successes = [r for r in results if isinstance(r, UsageEvent)]
        # May have 2 or 3 successes depending on FK enforcement
        assert len(successes) >= 2
