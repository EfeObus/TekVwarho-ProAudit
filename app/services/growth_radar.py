"""
Growth Radar & Tax Threshold Alert System

This module provides proactive tax planning intelligence for Nigerian SMEs,
specifically monitoring business growth against key tax thresholds:

- N50M turnover: CIT liability trigger (0% -> 20%)
- N100M turnover: Higher CIT rate (20% -> 30%) + Development Levy + CGT
- N25M turnover: Small company threshold

Includes:
- Real-time threshold monitoring
- Predictive growth analysis
- Proactive tax planning recommendations
- Transition planning calculators
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import logging

from sqlalchemy import select, and_, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============================================================================
# Nigerian 2026 Tax Thresholds
# ============================================================================

class TaxBracket(str, Enum):
    """Company Income Tax brackets based on turnover"""
    SMALL = "small"           # <N25M - 0% CIT
    MEDIUM = "medium"         # N25M-N100M - 20% CIT
    LARGE = "large"           # >N100M - 30% CIT


class ThresholdType(str, Enum):
    """Types of tax thresholds"""
    CIT_SMALL_MEDIUM = "cit_small_medium"     # N25M
    CIT_MEDIUM_LARGE = "cit_medium_large"     # N100M
    DEV_LEVY = "dev_levy"                      # N100M (4% Development Levy)
    TET = "tet"                                # N100M (2.5% Tertiary Education Tax)
    CGT = "cgt"                                # N100M (Capital Gains Tax applies)
    VAT_THRESHOLD = "vat_threshold"            # N25M (VAT registration mandatory)


# Tax thresholds in Naira
TAX_THRESHOLDS_2026 = {
    ThresholdType.CIT_SMALL_MEDIUM: Decimal("25000000"),     # N25M
    ThresholdType.CIT_MEDIUM_LARGE: Decimal("100000000"),    # N100M
    ThresholdType.DEV_LEVY: Decimal("100000000"),            # N100M
    ThresholdType.TET: Decimal("100000000"),                 # N100M
    ThresholdType.CGT: Decimal("100000000"),                 # N100M
    ThresholdType.VAT_THRESHOLD: Decimal("25000000"),        # N25M
}

# Tax rates by bracket
TAX_RATES_2026 = {
    TaxBracket.SMALL: {
        "cit": Decimal("0.00"),
        "dev_levy": Decimal("0.00"),
        "tet": Decimal("0.00"),
    },
    TaxBracket.MEDIUM: {
        "cit": Decimal("0.20"),
        "dev_levy": Decimal("0.00"),
        "tet": Decimal("0.00"),
    },
    TaxBracket.LARGE: {
        "cit": Decimal("0.30"),
        "dev_levy": Decimal("0.04"),
        "tet": Decimal("0.025"),
    },
}


@dataclass
class ThresholdAlert:
    """Alert for approaching or crossing a tax threshold"""
    threshold_type: ThresholdType
    threshold_amount: Decimal
    current_amount: Decimal
    distance_to_threshold: Decimal
    percentage_to_threshold: Decimal
    is_crossed: bool
    alert_level: str  # "info", "warning", "critical", "exceeded"
    message: str
    recommendations: List[str]
    estimated_additional_tax: Optional[Decimal] = None
    tax_planning_window_days: Optional[int] = None


@dataclass
class GrowthProjection:
    """Projected business growth and tax implications"""
    current_monthly_revenue: Decimal
    average_monthly_growth_rate: Decimal
    projected_annual_revenue: Decimal
    months_to_small_threshold: Optional[int]
    months_to_medium_threshold: Optional[int]
    projected_tax_bracket: TaxBracket
    projected_cit: Decimal
    projected_dev_levy: Decimal
    projected_tet: Decimal
    projected_total_tax: Decimal
    confidence_level: str  # "low", "medium", "high"


@dataclass
class TransitionPlan:
    """Tax transition planning recommendations"""
    current_bracket: TaxBracket
    target_bracket: TaxBracket
    current_turnover: Decimal
    threshold_amount: Decimal
    buffer_amount: Decimal  # Stay this much below threshold
    revenue_to_defer: Decimal
    tax_saved_by_staying_below: Decimal
    strategies: List[Dict[str, Any]]
    risks: List[str]
    timeline: str
    recommended_actions: List[str]


@dataclass
class GrowthRadarSummary:
    """Complete growth radar analysis"""
    entity_id: UUID
    entity_name: str
    analysis_date: date
    fiscal_year: int
    
    # Current status
    current_annual_revenue: Decimal
    current_tax_bracket: TaxBracket
    ytd_revenue: Decimal
    ytd_months: int
    
    # Alerts
    alerts: List[ThresholdAlert]
    
    # Projections
    growth_projection: Optional[GrowthProjection]
    
    # Transition planning
    transition_plan: Optional[TransitionPlan]
    
    # Score
    risk_score: int  # 0-100
    opportunity_score: int  # 0-100
    
    # Timestamps
    generated_at: datetime


class GrowthRadarService:
    """
    Growth Radar & Tax Threshold Alert Service
    
    Provides proactive tax planning intelligence for Nigerian SMEs
    by monitoring business growth against key tax thresholds.
    """
    
    def __init__(self):
        self.thresholds = TAX_THRESHOLDS_2026
        self.rates = TAX_RATES_2026
    
    def get_tax_bracket(self, annual_turnover: Decimal) -> TaxBracket:
        """Determine tax bracket based on annual turnover."""
        if annual_turnover < self.thresholds[ThresholdType.CIT_SMALL_MEDIUM]:
            return TaxBracket.SMALL
        elif annual_turnover < self.thresholds[ThresholdType.CIT_MEDIUM_LARGE]:
            return TaxBracket.MEDIUM
        else:
            return TaxBracket.LARGE
    
    def calculate_bracket_taxes(
        self,
        taxable_profit: Decimal,
        bracket: TaxBracket,
    ) -> Dict[str, Decimal]:
        """Calculate all taxes for a given bracket."""
        rates = self.rates[bracket]
        
        cit = (taxable_profit * rates["cit"]).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        dev_levy = (taxable_profit * rates["dev_levy"]).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        tet = (taxable_profit * rates["tet"]).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        return {
            "cit": cit,
            "dev_levy": dev_levy,
            "tet": tet,
            "total": cit + dev_levy + tet,
        }
    
    def analyze_threshold_proximity(
        self,
        current_revenue: Decimal,
        threshold_type: ThresholdType,
        projected_annual: Optional[Decimal] = None,
    ) -> ThresholdAlert:
        """
        Analyze proximity to a specific tax threshold.
        """
        threshold = self.thresholds[threshold_type]
        
        # Use projected if available, otherwise annualize current
        analysis_amount = projected_annual or current_revenue
        
        distance = threshold - analysis_amount
        is_crossed = distance <= Decimal("0")
        
        # Calculate percentage to threshold
        if threshold > Decimal("0"):
            percentage = (analysis_amount / threshold * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            percentage = Decimal("100")
        
        # Determine alert level
        if is_crossed:
            alert_level = "exceeded"
        elif percentage >= Decimal("95"):
            alert_level = "critical"
        elif percentage >= Decimal("85"):
            alert_level = "warning"
        elif percentage >= Decimal("75"):
            alert_level = "info"
        else:
            alert_level = "normal"
        
        # Generate message and recommendations
        message, recommendations = self._generate_threshold_message(
            threshold_type, distance, percentage, is_crossed
        )
        
        # Calculate additional tax if threshold crossed
        additional_tax = None
        if threshold_type == ThresholdType.CIT_SMALL_MEDIUM:
            if is_crossed:
                # Moving from 0% to 20%
                additional_tax = analysis_amount * Decimal("0.20") * Decimal("0.30")  # Est. profit margin
        elif threshold_type == ThresholdType.CIT_MEDIUM_LARGE:
            if is_crossed:
                # Moving from 20% to 30% + Dev Levy + TET
                additional_tax = analysis_amount * Decimal("0.165") * Decimal("0.30")  # 10% CIT + 4% + 2.5%
        
        return ThresholdAlert(
            threshold_type=threshold_type,
            threshold_amount=threshold,
            current_amount=analysis_amount,
            distance_to_threshold=abs(distance),
            percentage_to_threshold=percentage,
            is_crossed=is_crossed,
            alert_level=alert_level,
            message=message,
            recommendations=recommendations,
            estimated_additional_tax=additional_tax,
            tax_planning_window_days=self._estimate_planning_window(distance, current_revenue),
        )
    
    def _generate_threshold_message(
        self,
        threshold_type: ThresholdType,
        distance: Decimal,
        percentage: Decimal,
        is_crossed: bool,
    ) -> Tuple[str, List[str]]:
        """Generate alert message and recommendations based on threshold."""
        
        if threshold_type == ThresholdType.CIT_SMALL_MEDIUM:
            threshold_name = "N25M CIT threshold"
            if is_crossed:
                message = f"Your business has crossed the {threshold_name}. You are now liable for 20% Company Income Tax."
                recommendations = [
                    "Review deductible expenses to reduce taxable profit",
                    "Consider timing of revenue recognition",
                    "Engage a tax consultant for compliance planning",
                    "Set up quarterly CIT provisional payments",
                ]
            elif percentage >= Decimal("85"):
                message = f"WARNING: You are {percentage}% towards the {threshold_name}. Consider tax planning strategies."
                recommendations = [
                    "Defer non-essential revenue to next fiscal year if close to year-end",
                    "Accelerate deductible capital expenditure",
                    "Review invoicing timing for major contracts",
                    "Consider incorporating additional business segments separately",
                ]
            else:
                message = f"You are {percentage}% towards the {threshold_name}. Monitor growth trajectory."
                recommendations = [
                    "Continue monitoring monthly revenue",
                    "Plan for eventual CIT compliance",
                    "Build tax reserves for future liability",
                ]
        
        elif threshold_type == ThresholdType.CIT_MEDIUM_LARGE:
            threshold_name = "N100M threshold"
            if is_crossed:
                message = f"Your business has crossed the {threshold_name}. Additional taxes now apply: 30% CIT, 4% Development Levy, 2.5% TET."
                recommendations = [
                    "Engage tax advisors for comprehensive planning",
                    "Review all available tax incentives and exemptions",
                    "Optimize capital structure for tax efficiency",
                    "Consider business restructuring for tax efficiency",
                    "Implement robust tax compliance systems",
                ]
            elif percentage >= Decimal("85"):
                message = f"CRITICAL: You are {percentage}% towards the {threshold_name}. Major tax implications at threshold."
                recommendations = [
                    "Urgent: Review revenue timing strategies",
                    "Consider holding company restructure",
                    "Evaluate sector-specific tax incentives",
                    "Pioneer status application if eligible",
                    "Review intercompany pricing arrangements",
                ]
            else:
                message = f"You are {percentage}% towards the {threshold_name}. Plan for transition."
                recommendations = [
                    "Build reserves for increased tax burden",
                    "Review long-term tax strategy",
                    "Consider growth vs. tax optimization tradeoffs",
                ]
        
        else:
            message = f"Threshold analysis for {threshold_type.value}"
            recommendations = ["Consult with tax professional"]
        
        return message, recommendations
    
    def _estimate_planning_window(
        self,
        distance: Decimal,
        monthly_revenue: Decimal,
    ) -> Optional[int]:
        """Estimate days until threshold is crossed at current rate."""
        if distance <= Decimal("0"):
            return 0
        
        if monthly_revenue <= Decimal("0"):
            return None
        
        months = distance / monthly_revenue
        return int(months * 30)
    
    async def calculate_growth_projection(
        self,
        db: AsyncSession,
        entity_id: UUID,
    ) -> GrowthProjection:
        """
        Calculate growth projection based on historical data.
        """
        from app.models.transaction import Transaction
        
        # Get last 12 months of revenue
        twelve_months_ago = date.today() - timedelta(days=365)
        
        result = await db.execute(
            select(
                extract('year', Transaction.transaction_date).label('year'),
                extract('month', Transaction.transaction_date).label('month'),
                func.sum(Transaction.amount).label('total')
            ).where(
                and_(
                    Transaction.entity_id == entity_id,
                    Transaction.type == 'income',
                    Transaction.transaction_date >= twelve_months_ago,
                )
            ).group_by(
                extract('year', Transaction.transaction_date),
                extract('month', Transaction.transaction_date)
            ).order_by(
                extract('year', Transaction.transaction_date),
                extract('month', Transaction.transaction_date)
            )
        )
        
        monthly_data = result.all()
        
        if len(monthly_data) < 3:
            # Not enough data for meaningful projection
            return GrowthProjection(
                current_monthly_revenue=Decimal("0"),
                average_monthly_growth_rate=Decimal("0"),
                projected_annual_revenue=Decimal("0"),
                months_to_small_threshold=None,
                months_to_medium_threshold=None,
                projected_tax_bracket=TaxBracket.SMALL,
                projected_cit=Decimal("0"),
                projected_dev_levy=Decimal("0"),
                projected_tet=Decimal("0"),
                projected_total_tax=Decimal("0"),
                confidence_level="low",
            )
        
        # Calculate growth rate
        revenues = [Decimal(str(row.total or 0)) for row in monthly_data]
        current_monthly = revenues[-1] if revenues else Decimal("0")
        
        # Average monthly growth rate
        growth_rates = []
        for i in range(1, len(revenues)):
            if revenues[i-1] > Decimal("0"):
                rate = (revenues[i] - revenues[i-1]) / revenues[i-1]
                growth_rates.append(rate)
        
        avg_growth = Decimal("0")
        if growth_rates:
            avg_growth = sum(growth_rates) / len(growth_rates)
        
        # Project annual revenue
        projected_annual = sum(revenues)
        if len(revenues) < 12:
            # Annualize
            projected_annual = projected_annual * Decimal("12") / len(revenues)
        
        # Apply growth rate for remaining months
        remaining_months = 12 - len(revenues)
        if remaining_months > 0 and avg_growth > Decimal("-1"):
            for _ in range(remaining_months):
                current_monthly = current_monthly * (Decimal("1") + avg_growth)
                projected_annual += current_monthly
        
        # Calculate months to thresholds
        months_to_small = None
        months_to_medium = None
        
        if current_monthly > Decimal("0"):
            ytd = sum(revenues)
            distance_to_small = self.thresholds[ThresholdType.CIT_SMALL_MEDIUM] - ytd
            distance_to_medium = self.thresholds[ThresholdType.CIT_MEDIUM_LARGE] - ytd
            
            if distance_to_small > Decimal("0"):
                months_to_small = int(distance_to_small / current_monthly)
            if distance_to_medium > Decimal("0"):
                months_to_medium = int(distance_to_medium / current_monthly)
        
        # Determine projected bracket
        projected_bracket = self.get_tax_bracket(projected_annual)
        
        # Calculate projected taxes (assuming 30% profit margin)
        profit_margin = Decimal("0.30")
        projected_profit = projected_annual * profit_margin
        taxes = self.calculate_bracket_taxes(projected_profit, projected_bracket)
        
        # Confidence level based on data quality
        if len(revenues) >= 12:
            confidence = "high"
        elif len(revenues) >= 6:
            confidence = "medium"
        else:
            confidence = "low"
        
        return GrowthProjection(
            current_monthly_revenue=revenues[-1] if revenues else Decimal("0"),
            average_monthly_growth_rate=avg_growth,
            projected_annual_revenue=projected_annual,
            months_to_small_threshold=months_to_small,
            months_to_medium_threshold=months_to_medium,
            projected_tax_bracket=projected_bracket,
            projected_cit=taxes["cit"],
            projected_dev_levy=taxes["dev_levy"],
            projected_tet=taxes["tet"],
            projected_total_tax=taxes["total"],
            confidence_level=confidence,
        )
    
    def generate_transition_plan(
        self,
        current_revenue: Decimal,
        approaching_threshold: ThresholdType,
        profit_margin: Decimal = Decimal("0.30"),
    ) -> TransitionPlan:
        """
        Generate a tax transition plan for businesses approaching thresholds.
        """
        threshold = self.thresholds[approaching_threshold]
        current_bracket = self.get_tax_bracket(current_revenue)
        
        # Determine target bracket (next one up)
        if current_bracket == TaxBracket.SMALL:
            target_bracket = TaxBracket.MEDIUM
        else:
            target_bracket = TaxBracket.LARGE
        
        # Calculate buffer (stay 5% below threshold)
        buffer = threshold * Decimal("0.05")
        safe_revenue = threshold - buffer
        
        # Revenue to defer if over safe amount
        revenue_to_defer = max(Decimal("0"), current_revenue - safe_revenue)
        
        # Calculate tax savings from staying below
        current_profit = current_revenue * profit_margin
        current_taxes = self.calculate_bracket_taxes(current_profit, current_bracket)
        
        above_profit = threshold * profit_margin
        above_taxes = self.calculate_bracket_taxes(above_profit, target_bracket)
        
        tax_saved = above_taxes["total"] - current_taxes["total"]
        
        # Generate strategies
        strategies = self._generate_transition_strategies(
            approaching_threshold, current_revenue, threshold
        )
        
        # Identify risks
        risks = [
            "Deferring revenue may impact cash flow",
            "Tax authority scrutiny of timing manipulation",
            "Client relationships if invoicing is delayed",
            "Potential penalties if deemed artificial avoidance",
        ]
        
        # Timeline
        distance = threshold - current_revenue
        if distance > Decimal("0"):
            timeline = f"Approximately {int(distance / (current_revenue / 12))} months at current growth rate"
        else:
            timeline = "Threshold already exceeded"
        
        # Recommended actions
        recommended_actions = [
            "Consult with tax professional immediately",
            "Review all contracts for timing flexibility",
            "Accelerate deductible expenses",
            "Evaluate business restructuring options",
            "Consider sector-specific incentives",
        ]
        
        return TransitionPlan(
            current_bracket=current_bracket,
            target_bracket=target_bracket,
            current_turnover=current_revenue,
            threshold_amount=threshold,
            buffer_amount=buffer,
            revenue_to_defer=revenue_to_defer,
            tax_saved_by_staying_below=tax_saved,
            strategies=strategies,
            risks=risks,
            timeline=timeline,
            recommended_actions=recommended_actions,
        )
    
    def _generate_transition_strategies(
        self,
        threshold_type: ThresholdType,
        current_revenue: Decimal,
        threshold: Decimal,
    ) -> List[Dict[str, Any]]:
        """Generate specific strategies for threshold management."""
        
        strategies = []
        
        # Revenue timing strategy
        strategies.append({
            "name": "Revenue Timing Optimization",
            "description": "Adjust invoicing and revenue recognition timing",
            "impact": "Medium",
            "risk": "Low",
            "implementation": [
                "Review contracts for flexible invoicing terms",
                "Negotiate advance payments vs. milestone billing",
                "Consider fiscal year-end timing",
            ],
        })
        
        # Expense acceleration
        strategies.append({
            "name": "Expense Acceleration",
            "description": "Bring forward deductible expenses to reduce profit",
            "impact": "Medium",
            "risk": "Low",
            "implementation": [
                "Prepay rent, insurance, and subscriptions",
                "Accelerate capital equipment purchases",
                "Settle outstanding vendor invoices",
            ],
        })
        
        # Business restructuring
        if threshold_type == ThresholdType.CIT_MEDIUM_LARGE:
            strategies.append({
                "name": "Group Structure Optimization",
                "description": "Restructure into multiple entities below threshold",
                "impact": "High",
                "risk": "Medium",
                "implementation": [
                    "Separate distinct business lines",
                    "Create holding company structure",
                    "Establish service company for intercompany billing",
                    "Note: Must have genuine business purpose",
                ],
            })
        
        # Tax incentives
        strategies.append({
            "name": "Tax Incentive Utilization",
            "description": "Leverage available tax holidays and exemptions",
            "impact": "High",
            "risk": "Low",
            "implementation": [
                "Apply for Pioneer Status if eligible",
                "Utilize export processing zone benefits",
                "Claim R&D tax credits",
                "Free trade zone consideration",
            ],
        })
        
        return strategies
    
    async def generate_growth_radar_summary(
        self,
        db: AsyncSession,
        entity_id: UUID,
        fiscal_year: int,
    ) -> GrowthRadarSummary:
        """
        Generate complete growth radar analysis for an entity.
        """
        from app.models.entity import BusinessEntity
        from app.models.transaction import Transaction
        
        # Get entity
        entity_result = await db.execute(
            select(BusinessEntity).where(BusinessEntity.id == entity_id)
        )
        entity = entity_result.scalar_one_or_none()
        
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")
        
        # Get YTD revenue
        year_start = date(fiscal_year, 1, 1)
        
        ytd_result = await db.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.entity_id == entity_id,
                    Transaction.type == 'income',
                    Transaction.transaction_date >= year_start,
                )
            )
        )
        ytd_revenue = Decimal(str(ytd_result.scalar() or 0))
        
        # Calculate months elapsed
        today = date.today()
        ytd_months = max(1, (today.year - year_start.year) * 12 + today.month - year_start.month + 1)
        
        # Annualize current revenue
        annual_revenue = ytd_revenue * Decimal("12") / ytd_months
        
        # Determine current bracket
        current_bracket = self.get_tax_bracket(annual_revenue)
        
        # Generate alerts
        alerts = []
        for threshold_type in [ThresholdType.CIT_SMALL_MEDIUM, ThresholdType.CIT_MEDIUM_LARGE]:
            alert = self.analyze_threshold_proximity(
                current_revenue=annual_revenue,
                threshold_type=threshold_type,
            )
            if alert.alert_level != "normal":
                alerts.append(alert)
        
        # Get growth projection
        growth_projection = await self.calculate_growth_projection(db, entity_id)
        
        # Generate transition plan if approaching threshold
        transition_plan = None
        if alerts:
            # Find the most critical alert
            critical_alert = max(
                alerts,
                key=lambda a: {"normal": 0, "info": 1, "warning": 2, "critical": 3, "exceeded": 4}[a.alert_level]
            )
            transition_plan = self.generate_transition_plan(
                current_revenue=annual_revenue,
                approaching_threshold=critical_alert.threshold_type,
            )
        
        # Calculate scores
        risk_score = self._calculate_risk_score(alerts, current_bracket)
        opportunity_score = self._calculate_opportunity_score(growth_projection, current_bracket)
        
        return GrowthRadarSummary(
            entity_id=entity_id,
            entity_name=entity.name,
            analysis_date=today,
            fiscal_year=fiscal_year,
            current_annual_revenue=annual_revenue,
            current_tax_bracket=current_bracket,
            ytd_revenue=ytd_revenue,
            ytd_months=ytd_months,
            alerts=alerts,
            growth_projection=growth_projection,
            transition_plan=transition_plan,
            risk_score=risk_score,
            opportunity_score=opportunity_score,
            generated_at=datetime.utcnow(),
        )
    
    def _calculate_risk_score(
        self,
        alerts: List[ThresholdAlert],
        current_bracket: TaxBracket,
    ) -> int:
        """Calculate risk score (0-100) based on threshold proximity."""
        if not alerts:
            return 10  # Low baseline risk
        
        max_alert_score = {
            "normal": 10,
            "info": 30,
            "warning": 60,
            "critical": 85,
            "exceeded": 100,
        }
        
        return max(max_alert_score[a.alert_level] for a in alerts)
    
    def _calculate_opportunity_score(
        self,
        projection: GrowthProjection,
        current_bracket: TaxBracket,
    ) -> int:
        """Calculate opportunity score (0-100) for tax optimization."""
        score = 50  # Baseline
        
        # Higher score if in small bracket with room to grow
        if current_bracket == TaxBracket.SMALL:
            score += 20
        
        # Higher score if growth is moderate (easier to manage)
        if projection.average_monthly_growth_rate < Decimal("0.05"):
            score += 15
        
        # Higher score if far from thresholds
        if projection.months_to_small_threshold and projection.months_to_small_threshold > 12:
            score += 15
        
        return min(100, score)
    
    def summary_to_dict(self, summary: GrowthRadarSummary) -> Dict[str, Any]:
        """Convert summary to dictionary for API response."""
        return {
            "entity_id": str(summary.entity_id),
            "entity_name": summary.entity_name,
            "analysis_date": summary.analysis_date.isoformat(),
            "fiscal_year": summary.fiscal_year,
            "current_status": {
                "annual_revenue": float(summary.current_annual_revenue),
                "tax_bracket": summary.current_tax_bracket.value,
                "ytd_revenue": float(summary.ytd_revenue),
                "ytd_months": summary.ytd_months,
            },
            "alerts": [
                {
                    "type": alert.threshold_type.value,
                    "threshold": float(alert.threshold_amount),
                    "current": float(alert.current_amount),
                    "distance": float(alert.distance_to_threshold),
                    "percentage": float(alert.percentage_to_threshold),
                    "is_crossed": alert.is_crossed,
                    "level": alert.alert_level,
                    "message": alert.message,
                    "recommendations": alert.recommendations,
                    "additional_tax": float(alert.estimated_additional_tax) if alert.estimated_additional_tax else None,
                    "planning_window_days": alert.tax_planning_window_days,
                }
                for alert in summary.alerts
            ],
            "projection": {
                "monthly_revenue": float(summary.growth_projection.current_monthly_revenue),
                "growth_rate": float(summary.growth_projection.average_monthly_growth_rate),
                "projected_annual": float(summary.growth_projection.projected_annual_revenue),
                "projected_bracket": summary.growth_projection.projected_tax_bracket.value,
                "projected_taxes": {
                    "cit": float(summary.growth_projection.projected_cit),
                    "dev_levy": float(summary.growth_projection.projected_dev_levy),
                    "tet": float(summary.growth_projection.projected_tet),
                    "total": float(summary.growth_projection.projected_total_tax),
                },
                "months_to_small_threshold": summary.growth_projection.months_to_small_threshold,
                "months_to_medium_threshold": summary.growth_projection.months_to_medium_threshold,
                "confidence": summary.growth_projection.confidence_level,
            } if summary.growth_projection else None,
            "transition_plan": {
                "current_bracket": summary.transition_plan.current_bracket.value,
                "target_bracket": summary.transition_plan.target_bracket.value,
                "threshold": float(summary.transition_plan.threshold_amount),
                "buffer": float(summary.transition_plan.buffer_amount),
                "revenue_to_defer": float(summary.transition_plan.revenue_to_defer),
                "tax_saved": float(summary.transition_plan.tax_saved_by_staying_below),
                "strategies": summary.transition_plan.strategies,
                "risks": summary.transition_plan.risks,
                "timeline": summary.transition_plan.timeline,
                "actions": summary.transition_plan.recommended_actions,
            } if summary.transition_plan else None,
            "scores": {
                "risk": summary.risk_score,
                "opportunity": summary.opportunity_score,
            },
            "generated_at": summary.generated_at.isoformat(),
        }


# Singleton instance
growth_radar_service = GrowthRadarService()
