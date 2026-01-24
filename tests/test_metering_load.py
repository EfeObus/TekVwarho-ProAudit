"""
Load Tests for Metering Service (#48)

This module contains load and performance tests for the metering service,
testing throughput under high-load scenarios using pytest-benchmark.
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
async def load_test_org(db_session: AsyncSession):
    """Create organization for load testing."""
    org_id = uuid4()
    
    org = Organization(
        id=org_id,
        name="Load Test Organization",
        slug=f"test-{org_id.hex[:8]}",
        
    )
    db_session.add(org)
    
    tenant_sku = TenantSKU(
        id=uuid4(),
        organization_id=org_id,
        tier=SKUTier.ENTERPRISE,  # Enterprise for high limits
        billing_cycle=BillingCycle.MONTHLY,
        
        is_trial=False,
        current_period_start=datetime.utcnow() - timedelta(days=5),
        current_period_end=datetime.utcnow() + timedelta(days=25),
        price_ngn=7500000,
    )
    db_session.add(tenant_sku)
    
    await db_session.flush()
    await db_session.refresh(org)
    
    return org


@pytest.fixture
async def multiple_load_test_orgs(db_session: AsyncSession):
    """Create multiple organizations for multi-tenant load testing."""
    orgs = []
    
    for i in range(10):
        org_id = uuid4()
        org = Organization(
            id=org_id,
            name=f"Load Test Org {i}",
            email=f"loadtest{i}@example.com",
            
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
# HELPER FUNCTIONS
# =============================================================================

async def record_n_events(
    service: MeteringService,
    org_id,
    metric_type: UsageMetricType,
    count: int,
) -> float:
    """Record N events and return total time in seconds."""
    import time
    
    start = time.perf_counter()
    
    for i in range(count):
        await service.record_event(
            organization_id=org_id,
            metric_type=metric_type,
            quantity=1,
            resource_id=f"LOAD_TEST_{i}",
        )
    
    end = time.perf_counter()
    return end - start


async def record_n_events_concurrent(
    service: MeteringService,
    org_id,
    metric_type: UsageMetricType,
    count: int,
    batch_size: int = 50,
) -> float:
    """Record N events concurrently in batches."""
    import time
    
    start = time.perf_counter()
    
    for batch_start in range(0, count, batch_size):
        batch_end = min(batch_start + batch_size, count)
        tasks = [
            service.record_event(
                organization_id=org_id,
                metric_type=metric_type,
                quantity=1,
                resource_id=f"LOAD_TEST_{i}",
            )
            for i in range(batch_start, batch_end)
        ]
        await asyncio.gather(*tasks)
    
    end = time.perf_counter()
    return end - start


# =============================================================================
# THROUGHPUT TESTS
# =============================================================================

class TestRecordEventThroughput:
    """Tests for record_event throughput."""
    
    @pytest.mark.asyncio
    async def test_sequential_event_recording_100(
        self,
        db_session: AsyncSession,
        load_test_org,
    ):
        """Test sequential recording of 100 events."""
        service = MeteringService(db_session)
        count = 100
        
        duration = await record_n_events(
            service,
            load_test_org.id,
            UsageMetricType.API_CALLS,
            count,
        )
        
        events_per_second = count / duration
        
        print(f"\n--- Sequential Recording: 100 events ---")
        print(f"Duration: {duration:.3f}s")
        print(f"Throughput: {events_per_second:.1f} events/second")
        
        # Should handle at least 50 events/second sequentially
        assert events_per_second >= 50, f"Too slow: {events_per_second:.1f} events/s"
    
    @pytest.mark.asyncio
    async def test_concurrent_event_recording_100(
        self,
        db_session: AsyncSession,
        load_test_org,
    ):
        """Test concurrent recording of 100 events."""
        service = MeteringService(db_session)
        count = 100
        
        duration = await record_n_events_concurrent(
            service,
            load_test_org.id,
            UsageMetricType.API_CALLS,
            count,
            batch_size=50,
        )
        
        events_per_second = count / duration
        
        print(f"\n--- Concurrent Recording: 100 events ---")
        print(f"Duration: {duration:.3f}s")
        print(f"Throughput: {events_per_second:.1f} events/second")
        
        # Concurrent should be faster than sequential
        assert events_per_second >= 100, f"Too slow: {events_per_second:.1f} events/s"
    
    @pytest.mark.asyncio
    async def test_high_volume_500_events(
        self,
        db_session: AsyncSession,
        load_test_org,
    ):
        """Test high-volume recording of 500 events."""
        service = MeteringService(db_session)
        count = 500
        
        duration = await record_n_events_concurrent(
            service,
            load_test_org.id,
            UsageMetricType.TRANSACTIONS,
            count,
            batch_size=100,
        )
        
        events_per_second = count / duration
        
        print(f"\n--- High Volume: 500 events ---")
        print(f"Duration: {duration:.3f}s")
        print(f"Throughput: {events_per_second:.1f} events/second")
        
        # Should maintain reasonable throughput
        assert events_per_second >= 50


class TestGetUsageThroughput:
    """Tests for get_current_usage throughput."""
    
    @pytest.mark.asyncio
    async def test_sequential_usage_reads_100(
        self,
        db_session: AsyncSession,
        load_test_org,
    ):
        """Test 100 sequential usage reads."""
        service = MeteringService(db_session)
        
        # First create some usage
        for _ in range(10):
            await service.record_event(
                organization_id=load_test_org.id,
                metric_type=UsageMetricType.TRANSACTIONS,
                quantity=1,
            )
        await db_session.commit()
        
        import time
        count = 100
        
        start = time.perf_counter()
        for _ in range(count):
            await service.get_current_usage(
                load_test_org.id,
                UsageMetricType.TRANSACTIONS,
            )
        end = time.perf_counter()
        
        duration = end - start
        reads_per_second = count / duration
        
        print(f"\n--- Sequential Reads: 100 reads ---")
        print(f"Duration: {duration:.3f}s")
        print(f"Throughput: {reads_per_second:.1f} reads/second")
        
        # Reads should be fast
        assert reads_per_second >= 100
    
    @pytest.mark.asyncio
    async def test_concurrent_usage_reads_100(
        self,
        db_session: AsyncSession,
        load_test_org,
    ):
        """Test 100 concurrent usage reads."""
        service = MeteringService(db_session)
        
        # Create usage
        await service.record_event(
            organization_id=load_test_org.id,
            metric_type=UsageMetricType.INVOICES,
            quantity=10,
        )
        await db_session.commit()
        
        import time
        count = 100
        
        start = time.perf_counter()
        tasks = [
            service.get_current_usage(
                load_test_org.id,
                UsageMetricType.INVOICES,
            )
            for _ in range(count)
        ]
        results = await asyncio.gather(*tasks)
        end = time.perf_counter()
        
        duration = end - start
        reads_per_second = count / duration
        
        print(f"\n--- Concurrent Reads: 100 reads ---")
        print(f"Duration: {duration:.3f}s")
        print(f"Throughput: {reads_per_second:.1f} reads/second")
        
        # All results should be consistent
        assert all(r == results[0] for r in results)
        assert reads_per_second >= 200


class TestGetAllUsageThroughput:
    """Tests for get_all_current_usage throughput."""
    
    @pytest.mark.asyncio
    async def test_get_all_usage_performance(
        self,
        db_session: AsyncSession,
        load_test_org,
    ):
        """Test performance of get_all_current_usage."""
        service = MeteringService(db_session)
        
        # Create diverse usage
        await service.record_transaction(load_test_org.id, uuid4())
        await service.record_invoice(load_test_org.id, uuid4())
        await service.record_api_call(load_test_org.id)
        await service.update_storage_usage(load_test_org.id, Decimal("100.0"))
        await db_session.commit()
        
        import time
        count = 50
        
        start = time.perf_counter()
        for _ in range(count):
            await service.get_all_current_usage(load_test_org.id)
        end = time.perf_counter()
        
        duration = end - start
        calls_per_second = count / duration
        
        print(f"\n--- Get All Usage: 50 calls ---")
        print(f"Duration: {duration:.3f}s")
        print(f"Throughput: {calls_per_second:.1f} calls/second")
        
        # Should handle reasonable throughput
        assert calls_per_second >= 20


class TestMultiTenantLoad:
    """Tests for multi-tenant load scenarios."""
    
    @pytest.mark.asyncio
    async def test_concurrent_multi_tenant_recording(
        self,
        db_session: AsyncSession,
        multiple_load_test_orgs,
    ):
        """Test concurrent recording across multiple tenants."""
        service = MeteringService(db_session)
        
        import time
        events_per_org = 20
        
        start = time.perf_counter()
        
        tasks = []
        for org in multiple_load_test_orgs:
            for _ in range(events_per_org):
                tasks.append(
                    service.record_event(
                        organization_id=org.id,
                        metric_type=UsageMetricType.TRANSACTIONS,
                        quantity=1,
                    )
                )
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end = time.perf_counter()
        
        duration = end - start
        total_events = len(multiple_load_test_orgs) * events_per_org
        events_per_second = total_events / duration
        
        print(f"\n--- Multi-Tenant: {total_events} events across {len(multiple_load_test_orgs)} orgs ---")
        print(f"Duration: {duration:.3f}s")
        print(f"Throughput: {events_per_second:.1f} events/second")
        
        # Check for errors
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Got {len(errors)} errors: {errors[:3]}"
    
    @pytest.mark.asyncio
    async def test_multi_tenant_isolation_under_load(
        self,
        db_session: AsyncSession,
        multiple_load_test_orgs,
    ):
        """Test that tenant isolation is maintained under load."""
        service = MeteringService(db_session)
        
        # Different event counts per org
        org_counts = {
            multiple_load_test_orgs[i].id: (i + 1) * 5
            for i in range(len(multiple_load_test_orgs))
        }
        
        tasks = []
        for org_id, count in org_counts.items():
            for _ in range(count):
                tasks.append(
                    service.record_event(
                        organization_id=org_id,
                        metric_type=UsageMetricType.API_CALLS,
                        quantity=1,
                    )
                )
        
        await asyncio.gather(*tasks)
        await db_session.commit()
        
        # Verify isolation
        for org in multiple_load_test_orgs:
            expected = org_counts[org.id]
            actual = await service.get_current_usage(
                org.id,
                UsageMetricType.API_CALLS,
            )
            assert actual == expected, f"Org {org.id}: got {actual}, expected {expected}"


class TestMixedWorkload:
    """Tests for mixed read/write workloads."""
    
    @pytest.mark.asyncio
    async def test_mixed_read_write_workload(
        self,
        db_session: AsyncSession,
        load_test_org,
    ):
        """Test performance under mixed read/write workload."""
        service = MeteringService(db_session)
        
        import time
        import random
        
        operations = []
        read_count = 0
        write_count = 0
        
        # Generate mixed workload (70% writes, 30% reads)
        for _ in range(100):
            if random.random() < 0.7:
                operations.append(("write", None))
                write_count += 1
            else:
                operations.append(("read", None))
                read_count += 1
        
        start = time.perf_counter()
        
        for op_type, _ in operations:
            if op_type == "write":
                await service.record_event(
                    organization_id=load_test_org.id,
                    metric_type=UsageMetricType.TRANSACTIONS,
                    quantity=1,
                )
            else:
                await service.get_current_usage(
                    load_test_org.id,
                    UsageMetricType.TRANSACTIONS,
                )
        
        end = time.perf_counter()
        duration = end - start
        ops_per_second = len(operations) / duration
        
        print(f"\n--- Mixed Workload: {write_count} writes, {read_count} reads ---")
        print(f"Duration: {duration:.3f}s")
        print(f"Throughput: {ops_per_second:.1f} ops/second")
        
        assert ops_per_second >= 50


class TestLargeQuantities:
    """Tests for recording large quantities."""
    
    @pytest.mark.asyncio
    async def test_large_quantity_recording(
        self,
        db_session: AsyncSession,
        load_test_org,
    ):
        """Test recording events with large quantities."""
        service = MeteringService(db_session)
        
        import time
        
        quantities = [100, 500, 1000, 5000, 10000]
        
        start = time.perf_counter()
        for qty in quantities:
            await service.record_event(
                organization_id=load_test_org.id,
                metric_type=UsageMetricType.OCR_PAGES,
                quantity=qty,
            )
        end = time.perf_counter()
        
        await db_session.commit()
        
        duration = end - start
        
        print(f"\n--- Large Quantities: {quantities} ---")
        print(f"Duration: {duration:.3f}s")
        
        # Verify total
        total = await service.get_current_usage(
            load_test_org.id,
            UsageMetricType.OCR_PAGES,
        )
        expected_total = sum(quantities)
        assert total == expected_total


class TestUsageHistoryPerformance:
    """Tests for usage history retrieval performance."""
    
    @pytest.mark.asyncio
    async def test_get_usage_history_performance(
        self,
        db_session: AsyncSession,
        load_test_org,
    ):
        """Test performance of usage history retrieval."""
        service = MeteringService(db_session)
        
        # Create historical records
        now = datetime.utcnow()
        for month_offset in range(6):
            period_start = (now - timedelta(days=30 * month_offset)).date().replace(day=1)
            next_month = period_start.replace(month=period_start.month + 1) if period_start.month < 12 else period_start.replace(year=period_start.year + 1, month=1)
            
            record = UsageRecord(
                id=uuid4(),
                organization_id=load_test_org.id,
                period_start=period_start,
                period_end=next_month,
                transactions_count=100 * (month_offset + 1),
                users_count=5,
                entities_count=3,
                invoices_count=50 * (month_offset + 1),
                api_calls_count=1000 * (month_offset + 1),
                ocr_pages_count=20,
                storage_used_mb=Decimal("100.00"),
                ml_inferences_count=10,
                employees_count=0,
            )
            db_session.add(record)
        
        await db_session.flush()
        
        import time
        count = 50
        
        start = time.perf_counter()
        for _ in range(count):
            await service.get_usage_history(load_test_org.id, months=6)
        end = time.perf_counter()
        
        duration = end - start
        queries_per_second = count / duration
        
        print(f"\n--- Usage History: 50 queries ---")
        print(f"Duration: {duration:.3f}s")
        print(f"Throughput: {queries_per_second:.1f} queries/second")
        
        assert queries_per_second >= 20


class TestSustainedLoad:
    """Tests for sustained load over time."""
    
    @pytest.mark.asyncio
    async def test_sustained_load_5_seconds(
        self,
        db_session: AsyncSession,
        load_test_org,
    ):
        """Test sustained load over 5 seconds."""
        service = MeteringService(db_session)
        
        import time
        
        duration_target = 5.0  # seconds
        batch_size = 20
        event_count = 0
        
        start = time.perf_counter()
        
        while (time.perf_counter() - start) < duration_target:
            tasks = [
                service.record_event(
                    organization_id=load_test_org.id,
                    metric_type=UsageMetricType.API_CALLS,
                    quantity=1,
                )
                for _ in range(batch_size)
            ]
            await asyncio.gather(*tasks)
            event_count += batch_size
        
        end = time.perf_counter()
        actual_duration = end - start
        events_per_second = event_count / actual_duration
        
        print(f"\n--- Sustained Load: {actual_duration:.1f}s ---")
        print(f"Total Events: {event_count}")
        print(f"Sustained Throughput: {events_per_second:.1f} events/second")
        
        # Should maintain reasonable throughput
        assert events_per_second >= 50


# =============================================================================
# BENCHMARK TESTS (Optional - requires pytest-benchmark)
# =============================================================================

class TestWithBenchmark:
    """
    Benchmark tests using pytest-benchmark.
    
    Run with: pytest tests/test_metering_load.py -v --benchmark-only
    
    Note: These tests require pytest-benchmark to be installed:
        pip install pytest-benchmark
    """
    
    @pytest.mark.asyncio
    async def test_record_event_simple(
        self,
        db_session: AsyncSession,
        load_test_org,
    ):
        """Simple record_event performance test."""
        service = MeteringService(db_session)
        
        # Warm up
        await service.record_event(
            organization_id=load_test_org.id,
            metric_type=UsageMetricType.TRANSACTIONS,
            quantity=1,
        )
        
        import time
        iterations = 10
        
        start = time.perf_counter()
        for _ in range(iterations):
            await service.record_event(
                organization_id=load_test_org.id,
                metric_type=UsageMetricType.TRANSACTIONS,
                quantity=1,
            )
        end = time.perf_counter()
        
        avg_time_ms = ((end - start) / iterations) * 1000
        
        print(f"\n--- Single Event Benchmark ---")
        print(f"Average time: {avg_time_ms:.2f}ms")
        
        # Single event should complete quickly
        assert avg_time_ms < 100  # Less than 100ms per event
