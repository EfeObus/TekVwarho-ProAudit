"""
TekVwarho ProAudit - Payroll Service

Comprehensive payroll calculation service with Nigerian compliance.

Nigerian Statutory Requirements:
1. PAYE (Pay As You Earn) - Personal Income Tax
   - 2026 Tax Bands apply
   - Consolidated Relief Allowance (CRA) = ₦200,000 or 1% (higher) + 20% of gross
   
2. Pension (Contributory Pension Scheme)
   - Employee: 8% of (Basic + Housing + Transport)
   - Employer: 10% of (Basic + Housing + Transport)
   - Regulated by PenCom
   
3. NHF (National Housing Fund)
   - 2.5% of Basic Salary
   - Employee contribution only
   
4. NSITF (Nigeria Social Insurance Trust Fund)
   - 1% of monthly payroll
   - Employer contribution only
   
5. ITF (Industrial Training Fund)
   - 1% of annual payroll
   - Employer contribution (companies with 5+ employees or ₦50M+ turnover)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any
from calendar import monthrange

from sqlalchemy import select, func, and_, or_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payroll import (
    Employee, EmployeeBankAccount, PayrollRun, Payslip, PayslipItem,
    StatutoryRemittance, EmploymentStatus, PayrollStatus, PayrollFrequency,
    PayItemType, PayItemCategory
)
from app.services.tax_calculators.paye_service import PAYECalculator


# ===========================================
# CONSTANTS
# ===========================================

# Pension rates
PENSION_EMPLOYEE_RATE = Decimal("8")  # 8%
PENSION_EMPLOYER_RATE = Decimal("10")  # 10%

# NHF rate
NHF_RATE = Decimal("2.5")  # 2.5% of basic salary

# NSITF rate (employer only)
NSITF_RATE = Decimal("1")  # 1% of monthly payroll

# ITF rate (employer only, companies with 5+ employees)
ITF_RATE = Decimal("1")  # 1% of annual payroll
ITF_EMPLOYEE_THRESHOLD = 5

# Minimum wage (Nigeria 2024)
MINIMUM_WAGE = Decimal("70000")


class PayrollService:
    """
    Payroll service for managing employees and processing payroll.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.paye_calculator = PAYECalculator()
    
    # ===========================================
    # EMPLOYEE MANAGEMENT
    # ===========================================
    
    async def create_employee(
        self,
        entity_id: uuid.UUID,
        data: Dict[str, Any],
        created_by_id: Optional[uuid.UUID] = None,
    ) -> Employee:
        """Create a new employee."""
        # Check for duplicate employee_id
        existing = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.entity_id == entity_id,
                    Employee.employee_id == data["employee_id"]
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Employee ID {data['employee_id']} already exists")
        
        # Extract bank accounts if provided
        bank_accounts_data = data.pop("bank_accounts", None)
        
        # Create employee
        employee = Employee(
            entity_id=entity_id,
            created_by_id=created_by_id,
            **data
        )
        self.db.add(employee)
        await self.db.flush()
        
        # Create bank accounts
        if bank_accounts_data:
            for ba_data in bank_accounts_data:
                bank_account = EmployeeBankAccount(
                    employee_id=employee.id,
                    **ba_data
                )
                self.db.add(bank_account)
        
        await self.db.commit()
        await self.db.refresh(employee)
        
        return employee
    
    async def get_employee(
        self,
        entity_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> Optional[Employee]:
        """Get employee by ID."""
        result = await self.db.execute(
            select(Employee)
            .options(selectinload(Employee.bank_accounts))
            .where(
                and_(
                    Employee.id == employee_id,
                    Employee.entity_id == entity_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_employee_by_staff_id(
        self,
        entity_id: uuid.UUID,
        staff_id: str,
    ) -> Optional[Employee]:
        """Get employee by staff/employee ID."""
        result = await self.db.execute(
            select(Employee)
            .options(selectinload(Employee.bank_accounts))
            .where(
                and_(
                    Employee.employee_id == staff_id,
                    Employee.entity_id == entity_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_employees(
        self,
        entity_id: uuid.UUID,
        status: Optional[EmploymentStatus] = None,
        department: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Tuple[List[Employee], int]:
        """List employees with filters and pagination."""
        query = select(Employee).where(Employee.entity_id == entity_id)
        
        if status:
            query = query.where(Employee.employment_status == status)
        
        if department:
            query = query.where(Employee.department == department)
        
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.email.ilike(search_term),
                    Employee.employee_id.ilike(search_term),
                )
            )
        
        # Count total
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        
        # Apply pagination
        query = query.order_by(Employee.last_name, Employee.first_name)
        query = query.offset((page - 1) * per_page).limit(per_page)
        query = query.options(selectinload(Employee.bank_accounts))
        
        result = await self.db.execute(query)
        employees = result.scalars().all()
        
        return list(employees), total
    
    async def update_employee(
        self,
        entity_id: uuid.UUID,
        employee_id: uuid.UUID,
        data: Dict[str, Any],
        updated_by_id: Optional[uuid.UUID] = None,
    ) -> Optional[Employee]:
        """Update employee details."""
        employee = await self.get_employee(entity_id, employee_id)
        if not employee:
            return None
        
        for key, value in data.items():
            if value is not None and hasattr(employee, key):
                setattr(employee, key, value)
        
        employee.updated_by_id = updated_by_id
        
        await self.db.commit()
        await self.db.refresh(employee)
        
        return employee
    
    async def add_bank_account(
        self,
        entity_id: uuid.UUID,
        employee_id: uuid.UUID,
        data: Dict[str, Any],
    ) -> EmployeeBankAccount:
        """Add bank account to employee."""
        employee = await self.get_employee(entity_id, employee_id)
        if not employee:
            raise ValueError("Employee not found")
        
        # If setting as primary, unset other primary accounts
        if data.get("is_primary", True):
            await self.db.execute(
                select(EmployeeBankAccount)
                .where(EmployeeBankAccount.employee_id == employee_id)
            )
            for ba in employee.bank_accounts:
                ba.is_primary = False
        
        bank_account = EmployeeBankAccount(
            employee_id=employee_id,
            **data
        )
        self.db.add(bank_account)
        await self.db.commit()
        await self.db.refresh(bank_account)
        
        return bank_account
    
    async def get_active_employees_count(self, entity_id: uuid.UUID) -> int:
        """Get count of active employees."""
        result = await self.db.execute(
            select(func.count())
            .select_from(Employee)
            .where(
                and_(
                    Employee.entity_id == entity_id,
                    Employee.employment_status == EmploymentStatus.ACTIVE,
                    Employee.is_active == True
                )
            )
        )
        return result.scalar() or 0
    
    async def get_departments(self, entity_id: uuid.UUID) -> List[str]:
        """Get list of unique departments."""
        result = await self.db.execute(
            select(Employee.department)
            .where(
                and_(
                    Employee.entity_id == entity_id,
                    Employee.department.isnot(None)
                )
            )
            .distinct()
        )
        return [r[0] for r in result.all() if r[0]]
    
    # ===========================================
    # SALARY CALCULATIONS
    # ===========================================
    
    def calculate_salary_breakdown(
        self,
        basic_salary: Decimal,
        housing_allowance: Decimal = Decimal("0"),
        transport_allowance: Decimal = Decimal("0"),
        other_allowances: Optional[Dict[str, float]] = None,
        pension_percentage: Decimal = PENSION_EMPLOYEE_RATE,
        is_pension_exempt: bool = False,
        is_nhf_exempt: bool = False,
    ) -> Dict[str, Any]:
        """
        Calculate complete salary breakdown with Nigerian compliance.
        
        Returns monthly and annual figures for all components.
        """
        # Convert other allowances
        other_allowances_decimal = {}
        total_other = Decimal("0")
        if other_allowances:
            for key, value in other_allowances.items():
                amount = Decimal(str(value))
                other_allowances_decimal[key] = amount
                total_other += amount
        
        # Monthly gross
        monthly_gross = basic_salary + housing_allowance + transport_allowance + total_other
        annual_gross = monthly_gross * 12
        
        # Pensionable earnings (Basic + Housing + Transport per PenCom)
        monthly_pensionable = basic_salary + housing_allowance + transport_allowance
        annual_pensionable = monthly_pensionable * 12
        
        # Calculate employee pension contribution
        if is_pension_exempt:
            monthly_pension_employee = Decimal("0")
            pension_relief = Decimal("0")
        else:
            monthly_pension_employee = (monthly_pensionable * pension_percentage / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            pension_relief = monthly_pension_employee * 12
        
        # Calculate NHF
        if is_nhf_exempt:
            monthly_nhf = Decimal("0")
            nhf_relief = Decimal("0")
        else:
            monthly_nhf = (basic_salary * NHF_RATE / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            nhf_relief = monthly_nhf * 12
        
        # Use PAYE calculator for tax
        paye_result = self.paye_calculator.calculate_paye(
            gross_annual_income=float(annual_gross),
            basic_salary=float(basic_salary * 12),
            pension_percentage=float(pension_percentage) if not is_pension_exempt else 0,
            other_reliefs=float(nhf_relief) if not is_nhf_exempt else 0,
        )
        
        annual_paye = Decimal(str(paye_result["annual_tax"]))
        monthly_paye = (annual_paye / 12).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        cra = Decimal(str(paye_result["reliefs"]["consolidated_relief"]))
        annual_taxable = Decimal(str(paye_result["taxable_income"]))
        
        # Total reliefs
        total_reliefs = cra + pension_relief + nhf_relief
        
        # Monthly deductions
        total_monthly_deductions = monthly_paye + monthly_pension_employee + monthly_nhf
        
        # Net pay
        monthly_net = monthly_gross - total_monthly_deductions
        annual_net = monthly_net * 12
        
        # Employer contributions
        if is_pension_exempt:
            monthly_pension_employer = Decimal("0")
        else:
            monthly_pension_employer = (monthly_pensionable * PENSION_EMPLOYER_RATE / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        
        monthly_nsitf = (monthly_gross * NSITF_RATE / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        monthly_itf = (annual_gross * ITF_RATE / 100 / 12).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        # Total employer cost
        total_employer_cost = monthly_gross + monthly_pension_employer + monthly_nsitf + monthly_itf
        
        # Effective tax rate
        effective_rate = Decimal("0")
        if annual_gross > 0:
            effective_rate = (annual_paye / annual_gross * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        
        return {
            # Earnings
            "basic_salary": basic_salary,
            "housing_allowance": housing_allowance,
            "transport_allowance": transport_allowance,
            "other_allowances": other_allowances_decimal,
            "monthly_gross": monthly_gross,
            "annual_gross": annual_gross,
            
            # Reliefs (Annual)
            "consolidated_relief_allowance": cra,
            "pension_relief": pension_relief,
            "nhf_relief": nhf_relief,
            "total_reliefs": total_reliefs,
            
            # Taxable
            "annual_taxable_income": annual_taxable,
            "monthly_taxable_income": (annual_taxable / 12).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            
            # Tax (PAYE)
            "annual_paye": annual_paye,
            "monthly_paye": monthly_paye,
            "paye_breakdown": paye_result.get("band_breakdown", []),
            "effective_tax_rate": effective_rate,
            
            # Deductions (Monthly)
            "pension_employee": monthly_pension_employee,
            "nhf": monthly_nhf,
            "total_monthly_deductions": total_monthly_deductions,
            
            # Net
            "monthly_net_pay": monthly_net,
            "annual_net_pay": annual_net,
            
            # Employer contributions (Monthly)
            "pension_employer": monthly_pension_employer,
            "nsitf": monthly_nsitf,
            "itf": monthly_itf,
            "total_employer_cost": total_employer_cost,
        }
    
    # ===========================================
    # PAYROLL PROCESSING
    # ===========================================
    
    async def create_payroll_run(
        self,
        entity_id: uuid.UUID,
        name: str,
        period_start: date,
        period_end: date,
        payment_date: date,
        frequency: PayrollFrequency = PayrollFrequency.MONTHLY,
        description: Optional[str] = None,
        employee_ids: Optional[List[uuid.UUID]] = None,
        created_by_id: Optional[uuid.UUID] = None,
    ) -> PayrollRun:
        """
        Create a new payroll run and generate payslips for all active employees.
        """
        # Generate payroll code
        year = period_start.year
        month = period_start.month
        
        # Check for existing payroll in same period
        existing = await self.db.execute(
            select(PayrollRun).where(
                and_(
                    PayrollRun.entity_id == entity_id,
                    PayrollRun.period_start == period_start,
                    PayrollRun.period_end == period_end,
                    PayrollRun.status != PayrollStatus.CANCELLED
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Payroll already exists for period {period_start} to {period_end}")
        
        # Count existing payrolls for the year to generate sequence
        count_result = await self.db.execute(
            select(func.count())
            .select_from(PayrollRun)
            .where(
                and_(
                    PayrollRun.entity_id == entity_id,
                    extract('year', PayrollRun.period_start) == year
                )
            )
        )
        sequence = (count_result.scalar() or 0) + 1
        
        payroll_code = f"PAY-{year}-{month:02d}-{sequence:03d}"
        
        # Create payroll run
        payroll_run = PayrollRun(
            entity_id=entity_id,
            payroll_code=payroll_code,
            name=name,
            description=description,
            frequency=frequency,
            period_start=period_start,
            period_end=period_end,
            payment_date=payment_date,
            status=PayrollStatus.DRAFT,
            created_by_id=created_by_id,
        )
        self.db.add(payroll_run)
        await self.db.flush()
        
        # Get employees to include
        if employee_ids:
            employees_query = select(Employee).where(
                and_(
                    Employee.entity_id == entity_id,
                    Employee.id.in_(employee_ids),
                    Employee.is_active == True
                )
            ).options(selectinload(Employee.bank_accounts))
        else:
            employees_query = select(Employee).where(
                and_(
                    Employee.entity_id == entity_id,
                    Employee.employment_status == EmploymentStatus.ACTIVE,
                    Employee.is_active == True
                )
            ).options(selectinload(Employee.bank_accounts))
        
        result = await self.db.execute(employees_query)
        employees = result.scalars().all()
        
        if not employees:
            raise ValueError("No active employees found for payroll processing")
        
        # Calculate days in period
        days_in_period = (period_end - period_start).days + 1
        
        # Generate payslips
        payslip_sequence = 0
        total_gross = Decimal("0")
        total_deductions = Decimal("0")
        total_net = Decimal("0")
        total_employer_contributions = Decimal("0")
        total_paye = Decimal("0")
        total_pension_employee = Decimal("0")
        total_pension_employer = Decimal("0")
        total_nhf = Decimal("0")
        total_nsitf = Decimal("0")
        total_itf = Decimal("0")
        
        for employee in employees:
            payslip_sequence += 1
            payslip = await self._generate_payslip(
                payroll_run=payroll_run,
                employee=employee,
                payslip_number=f"{payroll_code}-{payslip_sequence:04d}",
                days_in_period=days_in_period,
            )
            
            # Accumulate totals
            total_gross += payslip.gross_pay
            total_deductions += payslip.total_deductions
            total_net += payslip.net_pay
            total_employer_contributions += (
                payslip.pension_employer + payslip.nsitf + payslip.itf
            )
            total_paye += payslip.paye_tax
            total_pension_employee += payslip.pension_employee
            total_pension_employer += payslip.pension_employer
            total_nhf += payslip.nhf
            total_nsitf += payslip.nsitf
            total_itf += payslip.itf
        
        # Update payroll run totals
        payroll_run.total_employees = len(employees)
        payroll_run.total_gross_pay = total_gross
        payroll_run.total_deductions = total_deductions
        payroll_run.total_net_pay = total_net
        payroll_run.total_employer_contributions = total_employer_contributions
        payroll_run.total_paye = total_paye
        payroll_run.total_pension_employee = total_pension_employee
        payroll_run.total_pension_employer = total_pension_employer
        payroll_run.total_nhf = total_nhf
        payroll_run.total_nsitf = total_nsitf
        payroll_run.total_itf = total_itf
        
        await self.db.commit()
        await self.db.refresh(payroll_run)
        
        return payroll_run
    
    async def _generate_payslip(
        self,
        payroll_run: PayrollRun,
        employee: Employee,
        payslip_number: str,
        days_in_period: int,
        days_worked: Optional[int] = None,
    ) -> Payslip:
        """Generate payslip for an employee."""
        if days_worked is None:
            days_worked = days_in_period
        
        days_absent = days_in_period - days_worked
        
        # Pro-rate if partial month
        prorate_factor = Decimal(str(days_worked)) / Decimal(str(days_in_period))
        
        # Calculate earnings
        basic = (employee.basic_salary * prorate_factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        housing = (employee.housing_allowance * prorate_factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        transport = (employee.transport_allowance * prorate_factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        other_earnings = Decimal("0")
        other_allowances_dict = {}
        if employee.other_allowances:
            for key, value in employee.other_allowances.items():
                amount = (Decimal(str(value)) * prorate_factor).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                other_allowances_dict[key] = float(amount)
                other_earnings += amount
        
        gross = basic + housing + transport + other_earnings
        
        # Calculate using full salary for tax (annualized then monthly)
        salary_breakdown = self.calculate_salary_breakdown(
            basic_salary=employee.basic_salary,
            housing_allowance=employee.housing_allowance,
            transport_allowance=employee.transport_allowance,
            other_allowances=employee.other_allowances,
            is_pension_exempt=employee.is_pension_exempt,
            is_nhf_exempt=employee.is_nhf_exempt,
        )
        
        # Apply pro-rata to calculated values
        paye = (salary_breakdown["monthly_paye"] * prorate_factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        pension_employee = (salary_breakdown["pension_employee"] * prorate_factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        nhf = (salary_breakdown["nhf"] * prorate_factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        total_deductions = paye + pension_employee + nhf
        net = gross - total_deductions
        
        # Employer contributions
        pension_employer = (salary_breakdown["pension_employer"] * prorate_factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        nsitf = (salary_breakdown["nsitf"] * prorate_factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        itf = (salary_breakdown["itf"] * prorate_factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        # Get primary bank account
        primary_bank = None
        for ba in employee.bank_accounts:
            if ba.is_primary and ba.is_active:
                primary_bank = ba
                break
        
        # Create payslip
        payslip = Payslip(
            payroll_run_id=payroll_run.id,
            employee_id=employee.id,
            payslip_number=payslip_number,
            days_in_period=days_in_period,
            days_worked=days_worked,
            days_absent=days_absent,
            
            # Earnings
            basic_salary=basic,
            housing_allowance=housing,
            transport_allowance=transport,
            other_earnings=other_earnings,
            gross_pay=gross,
            
            # Deductions
            paye_tax=paye,
            pension_employee=pension_employee,
            nhf=nhf,
            other_deductions=Decimal("0"),
            total_deductions=total_deductions,
            
            # Net
            net_pay=net,
            
            # Employer contributions
            pension_employer=pension_employer,
            nsitf=nsitf,
            itf=itf,
            
            # Tax calculation details
            consolidated_relief=salary_breakdown["consolidated_relief_allowance"],
            taxable_income=salary_breakdown["annual_taxable_income"],
            
            # Breakdowns
            earnings_breakdown={
                "basic_salary": float(basic),
                "housing_allowance": float(housing),
                "transport_allowance": float(transport),
                **other_allowances_dict,
            },
            deductions_breakdown={
                "paye_tax": float(paye),
                "pension_employee": float(pension_employee),
                "nhf": float(nhf),
            },
            tax_calculation={
                "annual_gross": float(salary_breakdown["annual_gross"]),
                "annual_taxable": float(salary_breakdown["annual_taxable_income"]),
                "annual_paye": float(salary_breakdown["annual_paye"]),
                "cra": float(salary_breakdown["consolidated_relief_allowance"]),
                "effective_rate": float(salary_breakdown["effective_tax_rate"]),
                "bands": salary_breakdown["paye_breakdown"],
            },
            
            # Bank details
            bank_name=primary_bank.bank_name.value if primary_bank else None,
            account_number=primary_bank.account_number if primary_bank else None,
            account_name=primary_bank.account_name if primary_bank else None,
        )
        self.db.add(payslip)
        await self.db.flush()
        
        # Create payslip line items
        await self._create_payslip_items(payslip, employee, salary_breakdown, prorate_factor)
        
        return payslip
    
    async def _create_payslip_items(
        self,
        payslip: Payslip,
        employee: Employee,
        breakdown: Dict[str, Any],
        prorate_factor: Decimal,
    ):
        """Create detailed payslip line items."""
        items = []
        sort_order = 0
        
        # Earnings
        earnings = [
            (PayItemCategory.BASIC_SALARY, "Basic Salary", payslip.basic_salary, True, True),
            (PayItemCategory.HOUSING_ALLOWANCE, "Housing Allowance", payslip.housing_allowance, True, True),
            (PayItemCategory.TRANSPORT_ALLOWANCE, "Transport Allowance", payslip.transport_allowance, True, True),
        ]
        
        for category, name, amount, taxable, pensionable in earnings:
            if amount > 0:
                sort_order += 1
                items.append(PayslipItem(
                    payslip_id=payslip.id,
                    item_type=PayItemType.EARNING,
                    category=category,
                    name=name,
                    amount=amount,
                    is_statutory=False,
                    is_taxable=taxable,
                    is_pensionable=pensionable,
                    sort_order=sort_order,
                ))
        
        # Other earnings
        if employee.other_allowances:
            for name, value in employee.other_allowances.items():
                amount = (Decimal(str(value)) * prorate_factor).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if amount > 0:
                    sort_order += 1
                    items.append(PayslipItem(
                        payslip_id=payslip.id,
                        item_type=PayItemType.EARNING,
                        category=PayItemCategory.OTHER_EARNING,
                        name=name.replace("_", " ").title(),
                        amount=amount,
                        is_statutory=False,
                        is_taxable=True,
                        is_pensionable=False,
                        sort_order=sort_order,
                    ))
        
        # Deductions
        deductions = [
            (PayItemCategory.PAYE_TAX, "PAYE Tax", payslip.paye_tax, True),
            (PayItemCategory.PENSION_EMPLOYEE, "Pension (Employee 8%)", payslip.pension_employee, True),
            (PayItemCategory.NHF, "NHF (2.5%)", payslip.nhf, True),
        ]
        
        for category, name, amount, statutory in deductions:
            if amount > 0:
                sort_order += 1
                items.append(PayslipItem(
                    payslip_id=payslip.id,
                    item_type=PayItemType.DEDUCTION,
                    category=category,
                    name=name,
                    amount=amount,
                    is_statutory=statutory,
                    is_taxable=False,
                    is_pensionable=False,
                    sort_order=sort_order,
                ))
        
        # Employer contributions
        employer_items = [
            (PayItemCategory.PENSION_EMPLOYER, "Pension (Employer 10%)", payslip.pension_employer),
            (PayItemCategory.NSITF, "NSITF (1%)", payslip.nsitf),
            (PayItemCategory.ITF, "ITF (1%)", payslip.itf),
        ]
        
        for category, name, amount in employer_items:
            if amount > 0:
                sort_order += 1
                items.append(PayslipItem(
                    payslip_id=payslip.id,
                    item_type=PayItemType.EMPLOYER_CONTRIBUTION,
                    category=category,
                    name=name,
                    amount=amount,
                    is_statutory=True,
                    is_taxable=False,
                    is_pensionable=False,
                    sort_order=sort_order,
                ))
        
        for item in items:
            self.db.add(item)
    
    async def get_payroll_run(
        self,
        entity_id: uuid.UUID,
        payroll_id: uuid.UUID,
    ) -> Optional[PayrollRun]:
        """Get payroll run by ID."""
        result = await self.db.execute(
            select(PayrollRun)
            .options(selectinload(PayrollRun.payslips))
            .where(
                and_(
                    PayrollRun.id == payroll_id,
                    PayrollRun.entity_id == entity_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_payroll_runs(
        self,
        entity_id: uuid.UUID,
        status: Optional[PayrollStatus] = None,
        year: Optional[int] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[PayrollRun], int]:
        """List payroll runs with filters."""
        query = select(PayrollRun).where(PayrollRun.entity_id == entity_id)
        
        if status:
            query = query.where(PayrollRun.status == status)
        
        if year:
            query = query.where(extract('year', PayrollRun.period_start) == year)
        
        # Count
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        
        # Paginate
        query = query.order_by(PayrollRun.period_start.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        
        result = await self.db.execute(query)
        runs = result.scalars().all()
        
        return list(runs), total
    
    async def approve_payroll(
        self,
        entity_id: uuid.UUID,
        payroll_id: uuid.UUID,
        approved_by_id: uuid.UUID,
    ) -> PayrollRun:
        """Approve a payroll run."""
        payroll = await self.get_payroll_run(entity_id, payroll_id)
        if not payroll:
            raise ValueError("Payroll run not found")
        
        if payroll.status not in [PayrollStatus.DRAFT, PayrollStatus.PENDING_APPROVAL]:
            raise ValueError(f"Cannot approve payroll in {payroll.status} status")
        
        payroll.status = PayrollStatus.APPROVED
        payroll.approved_by_id = approved_by_id
        payroll.approved_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(payroll)
        
        return payroll
    
    async def process_payroll(
        self,
        entity_id: uuid.UUID,
        payroll_id: uuid.UUID,
    ) -> PayrollRun:
        """Process approved payroll (mark as ready for payment)."""
        payroll = await self.get_payroll_run(entity_id, payroll_id)
        if not payroll:
            raise ValueError("Payroll run not found")
        
        if payroll.status != PayrollStatus.APPROVED:
            raise ValueError("Only approved payroll can be processed")
        
        payroll.status = PayrollStatus.PROCESSING
        payroll.processed_at = datetime.utcnow()
        
        # Create statutory remittance records
        await self._create_remittances(payroll)
        
        payroll.status = PayrollStatus.COMPLETED
        
        await self.db.commit()
        await self.db.refresh(payroll)
        
        return payroll
    
    async def _create_remittances(self, payroll: PayrollRun):
        """Create statutory remittance records for a payroll."""
        period_month = payroll.period_start.month
        period_year = payroll.period_start.year
        
        # Due dates (typically 10th of following month for PAYE, varies for others)
        next_month = payroll.period_end.month + 1
        next_year = payroll.period_end.year
        if next_month > 12:
            next_month = 1
            next_year += 1
        
        remittances = [
            ("paye", payroll.total_paye, date(next_year, next_month, 10)),
            ("pension", payroll.total_pension_employee + payroll.total_pension_employer, 
             date(next_year, next_month, 7)),
            ("nhf", payroll.total_nhf, date(next_year, next_month, 10)),
            ("nsitf", payroll.total_nsitf, date(next_year, next_month, 15)),
            ("itf", payroll.total_itf, date(next_year, next_month, 15)),
        ]
        
        for rem_type, amount, due_date in remittances:
            if amount > 0:
                # Check if already exists
                existing = await self.db.execute(
                    select(StatutoryRemittance).where(
                        and_(
                            StatutoryRemittance.entity_id == payroll.entity_id,
                            StatutoryRemittance.remittance_type == rem_type,
                            StatutoryRemittance.period_month == period_month,
                            StatutoryRemittance.period_year == period_year
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                
                remittance = StatutoryRemittance(
                    entity_id=payroll.entity_id,
                    payroll_run_id=payroll.id,
                    remittance_type=rem_type,
                    period_month=period_month,
                    period_year=period_year,
                    amount_due=amount,
                    due_date=due_date,
                )
                self.db.add(remittance)
    
    async def mark_payroll_paid(
        self,
        entity_id: uuid.UUID,
        payroll_id: uuid.UUID,
    ) -> PayrollRun:
        """Mark payroll as paid."""
        payroll = await self.get_payroll_run(entity_id, payroll_id)
        if not payroll:
            raise ValueError("Payroll run not found")
        
        if payroll.status != PayrollStatus.COMPLETED:
            raise ValueError("Only completed payroll can be marked as paid")
        
        payroll.status = PayrollStatus.PAID
        payroll.paid_at = datetime.utcnow()
        
        # Mark all payslips as paid
        for payslip in payroll.payslips:
            payslip.is_paid = True
            payslip.paid_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(payroll)
        
        return payroll
    
    # ===========================================
    # PAYSLIP RETRIEVAL
    # ===========================================
    
    async def get_payslip(
        self,
        entity_id: uuid.UUID,
        payslip_id: uuid.UUID,
    ) -> Optional[Payslip]:
        """Get payslip by ID."""
        result = await self.db.execute(
            select(Payslip)
            .join(PayrollRun)
            .options(
                selectinload(Payslip.items),
                selectinload(Payslip.employee),
            )
            .where(
                and_(
                    Payslip.id == payslip_id,
                    PayrollRun.entity_id == entity_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_payslips_for_payroll(
        self,
        entity_id: uuid.UUID,
        payroll_id: uuid.UUID,
    ) -> List[Payslip]:
        """Get all payslips for a payroll run."""
        result = await self.db.execute(
            select(Payslip)
            .join(PayrollRun)
            .options(selectinload(Payslip.employee))
            .where(
                and_(
                    Payslip.payroll_run_id == payroll_id,
                    PayrollRun.entity_id == entity_id
                )
            )
            .order_by(Payslip.payslip_number)
        )
        return list(result.scalars().all())
    
    async def get_employee_payslips(
        self,
        entity_id: uuid.UUID,
        employee_id: uuid.UUID,
        year: Optional[int] = None,
    ) -> List[Payslip]:
        """Get all payslips for an employee."""
        query = (
            select(Payslip)
            .join(PayrollRun)
            .where(
                and_(
                    Payslip.employee_id == employee_id,
                    PayrollRun.entity_id == entity_id
                )
            )
        )
        
        if year:
            query = query.where(extract('year', PayrollRun.period_start) == year)
        
        query = query.order_by(PayrollRun.period_start.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    # ===========================================
    # BANK SCHEDULE
    # ===========================================
    
    async def generate_bank_schedule(
        self,
        entity_id: uuid.UUID,
        payroll_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Generate bank payment schedule for a payroll."""
        payroll = await self.get_payroll_run(entity_id, payroll_id)
        if not payroll:
            raise ValueError("Payroll run not found")
        
        payslips = await self.list_payslips_for_payroll(entity_id, payroll_id)
        
        items = []
        total_amount = Decimal("0")
        
        for payslip in payslips:
            if payslip.net_pay > 0 and payslip.account_number:
                items.append({
                    "employee_id": payslip.employee.employee_id,
                    "employee_name": payslip.employee.full_name,
                    "bank_name": payslip.bank_name or "N/A",
                    "account_number": payslip.account_number,
                    "account_name": payslip.account_name or payslip.employee.full_name,
                    "amount": payslip.net_pay,
                    "narration": f"Salary - {payroll.name}",
                })
                total_amount += payslip.net_pay
        
        return {
            "payroll_code": payroll.payroll_code,
            "payment_date": payroll.payment_date,
            "total_amount": total_amount,
            "total_employees": len(items),
            "items": items,
        }
    
    # ===========================================
    # REMITTANCES
    # ===========================================
    
    async def list_remittances(
        self,
        entity_id: uuid.UUID,
        remittance_type: Optional[str] = None,
        is_paid: Optional[bool] = None,
        year: Optional[int] = None,
    ) -> List[StatutoryRemittance]:
        """List statutory remittances."""
        query = select(StatutoryRemittance).where(
            StatutoryRemittance.entity_id == entity_id
        )
        
        if remittance_type:
            query = query.where(StatutoryRemittance.remittance_type == remittance_type)
        
        if is_paid is not None:
            query = query.where(StatutoryRemittance.is_paid == is_paid)
        
        if year:
            query = query.where(StatutoryRemittance.period_year == year)
        
        query = query.order_by(
            StatutoryRemittance.period_year.desc(),
            StatutoryRemittance.period_month.desc()
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def mark_remittance_paid(
        self,
        entity_id: uuid.UUID,
        remittance_id: uuid.UUID,
        payment_date: date,
        payment_reference: str,
        receipt_number: Optional[str] = None,
    ) -> StatutoryRemittance:
        """Mark a remittance as paid."""
        result = await self.db.execute(
            select(StatutoryRemittance).where(
                and_(
                    StatutoryRemittance.id == remittance_id,
                    StatutoryRemittance.entity_id == entity_id
                )
            )
        )
        remittance = result.scalar_one_or_none()
        
        if not remittance:
            raise ValueError("Remittance not found")
        
        remittance.is_paid = True
        remittance.amount_paid = remittance.amount_due
        remittance.payment_date = payment_date
        remittance.payment_reference = payment_reference
        remittance.receipt_number = receipt_number
        
        await self.db.commit()
        await self.db.refresh(remittance)
        
        return remittance
    
    # ===========================================
    # DASHBOARD & REPORTS
    # ===========================================
    
    async def get_payroll_dashboard(
        self,
        entity_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Get payroll dashboard statistics."""
        # Employee counts
        total_employees = await self.db.execute(
            select(func.count()).select_from(Employee).where(
                Employee.entity_id == entity_id
            )
        )
        total_employees = total_employees.scalar() or 0
        
        active_employees = await self.get_active_employees_count(entity_id)
        
        # Get active employees for salary calculations
        result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.entity_id == entity_id,
                    Employee.employment_status == EmploymentStatus.ACTIVE,
                    Employee.is_active == True
                )
            )
        )
        employees = result.scalars().all()
        
        total_monthly = sum(e.monthly_gross for e in employees)
        total_annual = total_monthly * 12
        avg_salary = total_monthly / active_employees if active_employees > 0 else Decimal("0")
        
        # Current month payroll
        current_date = date.today()
        current_month_result = await self.db.execute(
            select(PayrollRun).where(
                and_(
                    PayrollRun.entity_id == entity_id,
                    extract('month', PayrollRun.period_start) == current_date.month,
                    extract('year', PayrollRun.period_start) == current_date.year,
                    PayrollRun.status != PayrollStatus.CANCELLED
                )
            )
        )
        current_payroll = current_month_result.scalar_one_or_none()
        
        current_month_gross = current_payroll.total_gross_pay if current_payroll else Decimal("0")
        current_month_net = current_payroll.total_net_pay if current_payroll else Decimal("0")
        current_month_paye = current_payroll.total_paye if current_payroll else Decimal("0")
        current_month_pension = (
            current_payroll.total_pension_employee + current_payroll.total_pension_employer
            if current_payroll else Decimal("0")
        )
        current_month_nhf = current_payroll.total_nhf if current_payroll else Decimal("0")
        
        # Department breakdown
        dept_result = await self.db.execute(
            select(
                Employee.department,
                func.count().label('count'),
                func.sum(Employee.basic_salary + Employee.housing_allowance + Employee.transport_allowance).label('total')
            )
            .where(
                and_(
                    Employee.entity_id == entity_id,
                    Employee.employment_status == EmploymentStatus.ACTIVE
                )
            )
            .group_by(Employee.department)
        )
        department_breakdown = [
            {
                "department": row.department or "Unassigned",
                "employee_count": row.count,
                "total_salary": float(row.total or 0)
            }
            for row in dept_result.all()
        ]
        
        # Recent payroll runs
        recent_runs, _ = await self.list_payroll_runs(entity_id, page=1, per_page=5)
        
        # Pending remittances
        pending = await self.list_remittances(entity_id, is_paid=False)
        
        return {
            "total_employees": total_employees,
            "active_employees": active_employees,
            "total_monthly_payroll": total_monthly,
            "total_annual_payroll": total_annual,
            "average_salary": avg_salary,
            "current_month_gross": current_month_gross,
            "current_month_net": current_month_net,
            "current_month_paye": current_month_paye,
            "current_month_pension": current_month_pension,
            "current_month_nhf": current_month_nhf,
            "department_breakdown": department_breakdown,
            "recent_payroll_runs": recent_runs,
            "pending_remittances": pending,
        }
