# TekVwarho ProAudit - System Architecture Documentation

## Overview

TekVwarho ProAudit is a **world-class Nigerian tax compliance and business management platform** built for the 2026 Tax Reform Era. It implements NTAA 2025 (Nigerian Tax Administration Act) compliance standards and integrates with FIRS (Federal Inland Revenue Service) systems.

---

## World-Class Accounting System

### Core Principles

1. **Double-Entry Bookkeeping**
   - Every transaction has equal debits and credits
   - Maintains complete audit trail
   - Ensures balance sheet integrity

2. **Nigerian Tax Compliance**
   - VAT (7.5% standard rate, with exemptions)
   - PAYE (Pay As You Earn) with graduated tax bands
   - WHT (Withholding Tax) on various transaction types
   - Stamp Duty on transactions above ₦10,000
   - CIT (Company Income Tax) integration

3. **2026 Tax Reform Features**
   - NRS (National Revenue Service) Integration via IRN (Invoice Reference Numbers)
   - Real-time invoice submission to FIRS
   - TIN (Tax Identification Number) validation
   - Electronic invoicing compliance

### Financial Modules

| Module | Purpose |
|--------|---------|
| **Transactions** | Record all financial movements (income, expense, transfer) |
| **Invoices** | Generate and track sales invoices with NRS integration |
| **Sales** | Point-of-sale recording with instant VAT calculation |
| **Vendors** | Supplier management with WHT tracking |
| **Customers** | Client management with credit tracking |
| **Inventory** | Stock management with FIFO/LIFO costing |
| **Fixed Assets** | Capital asset register with depreciation schedules |
| **Bank Reconciliation** | Match bank statements with system transactions |
| **Expense Claims** | Employee reimbursement workflow |

---

## System Connections & Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TekVwarho ProAudit Platform                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │  Customers  │◄───►│   Sales     │◄───►│  Inventory  │               │
│  └─────────────┘     └─────────────┘     └─────────────┘               │
│         │                   │                   │                       │
│         ▼                   ▼                   ▼                       │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │  Invoices   │◄───►│Transactions │◄───►│   Vendors   │               │
│  └─────────────┘     └─────────────┘     └─────────────┘               │
│         │                   │                   │                       │
│         ▼                   ▼                   ▼                       │
│  ┌─────────────────────────────────────────────────────┐               │
│  │                    AUDIT SYSTEM                      │               │
│  │  • Immutable Logs • Forensic Analysis • WORM Vault  │               │
│  └─────────────────────────────────────────────────────┘               │
│         │                   │                   │                       │
│         ▼                   ▼                   ▼                       │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │   Tax 2026  │◄───►│   Payroll   │◄───►│ Fixed Assets│               │
│  │  (NRS/IRN)  │     │   (PAYE)    │     │(Depreciation)│              │
│  └─────────────┘     └─────────────┘     └─────────────┘               │
│                             │                                           │
│                             ▼                                           │
│                    ┌─────────────────┐                                  │
│                    │   ML/AI Engine  │                                  │
│                    │  • Forecasting  │                                  │
│                    │  • OCR          │                                  │
│                    │  • Predictions  │                                  │
│                    └─────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Audit System Connections

### How Audit Connects to Everything

**Every action in the system creates an audit record:**

1. **User Actions → Audit Log**
   ```python
   # When a user creates a transaction:
   await audit_service.log_action(
       user_id=current_user.id,
       action="CREATE",
       target_entity_type="transaction",
       target_entity_id=transaction.id,
       details={"amount": 50000, "type": "income"}
   )
   ```

2. **Transaction → Multiple Audit Hooks**
   - Creation logged
   - Modifications tracked with before/after snapshots
   - Deletions recorded (soft delete)
   - VAT calculations audited
   - WHT deductions logged

3. **Forensic Analysis Tools**
   | Tool | Purpose | Connects To |
   |------|---------|-------------|
   | **Benford's Law** | Detect manipulated numbers | Transactions, Invoices |
   | **Z-Score Anomaly** | Statistical outlier detection | All financial records |
   | **NRS Gap Analysis** | Find unreported invoices | Invoices, Tax submissions |

4. **WORM Storage (Write Once Read Many)**
   - Critical audit evidence stored immutably
   - Hash chain integrity verification
   - 7-year retention compliance

### Audit Flow Diagram

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   ACTION    │───►│ AUDIT LOG   │───►│  EVIDENCE   │
│ (Any CRUD)  │    │  Created    │    │   Stored    │
└─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Hash Chain │    │  Forensic   │    │    WORM     │
│  Updated    │    │  Analysis   │    │   Vault     │
└─────────────┘    └─────────────┘    └─────────────┘
```

---

## Payroll System Connections

### How Payroll Integrates

**Payroll connects to these modules:**

1. **Employees → Payroll**
   - Basic salary configuration
   - Allowances (housing, transport, meal, etc.)
   - Deductions (pension, loan, union dues)

2. **Payroll → Tax System**
   ```
   Gross Salary
       │
       ├─► Pension Contribution (8% employee / 10% employer)
       │
       ├─► NHF (2.5% of basic salary)
       │
       ├─► PAYE Tax (graduated rates)
       │   • First ₦300,000: 7%
       │   • Next ₦300,000: 11%
       │   • Next ₦500,000: 15%
       │   • Next ₦500,000: 19%
       │   • Next ₦1,600,000: 21%
       │   • Above ₦3,200,000: 24%
       │
       └─► Net Salary
   ```

3. **Payroll → Audit**
   - Every payroll run logged
   - Decision audit trail (why deductions were made)
   - PAYE calculations with step-by-step explainability
   - Exception handling documented

4. **Payroll → Bank Reconciliation**
   - Salary payments matched to bank transactions
   - Bulk payment tracking
   - Reconciliation report generation

### Payroll Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      PAYROLL SYSTEM                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐         ┌─────────────┐         ┌───────────┐ │
│  │  Employee   │────────►│  Calculate  │────────►│  Payslip  │ │
│  │  Profile    │         │   Salary    │         │ Generated │ │
│  └─────────────┘         └─────────────┘         └───────────┘ │
│         │                       │                       │       │
│         ▼                       ▼                       ▼       │
│  ┌─────────────┐         ┌─────────────┐         ┌───────────┐ │
│  │ Allowances  │         │    PAYE     │         │  Decision │ │
│  │ & Benefits  │────────►│  Deduction  │────────►│   Log     │ │
│  └─────────────┘         └─────────────┘         └───────────┘ │
│         │                       │                       │       │
│         ▼                       ▼                       ▼       │
│  ┌─────────────┐         ┌─────────────┐         ┌───────────┐ │
│  │   Pension   │         │    NHF      │         │   Audit   │ │
│  │     8%      │         │    2.5%     │         │   Trail   │ │
│  └─────────────┘         └─────────────┘         └───────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Inventory to Sales to Customers Flow

### Complete Sales Cycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    INVENTORY MANAGEMENT                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐                                                │
│  │  Products   │─────────────────────────────────┐              │
│  │  (SKU)      │                                 │              │
│  └─────────────┘                                 │              │
│         │                                        ▼              │
│         ▼                              ┌─────────────────────┐  │
│  ┌─────────────┐                       │   STOCK MOVEMENT    │  │
│  │   Stock     │                       │   • Purchase        │  │
│  │   Levels    │◄──────────────────────│   • Sale            │  │
│  └─────────────┘                       │   • Adjustment      │  │
│         │                              │   • Transfer        │  │
│         ▼                              └─────────────────────┘  │
│  ┌─────────────┐                                                │
│  │  Reorder    │                                                │
│  │   Alerts    │                                                │
│  └─────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SALES RECORDING                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  Customer   │───►│   Sale      │───►│   Invoice   │         │
│  │  Selection  │    │   Created   │    │  Generated  │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                            │                  │                 │
│                            ▼                  ▼                 │
│                     ┌─────────────┐    ┌─────────────┐         │
│                     │    VAT      │    │    NRS      │         │
│                     │    7.5%     │    │    IRN      │         │
│                     └─────────────┘    └─────────────┘         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CUSTOMER MANAGEMENT                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  Customer   │◄──►│  Balance    │◄──►│  Payment    │         │
│  │  Profile    │    │  Tracking   │    │  History    │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────────────────────────────────────────┐           │
│  │              CREDIT MANAGEMENT                   │           │
│  │   • Credit Limit    • Outstanding Balance       │           │
│  │   • Payment Terms   • Aging Analysis            │           │
│  └─────────────────────────────────────────────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Relationships

| From | To | Relationship |
|------|-----|-------------|
| Product | Inventory | Stock levels tracked per product |
| Inventory | Sale | Stock reduced on sale |
| Sale | Transaction | Financial record created |
| Sale | Invoice | Customer invoice generated |
| Invoice | NRS | IRN submitted to FIRS |
| Customer | Sale | Customer linked to purchases |
| Customer | Balance | Outstanding amounts tracked |

---

## ML/AI Engine Connections

### Machine Learning Features

1. **Cash Flow Forecasting**
   - Analyzes historical transactions
   - Predicts future cash positions
   - Alerts on potential shortfalls

2. **Revenue Growth Prediction**
   - Uses neural networks
   - Considers seasonality
   - Provides confidence intervals

3. **OCR Document Processing**
   - Receipt scanning
   - Invoice digitization
   - Automatic categorization

4. **NLP Analysis**
   - Transaction description understanding
   - Sentiment analysis on notes
   - Anomaly detection in text

### ML Data Sources

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│Transactions │───►│             │───►│  Forecast   │
└─────────────┘    │             │    └─────────────┘
                   │   ML/AI     │
┌─────────────┐    │   ENGINE    │    ┌─────────────┐
│  Invoices   │───►│             │───►│  Growth     │
└─────────────┘    │             │    │ Prediction  │
                   │             │    └─────────────┘
┌─────────────┐    │             │    ┌─────────────┐
│   Sales     │───►│             │───►│  Anomaly    │
└─────────────┘    └─────────────┘    │  Detection  │
                                       └─────────────┘
```

---

## API Structure

### Endpoint Hierarchy

```
/api/v1/
├── auth/                    # Authentication
├── staff/                   # Platform staff management
├── entities/                # Business entities
│   ├── {entity_id}/
│   │   ├── transactions/
│   │   ├── invoices/
│   │   ├── vendors/
│   │   ├── customers/
│   │   ├── inventory/
│   │   ├── reports/
│   │   └── audit/
├── payroll/                 # Payroll system
│   ├── calculate-salary/
│   ├── employees/
│   ├── payroll-runs/
│   └── advanced/
│       ├── compliance-status/
│       ├── impact-preview/
│       └── decision-log/
├── tax-2026/               # 2026 Tax Reform
├── ml/                     # Machine Learning
│   ├── dashboard/
│   ├── forecast/
│   └── predict/
└── bank-reconciliation/
    └── expense-claims/
```

---

## File Structure

```
TekVwarho ProAudit/
├── main.py                 # FastAPI application entry
├── app/
│   ├── config.py          # Environment configuration
│   ├── database.py        # SQLAlchemy setup
│   ├── models/            # Database models
│   ├── schemas/           # Pydantic schemas
│   ├── routers/           # API endpoints
│   ├── services/          # Business logic
│   └── utils/             # Utilities
├── templates/             # Jinja2 HTML templates
├── static/                # CSS, JS, images
├── docs/                  # Documentation
└── tests/                 # Test suite
```

---

## Security Architecture

1. **Authentication**
   - JWT tokens in HTTP-only cookies
   - Refresh token rotation
   - Session management

2. **Authorization (RBAC)**
   - Platform Staff roles (Super Admin, Admin, Support)
   - Organization roles (Owner, Admin, Accountant, Viewer)
   - Entity-level permissions

3. **Data Protection**
   - NDPA (Nigeria Data Protection Act) compliance
   - Encryption at rest and in transit
   - Geo-fencing for Nigerian operations

4. **Audit Compliance**
   - NTAA 2025 requirements
   - Immutable audit trails
   - 7-year data retention

---

## Accounting & Reports Architecture

### Page Separation

The system separates accounting operations from financial reporting for clarity:

| Page | URL | Purpose |
|------|-----|---------|
| **Accounting** | `/accounting` | GL management, Journal Entries, Fiscal Periods |
| **Reports** | `/reports` | Financial Reports, Tax Reports, Audit Vault |

### Navigation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                       /accounting                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Chart of  │  │   Journal   │  │   Fiscal    │             │
│  │   Accounts  │  │   Entries   │  │   Periods   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                          │                                       │
│              "📊 Financial Reports" button                       │
│                          │                                       │
└──────────────────────────┼───────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                         /reports                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Financial  │  │    Tax      │  │   Audit     │             │
│  │  Reports    │  │   Reports   │  │   Vault     │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                          │                                       │
│              "← Back to Accounting" button                       │
│                          │                                       │
└──────────────────────────┼───────────────────────────────────────┘
                           │
                           ▼
                     /accounting
```

### API Endpoints

The accounting router (`/api/v1/entities/{id}/accounting/`) handles:
- Chart of Accounts CRUD
- Journal Entries CRUD  
- Fiscal Periods management
- GL Balance recalculation

The reports router (`/api/v1/entities/{id}/reports/`) handles:
- Trial Balance generation
- Profit & Loss (Income Statement)
- Balance Sheet
- Cash Flow Statement
- Tax Reports (VAT, WHT, PAYE, CIT)
- AR/AP Aging Reports

### Data Flow: Journal Entries → Reports

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Source System  │────►│ Journal Entry   │────►│  GL Account     │
│ (Invoice, Txn)  │     │    Created      │     │ Balance Updated │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │ Reports Reflect │
                                                │  Updated Data   │
                                                └─────────────────┘
```

---

## Summary Statistics

| Component | Count |
|-----------|-------|
| API Routers | 30+ |
| Database Models | 50+ |
| HTML Templates | 35+ |
| Service Classes | 25+ |
| ML Features | 5 |

---

*This documentation provides a comprehensive overview of the TekVwarho ProAudit system architecture, showing how all components connect and interact to deliver a world-class Nigerian tax compliance platform.*
