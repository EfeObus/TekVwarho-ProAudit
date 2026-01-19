"""
Generate Historical Journal Entries from Source Systems
========================================================
This script generates journal entries for ALL entities in the system
from existing source data (invoices, transactions, fixed assets, payroll, etc.)

This is Option 1: Retroactively create journal entries from historical data.

Usage:
    python scripts/generate_historical_journal_entries.py [--entity-id UUID] [--dry-run]

Options:
    --entity-id UUID    Only process a specific entity (default: all entities)
    --dry-run           Show what would be created without actually creating
"""

import asyncio
import uuid
import sys
import argparse
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

# Add project root to path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models.entity import BusinessEntity
from app.models.invoice import Invoice, InvoiceStatus, InvoiceLineItem
from app.models.transaction import Transaction, TransactionType
from app.models.fixed_asset import FixedAsset, DepreciationEntry, AssetStatus
from app.models.payroll import PayrollRun
from app.models.accounting import (
    ChartOfAccounts, JournalEntry, JournalEntryLine, 
    JournalEntryStatus, JournalEntryType, FiscalPeriod, FiscalPeriodStatus
)


# GL Account Codes (Nigerian Chart of Accounts standard)
GL_ACCOUNTS = {
    # Assets
    "CASH": "1110",
    "BANK": "1120",
    "ACCOUNTS_RECEIVABLE": "1130",
    "INVENTORY": "1140",
    "PREPAID_EXPENSES": "1150",
    "PROPERTY_PLANT_EQUIPMENT": "1210",
    "ACCUMULATED_DEPRECIATION": "1220",
    
    # Liabilities
    "ACCOUNTS_PAYABLE": "2110",
    "ACCRUED_EXPENSES": "2120",
    "VAT_PAYABLE": "2130",
    "PAYROLL_PAYABLE": "2140",
    "PAYE_PAYABLE": "2141",
    "PENSION_PAYABLE": "2142",
    "NHF_PAYABLE": "2143",
    
    # Equity
    "RETAINED_EARNINGS": "3100",
    
    # Revenue
    "SALES_REVENUE": "4100",
    "SERVICE_REVENUE": "4200",
    "OTHER_INCOME": "4900",
    
    # Expenses
    "COST_OF_GOODS_SOLD": "5100",
    "SALARY_EXPENSE": "6110",
    "RENT_EXPENSE": "6120",
    "UTILITIES_EXPENSE": "6130",
    "DEPRECIATION_EXPENSE": "6140",
    "OFFICE_SUPPLIES": "6150",
    "MARKETING_EXPENSE": "6160",
    "TRAVEL_EXPENSE": "6170",
    "PROFESSIONAL_FEES": "6180",
    "INSURANCE_EXPENSE": "6190",
    "MISCELLANEOUS_EXPENSE": "6900",
}


class JournalEntryGenerator:
    """Generates journal entries from source systems."""
    
    def __init__(self, session: AsyncSession, dry_run: bool = False):
        self.session = session
        self.dry_run = dry_run
        self.stats = {
            "invoices_processed": 0,
            "transactions_processed": 0,
            "fixed_assets_processed": 0,
            "payroll_runs_processed": 0,
            "journal_entries_created": 0,
            "errors": [],
        }
        self._account_cache: Dict[str, uuid.UUID] = {}
        self._period_cache: Dict[Tuple[uuid.UUID, date], Optional[uuid.UUID]] = {}
        self._entry_counter: Dict[uuid.UUID, int] = {}
    
    async def get_account_id(self, entity_id: uuid.UUID, account_code: str) -> Optional[uuid.UUID]:
        """Get GL account ID by code, with caching."""
        cache_key = f"{entity_id}:{account_code}"
        if cache_key in self._account_cache:
            return self._account_cache[cache_key]
        
        result = await self.session.execute(
            select(ChartOfAccounts.id)
            .where(ChartOfAccounts.entity_id == entity_id)
            .where(ChartOfAccounts.account_code == account_code)
            .where(ChartOfAccounts.is_active == True)
        )
        account_id = result.scalar_one_or_none()
        self._account_cache[cache_key] = account_id
        return account_id
    
    async def get_or_create_fiscal_period(self, entity_id: uuid.UUID, entry_date: date) -> Optional[uuid.UUID]:
        """Get fiscal period for date, creating if necessary."""
        cache_key = (entity_id, entry_date)
        if cache_key in self._period_cache:
            return self._period_cache[cache_key]
        
        # Find existing period
        result = await self.session.execute(
            select(FiscalPeriod.id)
            .where(FiscalPeriod.entity_id == entity_id)
            .where(FiscalPeriod.start_date <= entry_date)
            .where(FiscalPeriod.end_date >= entry_date)
        )
        period_id = result.scalar_one_or_none()
        
        if not period_id:
            # Period doesn't exist - we'll skip this entry
            self._period_cache[cache_key] = None
            return None
        
        self._period_cache[cache_key] = period_id
        return period_id
    
    async def get_next_entry_number(self, entity_id: uuid.UUID, entry_date: date) -> str:
        """Generate unique entry number."""
        if entity_id not in self._entry_counter:
            # Get max entry number for this entity
            result = await self.session.execute(
                select(func.count(JournalEntry.id))
                .where(JournalEntry.entity_id == entity_id)
            )
            count = result.scalar() or 0
            self._entry_counter[entity_id] = count
        
        self._entry_counter[entity_id] += 1
        return f"JE-{entry_date.strftime('%Y%m')}-{self._entry_counter[entity_id]:05d}"
    
    async def check_entry_exists(
        self, 
        entity_id: uuid.UUID, 
        source_module: str, 
        source_document_id: uuid.UUID
    ) -> bool:
        """Check if journal entry already exists for this source document."""
        result = await self.session.execute(
            select(func.count(JournalEntry.id))
            .where(JournalEntry.entity_id == entity_id)
            .where(JournalEntry.source_module == source_module)
            .where(JournalEntry.source_document_id == source_document_id)
        )
        count = result.scalar() or 0
        return count > 0
    
    async def create_journal_entry(
        self,
        entity_id: uuid.UUID,
        entry_date: date,
        entry_type: JournalEntryType,
        description: str,
        lines: List[Dict[str, Any]],
        source_module: str,
        source_document_type: str,
        source_document_id: uuid.UUID,
        source_reference: str,
    ) -> Optional[JournalEntry]:
        """Create a journal entry with lines."""
        # Check if already exists
        if await self.check_entry_exists(entity_id, source_module, source_document_id):
            return None
        
        # Get fiscal period
        period_id = await self.get_or_create_fiscal_period(entity_id, entry_date)
        if not period_id:
            self.stats["errors"].append(
                f"No fiscal period for {entry_date} in entity {entity_id}"
            )
            return None
        
        # Calculate totals
        total_debit = sum(Decimal(str(line.get("debit_amount", 0))) for line in lines)
        total_credit = sum(Decimal(str(line.get("credit_amount", 0))) for line in lines)
        
        # Verify balanced
        if abs(total_debit - total_credit) > Decimal("0.01"):
            self.stats["errors"].append(
                f"Unbalanced entry for {source_reference}: Debit={total_debit}, Credit={total_credit}"
            )
            return None
        
        if self.dry_run:
            print(f"  [DRY-RUN] Would create JE: {description} ({total_debit:,.2f})")
            self.stats["journal_entries_created"] += 1
            return None
        
        # Create entry
        entry_number = await self.get_next_entry_number(entity_id, entry_date)
        
        entry = JournalEntry(
            entity_id=entity_id,
            fiscal_period_id=period_id,
            entry_number=entry_number,
            entry_date=entry_date,
            entry_type=entry_type,
            source_module=source_module,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            source_reference=source_reference,
            description=description,
            total_debit=total_debit,
            total_credit=total_credit,
            currency="NGN",
            status=JournalEntryStatus.POSTED,
            posted_at=datetime.utcnow(),
        )
        self.session.add(entry)
        await self.session.flush()
        
        # Create lines
        for idx, line_data in enumerate(lines, 1):
            line = JournalEntryLine(
                journal_entry_id=entry.id,
                account_id=line_data["account_id"],
                line_number=idx,
                description=line_data.get("description", ""),
                debit_amount=Decimal(str(line_data.get("debit_amount", 0))),
                credit_amount=Decimal(str(line_data.get("credit_amount", 0))),
            )
            self.session.add(line)
        
        self.stats["journal_entries_created"] += 1
        return entry
    
    async def process_invoices(self, entity_id: uuid.UUID):
        """Generate journal entries from invoices."""
        print(f"  Processing invoices...")
        
        # Get accounts
        ar_account = await self.get_account_id(entity_id, GL_ACCOUNTS["ACCOUNTS_RECEIVABLE"])
        revenue_account = await self.get_account_id(entity_id, GL_ACCOUNTS["SALES_REVENUE"])
        vat_account = await self.get_account_id(entity_id, GL_ACCOUNTS["VAT_PAYABLE"])
        bank_account = await self.get_account_id(entity_id, GL_ACCOUNTS["BANK"])
        
        if not ar_account or not revenue_account:
            self.stats["errors"].append(f"Entity {entity_id}: Missing AR or Revenue accounts")
            return
        
        # Get non-draft invoices
        result = await self.session.execute(
            select(Invoice)
            .where(Invoice.entity_id == entity_id)
            .where(Invoice.status != InvoiceStatus.DRAFT)
            .options(selectinload(Invoice.line_items))
        )
        invoices = result.scalars().all()
        
        for invoice in invoices:
            # Skip if entry already exists
            if await self.check_entry_exists(entity_id, "INVOICES", invoice.id):
                continue
            
            lines = []
            
            # Debit AR for total amount
            lines.append({
                "account_id": ar_account,
                "description": f"Invoice {invoice.invoice_number} - AR",
                "debit_amount": invoice.total_amount,
                "credit_amount": Decimal("0"),
            })
            
            # Credit Revenue for subtotal
            lines.append({
                "account_id": revenue_account,
                "description": f"Invoice {invoice.invoice_number} - Revenue",
                "debit_amount": Decimal("0"),
                "credit_amount": invoice.subtotal,
            })
            
            # Credit VAT if applicable
            if invoice.vat_amount and invoice.vat_amount > 0 and vat_account:
                lines.append({
                    "account_id": vat_account,
                    "description": f"Invoice {invoice.invoice_number} - VAT",
                    "debit_amount": Decimal("0"),
                    "credit_amount": invoice.vat_amount,
                })
            
            await self.create_journal_entry(
                entity_id=entity_id,
                entry_date=invoice.invoice_date,
                entry_type=JournalEntryType.SALES,
                description=f"Sales Invoice {invoice.invoice_number}",
                lines=lines,
                source_module="INVOICES",
                source_document_type="INVOICE",
                source_document_id=invoice.id,
                source_reference=invoice.invoice_number,
            )
            
            # If invoice is paid, create payment entry
            if invoice.status == InvoiceStatus.PAID and invoice.amount_paid and invoice.amount_paid > 0:
                if bank_account:
                    payment_lines = [
                        {
                            "account_id": bank_account,
                            "description": f"Payment for Invoice {invoice.invoice_number}",
                            "debit_amount": invoice.amount_paid,
                            "credit_amount": Decimal("0"),
                        },
                        {
                            "account_id": ar_account,
                            "description": f"Payment for Invoice {invoice.invoice_number}",
                            "debit_amount": Decimal("0"),
                            "credit_amount": invoice.amount_paid,
                        },
                    ]
                    
                    payment_date = invoice.updated_at.date() if invoice.updated_at else invoice.invoice_date
                    
                    await self.create_journal_entry(
                        entity_id=entity_id,
                        entry_date=payment_date,
                        entry_type=JournalEntryType.RECEIPT,
                        description=f"Payment Received - Invoice {invoice.invoice_number}",
                        lines=payment_lines,
                        source_module="INVOICES",
                        source_document_type="PAYMENT",
                        source_document_id=invoice.id,
                        source_reference=f"PMT-{invoice.invoice_number}",
                    )
            
            self.stats["invoices_processed"] += 1
    
    async def process_transactions(self, entity_id: uuid.UUID):
        """Generate journal entries from transactions."""
        print(f"  Processing transactions...")
        
        # Get accounts
        bank_account = await self.get_account_id(entity_id, GL_ACCOUNTS["BANK"])
        cash_account = await self.get_account_id(entity_id, GL_ACCOUNTS["CASH"])
        ar_account = await self.get_account_id(entity_id, GL_ACCOUNTS["ACCOUNTS_RECEIVABLE"])
        ap_account = await self.get_account_id(entity_id, GL_ACCOUNTS["ACCOUNTS_PAYABLE"])
        revenue_account = await self.get_account_id(entity_id, GL_ACCOUNTS["SALES_REVENUE"])
        misc_expense = await self.get_account_id(entity_id, GL_ACCOUNTS["MISCELLANEOUS_EXPENSE"])
        
        if not bank_account:
            self.stats["errors"].append(f"Entity {entity_id}: Missing Bank account")
            return
        
        # Get transactions
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.entity_id == entity_id)
        )
        transactions = result.scalars().all()
        
        for txn in transactions:
            # Skip if entry already exists
            if await self.check_entry_exists(entity_id, "TRANSACTIONS", txn.id):
                continue
            
            lines = []
            entry_type = JournalEntryType.MANUAL
            
            if txn.transaction_type == TransactionType.INCOME:
                # Income: Dr Bank, Cr Revenue
                entry_type = JournalEntryType.RECEIPT
                lines = [
                    {
                        "account_id": bank_account,
                        "description": txn.description or "Income",
                        "debit_amount": abs(txn.amount),
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": revenue_account or misc_expense,
                        "description": txn.description or "Income",
                        "debit_amount": Decimal("0"),
                        "credit_amount": abs(txn.amount),
                    },
                ]
            elif txn.transaction_type == TransactionType.EXPENSE:
                # Expense: Dr Expense, Cr Bank
                entry_type = JournalEntryType.PAYMENT
                expense_account = misc_expense or bank_account
                lines = [
                    {
                        "account_id": expense_account,
                        "description": txn.description or "Expense",
                        "debit_amount": abs(txn.amount),
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": bank_account,
                        "description": txn.description or "Expense",
                        "debit_amount": Decimal("0"),
                        "credit_amount": abs(txn.amount),
                    },
                ]
            elif txn.transaction_type == TransactionType.TRANSFER:
                # Transfer between accounts (skip for now, needs more info)
                continue
            else:
                continue
            
            if lines:
                await self.create_journal_entry(
                    entity_id=entity_id,
                    entry_date=txn.transaction_date,
                    entry_type=entry_type,
                    description=txn.description or f"Transaction {txn.reference}",
                    lines=lines,
                    source_module="TRANSACTIONS",
                    source_document_type=txn.transaction_type.value,
                    source_document_id=txn.id,
                    source_reference=txn.reference or str(txn.id)[:8],
                )
                self.stats["transactions_processed"] += 1
    
    async def process_fixed_assets(self, entity_id: uuid.UUID):
        """Generate journal entries from fixed assets (acquisition and depreciation)."""
        print(f"  Processing fixed assets...")
        
        # Get accounts
        ppe_account = await self.get_account_id(entity_id, GL_ACCOUNTS["PROPERTY_PLANT_EQUIPMENT"])
        accum_depr_account = await self.get_account_id(entity_id, GL_ACCOUNTS["ACCUMULATED_DEPRECIATION"])
        depr_expense_account = await self.get_account_id(entity_id, GL_ACCOUNTS["DEPRECIATION_EXPENSE"])
        bank_account = await self.get_account_id(entity_id, GL_ACCOUNTS["BANK"])
        ap_account = await self.get_account_id(entity_id, GL_ACCOUNTS["ACCOUNTS_PAYABLE"])
        
        if not ppe_account:
            self.stats["errors"].append(f"Entity {entity_id}: Missing PPE account")
            return
        
        # Get assets
        result = await self.session.execute(
            select(FixedAsset)
            .where(FixedAsset.entity_id == entity_id)
            .options(selectinload(FixedAsset.depreciation_entries))
        )
        assets = result.scalars().all()
        
        for asset in assets:
            # Create acquisition entry
            if not await self.check_entry_exists(entity_id, "FIXED_ASSETS", asset.id):
                acquisition_lines = [
                    {
                        "account_id": ppe_account,
                        "description": f"Asset Acquisition: {asset.name}",
                        "debit_amount": asset.acquisition_cost,
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": ap_account or bank_account,
                        "description": f"Asset Acquisition: {asset.name}",
                        "debit_amount": Decimal("0"),
                        "credit_amount": asset.acquisition_cost,
                    },
                ]
                
                await self.create_journal_entry(
                    entity_id=entity_id,
                    entry_date=asset.acquisition_date,
                    entry_type=JournalEntryType.PURCHASE,
                    description=f"Fixed Asset Acquisition: {asset.name} ({asset.asset_code})",
                    lines=acquisition_lines,
                    source_module="FIXED_ASSETS",
                    source_document_type="ACQUISITION",
                    source_document_id=asset.id,
                    source_reference=asset.asset_code,
                )
                self.stats["fixed_assets_processed"] += 1
            
            # Create depreciation entries
            if accum_depr_account and depr_expense_account:
                for depr in asset.depreciation_entries:
                    depr_doc_id = depr.id if hasattr(depr, 'id') else asset.id
                    if not await self.check_entry_exists(entity_id, "DEPRECIATION", depr_doc_id):
                        depr_lines = [
                            {
                                "account_id": depr_expense_account,
                                "description": f"Depreciation: {asset.name}",
                                "debit_amount": depr.depreciation_amount,
                                "credit_amount": Decimal("0"),
                            },
                            {
                                "account_id": accum_depr_account,
                                "description": f"Depreciation: {asset.name}",
                                "debit_amount": Decimal("0"),
                                "credit_amount": depr.depreciation_amount,
                            },
                        ]
                        
                        await self.create_journal_entry(
                            entity_id=entity_id,
                            entry_date=depr.period_end_date,
                            entry_type=JournalEntryType.DEPRECIATION,
                            description=f"Monthly Depreciation: {asset.name}",
                            lines=depr_lines,
                            source_module="DEPRECIATION",
                            source_document_type="DEPRECIATION",
                            source_document_id=depr_doc_id,
                            source_reference=f"DEPR-{asset.asset_code}-{depr.period_end_date.strftime('%Y%m')}",
                        )
    
    async def process_payroll_runs(self, entity_id: uuid.UUID):
        """Generate journal entries from completed payroll runs."""
        print(f"  Processing payroll runs...")
        
        # Get accounts
        salary_expense = await self.get_account_id(entity_id, GL_ACCOUNTS["SALARY_EXPENSE"])
        bank_account = await self.get_account_id(entity_id, GL_ACCOUNTS["BANK"])
        paye_payable = await self.get_account_id(entity_id, GL_ACCOUNTS["PAYE_PAYABLE"])
        pension_payable = await self.get_account_id(entity_id, GL_ACCOUNTS["PENSION_PAYABLE"])
        nhf_payable = await self.get_account_id(entity_id, GL_ACCOUNTS["NHF_PAYABLE"])
        
        if not salary_expense or not bank_account:
            self.stats["errors"].append(f"Entity {entity_id}: Missing Salary or Bank accounts")
            return
        
        # Get completed payroll runs
        result = await self.session.execute(
            select(PayrollRun)
            .where(PayrollRun.entity_id == entity_id)
            .where(PayrollRun.status == "COMPLETED")
        )
        payroll_runs = result.scalars().all()
        
        for run in payroll_runs:
            if await self.check_entry_exists(entity_id, "PAYROLL", run.id):
                continue
            
            # Build journal entry lines
            lines = []
            
            # Debit Salary Expense for gross pay
            lines.append({
                "account_id": salary_expense,
                "description": f"Payroll {run.pay_period_start} to {run.pay_period_end}",
                "debit_amount": run.total_gross_pay,
                "credit_amount": Decimal("0"),
            })
            
            # Credit Bank for net pay
            lines.append({
                "account_id": bank_account,
                "description": f"Net Pay - Payroll {run.pay_period_start}",
                "debit_amount": Decimal("0"),
                "credit_amount": run.total_net_pay,
            })
            
            # Credit PAYE Payable
            if run.total_paye and run.total_paye > 0 and paye_payable:
                lines.append({
                    "account_id": paye_payable,
                    "description": f"PAYE Tax - Payroll {run.pay_period_start}",
                    "debit_amount": Decimal("0"),
                    "credit_amount": run.total_paye,
                })
            
            # Credit Pension Payable
            if run.total_pension_employee and run.total_pension_employee > 0 and pension_payable:
                lines.append({
                    "account_id": pension_payable,
                    "description": f"Pension - Payroll {run.pay_period_start}",
                    "debit_amount": Decimal("0"),
                    "credit_amount": run.total_pension_employee,
                })
            
            # Credit NHF Payable
            if run.total_nhf and run.total_nhf > 0 and nhf_payable:
                lines.append({
                    "account_id": nhf_payable,
                    "description": f"NHF - Payroll {run.pay_period_start}",
                    "debit_amount": Decimal("0"),
                    "credit_amount": run.total_nhf,
                })
            
            await self.create_journal_entry(
                entity_id=entity_id,
                entry_date=run.payment_date or run.pay_period_end,
                entry_type=JournalEntryType.PAYROLL,
                description=f"Payroll: {run.pay_period_start} to {run.pay_period_end}",
                lines=lines,
                source_module="PAYROLL",
                source_document_type="PAYROLL_RUN",
                source_document_id=run.id,
                source_reference=run.run_number,
            )
            self.stats["payroll_runs_processed"] += 1
    
    async def process_entity(self, entity: BusinessEntity):
        """Process all source systems for an entity."""
        print(f"\nProcessing Entity: {entity.name} ({entity.id})")
        
        await self.process_invoices(entity.id)
        await self.process_transactions(entity.id)
        await self.process_fixed_assets(entity.id)
        await self.process_payroll_runs(entity.id)
    
    async def run(self, entity_id: Optional[uuid.UUID] = None):
        """Run the journal entry generation."""
        print("=" * 60)
        print("Historical Journal Entry Generator")
        print("=" * 60)
        
        if self.dry_run:
            print("\n*** DRY RUN MODE - No data will be created ***\n")
        
        # Get entities to process
        if entity_id:
            result = await self.session.execute(
                select(BusinessEntity).where(BusinessEntity.id == entity_id)
            )
            entities = result.scalars().all()
            if not entities:
                print(f"Entity {entity_id} not found!")
                return
        else:
            result = await self.session.execute(
                select(BusinessEntity).where(BusinessEntity.is_active == True)
            )
            entities = result.scalars().all()
        
        print(f"Found {len(entities)} entities to process")
        
        for entity in entities:
            await self.process_entity(entity)
        
        if not self.dry_run:
            await self.session.commit()
        
        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Invoices processed:       {self.stats['invoices_processed']}")
        print(f"Transactions processed:   {self.stats['transactions_processed']}")
        print(f"Fixed Assets processed:   {self.stats['fixed_assets_processed']}")
        print(f"Payroll Runs processed:   {self.stats['payroll_runs_processed']}")
        print(f"Journal Entries created:  {self.stats['journal_entries_created']}")
        
        if self.stats["errors"]:
            print(f"\nErrors ({len(self.stats['errors'])}):")
            for error in self.stats["errors"][:10]:  # Show first 10
                print(f"  - {error}")
            if len(self.stats["errors"]) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more")


async def main():
    parser = argparse.ArgumentParser(description="Generate historical journal entries")
    parser.add_argument("--entity-id", type=str, help="Process only this entity")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    args = parser.parse_args()
    
    entity_id = uuid.UUID(args.entity_id) if args.entity_id else None
    
    async with async_session_maker() as session:
        generator = JournalEntryGenerator(session, dry_run=args.dry_run)
        await generator.run(entity_id)


if __name__ == "__main__":
    asyncio.run(main())
