#!/usr/bin/env python3
"""
Seed script to generate impact previews for all existing payroll runs.

This script creates impact preview records for each payroll run that
doesn't already have one. It calculates variances by comparing each
payroll run with the previous one.

Usage:
    python scripts/seed_impact_previews.py
"""

import asyncio
import sys
import os
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.payroll import PayrollRun, PayrollStatus, Payslip
from app.models.payroll_advanced import PayrollImpactPreview

# Create async engine
engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_employee_count(db: AsyncSession, payroll_run_id) -> int:
    """Get the number of employees in a payroll run."""
    result = await db.execute(
        select(Payslip.employee_id)
        .where(Payslip.payroll_run_id == payroll_run_id)
        .distinct()
    )
    return len(result.scalars().all())


async def generate_impact_preview_for_run(
    db: AsyncSession,
    current_payroll: PayrollRun,
    previous_payroll: PayrollRun | None,
) -> PayrollImpactPreview:
    """Generate impact preview for a single payroll run."""
    
    # Current period totals
    current_gross = current_payroll.total_gross_pay or Decimal("0")
    current_net = current_payroll.total_net_pay or Decimal("0")
    current_paye = current_payroll.total_paye or Decimal("0")
    current_employer_cost = (
        current_gross +
        (current_payroll.total_pension_employer or Decimal("0")) +
        (current_payroll.total_nsitf or Decimal("0")) +
        (current_payroll.total_itf or Decimal("0"))
    )
    current_employee_count = await get_employee_count(db, current_payroll.id)
    
    # Previous period totals
    if previous_payroll:
        previous_gross = previous_payroll.total_gross_pay or Decimal("0")
        previous_net = previous_payroll.total_net_pay or Decimal("0")
        previous_paye = previous_payroll.total_paye or Decimal("0")
        previous_employer_cost = (
            previous_gross +
            (previous_payroll.total_pension_employer or Decimal("0")) +
            (previous_payroll.total_nsitf or Decimal("0")) +
            (previous_payroll.total_itf or Decimal("0"))
        )
        previous_employee_count = await get_employee_count(db, previous_payroll.id)
        previous_payroll_id = previous_payroll.id
    else:
        previous_gross = Decimal("0")
        previous_net = Decimal("0")
        previous_paye = Decimal("0")
        previous_employer_cost = Decimal("0")
        previous_employee_count = 0
        previous_payroll_id = None
    
    # Calculate variances
    gross_variance = current_gross - previous_gross
    net_variance = current_net - previous_net
    paye_variance = current_paye - previous_paye
    employer_cost_variance = current_employer_cost - previous_employer_cost
    
    if previous_gross > 0:
        gross_variance_percent = (
            (gross_variance / previous_gross) * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        gross_variance_percent = Decimal("100") if current_gross > 0 else Decimal("0")
    
    # Generate variance drivers (simplified for seeding)
    variance_drivers = []
    if gross_variance != 0:
        variance_drivers.append({
            "category": "Base Salary Changes",
            "amount": float(gross_variance * Decimal("0.6")),
            "description": "Monthly salary adjustments"
        })
        variance_drivers.append({
            "category": "Allowance Changes",
            "amount": float(gross_variance * Decimal("0.25")),
            "description": "Housing, transport, and other allowances"
        })
        variance_drivers.append({
            "category": "Bonus/Overtime",
            "amount": float(gross_variance * Decimal("0.15")),
            "description": "Performance bonuses and overtime pay"
        })
    
    # Generate summary
    employee_change = current_employee_count - previous_employee_count
    if gross_variance > 0:
        trend = "increased"
    elif gross_variance < 0:
        trend = "decreased"
    else:
        trend = "remained stable"
    
    impact_summary = f"Payroll costs {trend} by {abs(gross_variance_percent):.1f}% compared to previous period. "
    if employee_change > 0:
        impact_summary += f"{employee_change} new employee(s) added. "
    elif employee_change < 0:
        impact_summary += f"{abs(employee_change)} employee(s) removed. "
    
    if current_employee_count > 0:
        avg_cost = current_gross / current_employee_count
        impact_summary += f"Average cost per employee: ₦{avg_cost:,.2f}."
    
    # Create preview
    preview = PayrollImpactPreview(
        payroll_run_id=current_payroll.id,
        previous_payroll_id=previous_payroll_id,
        current_gross=current_gross,
        current_net=current_net,
        current_paye=current_paye,
        current_employer_cost=current_employer_cost,
        current_employee_count=current_employee_count,
        previous_gross=previous_gross,
        previous_net=previous_net,
        previous_paye=previous_paye,
        previous_employer_cost=previous_employer_cost,
        previous_employee_count=previous_employee_count,
        gross_variance=gross_variance,
        gross_variance_percent=gross_variance_percent,
        net_variance=net_variance,
        paye_variance=paye_variance,
        employer_cost_variance=employer_cost_variance,
        variance_drivers=variance_drivers,
        new_hires_count=max(0, employee_change),
        new_hires_cost=Decimal("0"),  # Would need more complex logic
        terminations_count=max(0, -employee_change),
        terminations_savings=Decimal("0"),  # Would need more complex logic
        impact_summary=impact_summary,
        generated_at=datetime.utcnow(),
    )
    
    return preview


async def seed_impact_previews():
    """Main function to seed impact previews for all payroll runs."""
    print("=" * 60)
    print("Seeding Impact Previews for Payroll Runs")
    print("=" * 60)
    
    async with async_session_maker() as db:
        # Get all payroll runs ordered by period_start
        result = await db.execute(
            select(PayrollRun)
            .where(
                PayrollRun.status.in_([
                    PayrollStatus.APPROVED,
                    PayrollStatus.PROCESSING,
                    PayrollStatus.COMPLETED,
                    PayrollStatus.PAID,
                ])
            )
            .order_by(PayrollRun.entity_id, PayrollRun.period_start)
        )
        payroll_runs = result.scalars().all()
        
        if not payroll_runs:
            print("No payroll runs found to process.")
            return
        
        print(f"Found {len(payroll_runs)} payroll runs to process.\n")
        
        # Group by entity
        entity_payrolls = {}
        for pr in payroll_runs:
            if pr.entity_id not in entity_payrolls:
                entity_payrolls[pr.entity_id] = []
            entity_payrolls[pr.entity_id].append(pr)
        
        created_count = 0
        skipped_count = 0
        
        for entity_id, payrolls in entity_payrolls.items():
            print(f"\nProcessing entity: {entity_id}")
            print(f"  Payroll runs: {len(payrolls)}")
            
            previous_payroll = None
            
            for payroll in payrolls:
                # Check if preview already exists
                existing = await db.execute(
                    select(PayrollImpactPreview).where(
                        PayrollImpactPreview.payroll_run_id == payroll.id
                    )
                )
                if existing.scalar_one_or_none():
                    print(f"  ⏭️  Skipping {payroll.name} (preview exists)")
                    skipped_count += 1
                    previous_payroll = payroll
                    continue
                
                # Generate preview
                preview = await generate_impact_preview_for_run(db, payroll, previous_payroll)
                db.add(preview)
                
                print(f"  ✅ Created preview for: {payroll.name}")
                print(f"     Period: {payroll.period_start} to {payroll.period_end}")
                print(f"     Gross: ₦{payroll.total_gross_pay:,.2f}")
                if previous_payroll:
                    print(f"     Variance: {preview.gross_variance_percent:+.1f}%")
                
                created_count += 1
                previous_payroll = payroll
        
        await db.commit()
        
        print("\n" + "=" * 60)
        print("Summary:")
        print(f"  Created: {created_count} impact previews")
        print(f"  Skipped: {skipped_count} (already existed)")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_impact_previews())
