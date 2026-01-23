"""
Export and Download Router

Provides endpoints for exporting financial reports and downloading data
in various formats (PDF, Excel, CSV).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Literal
from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel
import csv
import io
import json

from app.database import get_async_session
from app.dependencies import get_current_active_user, verify_entity_access
from app.models.user import User
from app.services.reports_service import ReportsService
from app.services.audit_service import AuditService
from app.models.audit_consolidated import AuditAction

router = APIRouter(
    prefix="/api/v1/{entity_id}/exports",
    tags=["Export & Download"],
)


# ===========================================
# REPORT EXPORTS
# ===========================================

class ExportMetadata(BaseModel):
    """Metadata for export."""
    report_type: str
    format: str
    generated_at: datetime
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    entity_id: UUID


@router.get(
    "/reports/profit-loss",
    summary="Export Profit & Loss Report",
    description="Download the Profit & Loss statement in the specified format.",
)
async def export_profit_loss(
    entity_id: UUID,
    start_date: date = Query(..., description="Report start date"),
    end_date: date = Query(..., description="Report end date"),
    format: Literal["pdf", "excel", "csv", "json"] = Query("pdf", description="Export format"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Export Profit & Loss report."""
    await verify_entity_access(entity_id, current_user, db)
    
    reports_service = ReportsService(db)
    
    try:
        report_data = await reports_service.generate_profit_loss(
            entity_id=entity_id,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}",
        )
    
    # Audit logging for report export
    audit_service = AuditService(db)
    await audit_service.log_action(
        business_entity_id=entity_id,
        entity_type="report_export",
        entity_id=f"profit_loss_{start_date}_{end_date}",
        action=AuditAction.EXPORT,
        user_id=current_user.id,
        new_values={
            "report_type": "profit_loss",
            "format": format,
            "start_date": str(start_date),
            "end_date": str(end_date),
        }
    )
    
    if format == "json":
        return report_data
    
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Category', 'Amount'])
        
        # Revenue
        writer.writerow(['REVENUE', ''])
        for item in report_data.get('revenue', []):
            writer.writerow([item['name'], item['amount']])
        writer.writerow(['Total Revenue', report_data.get('total_revenue', 0)])
        
        writer.writerow(['', ''])
        
        # Expenses
        writer.writerow(['EXPENSES', ''])
        for item in report_data.get('expenses', []):
            writer.writerow([item['name'], item['amount']])
        writer.writerow(['Total Expenses', report_data.get('total_expenses', 0)])
        
        writer.writerow(['', ''])
        writer.writerow(['NET PROFIT/LOSS', report_data.get('net_profit', 0)])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=profit_loss_{start_date}_{end_date}.csv"
            }
        )
    
    elif format == "excel":
        # Placeholder for Excel export - would use openpyxl in production
        # For now, return CSV with Excel mime type
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Profit & Loss Statement', f'{start_date} to {end_date}'])
        writer.writerow(['Category', 'Amount'])
        
        for item in report_data.get('revenue', []):
            writer.writerow([item['name'], item['amount']])
        writer.writerow(['Total Revenue', report_data.get('total_revenue', 0)])
        
        for item in report_data.get('expenses', []):
            writer.writerow([item['name'], item['amount']])
        writer.writerow(['Total Expenses', report_data.get('total_expenses', 0)])
        writer.writerow(['Net Profit/Loss', report_data.get('net_profit', 0)])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=profit_loss_{start_date}_{end_date}.xlsx"
            }
        )
    
    else:  # PDF
        # Placeholder for PDF generation
        pdf_content = f"""
        PROFIT & LOSS STATEMENT
        Period: {start_date} to {end_date}
        
        Total Revenue: {report_data.get('total_revenue', 0)}
        Total Expenses: {report_data.get('total_expenses', 0)}
        Net Profit/Loss: {report_data.get('net_profit', 0)}
        """.encode()
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=profit_loss_{start_date}_{end_date}.pdf"
            }
        )


@router.get(
    "/reports/cash-flow",
    summary="Export Cash Flow Statement",
    description="Download the Cash Flow statement in the specified format.",
)
async def export_cash_flow(
    entity_id: UUID,
    start_date: date = Query(..., description="Report start date"),
    end_date: date = Query(..., description="Report end date"),
    format: Literal["pdf", "excel", "csv", "json"] = Query("pdf", description="Export format"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Export Cash Flow statement."""
    await verify_entity_access(entity_id, current_user, db)
    
    reports_service = ReportsService(db)
    
    try:
        report_data = await reports_service.generate_cash_flow(
            entity_id=entity_id,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}",
        )
    
    if format == "json":
        return report_data
    
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Category', 'Amount'])
        
        writer.writerow(['Operating Activities', report_data.get('operating_activities', 0)])
        writer.writerow(['Investing Activities', report_data.get('investing_activities', 0)])
        writer.writerow(['Financing Activities', report_data.get('financing_activities', 0)])
        writer.writerow(['Net Cash Flow', report_data.get('net_cash_flow', 0)])
        writer.writerow(['Opening Balance', report_data.get('opening_balance', 0)])
        writer.writerow(['Closing Balance', report_data.get('closing_balance', 0)])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=cash_flow_{start_date}_{end_date}.csv"
            }
        )
    
    else:  # PDF/Excel placeholder
        content = f"""
        CASH FLOW STATEMENT
        Period: {start_date} to {end_date}
        
        Operating Activities: {report_data.get('operating_activities', 0)}
        Investing Activities: {report_data.get('investing_activities', 0)}
        Financing Activities: {report_data.get('financing_activities', 0)}
        Net Cash Flow: {report_data.get('net_cash_flow', 0)}
        """.encode()
        
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=cash_flow_{start_date}_{end_date}.pdf"
            }
        )


@router.get(
    "/reports/balance-sheet",
    summary="Export Balance Sheet",
    description="Download the Balance Sheet in the specified format.",
)
async def export_balance_sheet(
    entity_id: UUID,
    as_of_date: date = Query(..., description="Balance sheet date"),
    format: Literal["pdf", "excel", "csv", "json"] = Query("pdf", description="Export format"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Export Balance Sheet."""
    await verify_entity_access(entity_id, current_user, db)
    
    reports_service = ReportsService(db)
    
    try:
        report_data = await reports_service.generate_balance_sheet(
            entity_id=entity_id,
            as_of_date=as_of_date,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}",
        )
    
    if format == "json":
        return report_data
    
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Category', 'Amount'])
        
        writer.writerow(['ASSETS', ''])
        writer.writerow(['Total Assets', report_data.get('total_assets', 0)])
        
        writer.writerow(['LIABILITIES', ''])
        writer.writerow(['Total Liabilities', report_data.get('total_liabilities', 0)])
        
        writer.writerow(['EQUITY', ''])
        writer.writerow(['Total Equity', report_data.get('total_equity', 0)])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=balance_sheet_{as_of_date}.csv"
            }
        )
    
    else:  # PDF/Excel
        content = f"""
        BALANCE SHEET
        As of: {as_of_date}
        
        Total Assets: {report_data.get('total_assets', 0)}
        Total Liabilities: {report_data.get('total_liabilities', 0)}
        Total Equity: {report_data.get('total_equity', 0)}
        """.encode()
        
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=balance_sheet_{as_of_date}.pdf"
            }
        )


@router.get(
    "/reports/tax-summary",
    summary="Export Tax Summary Report",
    description="Download tax summary with VAT, CIT, and WHT details.",
)
async def export_tax_summary(
    entity_id: UUID,
    tax_year: int = Query(..., description="Tax year"),
    format: Literal["pdf", "excel", "csv", "json"] = Query("pdf", description="Export format"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Export Tax Summary."""
    await verify_entity_access(entity_id, current_user, db)
    
    reports_service = ReportsService(db)
    
    try:
        report_data = await reports_service.generate_tax_summary(
            entity_id=entity_id,
            tax_year=tax_year,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}",
        )
    
    if format == "json":
        return report_data
    
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Tax Type', 'Amount Due', 'Amount Paid', 'Balance'])
        
        for tax_type in ['vat', 'cit', 'wht']:
            tax_data = report_data.get(tax_type, {})
            writer.writerow([
                tax_type.upper(),
                tax_data.get('amount_due', 0),
                tax_data.get('amount_paid', 0),
                tax_data.get('balance', 0),
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=tax_summary_{tax_year}.csv"
            }
        )
    
    else:  # PDF
        content = f"""
        TAX SUMMARY REPORT
        Tax Year: {tax_year}
        
        VAT: {report_data.get('vat', {}).get('balance', 0)}
        CIT: {report_data.get('cit', {}).get('balance', 0)}
        WHT: {report_data.get('wht', {}).get('balance', 0)}
        """.encode()
        
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=tax_summary_{tax_year}.pdf"
            }
        )


# ===========================================
# AUDIT TRAIL EXPORTS
# ===========================================

@router.get(
    "/audit-trail",
    summary="Export Audit Trail",
    description="Download the audit trail for compliance purposes.",
)
async def export_audit_trail(
    entity_id: UUID,
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    format: Literal["csv", "json"] = Query("csv", description="Export format"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Export audit trail."""
    await verify_entity_access(entity_id, current_user, db)
    
    from app.services.audit_service import AuditService
    audit_service = AuditService(db)
    
    logs = await audit_service.get_audit_logs(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
        action_type=action_type,
        limit=10000,  # High limit for export
    )
    
    if format == "json":
        return {"audit_logs": logs}
    
    else:  # CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['timestamp', 'user', 'action', 'resource_type', 'resource_id', 'details', 'ip_address'])
        
        for log in logs:
            writer.writerow([
                log.get('timestamp', ''),
                log.get('user_email', ''),
                log.get('action', ''),
                log.get('resource_type', ''),
                log.get('resource_id', ''),
                json.dumps(log.get('details', {})),
                log.get('ip_address', ''),
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_trail_{entity_id}_{date.today().isoformat()}.csv"
            }
        )


# ===========================================
# DATA BACKUP EXPORT
# ===========================================

@router.get(
    "/backup",
    summary="Export All Data",
    description="Download a complete backup of all entity data for archival purposes.",
)
async def export_full_backup(
    entity_id: UUID,
    include_audit: bool = Query(True, description="Include audit trail"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Export full data backup."""
    await verify_entity_access(entity_id, current_user, db)
    
    # In production, this would compile all entity data
    # For now, return metadata
    backup_data = {
        "export_info": {
            "entity_id": str(entity_id),
            "exported_at": datetime.now().isoformat(),
            "exported_by": current_user.email,
            "version": "1.0",
        },
        "data_summary": {
            "transactions": 0,
            "invoices": 0,
            "customers": 0,
            "vendors": 0,
            "inventory_items": 0,
            "audit_logs": 0 if not include_audit else 0,
        },
    }
    
    return Response(
        content=json.dumps(backup_data, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=backup_{entity_id}_{date.today().isoformat()}.json"
        }
    )
