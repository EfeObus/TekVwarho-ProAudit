"""
Audit and Compliance Reporting Service
Implements comprehensive reporting for Nigerian Tax Reform 2026

Reports:
- Transaction History Logs (Audit Trail)
- NRS Reconciliation Report
- WHT Credit Note Tracker
- Input VAT Recovery Schedule
- Payroll Statutory Schedules
- AR/AP Aging Reports
- Budget vs Actual Analysis
- Dimensional/Segment Reports
"""

from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from collections import defaultdict
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, case
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


class AuditReportingService:
    """
    Comprehensive audit and compliance reporting service
    """
    
    async def generate_audit_trail(
        self,
        db: AsyncSession,
        entity_id: UUID,
        start_date: date,
        end_date: date,
        user_id: Optional[UUID] = None,
        resource_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Transaction History Logs (Audit Trail)
        
        Shows who created, edited, or deleted any entry with timestamps and IP addresses
        """
        from app.models.audit_consolidated import AuditLog
        from app.models.user import User
        
        # Build query
        query = select(AuditLog).where(
            and_(
                AuditLog.entity_id == entity_id,
                AuditLog.created_at >= datetime.combine(start_date, datetime.min.time()),
                AuditLog.created_at <= datetime.combine(end_date, datetime.max.time())
            )
        ).options(selectinload(AuditLog.user))
        
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        
        query = query.order_by(desc(AuditLog.created_at))
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        # Group by action type
        action_summary = defaultdict(int)
        user_activity = defaultdict(lambda: {"actions": 0, "last_activity": None})
        
        entries = []
        for log in logs:
            action_summary[log.action] += 1
            
            user_key = str(log.user_id) if log.user_id else "system"
            user_activity[user_key]["actions"] += 1
            if not user_activity[user_key]["last_activity"]:
                user_activity[user_key]["last_activity"] = log.created_at.isoformat()
            
            entries.append({
                "id": str(log.id),
                "timestamp": log.created_at.isoformat(),
                "user_id": str(log.user_id) if log.user_id else None,
                "user_email": log.user.email if log.user else "System",
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "changes": log.changes if hasattr(log, 'changes') else None,
                "ip_address": log.ip_address if hasattr(log, 'ip_address') else None,
                "user_agent": log.user_agent if hasattr(log, 'user_agent') else None,
                "description": log.description if hasattr(log, 'description') else None
            })
        
        return {
            "entity_id": str(entity_id),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "total_entries": len(entries),
                "action_breakdown": dict(action_summary),
                "unique_users": len(user_activity)
            },
            "user_activity": {
                k: v for k, v in user_activity.items()
            },
            "entries": entries,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def generate_nrs_reconciliation(
        self,
        db: AsyncSession,
        entity_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        NRS Reconciliation Report
        
        Compares internal sales records against IRNs generated on the NRS portal
        """
        from app.models.invoice import Invoice
        
        # Get all invoices for period
        query = select(Invoice).where(
            and_(
                Invoice.entity_id == entity_id,
                Invoice.invoice_date >= start_date,
                Invoice.invoice_date <= end_date
            )
        ).order_by(Invoice.invoice_date)
        
        result = await db.execute(query)
        invoices = result.scalars().all()
        
        # Categorize invoices
        matched = []
        unmatched = []
        pending_irn = []
        
        total_internal = Decimal("0")
        total_nrs = Decimal("0")
        
        for inv in invoices:
            total = inv.total_amount or Decimal("0")
            total_internal += total
            
            # Check if invoice has IRN
            has_irn = hasattr(inv, 'irn') and inv.irn
            nrs_validated = hasattr(inv, 'nrs_validated') and inv.nrs_validated
            
            invoice_data = {
                "invoice_id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "customer_name": inv.customer_name if hasattr(inv, 'customer_name') else None,
                "subtotal": str(inv.subtotal or 0),
                "vat_amount": str(inv.vat_amount or 0),
                "total_amount": str(total),
                "irn": inv.irn if has_irn else None,
                "nrs_validated": nrs_validated
            }
            
            if nrs_validated:
                matched.append(invoice_data)
                total_nrs += total
            elif has_irn:
                pending_irn.append(invoice_data)
            else:
                unmatched.append(invoice_data)
        
        variance = total_internal - total_nrs
        variance_percentage = (variance / total_internal * 100) if total_internal else Decimal("0")
        
        # Identify discrepancies
        discrepancies = []
        if variance > 0:
            discrepancies.append({
                "type": "unrecorded_on_nrs",
                "amount": str(variance),
                "description": f"NGN {variance:,.2f} in invoices not yet validated on NRS"
            })
        
        return {
            "entity_id": str(entity_id),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "total_invoices": len(invoices),
                "matched_with_nrs": len(matched),
                "pending_irn": len(pending_irn),
                "unmatched": len(unmatched)
            },
            "financials": {
                "total_internal_sales": str(total_internal),
                "total_nrs_validated": str(total_nrs),
                "variance": str(variance),
                "variance_percentage": str(variance_percentage.quantize(Decimal("0.01")))
            },
            "discrepancies": discrepancies,
            "matched_invoices": matched,
            "pending_invoices": pending_irn,
            "unmatched_invoices": unmatched,
            "reconciliation_status": "matched" if not discrepancies else "discrepancies_found",
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def generate_wht_tracker(
        self,
        db: AsyncSession,
        entity_id: UUID,
        tax_year: int
    ) -> Dict[str, Any]:
        """
        WHT Credit Note Tracker
        
        Schedule of WHT deducted by clients vs credit notes received
        """
        from app.models.advanced_accounting import WHTCreditNote
        from app.models.invoice import Invoice
        
        # Get all WHT credit notes for the year
        credit_notes_query = select(WHTCreditNote).where(
            and_(
                WHTCreditNote.entity_id == entity_id,
                WHTCreditNote.tax_year == tax_year
            )
        ).order_by(WHTCreditNote.issue_date)
        
        result = await db.execute(credit_notes_query)
        credit_notes = result.scalars().all()
        
        # Get invoices where WHT was deducted (estimate from receivables)
        # This would typically come from payment records
        invoices_query = select(Invoice).where(
            and_(
                Invoice.entity_id == entity_id,
                Invoice.invoice_date >= date(tax_year, 1, 1),
                Invoice.invoice_date <= date(tax_year, 12, 31)
            )
        )
        
        inv_result = await db.execute(invoices_query)
        invoices = inv_result.scalars().all()
        
        # Calculate expected WHT (assuming 10% on professional services)
        expected_wht = sum(
            (inv.total_amount or Decimal("0")) * Decimal("0.10") 
            for inv in invoices 
            if hasattr(inv, 'wht_applicable') and inv.wht_applicable
        )
        
        # Group credit notes by status
        received_total = Decimal("0")
        applied_total = Decimal("0")
        pending_total = Decimal("0")
        
        credit_note_details = []
        by_issuer = defaultdict(lambda: {"count": 0, "amount": Decimal("0")})
        
        for cn in credit_notes:
            amount = cn.wht_amount or Decimal("0")
            
            if cn.status == "received" or cn.status == "matched":
                received_total += amount
            if cn.status == "applied":
                applied_total += amount
            if cn.status == "pending":
                pending_total += amount
            
            by_issuer[cn.issuer_name]["count"] += 1
            by_issuer[cn.issuer_name]["amount"] += amount
            
            credit_note_details.append({
                "id": str(cn.id),
                "credit_note_number": cn.credit_note_number,
                "issue_date": cn.issue_date.isoformat() if cn.issue_date else None,
                "issuer_name": cn.issuer_name,
                "issuer_tin": cn.issuer_tin,
                "gross_amount": str(cn.gross_amount),
                "wht_rate": str(cn.wht_rate),
                "wht_amount": str(amount),
                "wht_type": cn.wht_type,
                "status": cn.status.value if hasattr(cn.status, 'value') else cn.status,
                "matched_invoice": str(cn.matched_invoice_id) if cn.matched_invoice_id else None
            })
        
        # Calculate gap
        gap = expected_wht - received_total
        recovery_rate = (received_total / expected_wht * 100) if expected_wht > 0 else Decimal("100")
        
        return {
            "entity_id": str(entity_id),
            "tax_year": tax_year,
            "summary": {
                "total_credit_notes": len(credit_notes),
                "expected_wht": str(expected_wht),
                "received_wht": str(received_total),
                "applied_wht": str(applied_total),
                "pending_wht": str(pending_total),
                "gap": str(gap),
                "recovery_rate": str(recovery_rate.quantize(Decimal("0.01")))
            },
            "by_issuer": {
                k: {"count": v["count"], "amount": str(v["amount"])}
                for k, v in by_issuer.items()
            },
            "credit_notes": credit_note_details,
            "recommendations": [
                f"Outstanding WHT gap of NGN {gap:,.2f} - follow up with clients",
                "Ensure all credit notes are collected within 6 years of issuance",
                "Apply received credit notes against tax liability in quarterly returns"
            ] if gap > 0 else ["All expected WHT credit notes received"],
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def generate_input_vat_schedule(
        self,
        db: AsyncSession,
        entity_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Input VAT Recovery Schedule
        
        Breakdown of VAT paid on services and fixed assets claimed as credit
        """
        from app.models.transaction import Transaction
        from app.models.vendor import Vendor
        
        # Get expense transactions with VAT
        query = select(Transaction).where(
            and_(
                Transaction.entity_id == entity_id,
                Transaction.transaction_type == "expense",
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            )
        ).options(selectinload(Transaction.vendor))
        
        result = await db.execute(query)
        transactions = result.scalars().all()
        
        # Calculate VAT on expenses
        vat_rate = Decimal("7.5") / 100
        
        eligible_items = []
        ineligible_items = []
        total_eligible_vat = Decimal("0")
        total_ineligible_vat = Decimal("0")
        
        by_category = defaultdict(lambda: {"vat": Decimal("0"), "count": 0})
        
        for txn in transactions:
            amount = txn.amount or Decimal("0")
            # Calculate VAT (assume inclusive pricing)
            vat_amount = amount * vat_rate / (1 + vat_rate)
            
            # Determine if VAT is recoverable
            # Non-recoverable: entertainment, personal, exempt supplies
            is_eligible = True
            reason = None
            
            # Check category for eligibility
            category_name = txn.category.name if txn.category else "Uncategorized"
            
            if "entertainment" in category_name.lower():
                is_eligible = False
                reason = "Entertainment expenses - not recoverable"
            elif "personal" in category_name.lower():
                is_eligible = False
                reason = "Personal expenses - not recoverable"
            
            # Check vendor TIN
            vendor_tin = None
            if txn.vendor:
                vendor_tin = txn.vendor.tin
            
            item_data = {
                "id": str(txn.id),
                "date": txn.transaction_date.isoformat() if txn.transaction_date else None,
                "description": txn.description,
                "vendor_name": txn.vendor.name if txn.vendor else None,
                "vendor_tin": vendor_tin,
                "gross_amount": str(amount),
                "vat_amount": str(vat_amount.quantize(Decimal("0.01"))),
                "category": category_name
            }
            
            if is_eligible and vendor_tin:
                eligible_items.append(item_data)
                total_eligible_vat += vat_amount
                by_category[category_name]["vat"] += vat_amount
                by_category[category_name]["count"] += 1
            else:
                item_data["ineligibility_reason"] = reason or "Missing vendor TIN"
                ineligible_items.append(item_data)
                total_ineligible_vat += vat_amount
        
        return {
            "entity_id": str(entity_id),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "total_expenses_reviewed": len(transactions),
                "eligible_for_recovery": len(eligible_items),
                "ineligible": len(ineligible_items),
                "total_eligible_vat": str(total_eligible_vat.quantize(Decimal("0.01"))),
                "total_ineligible_vat": str(total_ineligible_vat.quantize(Decimal("0.01")))
            },
            "by_category": {
                k: {"vat": str(v["vat"].quantize(Decimal("0.01"))), "count": v["count"]}
                for k, v in by_category.items()
            },
            "eligible_items": eligible_items[:100],  # Limit for performance
            "ineligible_items": ineligible_items[:50],
            "recommendations": [
                "Ensure all vendors provide valid TIN for VAT recovery",
                "Entertainment and personal expenses are not VAT recoverable",
                "Fixed assets VAT is fully recoverable in the period of acquisition"
            ],
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def generate_payroll_statutory_schedule(
        self,
        db: AsyncSession,
        entity_id: UUID,
        year: int,
        month: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Consolidated Payroll Statutory Schedule
        
        Monthly and annual breakdown of payroll deductions and contributions
        """
        from app.models.payroll import PayrollRun, PayrollItem
        
        # Build query
        query = select(PayrollRun).where(
            and_(
                PayrollRun.entity_id == entity_id,
                PayrollRun.pay_period_year == year
            )
        ).options(selectinload(PayrollRun.items))
        
        if month:
            query = query.where(PayrollRun.pay_period_month == month)
        
        query = query.order_by(PayrollRun.pay_period_month)
        
        result = await db.execute(query)
        payroll_runs = result.scalars().all()
        
        # Aggregate data
        monthly_data = {}
        annual_totals = {
            "gross_pay": Decimal("0"),
            "basic_salary": Decimal("0"),
            "taxable_income": Decimal("0"),
            "paye": Decimal("0"),
            "pension_employee": Decimal("0"),
            "pension_employer": Decimal("0"),
            "nhf": Decimal("0"),
            "nsitf": Decimal("0"),
            "net_pay": Decimal("0"),
            "employee_count": 0
        }
        
        pension_by_pfa = defaultdict(lambda: {"employee": Decimal("0"), "employer": Decimal("0"), "count": 0})
        
        for run in payroll_runs:
            month_key = f"{year}-{run.pay_period_month:02d}"
            
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    "gross_pay": Decimal("0"),
                    "taxable_income": Decimal("0"),
                    "paye": Decimal("0"),
                    "pension_employee": Decimal("0"),
                    "pension_employer": Decimal("0"),
                    "nhf": Decimal("0"),
                    "nsitf": Decimal("0"),
                    "net_pay": Decimal("0"),
                    "employee_count": 0
                }
            
            for item in run.items:
                monthly_data[month_key]["gross_pay"] += item.gross_pay or Decimal("0")
                monthly_data[month_key]["taxable_income"] += item.taxable_income or Decimal("0")
                monthly_data[month_key]["paye"] += item.paye_tax or Decimal("0")
                monthly_data[month_key]["pension_employee"] += item.pension_employee or Decimal("0")
                monthly_data[month_key]["pension_employer"] += item.pension_employer or Decimal("0")
                monthly_data[month_key]["nhf"] += item.nhf or Decimal("0")
                monthly_data[month_key]["nsitf"] += item.nsitf_contribution or Decimal("0")
                monthly_data[month_key]["net_pay"] += item.net_pay or Decimal("0")
                monthly_data[month_key]["employee_count"] += 1
                
                # Track by PFA
                pfa_name = item.employee.pfa_name if hasattr(item, 'employee') and item.employee else "Unknown PFA"
                pension_by_pfa[pfa_name]["employee"] += item.pension_employee or Decimal("0")
                pension_by_pfa[pfa_name]["employer"] += item.pension_employer or Decimal("0")
                pension_by_pfa[pfa_name]["count"] += 1
        
        # Calculate annual totals
        for month_data in monthly_data.values():
            for key in annual_totals:
                if key in month_data:
                    annual_totals[key] += month_data[key]
        
        # Convert Decimals to strings
        monthly_summary = {
            k: {kk: str(vv) for kk, vv in v.items()}
            for k, v in monthly_data.items()
        }
        
        return {
            "entity_id": str(entity_id),
            "year": year,
            "month": month,
            "annual_summary": {k: str(v) for k, v in annual_totals.items()},
            "monthly_breakdown": monthly_summary,
            "pension_by_pfa": {
                k: {
                    "employee_contribution": str(v["employee"]),
                    "employer_contribution": str(v["employer"]),
                    "total": str(v["employee"] + v["employer"]),
                    "employee_count": v["count"]
                }
                for k, v in pension_by_pfa.items()
            },
            "statutory_rates": {
                "pension_employee": "8%",
                "pension_employer": "10%",
                "nhf": "2.5%",
                "nsitf": "1%"
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def generate_aging_report(
        self,
        db: AsyncSession,
        entity_id: UUID,
        report_type: str = "receivable",  # receivable or payable
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        AR/AP Aging Report (30/60/90+ days)
        
        Crucial for identifying bad debts and managing cash flow
        """
        from app.models.invoice import Invoice
        
        if not as_of_date:
            as_of_date = date.today()
        
        # Get outstanding invoices
        if report_type == "receivable":
            query = select(Invoice).where(
                and_(
                    Invoice.entity_id == entity_id,
                    Invoice.status.in_(["sent", "pending", "overdue"]),
                    Invoice.invoice_date <= as_of_date
                )
            )
        else:
            # For payables, we'd query bills/vendor invoices
            # Simplified: use invoices marked as payable
            query = select(Invoice).where(
                and_(
                    Invoice.entity_id == entity_id,
                    Invoice.invoice_type == "bill",
                    Invoice.status.in_(["pending", "overdue"]),
                    Invoice.invoice_date <= as_of_date
                )
            )
        
        result = await db.execute(query)
        invoices = result.scalars().all()
        
        # Aging buckets
        buckets = {
            "current": {"count": 0, "amount": Decimal("0"), "items": []},
            "1_30_days": {"count": 0, "amount": Decimal("0"), "items": []},
            "31_60_days": {"count": 0, "amount": Decimal("0"), "items": []},
            "61_90_days": {"count": 0, "amount": Decimal("0"), "items": []},
            "over_90_days": {"count": 0, "amount": Decimal("0"), "items": []}
        }
        
        by_customer = defaultdict(lambda: {
            "total": Decimal("0"),
            "current": Decimal("0"),
            "overdue": Decimal("0")
        })
        
        for inv in invoices:
            due_date = inv.due_date or (inv.invoice_date + timedelta(days=30))
            days_overdue = (as_of_date - due_date).days
            amount = (inv.total_amount or Decimal("0")) - (inv.amount_paid or Decimal("0"))
            
            if amount <= 0:
                continue
            
            item_data = {
                "id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "due_date": due_date.isoformat(),
                "customer_name": inv.customer_name if hasattr(inv, 'customer_name') else None,
                "amount": str(amount),
                "days_overdue": days_overdue
            }
            
            customer = inv.customer_name if hasattr(inv, 'customer_name') else "Unknown"
            by_customer[customer]["total"] += amount
            
            if days_overdue <= 0:
                buckets["current"]["count"] += 1
                buckets["current"]["amount"] += amount
                buckets["current"]["items"].append(item_data)
                by_customer[customer]["current"] += amount
            elif days_overdue <= 30:
                buckets["1_30_days"]["count"] += 1
                buckets["1_30_days"]["amount"] += amount
                buckets["1_30_days"]["items"].append(item_data)
                by_customer[customer]["overdue"] += amount
            elif days_overdue <= 60:
                buckets["31_60_days"]["count"] += 1
                buckets["31_60_days"]["amount"] += amount
                buckets["31_60_days"]["items"].append(item_data)
                by_customer[customer]["overdue"] += amount
            elif days_overdue <= 90:
                buckets["61_90_days"]["count"] += 1
                buckets["61_90_days"]["amount"] += amount
                buckets["61_90_days"]["items"].append(item_data)
                by_customer[customer]["overdue"] += amount
            else:
                buckets["over_90_days"]["count"] += 1
                buckets["over_90_days"]["amount"] += amount
                buckets["over_90_days"]["items"].append(item_data)
                by_customer[customer]["overdue"] += amount
        
        # Calculate totals
        total_outstanding = sum(b["amount"] for b in buckets.values())
        total_overdue = sum(
            b["amount"] for k, b in buckets.items() 
            if k != "current"
        )
        
        # Format for output
        buckets_summary = {
            k: {
                "count": v["count"],
                "amount": str(v["amount"]),
                "items": v["items"][:20]  # Limit items per bucket
            }
            for k, v in buckets.items()
        }
        
        return {
            "entity_id": str(entity_id),
            "report_type": report_type,
            "as_of_date": as_of_date.isoformat(),
            "summary": {
                "total_outstanding": str(total_outstanding),
                "total_overdue": str(total_overdue),
                "overdue_percentage": str(
                    (total_overdue / total_outstanding * 100).quantize(Decimal("0.01"))
                    if total_outstanding > 0 else Decimal("0")
                )
            },
            "aging_buckets": buckets_summary,
            "by_customer": {
                k: {kk: str(vv) for kk, vv in v.items()}
                for k, v in list(by_customer.items())[:50]
            },
            "recommendations": self._get_aging_recommendations(buckets, report_type),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def generate_budget_variance(
        self,
        db: AsyncSession,
        entity_id: UUID,
        budget_id: UUID,
        through_month: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Budget vs Actual (BvA) Variance Analysis
        
        Compares yearly budget to actual performance
        """
        from app.models.advanced_accounting import Budget, BudgetLineItem
        from app.models.transaction import Transaction
        
        # Get budget
        budget_query = select(Budget).where(Budget.id == budget_id).options(
            selectinload(Budget.line_items)
        )
        result = await db.execute(budget_query)
        budget = result.scalar_one_or_none()
        
        if not budget:
            raise ValueError(f"Budget {budget_id} not found")
        
        if not through_month:
            through_month = date.today().month
        
        # Get actuals
        fy_start = budget.start_date
        fy_end = date(budget.fiscal_year, through_month, 28)  # Simplified
        
        # Get actual transactions grouped by category
        actuals_query = select(
            Transaction.category_id,
            func.sum(
                case(
                    (Transaction.transaction_type == "income", Transaction.amount),
                    else_=Decimal("0")
                )
            ).label("income"),
            func.sum(
                case(
                    (Transaction.transaction_type == "expense", Transaction.amount),
                    else_=Decimal("0")
                )
            ).label("expense")
        ).where(
            and_(
                Transaction.entity_id == entity_id,
                Transaction.transaction_date >= fy_start,
                Transaction.transaction_date <= fy_end
            )
        ).group_by(Transaction.category_id)
        
        actuals_result = await db.execute(actuals_query)
        actuals = {str(row[0]): {"income": row[1] or Decimal("0"), "expense": row[2] or Decimal("0")} 
                   for row in actuals_result.all()}
        
        # Build variance report
        month_cols = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        
        line_items_report = []
        total_budget = Decimal("0")
        total_actual = Decimal("0")
        
        for item in budget.line_items:
            # Calculate YTD budget
            ytd_budget = sum(
                getattr(item, f"{month}_amount", Decimal("0")) or Decimal("0")
                for month in month_cols[:through_month]
            )
            
            # Get actual
            category_id = str(item.category_id) if item.category_id else None
            if category_id and category_id in actuals:
                if item.line_type == "revenue":
                    ytd_actual = actuals[category_id]["income"]
                else:
                    ytd_actual = actuals[category_id]["expense"]
            else:
                ytd_actual = Decimal("0")
            
            variance = ytd_actual - ytd_budget
            variance_pct = (variance / ytd_budget * 100) if ytd_budget else Decimal("0")
            
            # Determine if favorable
            if item.line_type == "revenue":
                is_favorable = variance >= 0
            else:
                is_favorable = variance <= 0
            
            line_items_report.append({
                "account_code": item.account_code,
                "account_name": item.account_name,
                "line_type": item.line_type,
                "ytd_budget": str(ytd_budget),
                "ytd_actual": str(ytd_actual),
                "variance": str(variance),
                "variance_percentage": str(variance_pct.quantize(Decimal("0.01"))),
                "status": "favorable" if is_favorable else "unfavorable"
            })
            
            total_budget += ytd_budget
            total_actual += ytd_actual
        
        total_variance = total_actual - total_budget
        
        return {
            "entity_id": str(entity_id),
            "budget_id": str(budget_id),
            "budget_name": budget.name,
            "fiscal_year": budget.fiscal_year,
            "through_month": through_month,
            "summary": {
                "total_budget": str(total_budget),
                "total_actual": str(total_actual),
                "total_variance": str(total_variance),
                "variance_percentage": str(
                    (total_variance / total_budget * 100).quantize(Decimal("0.01"))
                    if total_budget else Decimal("0")
                )
            },
            "line_items": line_items_report,
            "favorable_count": sum(1 for li in line_items_report if li["status"] == "favorable"),
            "unfavorable_count": sum(1 for li in line_items_report if li["status"] == "unfavorable"),
            "recommendations": self._get_variance_recommendations(line_items_report),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def generate_dimensional_report(
        self,
        db: AsyncSession,
        entity_id: UUID,
        dimension_type: str,
        start_date: date,
        end_date: date,
        report_type: str = "profitability"  # profitability, revenue, expense
    ) -> Dict[str, Any]:
        """
        Dimensional/Segment Report
        
        P&L filtered by Department, Project, State, or LGA
        """
        from app.models.advanced_accounting import AccountingDimension, TransactionDimension
        from app.models.transaction import Transaction
        
        # Get dimensions
        dim_query = select(AccountingDimension).where(
            and_(
                AccountingDimension.entity_id == entity_id,
                AccountingDimension.dimension_type == dimension_type,
                AccountingDimension.is_active == True
            )
        )
        dim_result = await db.execute(dim_query)
        dimensions = dim_result.scalars().all()
        
        # Get transactions with dimension tags
        txn_query = select(
            TransactionDimension.dimension_id,
            Transaction.transaction_type,
            func.sum(TransactionDimension.allocated_amount).label("amount")
        ).join(
            Transaction, TransactionDimension.transaction_id == Transaction.id
        ).where(
            and_(
                Transaction.entity_id == entity_id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            )
        ).group_by(TransactionDimension.dimension_id, Transaction.transaction_type)
        
        txn_result = await db.execute(txn_query)
        transactions = txn_result.all()
        
        # Build dimension-based P&L
        dimension_data = {}
        for dim in dimensions:
            dimension_data[str(dim.id)] = {
                "code": dim.code,
                "name": dim.name,
                "revenue": Decimal("0"),
                "expense": Decimal("0"),
                "profit": Decimal("0"),
                "margin": Decimal("0")
            }
        
        for row in transactions:
            dim_id = str(row[0])
            txn_type = row[1]
            amount = row[2] or Decimal("0")
            
            if dim_id in dimension_data:
                if txn_type == "income":
                    dimension_data[dim_id]["revenue"] += amount
                else:
                    dimension_data[dim_id]["expense"] += amount
        
        # Calculate profits and margins
        for dim_id, data in dimension_data.items():
            data["profit"] = data["revenue"] - data["expense"]
            if data["revenue"] > 0:
                data["margin"] = (data["profit"] / data["revenue"] * 100).quantize(Decimal("0.01"))
        
        # Sort by profit
        sorted_dimensions = sorted(
            dimension_data.items(),
            key=lambda x: x[1]["profit"],
            reverse=True
        )
        
        # Calculate totals
        total_revenue = sum(d["revenue"] for d in dimension_data.values())
        total_expense = sum(d["expense"] for d in dimension_data.values())
        total_profit = sum(d["profit"] for d in dimension_data.values())
        
        return {
            "entity_id": str(entity_id),
            "dimension_type": dimension_type,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "totals": {
                "revenue": str(total_revenue),
                "expense": str(total_expense),
                "profit": str(total_profit),
                "margin": str(
                    (total_profit / total_revenue * 100).quantize(Decimal("0.01"))
                    if total_revenue > 0 else Decimal("0")
                )
            },
            "by_dimension": [
                {
                    "id": dim_id,
                    "code": data["code"],
                    "name": data["name"],
                    "revenue": str(data["revenue"]),
                    "expense": str(data["expense"]),
                    "profit": str(data["profit"]),
                    "margin": str(data["margin"])
                }
                for dim_id, data in sorted_dimensions
            ],
            "top_performers": [d[1]["name"] for d in sorted_dimensions[:5]],
            "bottom_performers": [d[1]["name"] for d in sorted_dimensions[-5:]],
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def _get_aging_recommendations(
        self,
        buckets: Dict,
        report_type: str
    ) -> List[str]:
        """Generate recommendations based on aging"""
        
        recommendations = []
        
        over_90 = buckets["over_90_days"]["amount"]
        total = sum(b["amount"] for b in buckets.values())
        
        if total > 0:
            over_90_pct = over_90 / total * 100
            
            if report_type == "receivable":
                if over_90_pct > 20:
                    recommendations.append(
                        f"HIGH RISK: {over_90_pct:.1f}% of receivables are over 90 days. Consider bad debt provision."
                    )
                if buckets["over_90_days"]["count"] > 0:
                    recommendations.append(
                        f"Review {buckets['over_90_days']['count']} accounts over 90 days for potential write-off"
                    )
                recommendations.append(
                    "Under 2026 Tax Reform, bad debts can only be claimed after 12 months or legal action"
                )
            else:
                if over_90_pct > 10:
                    recommendations.append(
                        f"Warning: {over_90_pct:.1f}% of payables are overdue. May affect credit rating."
                    )
        
        return recommendations
    
    def _get_variance_recommendations(
        self,
        line_items: List[Dict]
    ) -> List[str]:
        """Generate recommendations based on budget variance"""
        
        recommendations = []
        
        # Find significant unfavorable variances
        unfavorable = [
            li for li in line_items 
            if li["status"] == "unfavorable" and abs(Decimal(li["variance_percentage"])) > 10
        ]
        
        if unfavorable:
            recommendations.append(
                f"{len(unfavorable)} line items have unfavorable variance > 10%. Review spending controls."
            )
        
        # Check for unspent budget
        underspent = [
            li for li in line_items
            if li["line_type"] == "expense" and Decimal(li["variance"]) < 0
        ]
        
        if underspent:
            total_underspent = sum(abs(Decimal(li["variance"])) for li in underspent)
            recommendations.append(
                f"NGN {total_underspent:,.2f} underspent. Consider reallocation or carryforward."
            )
        
        return recommendations


# Singleton instance
audit_reporting_service = AuditReportingService()
