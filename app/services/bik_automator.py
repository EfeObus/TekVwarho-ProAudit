"""
Benefit-in-Kind (BIK) Automator for Nigerian Executive Compensation

This module provides automated calculation of taxable benefit values for:
- Company-provided motor vehicles
- Housing allowances and accommodation
- Utility payments
- Driver/domestic staff
- Other non-cash benefits

Based on Nigerian 2026 Tax Reform BIK valuation rules.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import logging

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============================================================================
# 2026 Nigerian BIK Valuation Rules
# ============================================================================

class VehicleType(str, Enum):
    """Types of company vehicles"""
    SALOON_CAR = "saloon_car"
    SUV = "suv"
    PICKUP = "pickup"
    LUXURY = "luxury"
    UTILITY = "utility"
    MOTORCYCLE = "motorcycle"


class AccommodationType(str, Enum):
    """Types of company accommodation"""
    OWNED_PROPERTY = "owned_property"
    RENTED_FURNISHED = "rented_furnished"
    RENTED_UNFURNISHED = "rented_unfurnished"
    HOTEL = "hotel"
    COMPANY_QUARTERS = "company_quarters"


class UtilityType(str, Enum):
    """Types of utilities provided"""
    ELECTRICITY = "electricity"
    WATER = "water"
    GAS = "gas"
    INTERNET = "internet"
    TELEPHONE = "telephone"
    SECURITY = "security"


# BIK Rates for 2026 (as percentage of employee's annual basic salary)
BIK_RATES_2026 = {
    # Motor vehicles - percentage of vehicle cost per annum
    "vehicle": {
        VehicleType.SALOON_CAR: Decimal("0.05"),      # 5% of cost p.a.
        VehicleType.SUV: Decimal("0.05"),              # 5% of cost p.a.
        VehicleType.PICKUP: Decimal("0.04"),           # 4% of cost p.a.
        VehicleType.LUXURY: Decimal("0.07"),           # 7% of cost p.a.
        VehicleType.UTILITY: Decimal("0.03"),          # 3% of cost p.a.
        VehicleType.MOTORCYCLE: Decimal("0.025"),      # 2.5% of cost p.a.
    },
    
    # Accommodation - percentage of annual basic salary
    "accommodation": {
        AccommodationType.OWNED_PROPERTY: Decimal("0.075"),      # 7.5% of salary
        AccommodationType.RENTED_FURNISHED: Decimal("0.10"),      # 10% of salary
        AccommodationType.RENTED_UNFURNISHED: Decimal("0.075"),   # 7.5% of salary
        AccommodationType.HOTEL: Decimal("0.15"),                 # 15% of salary
        AccommodationType.COMPANY_QUARTERS: Decimal("0.05"),      # 5% of salary
    },
    
    # Driver benefit - fixed annual amount
    "driver": Decimal("600000.00"),  # N600,000 per annum
    
    # Domestic staff - fixed per staff member per annum
    "domestic_staff": Decimal("400000.00"),  # N400,000 per staff
    
    # Furniture/equipment allowance - percentage of cost per annum
    "furniture": Decimal("0.10"),  # 10% of cost
    
    # Generator/power backup - percentage of cost per annum
    "generator": Decimal("0.10"),  # 10% of cost
}

# Maximum BIK caps (to prevent excessive taxation)
BIK_CAPS = {
    "vehicle_max_cost": Decimal("50000000.00"),      # N50M vehicle cost cap
    "accommodation_max_rent": Decimal("36000000.00"), # N36M annual rent cap
    "utility_annual_max": Decimal("6000000.00"),      # N6M utilities cap
}


@dataclass
class BIKItem:
    """Individual BIK item with calculated value"""
    category: str
    description: str
    cost_or_value: Decimal
    bik_rate: Decimal
    annual_bik_value: Decimal
    monthly_bik_value: Decimal
    months_applicable: int
    prorated_bik_value: Decimal
    notes: Optional[str] = None


@dataclass
class BIKSummary:
    """Complete BIK summary for an employee"""
    employee_id: UUID
    employee_name: str
    tax_year: int
    annual_basic_salary: Decimal
    items: List[BIKItem]
    total_annual_bik: Decimal
    total_monthly_bik: Decimal
    bik_as_percentage_of_salary: Decimal
    paye_on_bik: Decimal
    effective_bik_date: date
    calculation_date: datetime
    warnings: List[str]


class BIKAutomatorService:
    """
    Benefit-in-Kind Automator Service
    
    Automatically calculates taxable values for non-cash benefits
    based on Nigerian 2026 Tax Reform valuation rules.
    """
    
    def __init__(self):
        self.rates = BIK_RATES_2026
        self.caps = BIK_CAPS
    
    def calculate_vehicle_bik(
        self,
        vehicle_type: VehicleType,
        vehicle_cost: Decimal,
        months_used: int = 12,
        private_use_percentage: Decimal = Decimal("100"),
        has_driver: bool = False,
    ) -> Tuple[BIKItem, Optional[BIKItem]]:
        """
        Calculate BIK for company-provided vehicle.
        
        Args:
            vehicle_type: Type of vehicle (saloon, SUV, luxury, etc.)
            vehicle_cost: Original cost of vehicle
            months_used: Months vehicle was available to employee
            private_use_percentage: Percentage of private use (0-100)
            has_driver: Whether company provides a driver
        
        Returns:
            Tuple of (vehicle BIK item, driver BIK item if applicable)
        """
        # Apply vehicle cost cap
        capped_cost = min(vehicle_cost, self.caps["vehicle_max_cost"])
        
        # Get rate based on vehicle type
        rate = self.rates["vehicle"].get(vehicle_type, Decimal("0.05"))
        
        # Calculate annual BIK
        annual_bik = (capped_cost * rate * private_use_percentage / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        monthly_bik = (annual_bik / Decimal("12")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        # Prorate for months used
        prorated = (annual_bik * Decimal(months_used) / Decimal("12")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        notes = None
        if vehicle_cost > self.caps["vehicle_max_cost"]:
            notes = f"Vehicle cost capped at N{self.caps['vehicle_max_cost']:,.2f}"
        
        vehicle_item = BIKItem(
            category="Motor Vehicle",
            description=f"{vehicle_type.value.replace('_', ' ').title()} - Company Provided",
            cost_or_value=vehicle_cost,
            bik_rate=rate,
            annual_bik_value=annual_bik,
            monthly_bik_value=monthly_bik,
            months_applicable=months_used,
            prorated_bik_value=prorated,
            notes=notes,
        )
        
        driver_item = None
        if has_driver:
            driver_annual = self.rates["driver"]
            driver_monthly = (driver_annual / Decimal("12")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            driver_prorated = (driver_annual * Decimal(months_used) / Decimal("12")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            
            driver_item = BIKItem(
                category="Driver Benefit",
                description="Company-Provided Driver",
                cost_or_value=driver_annual,
                bik_rate=Decimal("1.00"),
                annual_bik_value=driver_annual,
                monthly_bik_value=driver_monthly,
                months_applicable=months_used,
                prorated_bik_value=driver_prorated,
                notes="Fixed annual benefit value",
            )
        
        return vehicle_item, driver_item
    
    def calculate_accommodation_bik(
        self,
        accommodation_type: AccommodationType,
        annual_basic_salary: Decimal,
        actual_rent_paid: Optional[Decimal] = None,
        months_occupied: int = 12,
        is_furnished: bool = False,
        furniture_value: Optional[Decimal] = None,
    ) -> Tuple[BIKItem, Optional[BIKItem]]:
        """
        Calculate BIK for company-provided accommodation.
        
        For rented accommodation, BIK is the HIGHER of:
        - Actual rent paid by employer, OR
        - Percentage of employee's basic salary
        
        Args:
            accommodation_type: Type of accommodation
            annual_basic_salary: Employee's annual basic salary
            actual_rent_paid: Annual rent paid by employer (if rented)
            months_occupied: Months accommodation was provided
            is_furnished: Whether accommodation is furnished
            furniture_value: Value of furniture if provided separately
        """
        rate = self.rates["accommodation"].get(
            accommodation_type, Decimal("0.075")
        )
        
        # Calculate salary-based BIK
        salary_based_bik = (annual_basic_salary * rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        # For rented property, use higher of rent or salary percentage
        if actual_rent_paid and accommodation_type in [
            AccommodationType.RENTED_FURNISHED,
            AccommodationType.RENTED_UNFURNISHED,
        ]:
            # Cap the rent
            capped_rent = min(actual_rent_paid, self.caps["accommodation_max_rent"])
            annual_bik = max(salary_based_bik, capped_rent)
            notes = f"Higher of rent (N{capped_rent:,.2f}) or {rate*100}% of salary"
        else:
            annual_bik = salary_based_bik
            notes = f"{rate*100}% of annual basic salary"
        
        monthly_bik = (annual_bik / Decimal("12")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        prorated = (annual_bik * Decimal(months_occupied) / Decimal("12")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        accom_item = BIKItem(
            category="Accommodation",
            description=f"{accommodation_type.value.replace('_', ' ').title()}",
            cost_or_value=actual_rent_paid or salary_based_bik,
            bik_rate=rate,
            annual_bik_value=annual_bik,
            monthly_bik_value=monthly_bik,
            months_applicable=months_occupied,
            prorated_bik_value=prorated,
            notes=notes,
        )
        
        # Furniture BIK if applicable
        furniture_item = None
        if furniture_value and furniture_value > Decimal("0"):
            furn_rate = self.rates["furniture"]
            furn_annual = (furniture_value * furn_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            furn_monthly = (furn_annual / Decimal("12")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            furn_prorated = (furn_annual * Decimal(months_occupied) / Decimal("12")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            
            furniture_item = BIKItem(
                category="Furniture & Equipment",
                description="Company-Provided Furniture",
                cost_or_value=furniture_value,
                bik_rate=furn_rate,
                annual_bik_value=furn_annual,
                monthly_bik_value=furn_monthly,
                months_applicable=months_occupied,
                prorated_bik_value=furn_prorated,
                notes=f"{furn_rate*100}% of furniture value",
            )
        
        return accom_item, furniture_item
    
    def calculate_utility_bik(
        self,
        utility_type: UtilityType,
        annual_amount: Decimal,
        months_provided: int = 12,
    ) -> BIKItem:
        """
        Calculate BIK for company-paid utilities.
        
        Utilities paid by employer are fully taxable as BIK.
        """
        # Cap utilities
        capped_amount = min(annual_amount, self.caps["utility_annual_max"])
        
        monthly_amount = (capped_amount / Decimal("12")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        prorated = (capped_amount * Decimal(months_provided) / Decimal("12")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        notes = None
        if annual_amount > self.caps["utility_annual_max"]:
            notes = f"Amount capped at N{self.caps['utility_annual_max']:,.2f}"
        
        return BIKItem(
            category="Utilities",
            description=f"{utility_type.value.replace('_', ' ').title()} - Company Paid",
            cost_or_value=annual_amount,
            bik_rate=Decimal("1.00"),
            annual_bik_value=capped_amount,
            monthly_bik_value=monthly_amount,
            months_applicable=months_provided,
            prorated_bik_value=prorated,
            notes=notes or "Full amount taxable as BIK",
        )
    
    def calculate_domestic_staff_bik(
        self,
        number_of_staff: int,
        months_employed: int = 12,
    ) -> BIKItem:
        """
        Calculate BIK for company-provided domestic staff.
        """
        staff_rate = self.rates["domestic_staff"]
        annual_bik = (staff_rate * Decimal(number_of_staff)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        monthly_bik = (annual_bik / Decimal("12")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        prorated = (annual_bik * Decimal(months_employed) / Decimal("12")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        return BIKItem(
            category="Domestic Staff",
            description=f"{number_of_staff} Domestic Staff Member(s)",
            cost_or_value=staff_rate * number_of_staff,
            bik_rate=Decimal("1.00"),
            annual_bik_value=annual_bik,
            monthly_bik_value=monthly_bik,
            months_applicable=months_employed,
            prorated_bik_value=prorated,
            notes=f"N{staff_rate:,.0f} per staff member per annum",
        )
    
    def calculate_generator_bik(
        self,
        generator_cost: Decimal,
        months_available: int = 12,
        fuel_allowance: Optional[Decimal] = None,
    ) -> Tuple[BIKItem, Optional[BIKItem]]:
        """
        Calculate BIK for company-provided generator/power backup.
        """
        rate = self.rates["generator"]
        annual_bik = (generator_cost * rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        monthly_bik = (annual_bik / Decimal("12")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        prorated = (annual_bik * Decimal(months_available) / Decimal("12")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        gen_item = BIKItem(
            category="Generator/Power Backup",
            description="Company-Provided Generator",
            cost_or_value=generator_cost,
            bik_rate=rate,
            annual_bik_value=annual_bik,
            monthly_bik_value=monthly_bik,
            months_applicable=months_available,
            prorated_bik_value=prorated,
            notes=f"{rate*100}% of generator cost per annum",
        )
        
        fuel_item = None
        if fuel_allowance and fuel_allowance > Decimal("0"):
            fuel_monthly = (fuel_allowance / Decimal("12")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            fuel_prorated = (fuel_allowance * Decimal(months_available) / Decimal("12")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            
            fuel_item = BIKItem(
                category="Generator Fuel",
                description="Fuel Allowance for Generator",
                cost_or_value=fuel_allowance,
                bik_rate=Decimal("1.00"),
                annual_bik_value=fuel_allowance,
                monthly_bik_value=fuel_monthly,
                months_applicable=months_available,
                prorated_bik_value=fuel_prorated,
                notes="Full fuel allowance taxable",
            )
        
        return gen_item, fuel_item
    
    def calculate_paye_on_bik(
        self,
        annual_basic_salary: Decimal,
        total_annual_bik: Decimal,
    ) -> Decimal:
        """
        Calculate PAYE tax on BIK using progressive tax bands.
        
        BIK is added to gross income for PAYE calculation.
        Returns the additional PAYE attributable to BIK.
        """
        from app.services.payroll_service import PayrollService
        
        # Calculate PAYE on salary only
        paye_salary_only = self._calculate_paye(annual_basic_salary)
        
        # Calculate PAYE on salary + BIK
        total_income = annual_basic_salary + total_annual_bik
        paye_with_bik = self._calculate_paye(total_income)
        
        # The difference is PAYE on BIK
        return (paye_with_bik - paye_salary_only).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    
    def _calculate_paye(self, annual_income: Decimal) -> Decimal:
        """Calculate PAYE using 2026 tax bands."""
        # 2026 PAYE Bands
        PAYE_BANDS = [
            (Decimal("300000"), Decimal("0.07")),    # First N300k @ 7%
            (Decimal("300000"), Decimal("0.11")),    # Next N300k @ 11%
            (Decimal("500000"), Decimal("0.15")),    # Next N500k @ 15%
            (Decimal("500000"), Decimal("0.19")),    # Next N500k @ 19%
            (Decimal("1600000"), Decimal("0.21")),   # Next N1.6M @ 21%
            (None, Decimal("0.24")),                  # Above @ 24%
        ]
        
        # Consolidated Relief Allowance
        cra = max(
            Decimal("200000"),
            annual_income * Decimal("0.01")
        ) + (annual_income * Decimal("0.20"))
        
        taxable = max(Decimal("0"), annual_income - cra)
        
        tax = Decimal("0")
        remaining = taxable
        
        for band_limit, rate in PAYE_BANDS:
            if band_limit is None:
                # Top band - tax all remaining
                tax += remaining * rate
                break
            
            if remaining <= Decimal("0"):
                break
            
            taxable_in_band = min(remaining, band_limit)
            tax += taxable_in_band * rate
            remaining -= taxable_in_band
        
        return tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    async def generate_employee_bik_summary(
        self,
        db: AsyncSession,
        employee_id: UUID,
        tax_year: int,
        benefits: Dict[str, Any],
    ) -> BIKSummary:
        """
        Generate complete BIK summary for an employee.
        
        Args:
            db: Database session
            employee_id: Employee UUID
            tax_year: Tax year for calculation
            benefits: Dictionary of benefits with values
                {
                    "vehicle": {"type": "suv", "cost": 15000000, "has_driver": True},
                    "accommodation": {"type": "rented_furnished", "rent": 6000000},
                    "utilities": [{"type": "electricity", "amount": 1200000}],
                    ...
                }
        """
        from app.models.payroll import Employee
        
        # Get employee details
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        employee = result.scalar_one_or_none()
        
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")
        
        items: List[BIKItem] = []
        warnings: List[str] = []
        annual_basic_salary = Decimal(str(employee.basic_salary * 12))
        
        # Process vehicle benefit
        if "vehicle" in benefits:
            veh = benefits["vehicle"]
            vehicle_item, driver_item = self.calculate_vehicle_bik(
                vehicle_type=VehicleType(veh.get("type", "saloon_car")),
                vehicle_cost=Decimal(str(veh.get("cost", 0))),
                months_used=veh.get("months", 12),
                private_use_percentage=Decimal(str(veh.get("private_use", 100))),
                has_driver=veh.get("has_driver", False),
            )
            items.append(vehicle_item)
            if driver_item:
                items.append(driver_item)
        
        # Process accommodation benefit
        if "accommodation" in benefits:
            acc = benefits["accommodation"]
            accom_item, furniture_item = self.calculate_accommodation_bik(
                accommodation_type=AccommodationType(acc.get("type", "rented_unfurnished")),
                annual_basic_salary=annual_basic_salary,
                actual_rent_paid=Decimal(str(acc.get("rent", 0))) if acc.get("rent") else None,
                months_occupied=acc.get("months", 12),
                is_furnished=acc.get("furnished", False),
                furniture_value=Decimal(str(acc.get("furniture_value", 0))) if acc.get("furniture_value") else None,
            )
            items.append(accom_item)
            if furniture_item:
                items.append(furniture_item)
        
        # Process utilities
        if "utilities" in benefits:
            for util in benefits["utilities"]:
                util_item = self.calculate_utility_bik(
                    utility_type=UtilityType(util.get("type", "electricity")),
                    annual_amount=Decimal(str(util.get("amount", 0))),
                    months_provided=util.get("months", 12),
                )
                items.append(util_item)
        
        # Process domestic staff
        if "domestic_staff" in benefits:
            staff = benefits["domestic_staff"]
            staff_item = self.calculate_domestic_staff_bik(
                number_of_staff=staff.get("count", 1),
                months_employed=staff.get("months", 12),
            )
            items.append(staff_item)
        
        # Process generator
        if "generator" in benefits:
            gen = benefits["generator"]
            gen_item, fuel_item = self.calculate_generator_bik(
                generator_cost=Decimal(str(gen.get("cost", 0))),
                months_available=gen.get("months", 12),
                fuel_allowance=Decimal(str(gen.get("fuel", 0))) if gen.get("fuel") else None,
            )
            items.append(gen_item)
            if fuel_item:
                items.append(fuel_item)
        
        # Calculate totals
        total_annual = sum(item.annual_bik_value for item in items)
        total_monthly = sum(item.monthly_bik_value for item in items)
        
        # Calculate BIK as percentage of salary
        bik_percentage = Decimal("0")
        if annual_basic_salary > Decimal("0"):
            bik_percentage = (total_annual / annual_basic_salary * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        
        # Calculate PAYE on BIK
        paye_on_bik = self.calculate_paye_on_bik(annual_basic_salary, total_annual)
        
        # Add warnings if BIK is unusually high
        if bik_percentage > Decimal("50"):
            warnings.append(
                f"BIK represents {bik_percentage}% of basic salary - "
                "consider restructuring compensation package"
            )
        
        return BIKSummary(
            employee_id=employee_id,
            employee_name=f"{employee.first_name} {employee.last_name}",
            tax_year=tax_year,
            annual_basic_salary=annual_basic_salary,
            items=items,
            total_annual_bik=total_annual,
            total_monthly_bik=total_monthly,
            bik_as_percentage_of_salary=bik_percentage,
            paye_on_bik=paye_on_bik,
            effective_bik_date=date(tax_year, 1, 1),
            calculation_date=datetime.utcnow(),
            warnings=warnings,
        )
    
    def bik_summary_to_dict(self, summary: BIKSummary) -> Dict[str, Any]:
        """Convert BIK summary to dictionary for API response."""
        return {
            "employee_id": str(summary.employee_id),
            "employee_name": summary.employee_name,
            "tax_year": summary.tax_year,
            "annual_basic_salary": float(summary.annual_basic_salary),
            "items": [
                {
                    "category": item.category,
                    "description": item.description,
                    "cost_or_value": float(item.cost_or_value),
                    "bik_rate": float(item.bik_rate),
                    "annual_bik_value": float(item.annual_bik_value),
                    "monthly_bik_value": float(item.monthly_bik_value),
                    "months_applicable": item.months_applicable,
                    "prorated_bik_value": float(item.prorated_bik_value),
                    "notes": item.notes,
                }
                for item in summary.items
            ],
            "totals": {
                "total_annual_bik": float(summary.total_annual_bik),
                "total_monthly_bik": float(summary.total_monthly_bik),
                "bik_as_percentage_of_salary": float(summary.bik_as_percentage_of_salary),
                "paye_on_bik": float(summary.paye_on_bik),
            },
            "effective_date": summary.effective_bik_date.isoformat(),
            "calculation_date": summary.calculation_date.isoformat(),
            "warnings": summary.warnings,
        }


# Singleton instance
bik_automator_service = BIKAutomatorService()
