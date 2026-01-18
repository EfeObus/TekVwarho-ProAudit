"""
Seed Script: Advanced Payroll Data
==================================
Populates advanced payroll tables for existing payroll runs.

This script creates:
- Statutory Remittances (PAYE, Pension, NHF, NSITF, ITF)
- Compliance Snapshots
- YTD Payroll Ledgers
- Payroll Decision Logs
- Payroll Exceptions

Run after seeding payroll runs with seed_efe_obus_furniture.py
"""

import asyncio
import uuid
import random
import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

# Add project root to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.database import async_session_maker
from app.models.entity import BusinessEntity
from app.models.payroll import (
    PayrollRun, PayrollStatus, Payslip,
    Employee, StatutoryRemittance,
)
from app.models.payroll_advanced import (
    ComplianceSnapshot, ComplianceStatus, PayrollDecisionLog,
    YTDPayrollLedger, PayrollException, ExceptionCode, ExceptionSeverity,
    RemittanceType
)
from app.models.user import User


# =============================================================================
# CONSTANTS
# =============================================================================

ENTITY_ID = uuid.UUID("453f0f12-202a-48b2-8c72-91526deeee56")  # Efe Obus Furniture

# Remittance due dates (day of month after payroll period)
REMITTANCE_DUE_DATES = {
    RemittanceType.PAYE: 10,      # 10th of following month
    RemittanceType.PENSION: 7,    # 7th of following month
    RemittanceType.NHF: 30,       # End of following month
    RemittanceType.NSITF: 15,     # 15th of following month
    RemittanceType.ITF: 15,       # 15th of following month
}


def get_content_hash(content: dict) -> str:
    """Generate SHA-256 hash for decision log content integrity."""
    import json
    content_str = json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(content_str.encode()).hexdigest()


# =============================================================================
# SEED FUNCTIONS
# =============================================================================

async def seed_statutory_remittances(db: AsyncSession):
    """Create statutory remittances for all completed/paid payroll runs."""
    print("Creating statutory remittances...")
    
    # Get all payroll runs for entity
    result = await db.execute(
        select(PayrollRun).where(
            and_(
                PayrollRun.entity_id == ENTITY_ID,
                PayrollRun.status.in_([PayrollStatus.COMPLETED, PayrollStatus.PAID])
            )
        )
    )
    payroll_runs = list(result.scalars().all())
    
    print(f"Found {len(payroll_runs)} payroll runs to process")
    
    remittances_created = 0
    
    for run in payroll_runs:
        # Get payslips for this run
        payslips_result = await db.execute(
            select(Payslip).where(Payslip.payroll_run_id == run.id)
        )
        payslips = list(payslips_result.scalars().all())
        
        if not payslips:
            continue
        
        # Calculate totals
        total_paye = sum(p.paye_tax or Decimal('0') for p in payslips)
        total_pension_employee = sum(p.pension_employee or Decimal('0') for p in payslips)
        total_pension_employer = sum(p.pension_employer or Decimal('0') for p in payslips)
        total_nhf = sum(p.nhf or Decimal('0') for p in payslips)
        total_nsitf = sum(p.nsitf or Decimal('0') for p in payslips)
        total_itf = sum(p.itf or Decimal('0') for p in payslips)
        
        period_month = run.period_start.month
        period_year = run.period_start.year
        
        # Calculate due dates (next month)
        due_month = period_month + 1 if period_month < 12 else 1
        due_year = period_year if period_month < 12 else period_year + 1
        
        remittance_data = [
            (RemittanceType.PAYE, total_paye, REMITTANCE_DUE_DATES[RemittanceType.PAYE]),
            (RemittanceType.PENSION, total_pension_employee + total_pension_employer, REMITTANCE_DUE_DATES[RemittanceType.PENSION]),
            (RemittanceType.NHF, total_nhf, REMITTANCE_DUE_DATES[RemittanceType.NHF]),
            (RemittanceType.NSITF, total_nsitf, REMITTANCE_DUE_DATES[RemittanceType.NSITF]),
            (RemittanceType.ITF, total_itf, REMITTANCE_DUE_DATES[RemittanceType.ITF]),
        ]
        
        for rem_type, amount, due_day in remittance_data:
            if amount <= 0:
                continue
            
            # Check if remittance already exists
            existing = await db.execute(
                select(StatutoryRemittance).where(
                    and_(
                        StatutoryRemittance.entity_id == ENTITY_ID,
                        StatutoryRemittance.payroll_run_id == run.id,
                        StatutoryRemittance.remittance_type == rem_type.value,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            # Determine status based on current date
            due_date = date(due_year, due_month, min(due_day, 28))  # Cap at 28 for safety
            today = date.today()
            
            if run.status == PayrollStatus.PAID:
                # Assume paid runs have paid remittances
                is_paid = True
                paid_date = due_date - timedelta(days=random.randint(1, 5))
                paid_amount = amount
                receipt_number = f"RMT-{rem_type.value[:3].upper()}-{period_year}{period_month:02d}-{random.randint(1000, 9999)}"
            else:
                # Not yet paid
                is_paid = False
                paid_date = None
                paid_amount = Decimal('0')
                receipt_number = None
            
            remittance = StatutoryRemittance(
                id=uuid.uuid4(),
                entity_id=ENTITY_ID,
                payroll_run_id=run.id,
                remittance_type=rem_type.value,
                period_month=period_month,
                period_year=period_year,
                amount_due=amount,
                amount_paid=paid_amount,
                due_date=due_date,
                payment_date=paid_date,
                is_paid=is_paid,
                receipt_number=receipt_number,
            )
            db.add(remittance)
            remittances_created += 1
    
    await db.commit()
    print(f"Created {remittances_created} statutory remittances")


async def seed_compliance_snapshots(db: AsyncSession):
    """Create compliance snapshots for each month with payroll data."""
    print("Creating compliance snapshots...")
    
    # Get all payroll runs grouped by month/year
    result = await db.execute(
        select(PayrollRun).where(PayrollRun.entity_id == ENTITY_ID)
    )
    payroll_runs = list(result.scalars().all())
    
    # Group by period
    periods = {}
    for run in payroll_runs:
        key = (run.period_start.month, run.period_start.year)
        if key not in periods:
            periods[key] = run
    
    snapshots_created = 0
    
    for (month, year), run in periods.items():
        # Check if snapshot exists
        existing = await db.execute(
            select(ComplianceSnapshot).where(
                and_(
                    ComplianceSnapshot.entity_id == ENTITY_ID,
                    ComplianceSnapshot.period_month == month,
                    ComplianceSnapshot.period_year == year,
                )
            )
        )
        if existing.scalar_one_or_none():
            continue
        
        # Get remittances for this period
        remittances = await db.execute(
            select(StatutoryRemittance).where(
                and_(
                    StatutoryRemittance.entity_id == ENTITY_ID,
                    StatutoryRemittance.period_month == month,
                    StatutoryRemittance.period_year == year,
                )
            )
        )
        remittances_list = list(remittances.scalars().all())
        
        # Build snapshot
        paye_rem = next((r for r in remittances_list if r.remittance_type == RemittanceType.PAYE.value), None)
        pension_rem = next((r for r in remittances_list if r.remittance_type == RemittanceType.PENSION.value), None)
        nhf_rem = next((r for r in remittances_list if r.remittance_type == RemittanceType.NHF.value), None)
        nsitf_rem = next((r for r in remittances_list if r.remittance_type == RemittanceType.NSITF.value), None)
        itf_rem = next((r for r in remittances_list if r.remittance_type == RemittanceType.ITF.value), None)
        
        def get_compliance_status(rem) -> ComplianceStatus:
            if not rem:
                return ComplianceStatus.NOT_DUE
            today = date.today()
            if rem.is_paid:
                return ComplianceStatus.ON_TIME
            elif today > rem.due_date:
                return ComplianceStatus.OVERDUE
            else:
                return ComplianceStatus.NOT_DUE
        
        snapshot = ComplianceSnapshot(
            id=uuid.uuid4(),
            entity_id=ENTITY_ID,
            period_month=month,
            period_year=year,
            
            # PAYE
            paye_status=get_compliance_status(paye_rem),
            paye_amount_due=paye_rem.amount_due if paye_rem else Decimal('0'),
            paye_amount_paid=paye_rem.amount_paid if paye_rem and paye_rem.amount_paid else Decimal('0'),
            paye_due_date=paye_rem.due_date if paye_rem else None,
            
            # Pension
            pension_status=get_compliance_status(pension_rem),
            pension_amount_due=pension_rem.amount_due if pension_rem else Decimal('0'),
            pension_amount_paid=pension_rem.amount_paid if pension_rem and pension_rem.amount_paid else Decimal('0'),
            pension_due_date=pension_rem.due_date if pension_rem else None,
            
            # NHF
            nhf_status=get_compliance_status(nhf_rem),
            nhf_amount_due=nhf_rem.amount_due if nhf_rem else Decimal('0'),
            nhf_amount_paid=nhf_rem.amount_paid if nhf_rem and nhf_rem.amount_paid else Decimal('0'),
            nhf_due_date=nhf_rem.due_date if nhf_rem else None,
            
            # NSITF
            nsitf_status=get_compliance_status(nsitf_rem),
            nsitf_amount_due=nsitf_rem.amount_due if nsitf_rem else Decimal('0'),
            nsitf_amount_paid=nsitf_rem.amount_paid if nsitf_rem and nsitf_rem.amount_paid else Decimal('0'),
            
            # ITF
            itf_status=get_compliance_status(itf_rem),
            itf_amount_due=itf_rem.amount_due if itf_rem else Decimal('0'),
            itf_amount_paid=itf_rem.amount_paid if itf_rem and itf_rem.amount_paid else Decimal('0'),
        )
        db.add(snapshot)
        snapshots_created += 1
    
    await db.commit()
    print(f"Created {snapshots_created} compliance snapshots")


async def seed_ytd_ledgers(db: AsyncSession):
    """Create YTD payroll ledger entries for employees."""
    print("Creating YTD payroll ledgers...")
    
    # Get employees for entity
    employees_result = await db.execute(
        select(Employee).where(Employee.entity_id == ENTITY_ID)
    )
    employees = list(employees_result.scalars().all())
    
    if not employees:
        print("No employees found, skipping YTD ledgers")
        return
    
    # Get all payslips grouped by employee and year
    payslips_result = await db.execute(
        select(Payslip).join(PayrollRun).where(
            and_(
                PayrollRun.entity_id == ENTITY_ID,
                PayrollRun.status.in_([PayrollStatus.COMPLETED, PayrollStatus.PAID])
            )
        )
    )
    payslips = list(payslips_result.scalars().all())
    
    # Group by employee and year
    ledger_data = {}
    for payslip in payslips:
        employee_id = payslip.employee_id
        # Get payroll run for the period year
        run_result = await db.execute(
            select(PayrollRun).where(PayrollRun.id == payslip.payroll_run_id)
        )
        run = run_result.scalar_one_or_none()
        if not run:
            continue
        
        year = run.period_start.year
        key = (employee_id, year)
        
        if key not in ledger_data:
            ledger_data[key] = {
                'gross': Decimal('0'),
                'basic': Decimal('0'),
                'housing': Decimal('0'),
                'transport': Decimal('0'),
                'other_earnings': Decimal('0'),
                'total_deductions': Decimal('0'),
                'paye': Decimal('0'),
                'pension_employee': Decimal('0'),
                'pension_employer': Decimal('0'),
                'nhf': Decimal('0'),
                'nsitf': Decimal('0'),
                'itf': Decimal('0'),
                'other_deductions': Decimal('0'),
                'net': Decimal('0'),
                'months_processed': 0,
            }
        
        data = ledger_data[key]
        data['gross'] += payslip.gross_pay or Decimal('0')
        data['basic'] += payslip.basic_salary or Decimal('0')
        data['housing'] += payslip.housing_allowance or Decimal('0')
        data['transport'] += payslip.transport_allowance or Decimal('0')
        data['other_earnings'] += payslip.other_earnings or Decimal('0')
        data['total_deductions'] += payslip.total_deductions or Decimal('0')
        data['paye'] += payslip.paye_tax or Decimal('0')
        data['pension_employee'] += payslip.pension_employee or Decimal('0')
        data['pension_employer'] += payslip.pension_employer or Decimal('0')
        data['nhf'] += payslip.nhf or Decimal('0')
        data['nsitf'] += payslip.nsitf or Decimal('0')
        data['itf'] += payslip.itf or Decimal('0')
        data['other_deductions'] += payslip.other_deductions or Decimal('0')
        data['net'] += payslip.net_pay or Decimal('0')
        data['months_processed'] += 1
    
    ledgers_created = 0
    
    for (employee_id, year), data in ledger_data.items():
        # Check if exists
        existing = await db.execute(
            select(YTDPayrollLedger).where(
                and_(
                    YTDPayrollLedger.entity_id == ENTITY_ID,
                    YTDPayrollLedger.employee_id == employee_id,
                    YTDPayrollLedger.tax_year == year,
                )
            )
        )
        if existing.scalar_one_or_none():
            continue
        
        # Calculate total employer cost
        total_employer_cost = (
            data['gross'] + 
            data['pension_employer'] + 
            data['nsitf'] + 
            data['itf']
        )
        
        ledger = YTDPayrollLedger(
            id=uuid.uuid4(),
            entity_id=ENTITY_ID,
            employee_id=employee_id,
            tax_year=year,
            ytd_gross=data['gross'],
            ytd_basic=data['basic'],
            ytd_housing=data['housing'],
            ytd_transport=data['transport'],
            ytd_other_earnings=data['other_earnings'],
            ytd_total_deductions=data['total_deductions'],
            ytd_paye=data['paye'],
            ytd_pension_employee=data['pension_employee'],
            ytd_pension_employer=data['pension_employer'],
            ytd_nhf=data['nhf'],
            ytd_nsitf=data['nsitf'],
            ytd_itf=data['itf'],
            ytd_other_deductions=data['other_deductions'],
            ytd_net=data['net'],
            ytd_total_employer_cost=total_employer_cost,
            months_processed=data['months_processed'],
        )
        db.add(ledger)
        ledgers_created += 1
    
    await db.commit()
    print(f"Created {ledgers_created} YTD payroll ledger entries")


async def seed_decision_logs(db: AsyncSession):
    """Create decision logs for payroll runs."""
    print("Creating payroll decision logs...")
    
    # Get a user to attribute decisions to
    user_result = await db.execute(
        select(User).where(User.email == "efeobukohwo64@gmail.com")
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        print("User not found, skipping decision logs")
        return
    
    # Get payroll runs
    runs_result = await db.execute(
        select(PayrollRun).where(
            and_(
                PayrollRun.entity_id == ENTITY_ID,
                PayrollRun.status.in_([PayrollStatus.APPROVED, PayrollStatus.COMPLETED, PayrollStatus.PAID])
            )
        ).order_by(PayrollRun.period_start)
    )
    runs = list(runs_result.scalars().all())
    
    logs_created = 0
    
    for run in runs:
        # Check if logs exist for this run
        existing = await db.execute(
            select(func.count(PayrollDecisionLog.id)).where(
                PayrollDecisionLog.payroll_run_id == run.id
            )
        )
        if existing.scalar() > 0:
            continue
        
        # Create approval log
        approval_content = {
            "payroll_id": str(run.id),
            "payroll_name": run.name,
            "action": "approved",
            "period": f"{run.period_start} to {run.period_end}",
        }
        
        approval_log = PayrollDecisionLog(
            id=uuid.uuid4(),
            entity_id=ENTITY_ID,
            payroll_run_id=run.id,
            decision_type="approval",
            category="payroll",
            title=f"Approved {run.name}",
            description=f"Payroll {run.name} was approved for processing. Period: {run.period_start} to {run.period_end}.",
            context_data=approval_content,
            created_by_id=user.id,
            created_by_name=f"{user.first_name} {user.last_name}",
            created_by_role=user.role.value if user.role else "admin",
            is_locked=run.status in [PayrollStatus.COMPLETED, PayrollStatus.PAID],
            content_hash=get_content_hash(approval_content),
            created_at=run.approved_at or run.created_at,
        )
        db.add(approval_log)
        logs_created += 1
        
        # Create processing log if completed/paid
        if run.status in [PayrollStatus.COMPLETED, PayrollStatus.PAID]:
            process_content = {
                "payroll_id": str(run.id),
                "payroll_name": run.name,
                "action": "processed",
                "total_net_pay": str(run.total_net_pay or 0),
            }
            
            process_log = PayrollDecisionLog(
                id=uuid.uuid4(),
                entity_id=ENTITY_ID,
                payroll_run_id=run.id,
                decision_type="note",
                category="payroll",
                title=f"Processed {run.name}",
                description=f"Payroll {run.name} was processed successfully. Total net pay: ₦{run.total_net_pay or 0:,.2f}",
                context_data=process_content,
                created_by_id=user.id,
                created_by_name=f"{user.first_name} {user.last_name}",
                created_by_role=user.role.value if user.role else "admin",
                is_locked=True,
                content_hash=get_content_hash(process_content),
                created_at=(run.approved_at or run.created_at) + timedelta(hours=1),
            )
            db.add(process_log)
            logs_created += 1
        
        # Create payment log if paid
        if run.status == PayrollStatus.PAID:
            payment_content = {
                "payroll_id": str(run.id),
                "payroll_name": run.name,
                "action": "paid",
                "paid_at": str(run.paid_at),
            }
            
            payment_log = PayrollDecisionLog(
                id=uuid.uuid4(),
                entity_id=ENTITY_ID,
                payroll_run_id=run.id,
                decision_type="note",
                category="payroll",
                title=f"Paid {run.name}",
                description=f"Payroll {run.name} salaries have been paid to all employees.",
                context_data=payment_content,
                created_by_id=user.id,
                created_by_name=f"{user.first_name} {user.last_name}",
                created_by_role=user.role.value if user.role else "admin",
                is_locked=True,
                content_hash=get_content_hash(payment_content),
                created_at=run.paid_at or (run.approved_at or run.created_at) + timedelta(days=1),
            )
            db.add(payment_log)
            logs_created += 1
    
    await db.commit()
    print(f"Created {logs_created} payroll decision logs")


async def main():
    """Run all seed functions."""
    print("=" * 60)
    print("Seeding Advanced Payroll Data")
    print("=" * 60)
    print(f"Entity ID: {ENTITY_ID}")
    print()
    
    async with async_session_maker() as db:
        await seed_statutory_remittances(db)
        await seed_compliance_snapshots(db)
        await seed_ytd_ledgers(db)
        await seed_decision_logs(db)
    
    print()
    print("=" * 60)
    print("Advanced Payroll Data Seeding Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
