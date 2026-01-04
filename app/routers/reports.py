"""
TekVwarho ProAudit - Reports Router

API endpoints for financial and tax reports.
"""

import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.dependencies import get_current_active_user
from app.services.reports_service import ReportsService
from app.models.user import User

router = APIRouter()


# ===========================================
# FINANCIAL REPORTS
# ===========================================

@router.get("/{entity_id}/reports/profit-loss")
async def get_profit_loss_report(
    entity_id: uuid.UUID,
    start_date: date = Query(..., description="Report period start date"),
    end_date: date = Query(..., description="Report period end date"),
    include_details: bool = Query(False, description="Include transaction details"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate Profit & Loss (Income Statement) report.
    
    Shows:
    - Revenue breakdown by category
    - Expense breakdown by category with WREN status
    - Gross profit calculation
    - VAT collected
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date",
        )
    
    service = ReportsService(db)
    report = await service.generate_profit_loss(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
        include_details=include_details,
    )
    
    return report


@router.get("/{entity_id}/reports/cash-flow")
async def get_cash_flow_report(
    entity_id: uuid.UUID,
    start_date: date = Query(..., description="Report period start date"),
    end_date: date = Query(..., description="Report period end date"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate Cash Flow Statement.
    
    Shows:
    - Cash from operating activities
    - Receivables status
    - Net cash flow
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date",
        )
    
    service = ReportsService(db)
    report = await service.generate_cash_flow(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    return report


@router.get("/{entity_id}/reports/summary")
async def get_income_expense_summary(
    entity_id: uuid.UUID,
    start_date: date = Query(..., description="Report period start date"),
    end_date: date = Query(..., description="Report period end date"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get income/expense summary with monthly breakdown.
    
    Ideal for charts and trend analysis.
    """
    service = ReportsService(db)
    summary = await service.generate_summary(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    return summary


@router.get("/{entity_id}/reports/dashboard")
async def get_dashboard_metrics(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get dashboard metrics.
    
    Returns:
    - This month's income/expense
    - Year-to-date totals
    - Outstanding and overdue receivables
    """
    service = ReportsService(db)
    metrics = await service.get_dashboard_metrics(entity_id=entity_id)
    
    return metrics


# ===========================================
# COMPLIANCE HEALTH & THRESHOLD MONITORING
# ===========================================

@router.get("/{entity_id}/reports/compliance-health")
async def get_compliance_health(
    entity_id: uuid.UUID,
    include_alerts: bool = Query(True, description="Include threshold alerts"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get real-time Compliance Health score with automated threshold monitoring.
    
    2026 Tax Reforms Compliance Checks:
    - TIN Registration (required for NRS e-invoicing)
    - CAC Registration
    - Small Company Status (0% CIT eligibility: Turnover ≤₦50M, Assets ≤₦250M)
    - Development Levy Exemption (Turnover ≤₦100M, Assets ≤₦250M)
    - VAT Registration threshold (₦25M annual turnover)
    
    Threshold Monitoring:
    - Automatic alerts when approaching threshold limits
    - Warning when turnover reaches 80% of threshold
    - Critical alerts when compliance issues detected
    
    Returns:
    - overall_status: 'excellent', 'good', 'warning', or 'critical'
    - score: 0-100 percentage
    - checks: Array of individual compliance check results
    - alerts: Threshold alerts (if include_alerts=True)
    - thresholds: Current values vs threshold limits
    """
    from app.services.compliance_health_service import ComplianceHealthService
    
    service = ComplianceHealthService(db)
    health = await service.get_compliance_health(
        entity_id=entity_id,
        include_alerts=include_alerts,
    )
    
    return health


@router.get("/{entity_id}/reports/compliance-health/thresholds")
async def get_compliance_thresholds(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get current threshold status for all compliance metrics.
    
    Shows:
    - Current values vs threshold limits
    - Percentage of threshold used
    - Estimated time to threshold breach (based on trend)
    """
    from app.services.compliance_health_service import ComplianceHealthService
    
    service = ComplianceHealthService(db)
    thresholds = await service.get_threshold_status(entity_id=entity_id)
    
    return thresholds


@router.get("/{entity_id}/reports/compliance-health/alerts")
async def get_compliance_alerts(
    entity_id: uuid.UUID,
    severity: Optional[str] = Query(None, description="Filter by severity: critical, warning, info"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get compliance threshold alerts.
    
    Alert Types:
    - VAT registration threshold approaching (80% of ₦25M)
    - Small Company status at risk (approaching ₦50M turnover)
    - Development Levy exemption at risk (approaching ₦100M turnover)
    - Missing required registrations (TIN, CAC)
    
    Severity Levels:
    - critical: Requires immediate action
    - warning: Threshold approaching
    - info: Informational notice
    """
    from app.services.compliance_health_service import ComplianceHealthService
    
    service = ComplianceHealthService(db)
    alerts = await service.get_alerts(entity_id=entity_id, severity=severity)
    
    return alerts


@router.post("/{entity_id}/reports/compliance-health/subscribe")
async def subscribe_to_compliance_alerts(
    entity_id: uuid.UUID,
    alert_types: list = Query(["critical", "warning"], description="Alert types to subscribe to"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Subscribe to compliance threshold alerts.
    
    Users will receive notifications when:
    - Approaching VAT registration threshold
    - Risk of losing Small Company status
    - Risk of losing Development Levy exemption
    - Critical compliance issues detected
    """
    from app.services.compliance_health_service import ComplianceHealthService
    
    service = ComplianceHealthService(db)
    subscription = await service.subscribe_alerts(
        entity_id=entity_id,
        user_id=current_user.id,
        alert_types=alert_types,
    )
    
    return subscription


# ===========================================
# TAX REPORTS
# ===========================================

@router.get("/{entity_id}/reports/tax/vat-return")
async def get_vat_return_report(
    entity_id: uuid.UUID,
    year: int = Query(..., ge=2020, le=2100, description="Tax year"),
    month: int = Query(..., ge=1, le=12, description="Tax month"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate VAT Return report for FIRS filing.
    
    Shows:
    - Output VAT (from sales)
    - Input VAT (from purchases)
    - Net VAT payable/refundable
    - Filing deadline
    """
    service = ReportsService(db)
    report = await service.generate_vat_return(
        entity_id=entity_id,
        year=year,
        month=month,
    )
    
    return report


@router.get("/{entity_id}/reports/tax/paye-summary")
async def get_paye_summary_report(
    entity_id: uuid.UUID,
    year: int = Query(..., ge=2020, le=2100, description="Tax year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Tax month (optional)"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate PAYE summary report.
    
    Shows:
    - Employee count
    - Total gross salaries
    - Total PAYE tax withheld
    """
    service = ReportsService(db)
    report = await service.generate_paye_summary(
        entity_id=entity_id,
        year=year,
        month=month,
    )
    
    return report


@router.get("/{entity_id}/reports/tax/wht-summary")
async def get_wht_summary_report(
    entity_id: uuid.UUID,
    start_date: date = Query(..., description="Report period start date"),
    end_date: date = Query(..., description="Report period end date"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate WHT summary report.
    
    Shows:
    - Transaction count with WHT
    - Total gross payments
    - Total WHT deducted
    """
    service = ReportsService(db)
    report = await service.generate_wht_summary(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    return report


@router.get("/{entity_id}/reports/tax/cit")
async def get_cit_report(
    entity_id: uuid.UUID,
    fiscal_year: int = Query(..., ge=2020, le=2100, description="Fiscal year"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate Company Income Tax (CIT) calculation report.
    
    Shows:
    - Financial summary (turnover, expenses, profit)
    - Company size classification
    - CIT calculation with applicable rate
    - Tertiary Education Tax
    - Minimum tax calculation
    """
    service = ReportsService(db)
    report = await service.generate_cit_report(
        entity_id=entity_id,
        fiscal_year=fiscal_year,
    )
    
    return report


# ===========================================
# TRIAL BALANCE & BALANCE SHEET
# ===========================================

@router.get("/{entity_id}/reports/trial-balance")
async def get_trial_balance(
    entity_id: uuid.UUID,
    as_of_date: date = Query(..., description="Trial balance as of date"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate Trial Balance report.
    
    Shows:
    - All accounts with debit/credit balances
    - Total debits and credits (should match)
    - Account category breakdown
    """
    service = ReportsService(db)
    report = await service.generate_trial_balance(
        entity_id=entity_id,
        as_of_date=as_of_date,
    )
    
    return report


@router.get("/{entity_id}/reports/balance-sheet")
async def get_balance_sheet(
    entity_id: uuid.UUID,
    as_of_date: date = Query(..., description="Balance sheet as of date"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate Balance Sheet report.
    
    Shows:
    - Assets (Current and Fixed)
    - Liabilities
    - Owner's Equity
    - Accounting equation validation
    """
    service = ReportsService(db)
    report = await service.generate_balance_sheet(
        entity_id=entity_id,
        as_of_date=as_of_date,
    )
    
    return report


@router.get("/{entity_id}/reports/fixed-assets")
async def get_fixed_assets_report(
    entity_id: uuid.UUID,
    as_of_date: date = Query(..., description="Report as of date"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate Fixed Asset Register report.
    
    Shows:
    - All fixed assets with acquisition details
    - Depreciation schedules
    - Net book values
    - Capital gains/losses on disposals
    """
    service = ReportsService(db)
    report = await service.generate_fixed_assets_report(
        entity_id=entity_id,
        as_of_date=as_of_date,
    )
    
    return report


# ===========================================
# PDF EXPORTS
# ===========================================

@router.get("/{entity_id}/reports/profit-loss/pdf")
async def export_profit_loss_pdf(
    entity_id: uuid.UUID,
    start_date: date = Query(..., description="Report period start date"),
    end_date: date = Query(..., description="Report period end date"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Export Profit & Loss report as PDF.
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date",
        )
    
    service = ReportsService(db)
    pdf_data = await service.export_profit_loss_pdf(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    from fastapi.responses import StreamingResponse
    import io
    
    return StreamingResponse(
        io.BytesIO(pdf_data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=profit_loss_{start_date}_{end_date}.pdf"
        }
    )


@router.get("/{entity_id}/reports/trial-balance/pdf")
async def export_trial_balance_pdf(
    entity_id: uuid.UUID,
    as_of_date: date = Query(..., description="Trial balance as of date"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Export Trial Balance report as PDF.
    """
    service = ReportsService(db)
    pdf_data = await service.export_trial_balance_pdf(
        entity_id=entity_id,
        as_of_date=as_of_date,
    )
    
    from fastapi.responses import StreamingResponse
    import io
    
    return StreamingResponse(
        io.BytesIO(pdf_data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=trial_balance_{as_of_date}.pdf"
        }
    )


@router.get("/{entity_id}/reports/fixed-assets/pdf")
async def export_fixed_assets_pdf(
    entity_id: uuid.UUID,
    as_of_date: date = Query(..., description="Report as of date"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Export Fixed Asset Register as PDF.
    """
    service = ReportsService(db)
    pdf_data = await service.export_fixed_assets_pdf(
        entity_id=entity_id,
        as_of_date=as_of_date,
    )
    
    from fastapi.responses import StreamingResponse
    import io
    
    return StreamingResponse(
        io.BytesIO(pdf_data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=fixed_asset_register_{as_of_date}.pdf"
        }
    )
