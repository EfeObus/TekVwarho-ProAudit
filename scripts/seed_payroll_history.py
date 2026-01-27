"""
Seed Script: Payroll History for Efe Obus Furniture Manufacturing LTD
======================================================================
Creates 5-10 years of payroll history for testing the payroll system.

This script:
- Assigns random TINs to employees without them
- Creates monthly payroll runs from 2015 to 2025
- Generates payslips with proper PAYE, Pension, NHF calculations
"""

import asyncio
import uuid
import random
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import List, Dict, Optional

# Add project root to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.entity import BusinessEntity
from app.models.payroll import (
    Employee, EmploymentStatus, PayrollRun, PayrollStatus, 
    Payslip, PayslipItem, PayItemType, PayItemCategory,
    PayrollFrequency
)


# Nigerian PAYE Tax Bands (2026 Tax Reform)
PAYE_BANDS_2026 = [
    (800_000, 0.00),          # First ₦800,000 - 0% (tax-free threshold)
    (300_000, 0.07),          # Next ₦300,000 - 7%
    (300_000, 0.11),          # Next ₦300,000 - 11%
    (500_000, 0.15),          # Next ₦500,000 - 15%
    (500_000, 0.19),          # Next ₦500,000 - 19%
    (1_600_000, 0.21),        # Next ₦1,600,000 - 21%
    (float('inf'), 0.24),     # Above ₦4,000,000 - 24%
]

# Pre-2026 PAYE Tax Bands (older payroll)
PAYE_BANDS_OLD = [
    (300_000, 0.07),          # First ₦300,000 - 7%
    (300_000, 0.11),          # Next ₦300,000 - 11%
    (500_000, 0.15),          # Next ₦500,000 - 15%
    (500_000, 0.19),          # Next ₦500,000 - 19%
    (1_600_000, 0.21),        # Next ₦1,600,000 - 21%
    (float('inf'), 0.24),     # Above ₦3,200,000 - 24%
]


def generate_tin() -> str:
    """Generate a random Nigerian TIN."""
    # Nigerian TIN format: 10-digit number with hyphen
    first_part = random.randint(10000000, 99999999)
    second_part = random.randint(1, 9999)
    return f"{first_part:08d}-{second_part:04d}"


def calculate_annual_paye(annual_gross: Decimal, annual_relief: Decimal, year: int = 2026) -> Decimal:
    """Calculate annual PAYE tax based on year."""
    taxable_income = max(Decimal("0"), annual_gross - annual_relief)
    
    # Select tax bands based on year
    if year >= 2026:
        bands = PAYE_BANDS_2026
    else:
        bands = PAYE_BANDS_OLD
    
    tax = Decimal("0")
    remaining = float(taxable_income)
    
    for band_limit, rate in bands:
        if remaining <= 0:
            break
        
        taxable_in_band = min(remaining, band_limit)
        tax += Decimal(str(taxable_in_band * rate))
        remaining -= taxable_in_band
    
    return tax


def calculate_consolidated_relief(annual_gross: Decimal) -> Decimal:
    """
    Calculate Consolidated Relief Allowance (CRA).
    CRA = ₦200,000 OR 1% of gross income (whichever is higher) + 20% of gross income
    """
    base_relief = max(Decimal("200000"), annual_gross * Decimal("0.01"))
    percentage_relief = annual_gross * Decimal("0.20")
    return base_relief + percentage_relief


def calculate_pension_employee(gross: Decimal) -> Decimal:
    """Calculate employee pension contribution (8%)."""
    return gross * Decimal("0.08")


def calculate_pension_employer(gross: Decimal) -> Decimal:
    """Calculate employer pension contribution (10%)."""
    return gross * Decimal("0.10")


def calculate_nhf(basic: Decimal) -> Decimal:
    """Calculate NHF contribution (2.5% of basic)."""
    return basic * Decimal("0.025")


def calculate_nsitf(gross: Decimal) -> Decimal:
    """Calculate NSITF (1% of gross - employer)."""
    return gross * Decimal("0.01")


def calculate_itf(gross: Decimal) -> Decimal:
    """Calculate ITF (1% of gross - employer)."""
    return gross * Decimal("0.01")


async def assign_missing_tins(session: AsyncSession, entity_id: uuid.UUID) -> int:
    """Assign random TINs to employees without them."""
    result = await session.execute(
        select(Employee).where(
            Employee.entity_id == entity_id,
            (Employee.tin == None) | (Employee.tin == "")
        )
    )
    employees = result.scalars().all()
    
    count = 0
    for emp in employees:
        emp.tin = generate_tin()
        emp.tax_state = emp.state or "Delta"
        count += 1
    
    await session.flush()
    print(f"  ✓ Assigned TINs to {count} employees")
    return count


async def get_entity_and_employees(session: AsyncSession) -> tuple:
    """Get Efe Obus Furniture entity and its employees."""
    # Find the entity
    result = await session.execute(
        select(BusinessEntity).where(
            BusinessEntity.name.ilike("%efe obus%")
        )
    )
    entity = result.scalar_one_or_none()
    
    if not entity:
        print("[FAIL] Efe Obus Furniture entity not found!")
        return None, []
    
    # Get all active employees (use is_active flag instead of enum comparison)
    result = await session.execute(
        select(Employee).where(
            Employee.entity_id == entity.id,
            Employee.is_active == True
        ).options(selectinload(Employee.bank_accounts)).order_by(Employee.hire_date)
    )
    employees = result.scalars().all()
    
    return entity, list(employees)


def get_employees_for_period(employees: List[Employee], period_date: date) -> List[Employee]:
    """Get employees who were hired by the given date."""
    return [emp for emp in employees if emp.hire_date <= period_date]


async def create_payroll_run(
    session: AsyncSession,
    entity_id: uuid.UUID,
    year: int,
    month: int,
    employees: List[Employee]
) -> Optional[PayrollRun]:
    """Create a payroll run for a specific month."""
    
    # Filter employees active for this period
    period_start = date(year, month, 1)
    period_end = (period_start + relativedelta(months=1)) - timedelta(days=1)
    payment_date = period_end + timedelta(days=5)
    
    active_employees = get_employees_for_period(employees, period_end)
    
    if not active_employees:
        return None
    
    # Create payroll run
    payroll_code = f"PAY-{year}-{month:02d}"
    month_name = period_start.strftime("%B")
    
    # Generate UUID for payroll run
    payroll_run_id = uuid.uuid4()
    
    # Calculate paid_at timestamp
    if payment_date.month == month:
        paid_at_dt = datetime(year, month, payment_date.day, 16, 0, 0)
    else:
        next_year = year + (1 if month == 12 else 0)
        next_month = (month % 12) + 1
        paid_at_dt = datetime(next_year, next_month, 5, 16, 0, 0)
    
    # Use raw SQL to insert with is_locked field
    insert_sql = text("""
        INSERT INTO payroll_runs (
            id, entity_id, payroll_code, name, description, frequency, 
            period_start, period_end, payment_date, status, total_employees,
            total_gross_pay, total_deductions, total_net_pay, total_employer_contributions,
            total_paye, total_pension_employee, total_pension_employer, total_nhf, 
            total_nsitf, total_itf, processed_at, paid_at, is_locked, created_at, updated_at
        ) VALUES (
            :id, :entity_id, :payroll_code, :name, :description, :frequency,
            :period_start, :period_end, :payment_date, :status, :total_employees,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, :processed_at, :paid_at, :is_locked, 
            NOW(), NOW()
        )
    """)
    
    await session.execute(insert_sql, {
        "id": payroll_run_id,
        "entity_id": entity_id,
        "payroll_code": payroll_code,
        "name": f"{month_name} {year} Payroll",
        "description": f"Monthly payroll for {month_name} {year}",
        "frequency": "MONTHLY",
        "period_start": period_start,
        "period_end": period_end,
        "payment_date": payment_date,
        "status": "PAID",
        "total_employees": len(active_employees),
        "processed_at": datetime(year, month, period_end.day, 14, 0, 0),
        "paid_at": paid_at_dt,
        "is_locked": True,  # Historical payrolls are locked
    })
    
    # Create a mock PayrollRun object for relationship handling
    class MockPayrollRun:
        def __init__(self, run_id, employees_count):
            self.id = run_id
            self.total_employees = employees_count
            self.total_gross_pay = Decimal("0")
            self.total_deductions = Decimal("0")
            self.total_net_pay = Decimal("0")
            self.total_employer_contributions = Decimal("0")
            self.total_paye = Decimal("0")
            self.total_pension_employee = Decimal("0")
            self.total_pension_employer = Decimal("0")
            self.total_nhf = Decimal("0")
            self.total_nsitf = Decimal("0")
            self.total_itf = Decimal("0")
    
    payroll_run = MockPayrollRun(payroll_run_id, len(active_employees))
    
    # Totals for the payroll run
    total_gross = Decimal("0")
    total_deductions = Decimal("0")
    total_net = Decimal("0")
    total_employer_contributions = Decimal("0")
    total_paye = Decimal("0")
    total_pension_emp = Decimal("0")
    total_pension_employer = Decimal("0")
    total_nhf = Decimal("0")
    total_nsitf = Decimal("0")
    total_itf = Decimal("0")
    
    # Create payslips for each employee
    for idx, emp in enumerate(active_employees, 1):
        payslip = await create_payslip(session, payroll_run.id, emp, year, month, idx)
        
        # Accumulate totals
        total_gross += payslip.gross_pay
        total_deductions += payslip.total_deductions
        total_net += payslip.net_pay
        total_paye += payslip.paye_tax
        total_pension_emp += payslip.pension_employee
        total_pension_employer += payslip.pension_employer
        total_nhf += payslip.nhf
        total_nsitf += payslip.nsitf
        total_itf += payslip.itf
        total_employer_contributions += (payslip.pension_employer + payslip.nsitf + payslip.itf)
    
    # Update payroll run totals using SQL
    update_sql = text("""
        UPDATE payroll_runs SET
            total_gross_pay = :total_gross,
            total_deductions = :total_deductions,
            total_net_pay = :total_net,
            total_employer_contributions = :total_employer_contributions,
            total_paye = :total_paye,
            total_pension_employee = :total_pension_emp,
            total_pension_employer = :total_pension_employer,
            total_nhf = :total_nhf,
            total_nsitf = :total_nsitf,
            total_itf = :total_itf,
            updated_at = NOW()
        WHERE id = :run_id
    """)
    
    await session.execute(update_sql, {
        "run_id": payroll_run.id,
        "total_gross": total_gross,
        "total_deductions": total_deductions,
        "total_net": total_net,
        "total_employer_contributions": total_employer_contributions,
        "total_paye": total_paye,
        "total_pension_emp": total_pension_emp,
        "total_pension_employer": total_pension_employer,
        "total_nhf": total_nhf,
        "total_nsitf": total_nsitf,
        "total_itf": total_itf,
    })
    
    # Update mock object for return
    payroll_run.total_gross_pay = total_gross
    payroll_run.total_deductions = total_deductions
    payroll_run.total_net_pay = total_net
    
    return payroll_run


async def create_payslip(
    session: AsyncSession,
    payroll_run_id: uuid.UUID,
    employee: Employee,
    year: int,
    month: int,
    slip_number: int
) -> Payslip:
    """Create a payslip for an employee."""
    
    # Get employee salary components
    basic = employee.basic_salary
    housing = employee.housing_allowance
    transport = employee.transport_allowance
    meal = getattr(employee, 'meal_allowance', Decimal("0")) or Decimal("0")
    utility = getattr(employee, 'utility_allowance', Decimal("0")) or Decimal("0")
    
    # Calculate gross pay (pensionable earnings for pension calculation)
    pensionable_gross = basic + housing + transport
    total_gross = basic + housing + transport + meal + utility
    
    # Calculate annual figures for PAYE
    annual_gross = total_gross * Decimal("12")
    annual_relief = calculate_consolidated_relief(annual_gross)
    
    # Calculate pension relief (8% employee contribution is tax deductible)
    annual_pension_employee = calculate_pension_employee(pensionable_gross) * Decimal("12")
    
    # Total relief for PAYE calculation
    total_annual_relief = annual_relief + annual_pension_employee
    
    # Calculate annual PAYE and monthly portion
    annual_paye = calculate_annual_paye(annual_gross, total_annual_relief, year)
    monthly_paye = (annual_paye / Decimal("12")).quantize(Decimal("0.01"))
    
    # Calculate monthly deductions
    monthly_pension_emp = calculate_pension_employee(pensionable_gross).quantize(Decimal("0.01"))
    monthly_nhf = calculate_nhf(basic).quantize(Decimal("0.01"))
    
    # Employer contributions
    monthly_pension_employer = calculate_pension_employer(pensionable_gross).quantize(Decimal("0.01"))
    monthly_nsitf = calculate_nsitf(total_gross).quantize(Decimal("0.01"))
    monthly_itf = calculate_itf(total_gross).quantize(Decimal("0.01"))
    
    # Total deductions and net pay
    total_deductions = monthly_paye + monthly_pension_emp + monthly_nhf
    net_pay = total_gross - total_deductions
    
    # Monthly relief
    monthly_relief = (annual_relief / Decimal("12")).quantize(Decimal("0.01"))
    monthly_taxable = (annual_gross - total_annual_relief) / Decimal("12")
    monthly_taxable = max(Decimal("0"), monthly_taxable.quantize(Decimal("0.01")))
    
    # Prepare JSON data
    import json
    earnings_breakdown = json.dumps({
        "basic_salary": float(basic),
        "housing_allowance": float(housing),
        "transport_allowance": float(transport),
        "meal_allowance": float(meal),
        "utility_allowance": float(utility),
    })
    
    deductions_breakdown = json.dumps({
        "paye_tax": float(monthly_paye),
        "pension_employee": float(monthly_pension_emp),
        "nhf": float(monthly_nhf),
    })
    
    tax_calculation = json.dumps({
        "annual_gross": float(annual_gross),
        "consolidated_relief": float(annual_relief),
        "pension_relief": float(annual_pension_employee),
        "total_relief": float(total_annual_relief),
        "annual_taxable": float(max(Decimal("0"), annual_gross - total_annual_relief)),
        "annual_paye": float(annual_paye),
        "monthly_paye": float(monthly_paye),
        "tax_year": year,
    })
    
    # Get bank info
    bank_name = str(employee.bank_accounts[0].bank_name.value) if employee.bank_accounts else None
    account_number = employee.bank_accounts[0].account_number if employee.bank_accounts else None
    account_name = employee.bank_accounts[0].account_name if employee.bank_accounts else None
    
    # Create payslip using raw SQL to include meal_allowance and utility_allowance columns
    payslip_id = uuid.uuid4()
    payslip_number = f"PS-{year}{month:02d}-{slip_number:04d}"
    paid_at = datetime(year, month, 28, 16, 0, 0)
    other_earnings = meal + utility
    
    insert_sql = text("""
        INSERT INTO payslips (
            id, payroll_run_id, employee_id, payslip_number,
            days_in_period, days_worked, days_absent,
            basic_salary, housing_allowance, transport_allowance, 
            meal_allowance, utility_allowance, overtime_pay, bonus,
            other_earnings, gross_pay,
            paye_tax, pension_employee, nhf,
            loan_deduction, salary_advance_deduction, cooperative_deduction, union_dues,
            other_deductions, total_deductions,
            net_pay, pension_employer, nsitf, itf,
            hmo_employer, group_life_insurance,
            consolidated_relief, rent_relief, pension_relief, nhf_relief, taxable_income,
            earnings_breakdown, deductions_breakdown, tax_calculation,
            bank_name, account_number, account_name,
            is_paid, paid_at, is_emailed,
            created_at, updated_at
        ) VALUES (
            :id, :payroll_run_id, :employee_id, :payslip_number,
            30, 30, 0,
            :basic_salary, :housing_allowance, :transport_allowance,
            :meal_allowance, :utility_allowance, 0, 0,
            :other_earnings, :gross_pay,
            :paye_tax, :pension_employee, :nhf,
            0, 0, 0, 0,
            0, :total_deductions,
            :net_pay, :pension_employer, :nsitf, :itf,
            0, 0,
            :consolidated_relief, 0, :pension_relief, :nhf_relief, :taxable_income,
            CAST(:earnings_breakdown AS json), CAST(:deductions_breakdown AS json), CAST(:tax_calculation AS json),
            :bank_name, :account_number, :account_name,
            true, :paid_at, false,
            NOW(), NOW()
        )
    """)
    
    await session.execute(insert_sql, {
        "id": payslip_id,
        "payroll_run_id": payroll_run_id,
        "employee_id": employee.id,
        "payslip_number": payslip_number,
        "basic_salary": basic,
        "housing_allowance": housing,
        "transport_allowance": transport,
        "meal_allowance": meal,
        "utility_allowance": utility,
        "other_earnings": other_earnings,
        "gross_pay": total_gross,
        "paye_tax": monthly_paye,
        "pension_employee": monthly_pension_emp,
        "nhf": monthly_nhf,
        "total_deductions": total_deductions,
        "net_pay": net_pay,
        "pension_employer": monthly_pension_employer,
        "nsitf": monthly_nsitf,
        "itf": monthly_itf,
        "consolidated_relief": monthly_relief,
        "pension_relief": (annual_pension_employee / Decimal("12")).quantize(Decimal("0.01")),
        "nhf_relief": monthly_nhf,
        "taxable_income": monthly_taxable,
        "earnings_breakdown": earnings_breakdown,
        "deductions_breakdown": deductions_breakdown,
        "tax_calculation": tax_calculation,
        "bank_name": bank_name,
        "account_number": account_number,
        "account_name": account_name,
        "paid_at": paid_at,
    })
    
    # Create a mock payslip object for return value
    class PayslipResult:
        def __init__(self):
            self.id = payslip_id
            self.gross_pay = total_gross
            self.total_deductions = total_deductions
            self.net_pay = net_pay
            self.paye_tax = monthly_paye
            self.pension_employee = monthly_pension_emp
            self.nhf = monthly_nhf
            self.pension_employer = monthly_pension_employer
            self.nsitf = monthly_nsitf
            self.itf = monthly_itf
    
    payslip = PayslipResult()
    
    # Skip payslip_items creation due to model/database mismatch
    # The main payroll data is already complete in the payslips table
    
    return payslip


async def create_payslip_items(
    session: AsyncSession,
    payslip_id: uuid.UUID,
    basic: Decimal,
    housing: Decimal,
    transport: Decimal,
    meal: Decimal,
    utility: Decimal,
    paye: Decimal,
    pension_emp: Decimal,
    nhf: Decimal,
    pension_employer: Decimal,
    nsitf: Decimal,
    itf: Decimal
):
    """Create individual payslip line items."""
    items = [
        # Earnings
        PayslipItem(
            payslip_id=payslip_id,
            item_type=PayItemType.EARNING,
            category=PayItemCategory.BASIC_SALARY,
            name="Basic Salary",
            amount=basic,
        ),
        PayslipItem(
            payslip_id=payslip_id,
            item_type=PayItemType.EARNING,
            category=PayItemCategory.HOUSING_ALLOWANCE,
            name="Housing Allowance",
            amount=housing,
        ),
        PayslipItem(
            payslip_id=payslip_id,
            item_type=PayItemType.EARNING,
            category=PayItemCategory.TRANSPORT_ALLOWANCE,
            name="Transport Allowance",
            amount=transport,
        ),
    ]
    
    if meal > 0:
        items.append(PayslipItem(
            payslip_id=payslip_id,
            item_type=PayItemType.EARNING,
            category=PayItemCategory.MEAL_ALLOWANCE,
            name="Meal Allowance",
            amount=meal,
        ))
    
    if utility > 0:
        items.append(PayslipItem(
            payslip_id=payslip_id,
            item_type=PayItemType.EARNING,
            category=PayItemCategory.UTILITY_ALLOWANCE,
            name="Utility Allowance",
            amount=utility,
        ))
    
    # Deductions
    items.extend([
        PayslipItem(
            payslip_id=payslip_id,
            item_type=PayItemType.DEDUCTION,
            category=PayItemCategory.PAYE_TAX,
            name="PAYE Tax",
            amount=paye,
        ),
        PayslipItem(
            payslip_id=payslip_id,
            item_type=PayItemType.DEDUCTION,
            category=PayItemCategory.PENSION_EMPLOYEE,
            name="Pension (Employee 8%)",
            amount=pension_emp,
            is_percentage=True,
            percentage_value=Decimal("8.00"),
        ),
        PayslipItem(
            payslip_id=payslip_id,
            item_type=PayItemType.DEDUCTION,
            category=PayItemCategory.NHF,
            name="NHF (2.5%)",
            amount=nhf,
            is_percentage=True,
            percentage_value=Decimal("2.50"),
        ),
    ])
    
    # Employer contributions
    items.extend([
        PayslipItem(
            payslip_id=payslip_id,
            item_type=PayItemType.EMPLOYER_CONTRIBUTION,
            category=PayItemCategory.PENSION_EMPLOYER,
            name="Pension (Employer 10%)",
            amount=pension_employer,
            is_percentage=True,
            percentage_value=Decimal("10.00"),
        ),
        PayslipItem(
            payslip_id=payslip_id,
            item_type=PayItemType.EMPLOYER_CONTRIBUTION,
            category=PayItemCategory.NSITF,
            name="NSITF (1%)",
            amount=nsitf,
            is_percentage=True,
            percentage_value=Decimal("1.00"),
        ),
        PayslipItem(
            payslip_id=payslip_id,
            item_type=PayItemType.EMPLOYER_CONTRIBUTION,
            category=PayItemCategory.ITF,
            name="ITF (1%)",
            amount=itf,
            is_percentage=True,
            percentage_value=Decimal("1.00"),
        ),
    ])
    
    for item in items:
        session.add(item)
    
    await session.flush()


async def seed_payroll_history():
    """Main function to seed payroll history."""
    print("\n" + "=" * 70)
    print("  SEEDING PAYROLL HISTORY - Efe Obus Furniture Manufacturing LTD")
    print("=" * 70 + "\n")
    
    async with async_session_maker() as session:
        try:
            # Get entity and employees
            entity, employees = await get_entity_and_employees(session)
            
            if not entity:
                return
            
            print(f"[INFO] Entity: {entity.name}")
            print(f"[USERS] Total Employees: {len(employees)}")
            
            # Assign TINs to employees without them
            print("\n[SYNC] Assigning TINs to employees...")
            await assign_missing_tins(session, entity.id)
            
            # Determine payroll history range
            # Start from the earliest hire date or 2015, whichever is later
            earliest_hire = min(emp.hire_date for emp in employees)
            start_year = max(earliest_hire.year, 2015)
            end_year = 2025  # Up to December 2025
            
            print(f"\n[DATE] Creating payroll history from {start_year} to {end_year}...")
            print(f"   Total months: {(end_year - start_year + 1) * 12}")
            
            total_runs = 0
            total_payslips = 0
            
            for year in range(start_year, end_year + 1):
                year_runs = 0
                print(f"\n  Year {year}: ", end="", flush=True)
                
                for month in range(1, 13):
                    # Skip future months
                    if year == 2026 and month > 1:
                        break
                    
                    payroll_run = await create_payroll_run(
                        session, entity.id, year, month, employees
                    )
                    
                    if payroll_run:
                        total_runs += 1
                        year_runs += 1
                        total_payslips += payroll_run.total_employees
                        print("✓", end="", flush=True)
                    else:
                        print("·", end="", flush=True)
                
                print(f" ({year_runs} runs)")
            
            await session.commit()
            
            print("\n" + "=" * 70)
            print("  [OK] PAYROLL HISTORY SEEDING COMPLETE!")
            print("=" * 70)
            print(f"\n   Summary:")
            print(f"     • Payroll Runs Created: {total_runs}")
            print(f"     • Payslips Generated: {total_payslips}")
            print(f"     • Period: {start_year} - {end_year}")
            print(f"     • Employees with TINs: All employees now have TINs\n")
            
        except Exception as e:
            await session.rollback()
            print(f"\n[FAIL] Error seeding payroll history: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(seed_payroll_history())
