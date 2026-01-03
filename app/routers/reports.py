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
