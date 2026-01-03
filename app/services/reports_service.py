"""
TekVwarho ProAudit - Reports Service

Financial and tax reporting service.

Reports:
- Profit & Loss Statement
- Balance Sheet (simplified)
- Cash Flow Statement
- VAT Return Report
- PAYE Summary
- WHT Summary
- CIT Calculation Report
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionType
from app.models.invoice import Invoice, InvoiceStatus
from app.models.category import Category


class ReportsService:
    """Service for generating financial and tax reports."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ===========================================
    # PROFIT & LOSS REPORT
    # ===========================================
    
    async def generate_profit_loss(
        self,
        entity_id: uuid.UUID,
        start_date: date,
        end_date: date,
        include_details: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate Profit & Loss (Income Statement) report.
        
        Structure:
        - Revenue
          - Sales/Service Income
          - Other Income
        - Less: Cost of Sales
        - Gross Profit
        - Less: Operating Expenses
        - Operating Profit
        - Less: Tax
        - Net Profit
        """
        # Get income by category
        income_result = await self.db.execute(
            select(
                Category.name.label("category"),
                func.sum(Transaction.amount).label("total"),
            )
            .join(Category, Transaction.category_id == Category.id, isouter=True)
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.INCOME)
            .where(Transaction.transaction_date >= start_date)
            .where(Transaction.transaction_date <= end_date)
            .group_by(Category.name)
        )
        income_categories = {
            row.category or "Uncategorized": float(row.total)
            for row in income_result
        }
        total_income = sum(income_categories.values())
        
        # Get expenses by category
        expense_result = await self.db.execute(
            select(
                Category.name.label("category"),
                Category.wren_status.label("wren_status"),
                func.sum(Transaction.amount).label("total"),
            )
            .join(Category, Transaction.category_id == Category.id, isouter=True)
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.EXPENSE)
            .where(Transaction.transaction_date >= start_date)
            .where(Transaction.transaction_date <= end_date)
            .group_by(Category.name, Category.wren_status)
        )
        expense_categories = {}
        for row in expense_result:
            cat_name = row.category or "Uncategorized"
            expense_categories[cat_name] = {
                "total": float(row.total),
                "wren_status": row.wren_status.value if row.wren_status else None,
            }
        total_expenses = sum(exp["total"] for exp in expense_categories.values())
        
        # Calculate VAT
        vat_result = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.vat_amount), 0).label("total_vat"),
            )
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_date >= start_date)
            .where(Transaction.transaction_date <= end_date)
        )
        total_vat = float(vat_result.scalar() or 0)
        
        # Calculate net profit
        gross_profit = total_income - total_expenses
        
        report = {
            "report_type": "profit_loss",
            "entity_id": str(entity_id),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_revenue": total_income,
                "total_expenses": total_expenses,
                "gross_profit": gross_profit,
                "vat_collected": total_vat,
                "net_profit": gross_profit,
            },
            "revenue": {
                "categories": income_categories,
                "total": total_income,
            },
            "expenses": {
                "categories": expense_categories,
                "total": total_expenses,
            },
        }
        
        if include_details:
            # Add transaction details
            income_transactions = await self._get_transactions_summary(
                entity_id, start_date, end_date, TransactionType.INCOME
            )
            expense_transactions = await self._get_transactions_summary(
                entity_id, start_date, end_date, TransactionType.EXPENSE
            )
            report["details"] = {
                "income_transactions": income_transactions,
                "expense_transactions": expense_transactions,
            }
        
        return report
    
    async def _get_transactions_summary(
        self,
        entity_id: uuid.UUID,
        start_date: date,
        end_date: date,
        transaction_type: TransactionType,
    ) -> List[Dict[str, Any]]:
        """Get transaction summary for report details."""
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == transaction_type)
            .where(Transaction.transaction_date >= start_date)
            .where(Transaction.transaction_date <= end_date)
            .order_by(Transaction.transaction_date)
            .limit(100)
        )
        
        return [
            {
                "id": str(t.id),
                "date": t.transaction_date.isoformat(),
                "description": t.description,
                "amount": float(t.amount),
                "vat_amount": float(t.vat_amount) if t.vat_amount else 0,
            }
            for t in result.scalars()
        ]
    
    # ===========================================
    # CASH FLOW REPORT
    # ===========================================
    
    async def generate_cash_flow(
        self,
        entity_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Generate Cash Flow Statement.
        
        Simplified format:
        - Cash from Operating Activities
        - Cash from Investing Activities
        - Cash from Financing Activities
        - Net Change in Cash
        """
        # Operating activities (income minus expenses)
        income_total = await self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.INCOME)
            .where(Transaction.transaction_date >= start_date)
            .where(Transaction.transaction_date <= end_date)
        ) or 0
        
        expense_total = await self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.EXPENSE)
            .where(Transaction.transaction_date >= start_date)
            .where(Transaction.transaction_date <= end_date)
        ) or 0
        
        # Receivables (invoices)
        invoiced_total = await self.db.scalar(
            select(func.coalesce(func.sum(Invoice.total_amount), 0))
            .where(Invoice.entity_id == entity_id)
            .where(Invoice.invoice_date >= start_date)
            .where(Invoice.invoice_date <= end_date)
            .where(Invoice.status.in_([InvoiceStatus.FINALIZED, InvoiceStatus.PAID]))
        ) or 0
        
        collected_total = await self.db.scalar(
            select(func.coalesce(func.sum(Invoice.amount_paid), 0))
            .where(Invoice.entity_id == entity_id)
            .where(Invoice.invoice_date >= start_date)
            .where(Invoice.invoice_date <= end_date)
        ) or 0
        
        operating_cash_flow = float(income_total) - float(expense_total)
        receivables_change = float(invoiced_total) - float(collected_total)
        
        return {
            "report_type": "cash_flow",
            "entity_id": str(entity_id),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "operating_activities": {
                "cash_received": float(income_total),
                "cash_paid": float(expense_total),
                "net_operating": operating_cash_flow,
            },
            "receivables": {
                "invoiced": float(invoiced_total),
                "collected": float(collected_total),
                "outstanding": receivables_change,
            },
            "summary": {
                "net_cash_flow": operating_cash_flow,
            },
        }
    
    # ===========================================
    # INCOME/EXPENSE SUMMARY
    # ===========================================
    
    async def generate_summary(
        self,
        entity_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """Generate income/expense summary for dashboard."""
        # Monthly breakdown
        monthly_result = await self.db.execute(
            select(
                func.date_trunc('month', Transaction.transaction_date).label("month"),
                Transaction.transaction_type,
                func.sum(Transaction.amount).label("total"),
            )
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_date >= start_date)
            .where(Transaction.transaction_date <= end_date)
            .group_by(
                func.date_trunc('month', Transaction.transaction_date),
                Transaction.transaction_type,
            )
            .order_by(func.date_trunc('month', Transaction.transaction_date))
        )
        
        monthly_data = {}
        for row in monthly_result:
            month_str = row.month.strftime("%Y-%m")
            if month_str not in monthly_data:
                monthly_data[month_str] = {"income": 0, "expense": 0}
            
            if row.transaction_type == TransactionType.INCOME:
                monthly_data[month_str]["income"] = float(row.total)
            else:
                monthly_data[month_str]["expense"] = float(row.total)
        
        # Calculate totals
        total_income = sum(m["income"] for m in monthly_data.values())
        total_expense = sum(m["expense"] for m in monthly_data.values())
        
        return {
            "entity_id": str(entity_id),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "totals": {
                "income": total_income,
                "expense": total_expense,
                "net": total_income - total_expense,
            },
            "monthly": monthly_data,
        }
    
    # ===========================================
    # TAX REPORTS
    # ===========================================
    
    async def generate_vat_return(
        self,
        entity_id: uuid.UUID,
        year: int,
        month: int,
    ) -> Dict[str, Any]:
        """Generate VAT return report for FIRS filing."""
        from calendar import monthrange
        
        start_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)
        
        # Output VAT (from invoices)
        output_vat = await self.db.scalar(
            select(func.coalesce(func.sum(Invoice.vat_amount), 0))
            .where(Invoice.entity_id == entity_id)
            .where(Invoice.invoice_date >= start_date)
            .where(Invoice.invoice_date <= end_date)
            .where(Invoice.status.in_([InvoiceStatus.FINALIZED, InvoiceStatus.PAID]))
        ) or 0
        
        # Input VAT (from expenses)
        input_vat = await self.db.scalar(
            select(func.coalesce(func.sum(Transaction.vat_amount), 0))
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.EXPENSE)
            .where(Transaction.transaction_date >= start_date)
            .where(Transaction.transaction_date <= end_date)
        ) or 0
        
        net_vat = float(output_vat) - float(input_vat)
        
        return {
            "report_type": "vat_return",
            "entity_id": str(entity_id),
            "period": f"{year}-{month:02d}",
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "output_vat": {
                "description": "VAT collected on sales",
                "amount": float(output_vat),
            },
            "input_vat": {
                "description": "VAT paid on purchases",
                "amount": float(input_vat),
            },
            "net_vat_payable": net_vat,
            "is_refund": net_vat < 0,
            "filing_deadline": date(year, month + 1 if month < 12 else 1, 21).isoformat(),
        }
    
    async def generate_paye_summary(
        self,
        entity_id: uuid.UUID,
        year: int,
        month: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate PAYE summary report."""
        from app.models.tax import PAYERecord
        
        query = select(
            func.count(PAYERecord.id).label("employee_count"),
            func.sum(PAYERecord.gross_salary).label("total_gross"),
            func.sum(PAYERecord.tax_amount).label("total_paye"),
        ).where(PAYERecord.entity_id == entity_id).where(PAYERecord.period_year == year)
        
        if month:
            query = query.where(PAYERecord.period_month == month)
        
        result = await self.db.execute(query)
        row = result.one()
        
        return {
            "report_type": "paye_summary",
            "entity_id": str(entity_id),
            "year": year,
            "month": month,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "employee_count": row.employee_count or 0,
                "total_gross_salary": float(row.total_gross or 0),
                "total_paye_tax": float(row.total_paye or 0),
            },
        }
    
    async def generate_wht_summary(
        self,
        entity_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """Generate WHT summary report."""
        # Get WHT from expense transactions
        result = await self.db.execute(
            select(
                func.count(Transaction.id).label("count"),
                func.sum(Transaction.wht_amount).label("total_wht"),
                func.sum(Transaction.amount).label("total_gross"),
            )
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.EXPENSE)
            .where(Transaction.transaction_date >= start_date)
            .where(Transaction.transaction_date <= end_date)
            .where(Transaction.wht_amount > 0)
        )
        row = result.one()
        
        return {
            "report_type": "wht_summary",
            "entity_id": str(entity_id),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "transaction_count": row.count or 0,
                "total_gross_payments": float(row.total_gross or 0),
                "total_wht_deducted": float(row.total_wht or 0),
            },
        }
    
    async def generate_cit_report(
        self,
        entity_id: uuid.UUID,
        fiscal_year: int,
    ) -> Dict[str, Any]:
        """Generate CIT calculation report."""
        start_date = date(fiscal_year, 1, 1)
        end_date = date(fiscal_year, 12, 31)
        
        # Get P&L data
        pnl = await self.generate_profit_loss(entity_id, start_date, end_date)
        
        turnover = pnl["summary"]["total_revenue"]
        profit = pnl["summary"]["gross_profit"]
        
        # Calculate CIT
        from app.services.tax_calculators.cit_service import CITCalculator
        
        cit_result = CITCalculator.calculate_cit(
            gross_turnover=turnover,
            assessable_profit=profit,
        )
        
        return {
            "report_type": "cit_calculation",
            "entity_id": str(entity_id),
            "fiscal_year": fiscal_year,
            "generated_at": datetime.utcnow().isoformat(),
            "financial_summary": {
                "gross_turnover": turnover,
                "total_expenses": pnl["summary"]["total_expenses"],
                "assessable_profit": profit,
            },
            "cit_calculation": cit_result,
        }
    
    # ===========================================
    # DASHBOARD METRICS
    # ===========================================
    
    async def get_dashboard_metrics(
        self,
        entity_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Get dashboard metrics for an entity."""
        today = date.today()
        month_start = date(today.year, today.month, 1)
        year_start = date(today.year, 1, 1)
        
        # This month totals
        month_income = await self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.INCOME)
            .where(Transaction.transaction_date >= month_start)
        ) or 0
        
        month_expense = await self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.EXPENSE)
            .where(Transaction.transaction_date >= month_start)
        ) or 0
        
        # Year to date totals
        ytd_income = await self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.INCOME)
            .where(Transaction.transaction_date >= year_start)
        ) or 0
        
        ytd_expense = await self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.EXPENSE)
            .where(Transaction.transaction_date >= year_start)
        ) or 0
        
        # Outstanding invoices
        outstanding = await self.db.scalar(
            select(func.coalesce(
                func.sum(Invoice.total_amount - Invoice.amount_paid), 0
            ))
            .where(Invoice.entity_id == entity_id)
            .where(Invoice.status == InvoiceStatus.FINALIZED)
        ) or 0
        
        # Overdue invoices
        overdue = await self.db.scalar(
            select(func.coalesce(
                func.sum(Invoice.total_amount - Invoice.amount_paid), 0
            ))
            .where(Invoice.entity_id == entity_id)
            .where(Invoice.status == InvoiceStatus.FINALIZED)
            .where(Invoice.due_date < today)
        ) or 0
        
        return {
            "entity_id": str(entity_id),
            "generated_at": datetime.utcnow().isoformat(),
            "this_month": {
                "income": float(month_income),
                "expense": float(month_expense),
                "net": float(month_income) - float(month_expense),
            },
            "year_to_date": {
                "income": float(ytd_income),
                "expense": float(ytd_expense),
                "net": float(ytd_income) - float(ytd_expense),
            },
            "receivables": {
                "outstanding": float(outstanding),
                "overdue": float(overdue),
            },
        }
