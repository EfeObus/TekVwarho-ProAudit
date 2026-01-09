"""
Tax Intelligence Command Center
Implements proactive tax optimization and forecasting for Nigerian Tax Reform 2026

Features:
- ETR Optimization Engine
- Tax Sensitivity Analysis
- Cash Flow Forecasting
- Scenario Modeling
- WHT Credit Management
"""

from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from dataclasses import dataclass
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, extract

logger = logging.getLogger(__name__)


@dataclass
class TaxForecast:
    """Tax forecast result"""
    period: str
    vat_liability: Decimal
    cit_liability: Decimal
    paye_liability: Decimal
    wht_liability: Decimal
    development_levy: Decimal
    total_liability: Decimal
    effective_tax_rate: Decimal
    recommendations: List[str]


@dataclass
class CashFlowForecast:
    """Monthly cash flow forecast"""
    month: str
    opening_balance: Decimal
    projected_income: Decimal
    projected_expenses: Decimal
    tax_payments: Decimal
    net_cash_flow: Decimal
    closing_balance: Decimal
    burn_rate: Decimal


@dataclass
class ScenarioResult:
    """What-if scenario analysis result"""
    scenario_name: str
    base_values: Dict[str, Decimal]
    adjusted_values: Dict[str, Decimal]
    impact: Dict[str, Decimal]
    recommendations: List[str]


class TaxIntelligenceService:
    """
    Tax Intelligence Command Center
    Provides proactive tax optimization and strategic forecasting
    """
    
    # 2026 Nigerian Tax Rates
    TAX_RATES_2026 = {
        "vat": Decimal("7.5"),  # Standard VAT
        "cit_standard": Decimal("30"),  # Standard CIT
        "cit_medium": Decimal("20"),  # Turnover 25M-100M
        "cit_small": Decimal("0"),  # Turnover < 25M
        "development_levy": Decimal("4"),  # 4% of assessable profit
        "tertiary_education_tax": Decimal("2.5"),  # TET rate
        "minimum_tax": Decimal("0.5"),  # Minimum tax on gross turnover
        "wht_professional": Decimal("10"),
        "wht_contract": Decimal("5"),
        "wht_rent": Decimal("10"),
        "wht_dividend": Decimal("10"),
    }
    
    # CIT thresholds
    CIT_THRESHOLDS = {
        "small": Decimal("25000000"),  # < 25M
        "medium": Decimal("100000000"),  # 25M - 100M
        "large": Decimal("50000000000"),  # 50B for special rates
    }
    
    # PAYE 2026 Brackets
    PAYE_BRACKETS_2026 = [
        (Decimal("800000"), Decimal("0")),  # First 800K - 0%
        (Decimal("2000000"), Decimal("15")),  # Next 2M - 15%
        (Decimal("3200000"), Decimal("20")),  # Next 3.2M - 20%
        (Decimal("6000000"), Decimal("25")),  # Next 6M - 25%
        (Decimal("999999999999"), Decimal("30")),  # Above - 30% (effectively infinite)
    ]
    
    async def calculate_etr(
        self,
        db: AsyncSession,
        entity_id: UUID,
        fiscal_year: int,
        include_projections: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate Effective Tax Rate with breakdown
        
        ETR = Total Tax Expense / Pre-Tax Profit
        """
        from app.models.transaction import Transaction
        from app.models.invoice import Invoice
        from app.models.entity import BusinessEntity
        
        # Get entity details
        entity_query = select(BusinessEntity).where(BusinessEntity.id == entity_id)
        entity_result = await db.execute(entity_query)
        entity = entity_result.scalar_one_or_none()
        
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")
        
        # Calculate fiscal year dates
        fy_start_month = entity.fiscal_year_start_month or 1
        if fy_start_month == 1:
            fy_start = date(fiscal_year, 1, 1)
            fy_end = date(fiscal_year, 12, 31)
        else:
            fy_start = date(fiscal_year - 1, fy_start_month, 1)
            fy_end = date(fiscal_year, fy_start_month - 1, 28)  # Simplified
        
        # Get revenue
        revenue_query = select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.entity_id == entity_id,
                Transaction.transaction_type == "income",
                Transaction.transaction_date >= fy_start,
                Transaction.transaction_date <= fy_end
            )
        )
        revenue_result = await db.execute(revenue_query)
        total_revenue = revenue_result.scalar() or Decimal("0")
        
        # Get expenses
        expense_query = select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.entity_id == entity_id,
                Transaction.transaction_type == "expense",
                Transaction.transaction_date >= fy_start,
                Transaction.transaction_date <= fy_end
            )
        )
        expense_result = await db.execute(expense_query)
        total_expenses = expense_result.scalar() or Decimal("0")
        
        # Calculate profit before tax
        profit_before_tax = total_revenue - total_expenses
        
        # Get turnover for CIT rate determination
        turnover = entity.annual_turnover or total_revenue
        
        # Determine CIT rate
        if turnover < self.CIT_THRESHOLDS["small"]:
            cit_rate = self.TAX_RATES_2026["cit_small"]
        elif turnover < self.CIT_THRESHOLDS["medium"]:
            cit_rate = self.TAX_RATES_2026["cit_medium"]
        else:
            cit_rate = self.TAX_RATES_2026["cit_standard"]
        
        # Calculate taxes
        cit = max(
            profit_before_tax * (cit_rate / 100),
            total_revenue * (self.TAX_RATES_2026["minimum_tax"] / 100)  # Minimum tax
        )
        
        # Development Levy (4% of assessable profit for qualifying companies)
        development_levy = Decimal("0")
        if not entity.is_development_levy_exempt:
            development_levy = profit_before_tax * (self.TAX_RATES_2026["development_levy"] / 100)
        
        # TET
        tet = profit_before_tax * (self.TAX_RATES_2026["tertiary_education_tax"] / 100)
        
        # Get VAT collected
        vat_query = select(func.sum(Invoice.vat_amount)).where(
            and_(
                Invoice.entity_id == entity_id,
                Invoice.invoice_date >= fy_start,
                Invoice.invoice_date <= fy_end
            )
        )
        vat_result = await db.execute(vat_query)
        vat_collected = vat_result.scalar() or Decimal("0")
        
        # Total tax
        total_tax = cit + development_levy + tet
        
        # ETR
        etr = (total_tax / profit_before_tax * 100) if profit_before_tax > 0 else Decimal("0")
        
        # Recommendations
        recommendations = self._generate_tax_recommendations(
            turnover, profit_before_tax, etr, entity.is_vat_registered
        )
        
        return {
            "entity_id": str(entity_id),
            "fiscal_year": fiscal_year,
            "period": {
                "start": fy_start.isoformat(),
                "end": fy_end.isoformat()
            },
            "financials": {
                "total_revenue": str(total_revenue),
                "total_expenses": str(total_expenses),
                "profit_before_tax": str(profit_before_tax),
                "turnover": str(turnover)
            },
            "tax_calculations": {
                "cit_rate": str(cit_rate),
                "cit_liability": str(cit),
                "development_levy": str(development_levy),
                "tertiary_education_tax": str(tet),
                "vat_collected": str(vat_collected),
                "total_tax": str(total_tax)
            },
            "effective_tax_rate": str(etr.quantize(Decimal("0.01"))),
            "tax_category": self._get_tax_category(turnover),
            "recommendations": recommendations
        }
    
    async def tax_sensitivity_analysis(
        self,
        db: AsyncSession,
        entity_id: UUID,
        fiscal_year: int,
        capex_scenarios: List[Decimal]
    ) -> Dict[str, Any]:
        """
        Analyze how ETR changes with different capital expenditure levels
        
        For companies near the 50B threshold
        """
        
        base_etr = await self.calculate_etr(db, entity_id, fiscal_year)
        base_profit = Decimal(base_etr["financials"]["profit_before_tax"])
        base_rate = Decimal(base_etr["effective_tax_rate"])
        
        scenarios = []
        
        for capex in capex_scenarios:
            # Capex affects profit through depreciation (assume 25% straight line)
            annual_depreciation = capex * Decimal("0.25")
            adjusted_profit = base_profit - annual_depreciation
            
            # Recalculate tax
            turnover = Decimal(base_etr["financials"]["turnover"])
            
            if turnover < self.CIT_THRESHOLDS["small"]:
                cit_rate = self.TAX_RATES_2026["cit_small"]
            elif turnover < self.CIT_THRESHOLDS["medium"]:
                cit_rate = self.TAX_RATES_2026["cit_medium"]
            else:
                cit_rate = self.TAX_RATES_2026["cit_standard"]
            
            cit = adjusted_profit * (cit_rate / 100)
            dev_levy = adjusted_profit * (self.TAX_RATES_2026["development_levy"] / 100)
            tet = adjusted_profit * (self.TAX_RATES_2026["tertiary_education_tax"] / 100)
            total_tax = cit + dev_levy + tet
            
            new_etr = (total_tax / adjusted_profit * 100) if adjusted_profit > 0 else Decimal("0")
            
            scenarios.append({
                "capex_amount": str(capex),
                "annual_depreciation": str(annual_depreciation),
                "adjusted_profit": str(adjusted_profit),
                "total_tax": str(total_tax),
                "effective_tax_rate": str(new_etr.quantize(Decimal("0.01"))),
                "etr_change": str((new_etr - base_rate).quantize(Decimal("0.01"))),
                "tax_savings": str((Decimal(base_etr["tax_calculations"]["total_tax"]) - total_tax).quantize(Decimal("0.01")))
            })
        
        return {
            "entity_id": str(entity_id),
            "fiscal_year": fiscal_year,
            "base_scenario": {
                "profit_before_tax": str(base_profit),
                "effective_tax_rate": str(base_rate),
                "total_tax": base_etr["tax_calculations"]["total_tax"]
            },
            "capex_scenarios": scenarios,
            "optimal_capex": self._find_optimal_capex(scenarios),
            "recommendations": [
                "Consider timing large capital expenditures before fiscal year end",
                "Fixed asset investments can reduce taxable profit through depreciation",
                "Ensure all qualifying capital allowances are claimed"
            ]
        }
    
    async def forecast_cash_flow(
        self,
        db: AsyncSession,
        entity_id: UUID,
        months: int = 12,
        include_tax_payments: bool = True
    ) -> List[CashFlowForecast]:
        """
        Generate 12-month predictive cash flow chart
        Factors in 2026 PAYE brackets and Development Levy
        """
        from app.models.transaction import Transaction
        
        # Get historical data for trend analysis
        historical_months = 6
        end_date = date.today()
        start_date = end_date - timedelta(days=historical_months * 30)
        
        # Get average monthly income
        income_query = select(
            func.avg(func.sum(Transaction.amount))
        ).where(
            and_(
                Transaction.entity_id == entity_id,
                Transaction.transaction_type == "income",
                Transaction.transaction_date >= start_date
            )
        ).group_by(
            extract('month', Transaction.transaction_date)
        )
        
        # Simplified: use last month's data as baseline
        last_month_income_query = select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.entity_id == entity_id,
                Transaction.transaction_type == "income",
                Transaction.transaction_date >= end_date - timedelta(days=30)
            )
        )
        income_result = await db.execute(last_month_income_query)
        avg_monthly_income = income_result.scalar() or Decimal("100000")
        
        last_month_expense_query = select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.entity_id == entity_id,
                Transaction.transaction_type == "expense",
                Transaction.transaction_date >= end_date - timedelta(days=30)
            )
        )
        expense_result = await db.execute(last_month_expense_query)
        avg_monthly_expense = expense_result.scalar() or Decimal("80000")
        
        # Calculate burn rate
        burn_rate = avg_monthly_expense / avg_monthly_income if avg_monthly_income else Decimal("1")
        
        # Estimate tax payments
        monthly_paye = avg_monthly_expense * Decimal("0.15")  # Rough estimate
        monthly_vat = avg_monthly_income * Decimal("0.075")  # VAT on sales
        quarterly_cit = avg_monthly_income * 3 * Decimal("0.30") * Decimal("0.25")  # Quarterly installments
        
        forecasts = []
        current_balance = Decimal("1000000")  # Assume opening balance
        
        for i in range(months):
            month_date = end_date + timedelta(days=30 * (i + 1))
            month_str = month_date.strftime("%Y-%m")
            
            # Apply growth/seasonality factors (simplified)
            growth_factor = Decimal("1.02")  # 2% monthly growth
            seasonal_factor = self._get_seasonal_factor(month_date.month)
            
            projected_income = avg_monthly_income * growth_factor * seasonal_factor
            projected_expense = avg_monthly_expense * growth_factor
            
            # Tax payments
            tax_payments = monthly_paye + monthly_vat
            if month_date.month in [3, 6, 9, 12]:  # Quarterly
                tax_payments += quarterly_cit
            
            # Development levy (annual, in month 3)
            if month_date.month == 3:
                annual_profit = avg_monthly_income * 12 - avg_monthly_expense * 12
                dev_levy = annual_profit * Decimal("0.04")
                tax_payments += dev_levy
            
            net_cash_flow = projected_income - projected_expense - tax_payments
            closing_balance = current_balance + net_cash_flow
            
            forecasts.append(CashFlowForecast(
                month=month_str,
                opening_balance=current_balance,
                projected_income=projected_income,
                projected_expenses=projected_expense,
                tax_payments=tax_payments,
                net_cash_flow=net_cash_flow,
                closing_balance=closing_balance,
                burn_rate=burn_rate
            ))
            
            current_balance = closing_balance
        
        return forecasts
    
    async def run_scenario(
        self,
        db: AsyncSession,
        entity_id: UUID,
        scenario_name: str,
        adjustments: Dict[str, Any]
    ) -> ScenarioResult:
        """
        Run what-if scenario analysis
        
        Examples:
        - "What if we increase salaries by 10%?"
        - "What if we hire 5 new employees?"
        - "What if we expand to a new location?"
        """
        
        # Get current state
        current_etr = await self.calculate_etr(db, entity_id, date.today().year)
        
        base_revenue = Decimal(current_etr["financials"]["total_revenue"])
        base_expenses = Decimal(current_etr["financials"]["total_expenses"])
        base_profit = Decimal(current_etr["financials"]["profit_before_tax"])
        base_tax = Decimal(current_etr["tax_calculations"]["total_tax"])
        
        # Apply adjustments
        adjusted_revenue = base_revenue
        adjusted_expenses = base_expenses
        
        recommendations = []
        
        if "salary_increase_percent" in adjustments:
            increase = Decimal(str(adjustments["salary_increase_percent"])) / 100
            # Assume salaries are 40% of expenses
            salary_portion = base_expenses * Decimal("0.40")
            additional_cost = salary_portion * increase
            adjusted_expenses += additional_cost
            
            # Calculate CRA impact
            additional_cra = additional_cost * Decimal("0.20")  # 20% CRA
            recommendations.append(
                f"Salary increase adds NGN {additional_cost:,.2f} to expenses but provides NGN {additional_cra:,.2f} in additional CRA relief"
            )
        
        if "new_employees" in adjustments:
            count = adjustments["new_employees"]
            avg_salary = Decimal(str(adjustments.get("avg_salary", "500000")))
            annual_cost = count * avg_salary * 12
            adjusted_expenses += annual_cost
            
            # PAYE and pension implications
            annual_paye = self._calculate_paye(avg_salary * 12) * count
            annual_pension = avg_salary * 12 * Decimal("0.10") * count
            
            recommendations.append(
                f"New hires add NGN {annual_cost:,.2f} annually with PAYE of NGN {annual_paye:,.2f} and pension of NGN {annual_pension:,.2f}"
            )
        
        if "revenue_growth_percent" in adjustments:
            growth = Decimal(str(adjustments["revenue_growth_percent"])) / 100
            adjusted_revenue = base_revenue * (1 + growth)
            recommendations.append(
                f"Revenue growth of {adjustments['revenue_growth_percent']}% increases turnover to NGN {adjusted_revenue:,.2f}"
            )
        
        # Recalculate taxes
        adjusted_profit = adjusted_revenue - adjusted_expenses
        
        # Check if turnover changes tax category
        if adjusted_revenue < self.CIT_THRESHOLDS["small"]:
            cit_rate = self.TAX_RATES_2026["cit_small"]
        elif adjusted_revenue < self.CIT_THRESHOLDS["medium"]:
            cit_rate = self.TAX_RATES_2026["cit_medium"]
        else:
            cit_rate = self.TAX_RATES_2026["cit_standard"]
        
        adjusted_cit = adjusted_profit * (cit_rate / 100)
        adjusted_dev_levy = adjusted_profit * (self.TAX_RATES_2026["development_levy"] / 100)
        adjusted_tet = adjusted_profit * (self.TAX_RATES_2026["tertiary_education_tax"] / 100)
        adjusted_tax = adjusted_cit + adjusted_dev_levy + adjusted_tet
        
        adjusted_etr = (adjusted_tax / adjusted_profit * 100) if adjusted_profit > 0 else Decimal("0")
        
        return ScenarioResult(
            scenario_name=scenario_name,
            base_values={
                "revenue": base_revenue,
                "expenses": base_expenses,
                "profit": base_profit,
                "tax": base_tax,
                "etr": Decimal(current_etr["effective_tax_rate"])
            },
            adjusted_values={
                "revenue": adjusted_revenue,
                "expenses": adjusted_expenses,
                "profit": adjusted_profit,
                "tax": adjusted_tax,
                "etr": adjusted_etr
            },
            impact={
                "revenue_change": adjusted_revenue - base_revenue,
                "expense_change": adjusted_expenses - base_expenses,
                "profit_change": adjusted_profit - base_profit,
                "tax_change": adjusted_tax - base_tax,
                "etr_change": adjusted_etr - Decimal(current_etr["effective_tax_rate"])
            },
            recommendations=recommendations
        )
    
    def _calculate_paye(self, annual_income: Decimal) -> Decimal:
        """Calculate PAYE using 2026 brackets"""
        
        # CRA = 20% of income + whichever is higher of (1% of income or 200,000)
        cra_base = annual_income * Decimal("0.20")
        cra_variable = max(annual_income * Decimal("0.01"), Decimal("200000"))
        cra = cra_base + cra_variable
        
        taxable_income = max(annual_income - cra, Decimal("0"))
        
        tax = Decimal("0")
        remaining = taxable_income
        
        for threshold, rate in self.PAYE_BRACKETS_2026:
            if remaining <= 0:
                break
            taxable_in_bracket = min(remaining, threshold)
            tax += taxable_in_bracket * (rate / 100)
            remaining -= taxable_in_bracket
        
        return tax
    
    def _generate_tax_recommendations(
        self,
        turnover: Decimal,
        profit: Decimal,
        etr: Decimal,
        is_vat_registered: bool
    ) -> List[str]:
        """Generate actionable tax recommendations"""
        
        recommendations = []
        
        # Turnover-based recommendations
        if turnover < self.CIT_THRESHOLDS["small"]:
            recommendations.append(
                "You qualify for 0% CIT rate as a small company (turnover < NGN 25M)"
            )
        elif turnover < self.CIT_THRESHOLDS["medium"]:
            recommendations.append(
                "You qualify for 20% CIT rate as a medium company (turnover NGN 25M-100M)"
            )
            if turnover > self.CIT_THRESHOLDS["medium"] * Decimal("0.9"):
                recommendations.append(
                    "WARNING: You are near the 100M threshold. Consider timing revenue recognition."
                )
        else:
            recommendations.append(
                "Standard 30% CIT rate applies. Consider tax planning strategies."
            )
        
        # ETR optimization
        if etr > Decimal("35"):
            recommendations.append(
                "Your ETR is high. Consider reviewing allowable deductions and capital allowances."
            )
        
        # VAT
        if not is_vat_registered and turnover > Decimal("25000000"):
            recommendations.append(
                "You should be VAT registered as turnover exceeds NGN 25M threshold."
            )
        
        # General recommendations
        recommendations.extend([
            "Ensure all WHT credit notes are collected and applied",
            "Review input VAT recovery on eligible expenses",
            "Consider timing of major expenses before fiscal year end"
        ])
        
        return recommendations
    
    def _get_tax_category(self, turnover: Decimal) -> str:
        """Get tax category based on turnover"""
        if turnover < self.CIT_THRESHOLDS["small"]:
            return "small"
        elif turnover < self.CIT_THRESHOLDS["medium"]:
            return "medium"
        else:
            return "large"
    
    def _get_seasonal_factor(self, month: int) -> Decimal:
        """Get seasonal adjustment factor for Nigerian business"""
        # December typically higher, August lower (rainy season)
        factors = {
            1: Decimal("0.95"),
            2: Decimal("0.95"),
            3: Decimal("1.00"),
            4: Decimal("1.00"),
            5: Decimal("1.00"),
            6: Decimal("0.95"),
            7: Decimal("0.90"),
            8: Decimal("0.85"),
            9: Decimal("0.95"),
            10: Decimal("1.05"),
            11: Decimal("1.10"),
            12: Decimal("1.20"),
        }
        return factors.get(month, Decimal("1.00"))
    
    def _find_optimal_capex(self, scenarios: List[Dict]) -> Dict[str, Any]:
        """Find the optimal CAPEX scenario"""
        if not scenarios:
            return {"amount": "0", "reason": "No scenarios provided"}
        
        best = min(scenarios, key=lambda x: Decimal(x["effective_tax_rate"]))
        return {
            "amount": best["capex_amount"],
            "effective_tax_rate": best["effective_tax_rate"],
            "tax_savings": best["tax_savings"],
            "reason": "Lowest ETR achieved"
        }


# Singleton instance
tax_intelligence_service = TaxIntelligenceService()
