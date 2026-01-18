# TekVwarho ProAudit - Complete Accounting System Documentation

**Version:** 2.3.0  
**Last Updated:** January 18, 2026  
**Status:** Production-Ready  
**Market:** Nigerian Business Context

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Core Accounting Modules](#2-core-accounting-modules)
3. [Bank Reconciliation (The Control Spine)](#3-bank-reconciliation-the-control-spine)
4. [Nigerian Tax Integration](#4-nigerian-tax-integration)
5. [Month-End Close Workflow](#5-month-end-close-workflow)
6. [Database Design](#6-database-design)
7. [API Reference](#7-api-reference)
8. [Frontend Guide](#8-frontend-guide)
9. [Security & Compliance](#9-security--compliance)
10. [Audit Trail & Controls](#10-audit-trail--controls)

---

## 1. System Architecture

### Big Picture Data Flow

```
Users
 ↓
Transactions (Sales, Expenses, Payroll, Inventory)
 ↓
Sub-ledgers (AR, AP, Assets, Payroll)
 ↓
GENERAL LEDGER (Single Source of Truth)
 ↓
Bank GL Accounts
 ↓
BANK RECONCILIATION
 ↓
External Bank Statements (Reality)
```

### Core Philosophy

A complete accounting system must:

1. **Record transactions** - Day-to-day business activity
2. **Classify them correctly** - Accounts, taxes, periods
3. **Prove accuracy** - Controls, reconciliation, audit trail

**Bank reconciliation is the proof layer that validates everything else.**

---

## 2. Core Accounting Modules

### 2.1 Chart of Accounts (COA)

The foundation of the accounting system. Every other module depends on this.

**Nigerian Standard Account Structure:**

| Range | Type | Examples |
|-------|------|----------|
| 1000-1999 | Assets | Cash, Bank, AR, Inventory, Fixed Assets |
| 2000-2999 | Liabilities | AP, VAT Payable, WHT Payable, Loans |
| 3000-3999 | Equity | Share Capital, Retained Earnings |
| 4000-4999 | Revenue | Sales, Service Income, Interest |
| 5000-5999 | Expenses | COGS, Salaries, Bank Charges, EMTL |

**Key Account Codes:**

```python
# Bank Accounts (Link to Bank Reconciliation)
1120 - Bank Accounts (Header)
1121 - GTBank Current Account
1122 - Zenith Bank Current Account
1123 - UBA Domiciliary Account

# Tax Accounts (Nigerian Specific)
1160 - VAT Receivable (Input VAT)
1170 - WHT Receivable
2130 - VAT Payable (Output VAT)
2140 - WHT Payable
2150 - PAYE Payable
2160 - Pension Payable

# Expense Accounts (Bank Charges)
5100 - Bank Charges
5200 - EMTL Expense (Electronic Money Transfer Levy)
5210 - Stamp Duty Expense
```

**API Endpoints:**

```
GET  /api/v1/entities/{entity_id}/accounting/chart-of-accounts
POST /api/v1/entities/{entity_id}/accounting/chart-of-accounts
GET  /api/v1/entities/{entity_id}/accounting/chart-of-accounts/tree
POST /api/v1/entities/{entity_id}/accounting/chart-of-accounts/initialize
```

### 2.2 General Ledger (GL)

The central accounting engine. All modules post to the GL.

**Features:**

- Double-entry enforcement (debits must equal credits)
- Journal entries (manual & automated)
- Period-based posting
- Immutable audit trail
- Account balance tracking (YTD debit/credit)

**Journal Entry Types:**

```python
MANUAL = "manual"           # User-created entries
SALES = "sales"             # From invoices
PURCHASE = "purchase"       # From bills
RECEIPT = "receipt"         # Customer payments
PAYMENT = "payment"         # Vendor payments
PAYROLL = "payroll"         # Salary postings
DEPRECIATION = "depreciation"
TAX_ADJUSTMENT = "tax_adjustment"
BANK_RECONCILIATION = "bank_reconciliation"  # ← From reconciliation
INVENTORY_ADJUSTMENT = "inventory_adjustment"
CLOSING_ENTRY = "closing_entry"
```

**Connection to Bank Reconciliation:**

- Reconciliation compares GL bank balance vs bank statement
- Reconciliation creates adjusting journal entries
- Locked reconciliations lock GL periods

### 2.3 Accounts Receivable (AR)

**Features:**
- Customer management
- Invoice generation
- Receipt recording
- Credit notes
- WHT deduction handling

**Posting Rules:**

```
Invoice Created:
  Dr Accounts Receivable (1130)
  Cr Sales Revenue (4100)
  Cr VAT Payable (2130) - if applicable

Payment Received:
  Dr Bank (1120)
  Cr Accounts Receivable (1130)

WHT Deducted by Customer:
  Dr Bank (1120) - Net amount
  Dr WHT Receivable (1170) - WHT amount
  Cr Accounts Receivable (1130) - Gross amount
```

**Connection to Bank Reconciliation:**

- Customer payments appear on bank statement
- Reconciliation confirms payment actually hit the bank
- Unmatched receipts = deposits in transit or errors
- WHT-deducted payments reconciled net, tax posted separately

### 2.4 Accounts Payable (AP)

**Features:**
- Vendor management
- Bill recording
- Payment processing
- WHT application

**Posting Rules:**

```
Bill Recorded:
  Dr Expense/Inventory
  Dr VAT Receivable (1160) - if applicable
  Cr Accounts Payable (2110)

Payment Made:
  Dr Accounts Payable (2110)
  Cr Bank (1120)
  Cr WHT Payable (2140) - if WHT applied
```

**Connection to Bank Reconciliation:**

- Supplier payments must appear on bank statement
- Outstanding cheques remain unreconciled
- Bank charges deducted automatically reconciled
- Reversals detected and corrected

### 2.5 Cash & Bank Management

**Features:**
- Multiple bank accounts (Current, Savings, Domiciliary)
- Inter-bank transfers
- Currency support (NGN, USD, GBP, EUR)
- API integrations (Mono, Okra, Stitch)

**Connection to Bank Reconciliation:**

- Primary module reconciliation operates on
- Transfers require two reconciliations (source & destination)
- FX differences identified during reconciliation

### 2.6 Tax Management (Nigeria-Specific)

**VAT (7.5%):**
- Output VAT on sales
- Input VAT on purchases (recoverable)
- Monthly filing to FIRS

**WHT Rates:**
- Professional services: 10%
- Contracts: 5%
- Directors' fees: 10%
- Dividends: 10%

**Other Taxes:**
- EMTL: ₦50 on electronic inflows > ₦10,000
- Stamp Duty: ₦50 on electronic transfers > ₦10,000
- CIT: 0%/20%/30% based on company size
- TET: 2.5% of assessable profits
- Development Levy: 4% for large companies

**Connection to Bank Reconciliation:**

- EMTL & stamp duty often appear only in bank statements
- Reconciliation auto-detects and posts tax entries
- WHT net receipts reconciled correctly
- Tax balances proven via bank activity

### 2.7 Fixed Assets & Depreciation

**Features:**
- Asset register
- Depreciation schedules (Straight-line, Reducing balance)
- Disposal tracking
- Capital gains calculation

**Connection to Bank Reconciliation:**

- Asset purchases paid via bank
- Reconciliation confirms asset payment cleared
- Prevents "ghost assets" not actually paid for

### 2.8 Inventory & COGS

**Features:**
- Stock tracking
- Purchase recording
- COGS calculation
- Write-off management

**Connection to Bank Reconciliation:**

- Supplier payments tied to inventory purchases
- Reconciliation validates cash outflow
- Flags unpaid inventory purchases

### 2.9 Payroll

**Features:**
- Salary processing
- PAYE calculation (2026 bands)
- Pension deductions (employer/employee)
- NHF / NSITF contributions
- Bulk payment generation

**Connection to Bank Reconciliation:**

- Salary bulk payments reconciled
- Statutory remittances confirmed
- Failed salary payments detected

---

## 3. Bank Reconciliation (The Control Spine)

### Where It Sits in the System

```
Sales / Expenses / Payroll / Inventory
            ↓
     Sub-ledgers (AR, AP, etc.)
            ↓
       General Ledger
            ↓
     Bank GL Account Balance
            ↓
   BANK RECONCILIATION
            ↓
   Real Bank Statement Balance
```

**Reconciliation is the ONLY place internal records meet external reality.**

### What Bank Reconciliation Does

1. **Validates cash accuracy** - Book balance vs bank balance
2. **Detects missing entries** - Charges not recorded
3. **Detects duplicate entries** - Errors in posting
4. **Detects fraud or errors** - Unauthorized transactions
5. **Forces proper period closing** - No close without reconciliation
6. **Produces audit evidence** - Reconciliation statements

### Bank Statement Import Sources

| Source | Method | Nigerian Banks |
|--------|--------|----------------|
| Mono API | Direct connection | All major banks |
| Okra API | Direct connection | All major banks |
| Stitch API | Direct connection | Select banks |
| CSV Upload | Manual import | Any bank |
| Excel Upload | Manual import | Any bank |
| MT940 Upload | SWIFT format | Corporate accounts |
| PDF OCR | Document scanning | Legacy statements |

### Transaction Matching Engine

**Matching Types:**

```python
EXACT = "exact"              # Amount + Date match exactly
FUZZY = "fuzzy"              # Within tolerance (±3 days, ±0.01%)
ONE_TO_MANY = "one_to_many"  # 1 bank txn matches multiple book entries
MANY_TO_ONE = "many_to_one"  # Multiple bank txns match 1 book entry
RULE_BASED = "rule_based"    # Custom matching rules
MANUAL = "manual"            # User-confirmed match
```

**Matching Algorithm:**

```python
for each bank_txn:
    if exact_match(ledger_txn):
        match()
    elif fuzzy_match(±3 days, ±0.01%):
        suggest()
    elif many_to_one_possible():
        partial_match()
    else:
        mark_unreconciled()
```

### Nigerian Charge Auto-Detection

The system automatically detects and classifies:

| Charge Type | Detection Pattern | GL Account |
|-------------|-------------------|------------|
| EMTL | "EMTL", "E-Levy", ₦50 amount | 5200 |
| Stamp Duty | "Stamp Duty", "SD", ₦50 amount | 5210 |
| SMS Fee | "SMS Alert", "Notification" | 5100 |
| VAT on Charges | "VAT" in charge context | 1160 |
| WHT | "WHT", "Withholding" | 1170 |
| NIP Fee | "NIP", "NIBSS", "Transfer" | 5100 |
| POS Fee | "POS", "Card Transaction" | 5100 |
| Maintenance | "COT", "Maintenance Fee" | 5100 |

### GL Journal Entry Creation

When adjustments are posted, the system creates proper double-entry journals:

```
EMTL Charge (₦50):
  Dr EMTL Expense (5200)    ₦50
  Cr Bank (1120)            ₦50

Stamp Duty (₦50):
  Dr Stamp Duty (5210)      ₦50
  Cr Bank (1120)            ₦50

Interest Earned (₦1,000):
  Dr Bank (1120)            ₦1,000
  Cr Interest Income (4200) ₦1,000

VAT on Bank Charges (₦75):
  Dr VAT Receivable (1160)  ₦75
  Cr Bank (1120)            ₦75
```

### Reconciliation Workflow

```
1. SELECT BANK + PERIOD
        ↓
2. IMPORT STATEMENT
   - CSV upload
   - API sync
   - Manual entry
        ↓
3. AUTO-MATCH
   - Run matching engine
   - Review suggested matches
   - Confirm/reject matches
        ↓
4. RESOLVE EXCEPTIONS
   - Unmatched bank items → Add to books
   - Unmatched book items → Outstanding cheques/deposits
   - Charges → Auto-detect and create adjustments
        ↓
5. GENERATE ADJUSTING JOURNALS
   - Create GL entries for charges
   - Post to correct accounts
        ↓
6. CONFIRM BALANCES
   - Adjusted bank balance = Adjusted book balance
   - Difference must be ZERO
        ↓
7. SUBMIT FOR REVIEW
   - Manager approval required
        ↓
8. APPROVE & LOCK
   - Lock reconciliation
   - Lock related GL period
```

### Outstanding Items Management

**Types:**

- **Deposits in Transit**: Recorded in books, not yet on bank statement
- **Outstanding Cheques**: Issued but not yet cleared
- **Bank Errors**: Discrepancies to investigate
- **Book Errors**: Corrections needed

**Carry-Forward:**

Outstanding items automatically carry forward to the next reconciliation period.

---

## 4. Nigerian Tax Integration

### VAT Integration

```python
# From Invoice
Invoice Total: ₦1,000,000
VAT (7.5%):    ₦75,000

# Posting
Dr AR                     ₦1,075,000
Cr Revenue               ₦1,000,000
Cr VAT Payable              ₦75,000

# Bank Reconciliation confirms receipt
```

### WHT Credit Notes

```python
# Customer deducts WHT (10%)
Invoice: ₦100,000
WHT (10%): ₦10,000
Received: ₦90,000

# Posting
Dr Bank            ₦90,000
Dr WHT Receivable  ₦10,000
Cr AR             ₦100,000

# Reconciliation validates ₦90,000 receipt
```

### EMTL Auto-Posting

```python
# Bank statement shows EMTL
Amount: ₦50
Description: "EMTL CHARGE"

# System auto-detects and suggests
Dr EMTL Expense (5200)  ₦50
Cr Bank (1120)          ₦50
```

---

## 5. Month-End Close Workflow

### Enforced Order

```
1. POST ALL TRANSACTIONS
   - All drafts must be posted
   - No pending entries
        ↓
2. RECONCILE ALL BANK ACCOUNTS
   - Every bank account reconciled
   - Reconciliation approved
   - All adjustments posted to GL
        ↓
3. REVIEW OUTSTANDING ITEMS
   - Outstanding cheques documented
   - Deposits in transit explained
        ↓
4. LOCK THE PERIOD
   - Admin approval required
   - Period becomes read-only
        ↓
5. GENERATE FINANCIAL STATEMENTS
   - Trial balance
   - Income statement
   - Balance sheet
   - Cash flow statement
```

### Period Close Checklist

The system validates before closing:

- [ ] All journal entries posted
- [ ] All bank accounts reconciled up to period end
- [ ] All reconciliation adjustments posted to GL
- [ ] Trial balance is balanced
- [ ] Outstanding items reviewed and documented

**If any check fails → Period cannot be closed**

### API Endpoint

```
POST /api/v1/entities/{entity_id}/accounting/periods/{period_id}/close

Response:
{
  "success": false,
  "blocking_issues": [
    "GTBank (1234): Reconciled to 2026-01-15 only, need to 2026-01-31",
    "3 unposted journal entries"
  ]
}
```

---

## 6. Database Design

### Key Tables

```sql
-- Chart of Accounts
chart_of_accounts (
  id, entity_id, account_code, account_name,
  account_type, account_sub_type, normal_balance,
  parent_id, level, is_header, current_balance,
  is_tax_account, tax_type, tax_rate,
  is_reconcilable, bank_account_id
)

-- Journal Entries
journal_entries (
  id, entity_id, entry_date, reference,
  description, entry_type, status,
  total_debit, total_credit,
  fiscal_period_id, source_type, source_id
)

journal_entry_lines (
  id, journal_entry_id, account_code,
  account_id, description,
  debit_amount, credit_amount, line_number
)

-- Bank Reconciliation
bank_accounts (
  id, entity_id, bank_name, account_name,
  account_number, account_type, currency,
  opening_balance, current_balance,
  gl_account_code, last_reconciled_date,
  mono_account_id, okra_account_id, stitch_account_id
)

bank_statement_transactions (
  id, bank_account_id, reconciliation_id,
  transaction_date, description, reference,
  debit_amount, credit_amount, running_balance,
  match_status, match_type, match_confidence,
  is_bank_charge, is_emtl, is_stamp_duty, is_vat, is_wht
)

bank_reconciliations (
  id, bank_account_id, reconciliation_date,
  period_start, period_end,
  statement_opening_balance, statement_closing_balance,
  book_opening_balance, book_closing_balance,
  adjusted_bank_balance, adjusted_book_balance,
  difference, status,
  deposits_in_transit, outstanding_checks, bank_charges
)

reconciliation_adjustments (
  id, reconciliation_id, adjustment_type,
  amount, description, affects_bank, affects_book,
  gl_account_code, is_posted, journal_entry_id
)

-- Fiscal Periods
fiscal_periods (
  id, entity_id, fiscal_year_id,
  period_name, start_date, end_date,
  status, bank_reconciled, closed_at
)
```

### Critical Relationships

```
One bank account → many bank transactions
One reconciliation → many matches
One match → many bank txns + many GL txns
One adjustment → one journal entry (when posted)
One fiscal period → many journal entries
```

---

## 7. API Reference

### Chart of Accounts

```
GET    /api/v1/entities/{entity_id}/accounting/chart-of-accounts
POST   /api/v1/entities/{entity_id}/accounting/chart-of-accounts
GET    /api/v1/entities/{entity_id}/accounting/chart-of-accounts/{id}
PUT    /api/v1/entities/{entity_id}/accounting/chart-of-accounts/{id}
GET    /api/v1/entities/{entity_id}/accounting/chart-of-accounts/tree
POST   /api/v1/entities/{entity_id}/accounting/chart-of-accounts/initialize
```

### Journal Entries

```
GET    /api/v1/entities/{entity_id}/accounting/journal-entries
POST   /api/v1/entities/{entity_id}/accounting/journal-entries
GET    /api/v1/entities/{entity_id}/accounting/journal-entries/{id}
POST   /api/v1/entities/{entity_id}/accounting/journal-entries/{id}/post
POST   /api/v1/entities/{entity_id}/accounting/journal-entries/{id}/reverse
```

### Financial Reports

```
GET    /api/v1/entities/{entity_id}/accounting/reports/trial-balance
GET    /api/v1/entities/{entity_id}/accounting/reports/income-statement
GET    /api/v1/entities/{entity_id}/accounting/reports/balance-sheet
GET    /api/v1/entities/{entity_id}/accounting/reports/account-ledger/{account_id}
```

### Bank Reconciliation

```
# Bank Accounts
GET    /bank-reconciliation/accounts
POST   /bank-reconciliation/accounts
GET    /bank-reconciliation/accounts/{id}
PATCH  /bank-reconciliation/accounts/{id}
POST   /bank-reconciliation/accounts/{id}/import/csv
POST   /bank-reconciliation/accounts/{id}/sync

# Reconciliations
GET    /bank-reconciliation/reconciliations
POST   /bank-reconciliation/reconciliations
GET    /bank-reconciliation/reconciliations/{id}
GET    /bank-reconciliation/reconciliations/{id}/transactions
GET    /bank-reconciliation/reconciliations/{id}/adjustments
GET    /bank-reconciliation/reconciliations/{id}/unmatched-items

# Matching
POST   /bank-reconciliation/reconciliations/{id}/auto-match
POST   /bank-reconciliation/reconciliations/{id}/manual-match
POST   /bank-reconciliation/transactions/{id}/unmatch

# Adjustments
POST   /bank-reconciliation/reconciliations/{id}/adjustments
POST   /bank-reconciliation/reconciliations/{id}/adjustments/auto-create-charges
POST   /bank-reconciliation/reconciliations/{id}/create-journal-entries
DELETE /bank-reconciliation/adjustments/{id}

# Workflow
POST   /bank-reconciliation/reconciliations/{id}/submit
POST   /bank-reconciliation/reconciliations/{id}/approve
POST   /bank-reconciliation/reconciliations/{id}/reject

# Period Validation
GET    /bank-reconciliation/validate-for-period-close?period_end_date=2026-01-31

# Reporting
GET    /bank-reconciliation/summary
GET    /bank-reconciliation/reconciliations/{id}/report
GET    /bank-reconciliation/accounts/{id}/outstanding-items?as_of_date=2026-01-31
```

### Period Management

```
GET    /api/v1/entities/{entity_id}/accounting/fiscal-years
POST   /api/v1/entities/{entity_id}/accounting/fiscal-years
GET    /api/v1/entities/{entity_id}/accounting/periods
GET    /api/v1/entities/{entity_id}/accounting/periods/{id}/close-checklist
POST   /api/v1/entities/{entity_id}/accounting/periods/{id}/close
```

---

## 8. Frontend Guide

### Accounting Module (accounting.html)

**Features:**
- Chart of Accounts tree view with hierarchy
- Account details panel
- Journal entry creation/posting
- Fiscal period management
- Financial reports (Trial Balance, P&L, Balance Sheet)

**Key Actions:**
- Initialize Default COA
- Create/Edit accounts
- Create journal entries
- View account ledger
- Close periods

### Bank Reconciliation Module (bank_reconciliation.html)

**Features:**
- Bank account management
- Statement import (CSV, API sync)
- Transaction matching interface
- Adjustment management
- Reconciliation workflow

**Key Actions:**
- Add bank account (Nigerian banks dropdown)
- Import CSV statements
- Sync from Mono/Okra/Stitch
- Auto-match transactions
- Auto-detect bank charges
- Post adjustments to GL
- Submit for review
- Approve/reject reconciliation

---

## 9. Security & Compliance

### NDPA/NITDA 2023 Compliance

- PII encryption (AES-256-GCM)
- Field-level encryption for sensitive data
- Nigerian data sovereignty (geo-fencing)
- Right-to-erasure support

### Access Control

- Role-based access (Admin, Accountant, Manager, Auditor)
- Entity-level data isolation
- Auditor read-only enforcement

### Audit Trail

- All changes logged with timestamp and user
- Immutable journal entries
- Hash-chain verification for ledger integrity

---

## 10. Audit Trail & Controls

### What Auditors Ask

1. ✅ Are bank accounts reconciled?
2. ✅ Are periods locked?
3. ✅ Are reconciling items explained?
4. ✅ Is there an audit trail for all changes?
5. ✅ Can transactions be reproduced?

### Evidence Provided

- Bank reconciliation statements
- Outstanding items reports
- Adjustment journals
- Period close documentation
- Trial balance at period end

### Final Mental Model

```
Transactions record INTENT
Ledger records ACCOUNTING
Bank statement records REALITY
Bank reconciliation proves TRUTH
```

**That's why reconciliation is the centerpiece of a full accounting system.**

---

## Summary

When the system is fully connected:

✅ Every naira in the bank is explained  
✅ Every difference is justified  
✅ Every period is defensible  
✅ The accounting system is trustworthy  
