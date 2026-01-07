# TekVwarho ProAudit

> **Nigeria's Premier Tax Compliance & Business Management Platform for the 2026 Tax Reform Era**

[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
[![Nigeria Tax Compliant](https://img.shields.io/badge/NRS-2026%20Compliant-blue.svg)](#)
[![NDPA Compliant](https://img.shields.io/badge/NDPA-2023%20Compliant-green.svg)](#)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-green.svg)](#)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](#)

---

## Overview

TekVwarho ProAudit is a comprehensive financial management and tax compliance solution designed specifically for Nigerian businesses navigating the **2026 Tax Reform landscape**. The platform integrates real-time NRS (Nigeria Revenue Service) e-invoicing, automated tax calculations, and audit-ready financial reporting into a single, unified system.

**Copyright (c) 2026 Tekvwarho LTD. All Rights Reserved.**

### Why TekVwarho ProAudit?

With Nigeria's historic 2026 tax reforms introducing:
- **Progressive PAYE brackets** (starting with ₦800,000 tax-free threshold)
- **Mandatory e-invoicing** via the NRS portal
- **Input VAT recovery** on services and fixed assets
- **Small business exemptions** (0% CIT for turnover ≤ ₦50M)
- **4% Development Levy** for larger enterprises
- **Capital Gains taxed at CIT rate** (merged into corporate income)

...businesses need a modern, integrated solution that handles compliance automatically while providing actionable financial insights.

---

## Version 2.1.0 - Security & Compliance Suite (NDPA/NITDA 2023)

### Nigerian Data Protection Compliance
TekVwarho ProAudit now includes **enterprise-grade security** features fully compliant with Nigeria's Data Protection Act 2023 (NDPA) and NITDA guidelines.

#### PII Encryption (AES-256-GCM)
- **Field-Level Encryption**: BVN, NIN, RSA PIN, bank accounts, TIN, phone numbers
- **Authenticated Encryption**: AES-256-GCM with integrity verification
- **Key Rotation**: Versioned key management for security updates
- **PIIMasker**: Display-safe masking (`12345678901` → `***45***901`)

#### Nigerian Data Sovereignty
- **Geo-Fencing**: Restrict access to Nigerian IP ranges only
- **Nigerian ISP Blocks**: MTN, Airtel, Glo, 9mobile, MainOne, Rack Centre
- **AFRINIC Allocations**: Verified Nigerian IP address ranges
- **Logging**: All access attempts logged for compliance audits

#### Right-to-Erasure Workflow
- **NDPA Article 36 Compliance**: Data subject deletion requests
- **Statutory Retention**: Automatic 7-year hold for tax records
- **Audit Trail**: Complete logging of erasure activities
- **Selective Erasure**: Delete only non-statutory data

#### Rate Limiting & DDoS Protection
| Endpoint Category | Limit | Window |
|-------------------|-------|--------|
| Login | 5 requests | 1 minute |
| Registration | 3 requests | 1 minute |
| Tax Calculators | 30 requests | 1 minute |
| NRS Submission | 10 requests | 1 minute |
| Password Reset | 3 requests | 15 minutes |
| General API | 100 requests | 1 minute |

#### CSRF Protection (HTMX)
- **Double-Submit Cookie Pattern**: Industry-standard CSRF protection
- **HTMX Integration**: Automatic X-CSRF-Token header injection
- **SameSite Cookies**: Strict cookie configuration
- **Bearer Token Bypass**: API requests use JWT authentication

#### XSS Protection & Security Headers
- **Content Security Policy**: `default-src 'self'` with trusted sources
- **X-Frame-Options**: DENY (clickjacking protection)
- **HSTS**: 1-year max-age with includeSubDomains
- **X-Content-Type-Options**: nosniff
- **Referrer-Policy**: strict-origin-when-cross-origin

#### Brute Force Protection
- **Account Lockout**: 5 failed attempts maximum
- **Progressive Lockout**: 1min → 5min → 15min → 1hr → 24hr
- **Automatic Unlock**: Time-based lockout expiry
- **Login Integration**: Pre-authentication lockout check

#### Nigerian Validators
- `validate_nigerian_tin`: FIRS TIN format (10 characters)
- `validate_nigerian_bvn`: BVN format (11 digits)
- `validate_nigerian_nin`: NIN format (11 digits)
- `validate_nigerian_phone`: Nigerian phone (+234/0 prefix)
- `validate_nigerian_account`: NUBAN account (10 digits)

### Security Middleware Stack
The application loads 6 security middleware layers in optimal order:
1. **RequestLoggingMiddleware** - Security event logging
2. **SecurityHeadersMiddleware** - CSP, HSTS, X-Frame-Options
3. **CSRFMiddleware** - Double-submit cookie validation
4. **AccountLockoutMiddleware** - Pre-login lockout check
5. **RateLimitingMiddleware** - Per-endpoint rate limiting
6. **GeoFencingMiddleware** - Nigerian IP enforcement

### New Security Files
```
app/utils/ndpa_security.py     - NDPA security utilities (~700 lines)
app/middleware/security.py     - Security middleware (~500 lines)
app/middleware/__init__.py     - Middleware package exports
docs/SECURITY_ARCHITECTURE.md  - Security documentation
```

---

## Version 2.0.0 - Business Intelligence & Executive Compensation Suite

### BIK (Benefit-in-Kind) Automator for Executive Compensation
TekVwarho ProAudit now includes a **comprehensive BIK calculation engine** that automatically values executive benefits using 2026 Nigerian tax rules.

#### Vehicle Benefits
- **Saloon Car**: 5% of vehicle cost
- **SUV/Crossover**: 5% of vehicle cost + 25% premium
- **Pick-up Truck**: 4% of vehicle cost (commercial use)
- **Luxury Vehicle**: 7.5% of vehicle cost + luxury surcharge
- **Driver Benefit**: ₦600,000/year flat rate

#### Accommodation Benefits
- **Rented (Unfurnished)**: 7.5% of annual rent
- **Rented (Furnished)**: 10% of annual rent
- **Company-Owned**: 15% of annual salary
- **Furniture Allowance**: 10% of furniture value

#### Other Benefits
- **Utilities**: 100% of employer-paid amounts (electricity, water, gas, internet)
- **Domestic Staff**: ₦500,000/year per staff member
- **Generator**: 10% of cost + fuel allowance

#### PAYE on BIK
- Automatic PAYE calculation using 2026 progressive brackets
- Integration with payroll for consolidated tax reporting

### NIBSS Pension Direct-Debit Generator
Generate **bank-ready NIBSS XML files** for bulk pension payments to all licensed Pension Fund Administrators.

#### Supported PFAs (20+)
ARM, Stanbic IBTC, Leadway, AIICO, AXA Mansard, Crusader Sterling, Fidelity, First Guarantee, 
IEI Anchor, NLPC, NPF Pensions, Oak Pensions, OAK, PAL Pensions, Premium, Radix, 
Sigma, Tangerine, Trustfund, Veritas Glanvills

#### Features
- **NIBSS NIP Bulk Payment Format**: Bank-compatible XML structure
- **RSA PIN Validation**: Verify employee pension registration numbers
- **Multi-Batch Processing**: Handle thousands of pension payments
- **CSV Export**: Alternative format for bank uploads
- **Summary Reports**: Reconciliation-ready payment summaries

### Growth Radar & Tax Threshold Intelligence
Smart monitoring system that tracks your business growth and alerts you before crossing critical **tax thresholds**.

#### Nigerian Tax Thresholds Monitored
| Threshold | Amount | Tax Implications |
|-----------|--------|------------------|
| Small → Medium | ₦25,000,000 | CIT changes from 0% to 20% |
| Medium → Large | ₦100,000,000 | CIT 30%, Dev Levy 4%, TET 2.5% |
| VAT Registration | ₦25,000,000 | Mandatory VAT collection |

#### Features
- **Proximity Analysis**: Distance to next threshold in percentage
- **Growth Projection**: Months until threshold breach
- **Transition Planning**: Preparation checklist for bracket changes
- **Alert Levels**: Normal → Info → Warning → Critical → Exceeded

### Stock Write-off VAT Workflow
Automated handling of **inventory write-offs** with proper VAT input adjustment documentation.

#### Write-off Reasons Supported
- Expired goods (with expiry date validation)
- Damaged/defective stock
- Obsolete inventory
- Theft/loss (with police report)
- Spoilage (perishables)
- Quality failures (QC rejected)
- Sample distribution (marketing)
- Regulatory destruction (compliance)

#### VAT Adjustment
- Automatic 7.5% VAT input reversal calculation
- FIRS-compliant adjustment documentation
- Approval workflow integration
- Supporting document tracking

### Multi-Location Inventory Transfers
Full support for **inventory movements** between warehouses, stores, and production facilities.

#### Transfer Types
- Warehouse to Warehouse
- Store to Store
- Warehouse to Store
- Store to Warehouse
- Production to Warehouse
- Warehouse to Production
- Warehouse to Customer (Direct Ship)

#### Interstate Levy Calculation
- **0.5% Levy**: Automatically applied for cross-state transfers
- All 37 Nigerian states + FCT supported
- Levy documentation for state revenue authorities

### Robust Error Handling System
Enterprise-grade **exception handling** with 50+ custom error types for comprehensive error management.

#### Exception Categories
- **Validation Errors**: Field-level validation with Nigerian-specific rules
- **Authentication**: Login, token, and session errors
- **Authorization**: Role-based permission denials
- **Business Rules**: Domain-specific violations
- **Tax Calculations**: Nigerian tax computation errors
- **NRS Integration**: FIRS e-invoicing failures
- **Database**: Connection and integrity errors
- **External Services**: Third-party API failures

#### Nigerian-Specific Validators
- TIN format validation (FIRS format)
- BVN validation (11-digit format)
- Nigerian bank account validation
- RSA PIN validation (PEN + 12 digits)

### New API Endpoints

#### Business Intelligence
```
POST /api/v1/business-intelligence/bik/calculate
GET  /api/v1/business-intelligence/bik/rates
POST /api/v1/business-intelligence/pension/generate-nibss-file
POST /api/v1/business-intelligence/pension/generate-nibss-file/download
GET  /api/v1/business-intelligence/pension/pfa-list
POST /api/v1/business-intelligence/pension/validate-rsapin
GET  /api/v1/business-intelligence/growth-radar
GET  /api/v1/business-intelligence/growth-radar/thresholds
GET  /api/v1/business-intelligence/growth-radar/projection
POST /api/v1/business-intelligence/inventory/write-off
GET  /api/v1/business-intelligence/inventory/write-off/reasons
POST /api/v1/business-intelligence/inventory/write-off/{id}/vat-adjustment-doc
POST /api/v1/business-intelligence/inventory/transfer
GET  /api/v1/business-intelligence/inventory/transfer/states
GET  /api/v1/business-intelligence/inventory/transfer/types
```

### New Services Created
- `app/services/bik_automator.py` - BIK calculation engine
- `app/services/nibss_pension.py` - NIBSS XML generation
- `app/services/growth_radar.py` - Threshold monitoring
- `app/services/inventory_management.py` - Write-off and transfer workflows
- `app/utils/error_handling.py` - Comprehensive error system

### Documentation
- `docs/ADVANCED_ACCOUNTING_MODULE.md` - Complete module documentation

---

## Version 1.9.0 - Payroll System with Nigerian 2026 Compliance

### Complete Payroll Management
TekVwarho ProAudit now includes a **full-featured payroll system** designed specifically for Nigerian businesses, with complete 2026 Tax Reform compliance built-in.

### Nigerian Tax Reform 2026 - PAYE Compliance
- **New Tax-Free Threshold**: ₦800,000 annual (was ₦300,000) - employees earning below this pay no PAYE
- **Progressive PAYE Bands**:
  - ₦0 - ₦800,000: 0% (Exempt)
  - ₦800,001 - ₦2,400,000: 15%
  - ₦2,400,001 - ₦4,800,000: 20%
  - ₦4,800,001 - ₦7,200,000: 25%
  - Above ₦7,200,000: 30%
- **Consolidated Relief Allowance (CRA)**: ₦200,000 + 20% of Gross Income
- **2026 Rent Relief**: 20% of annual rent paid (max ₦500,000)
- **Life Insurance Premium Relief**: Monthly premiums (max ₦250,000/year)

### Statutory Deductions
- **Pension Contribution**: 8% employee / 10% employer (per PenCom guidelines)
- **NHF**: 2.5% of basic salary (for eligible employees)
- **NSITF**: 1% employer contribution
- **ITF**: 1% employer contribution for qualifying companies

### Employee Management
- **Comprehensive Employee Records**: Personal details, employment info, compliance data
- **Bank Account Management**: Multiple accounts per employee, primary account designation
- **Nigerian PFA Integration**: All 20 licensed Pension Fund Administrators supported
- **Leave Management**: Annual, sick, maternity, paternity, and other leave types

### Payroll Processing
- **Automated Salary Calculation**: Gross pay, deductions, net pay in one click
- **Payroll Runs**: Monthly, bi-weekly, or weekly pay periods
- **Approval Workflow**: Draft → Pending Approval → Approved → Processing → Paid
- **Bank Schedule Generation**: Payment file export for bank uploads
- **Payslip Generation**: Detailed payslips with all earnings and deductions

### Remittance Tracking
- **PAYE Remittance**: Track monthly PAYE submissions to state tax authorities
- **Pension Remittance**: Monitor PFA contribution transfers
- **NHF/NSITF/ITF Tracking**: Complete statutory remittance management
- **Due Date Alerts**: Never miss a compliance deadline

### Salary Calculator
- **Interactive Calculator**: Real-time net salary calculation
- **What-If Analysis**: Compare different salary structures
- **Tax Breakdown**: See exactly how PAYE is calculated
- **Employer Cost View**: Total cost-to-company analysis

### New API Endpoints
- `POST /api/v1/payroll/employees` - Create employee
- `GET /api/v1/payroll/employees` - List employees
- `POST /api/v1/payroll/payroll-runs` - Create payroll run
- `POST /api/v1/payroll/payroll-runs/{id}/process` - Process payroll
- `GET /api/v1/payroll/payslips` - List payslips
- `POST /api/v1/payroll/calculate-salary` - Calculate salary breakdown
- `GET /api/v1/payroll/remittances` - List statutory remittances
- `GET /api/v1/payroll/dashboard` - Payroll dashboard stats

### Frontend Pages
- **Payroll Dashboard**: At-a-glance payroll metrics and pending actions
- **Employees Tab**: Full employee directory with search and filters
- **Payroll Runs Tab**: View and manage all payroll runs
- **Remittances Tab**: Track all statutory remittance obligations
- **Loans Tab**: Employee loan and salary advance management
- **Salary Calculator Modal**: Interactive 2026-compliant calculator

### Database Schema
New tables added via Alembic migration `20260106_1600_add_payroll_system.py`:
- `employees` - Employee master records
- `employee_bank_accounts` - Bank account details
- `payroll_runs` - Payroll batch processing
- `payslips` - Individual employee payslips
- `payslip_items` - Earnings and deduction line items
- `statutory_remittances` - PAYE, pension, NHF tracking
- `employee_loans` - Loan and advance management
- `loan_repayments` - Loan repayment history
- `employee_leaves` - Leave requests and approvals
- `payroll_settings` - Entity-level payroll configuration

---

## Version 1.8.0 - Nigeria Address Fields & Registration Improvements

### Nigeria States & LGAs API
- **Complete Nigeria Data**: All 37 states and 774 Local Government Areas
- **REST API Endpoints**: `/api/v1/auth/nigeria/states` and `/api/v1/auth/nigeria/states/{state}/lgas`
- **Authoritative Data Source**: Accurate and comprehensive Nigeria geographic data
- **State Validation**: State and LGA validation for business entity addresses

### Registration Flow Improvements
- **Dynamic LGA Dropdown**: LGA field auto-populates based on selected state
- **State-Dependent Selection**: JavaScript-powered cascading dropdowns
- **Address Field Enhancement**: Both business entities and user profiles support LGA
- **Improved UX**: Clean, intuitive registration form with Nigerian address support

### Email Verification Enhancements
- **Verification Tracking**: New database fields track verification status
- **`email_verification_token`**: Secure token storage in database
- **`email_verification_sent_at`**: Timestamp for token expiry validation
- **`email_verified_at`**: Record of successful verification time
- **`is_invited_user`**: Distinguishes invited users from self-registered users

### Database Migration
- **New LGA Column**: Added `lga` column to `business_entities` table
- **User Verification Fields**: Added 4 new columns to `users` table
- **Alembic Migration**: `20260106_1400_add_lga_email_verification.py`

---

## Version 1.7.0 - Bulk Operations & Export Improvements

### Bulk Operations
- **Bulk Import**: CSV/Excel import for customers, vendors, inventory, and transactions
- **Bulk Delete**: Delete multiple records at once with confirmation
- **Background Processing**: Large imports handled via Celery workers
- **Progress Tracking**: Real-time progress indicators for bulk operations

### Export Enhancements  
- **Multi-Format Export**: PDF, Excel, CSV export for all data types
- **Custom Date Ranges**: Filter exports by date range
- **Template Support**: Downloadable CSV templates for bulk imports

---

## Version 1.6.0 - Security & Authentication Enhancements

### Email Verification System
- **Registration Verification**: New users receive verification email with secure token
- **Resend Verification**: Users can request new verification emails
- **Full URL Links**: Email links include complete URLs for better deliverability

### Staff Onboarding Security
- **Forced Password Reset**: Newly onboarded staff/admins must change password on first login
- **Security Banner**: Clear notification prompting password change
- **Automatic Redirect**: Staff redirected to settings page until password is changed

### Password Security Features
- **Password Visibility Toggle**: Eye icon to show/hide passwords on all auth forms
- **Password Reset Flow**: Complete forgot password → email → reset password workflow

### Global Error Handling
- **Consistent Error Responses**: All errors return standardized JSON format
- **Exception Types Handled**:
  - HTTP Exceptions (4xx/5xx)
  - Request Validation Errors (422)
  - Pydantic Validation Errors
  - Business Logic Errors (ValueError)
  - Permission Errors (403)
  - Unhandled Exceptions (500)
- **Development Mode**: Detailed error messages for debugging
- **Production Mode**: Sanitized error messages for security

---

## Version 1.4.0 - Complete 2026 Compliance

### TIN Validation (NRS Portal Integration)
- **Real-time TIN Verification**: Validate TINs via [NRS TaxID Portal](https://taxid.nrs.gov.ng/)
- **Individual Validation**: Verify individuals using 11-digit NIN (National Identification Number)
- **Corporate Validation**: Support for Business Name, Company, Incorporated Trustee, Limited Partnership, LLP
- **Vendor Compliance Check**: Pre-contract verification with **₦5,000,000** penalty warning

### 15% Minimum Effective Tax Rate (ETR)
- **Large Company Threshold**: Applies to businesses with turnover >= **₦50 billion**
- **MNE Constituents**: Applies to groups with revenue >= **€750 million**
- **Top-up Tax Calculation**: Automatic ETR shortfall detection and top-up calculation

### Capital Gains Tax (CGT) at 30%
- **New Rate for Large Companies**: CGT increased from 10% to **30%**
- **Small Company Exemption**: Turnover ≤ ₦100M AND assets ≤ ₦250M retain 10% rate
- **Indexation Allowance**: Inflation adjustment for long-held assets

### Zero-Rated VAT Input Credit Tracking
- **Refund Eligibility**: Track input VAT on zero-rated supplies (food, education, healthcare, exports)
- **IRN Validation**: Only purchases with valid NRS IRN qualify for refund
- **Claim Generation**: Automated refund claim calculation

### Peppol BIS Billing 3.0 Export
- **UBL 2.1 XML Export**: Peppol-compliant structured invoice format
- **JSON Export**: API-friendly invoice representation
- **CSID Generation**: Cryptographic Stamp Identifier for invoice integrity
- **QR Code Embedding**: Verification data for invoice authentication

### Compliance Penalty Tracker
- **Late Filing**: ₦100,000 first month + ₦50,000 subsequent months
- **Unregistered Vendor**: ₦5,000,000 fixed penalty
- **B2C Late Reporting**: ₦10,000 per transaction (max ₦500,000/day)
- **Tax Remittance**: 10% + 2% monthly interest for VAT/PAYE/WHT

---

## Version 1.3.0 - Fixed Assets & Dashboard

### Fixed Asset Register
- Complete capital asset tracking with depreciation (Straight Line, Reducing Balance, Units of Production)
- Automatic capital gain/loss calculation on disposal (taxed at CIT rate under 2026 reform)
- VAT recovery on capital assets via vendor IRN validation
- Standard Nigerian depreciation rates built-in

### Compliance Health Dashboard
- **TIN/CAC Vault**: Prominent display of tax credentials with verification status
- **Compliance Health Score**: Real-time compliance indicator (0-100%)
- **Small Company Status**: Automatic 0% CIT eligibility check
- **Development Levy Status**: Exemption threshold monitoring

### B2C Real-time Reporting
- Automatic reporting of B2C transactions over ₦50,000 to NRS within 24 hours
- Configurable reporting thresholds per entity

---

## Key Features

### Core Business Operations

| Feature | Description |
|---------|-------------|
| **Inventory Management** | Real-time stock tracking with automated low-stock alerts. "Stock-to-Tax" linking for expired/damaged goods write-offs |
| **Multi-Entity Accounts** | Separate ledgers for multiple businesses with Role-Based Access Control (Owner, Accountant, Auditor views) |
| **Supply Chain Tracking** | Vendor management with integrated TIN verification, VAT-compliance status tracking |
| **Expense & Income** | Automated categorization, WREN flagging for tax-deductible expenses |
| **Financial Reports** | One-click audit-ready PDFs: Trial Balance, P&L, Fixed Asset Registers |
| **Fixed Asset Register** | Capital asset tracking, depreciation schedules, capital gains reporting |

### 2026 Tax Compliance Engine

| Feature | Description |
|---------|-------------|
| **NRS E-Invoicing** | Real-time B2B/B2C invoice validation, automatic IRN and QR Code generation |
| **TIN Validation** | Real-time TIN verification via NRS TaxID portal (Individual/Corporate) |
| **Input VAT Recovery** | Track VAT paid on services and fixed assets as credits to reduce final VAT liability |
| **Zero-Rated VAT Tracker** | Track refund-eligible input VAT on zero-rated supplies (IRN validated) |
| **Smart Tax Logic** | Automatic 0% CIT for small businesses, 4% Development Levy for larger companies |
| **Minimum ETR (15%)** | Top-up tax calculation for companies with ₦50B+ turnover |
| **CGT at 30%** | Capital Gains Tax for large companies (small company exemption) |
| **Progressive PAYE** | Payroll module with 2026 tax bands (₦800,000 tax-free bracket support) |
| **72-Hour Dispute Window** | Track buyer rejections within the 72-hour window with legal lock protection |
| **B2C Real-time Reporting** | 24-hour NRS reporting for B2C transactions over ₦50,000 |
| **Compliance Penalties** | Automatic penalty calculation (late filing, unregistered vendor, B2C late) |
| **Peppol BIS 3.0** | Export invoices as UBL 2.1 XML/JSON for international trade |

### Advanced Financial Pipeline

| Feature | Description |
|---------|-------------|
| **Audit Vault** | 5-year digital record keeping compliant with NTAA requirements |
| **Asset Register** | Depreciation tracking and Capital Gains merged into CIT reporting |
| **Self-Assessment** | Pre-fills NRS forms based on yearly data for TaxPro Max upload |
| **TaxPro Max Export** | Ready-file CSV/Excel exports formatted for TaxPro Max upload requirements |
| **WHT Manager** | Automatic Withholding Tax calculations by service type and payee |
| **Compliance Health** | Real-time compliance score with automated threshold monitoring |

---

## Test Coverage

Comprehensive test suite verified with **313 tests passing**:

| Category | Tests | Status |
|----------|-------|--------|
| **Tax Calculators** (VAT, PAYE, WHT, CIT) | 28 tests | Passing |
| **2026 Tax Compliance** | 177 tests | Passing |
| **API & Authentication** | 50 tests | Passing |
| **Transaction Service** | 11 tests | Passing |
| **Compliance Health** | 47 tests | Passing |
| **Total** | **313 tests** | **All Passing** |

### Tax Calculator Details

| Tax Type | Tests | Status |
|----------|-------|--------|
| **VAT** (7.5%) | 4 tests | Passing |
| **PAYE** (2026 Bands) | 6 tests | Passing |
| **WHT** (By Service Type) | 7 tests | Passing |
| **CIT** (0%/20%/30%) | 6 tests | Passing |
| **Band Detection** | 5 tests | Passing |
| **Minimum ETR** (15%) | 5 tests | Passing |
| **CGT** (30% Large Co.) | 6 tests | Passing |
| **TIN Validation** | 10 tests | Passing |
| **Penalty Tracking** | 8 tests | Passing |
| **Peppol Export** | 6 tests | Passing |

---

## Target Users

1. **Small & Medium Enterprises (SMEs)** - Simplified compliance for the 0% CIT bracket
2. **Large Corporations** - Complex multi-entity management with Development Levy tracking
3. **Tax Consultants/Auditors** - Read-only audit views and export capabilities
4. **Accountants** - Day-to-day financial management and reconciliation
5. **External Accountants** - Client access for tax filings (time-limited)

---

## Technical Stack

```
Backend:        Python 3.11+ with FastAPI 0.110+
Database:       PostgreSQL 15+
ORM:            SQLAlchemy 2.0 + Alembic (Migrations)
Frontend:       Jinja2 Templates + HTMX + Alpine.js + TailwindCSS
E-Invoicing:    NRS API Integration (REST/Async)
Authentication: FastAPI-Users + OAuth2/JWT
Validation:     Pydantic v2
Task Queue:     Celery + Redis
PDF Generation: WeasyPrint / ReportLab
Hosting:        AWS / Azure (Nigeria Region for data residency)
Platforms:      Web (Responsive), Desktop (Windows/macOS - Future)
```

Note: No mobile application is planned. Future development will focus on 
native desktop applications for Windows and macOS.

---

## Project Structure

```
TekVwarho-ProAudit/
├── docs/
│   ├── BUSINESS_CASE.md          # Business justification & ROI
│   ├── USE_CASES.md              # Detailed use case scenarios
│   ├── UI_UX_RESEARCH.md         # User research & design guidelines
│   ├── TECHNICAL_ARCHITECTURE.md # System design & API specs
│   ├── WIREFRAMES.md             # Comprehensive wireframe designs
│   ├── COMPLIANCE_REQUIREMENTS.md # Nigeria 2026 tax law compliance
│   ├── ROADMAP.md                # Development phases & timeline
│   └── RECOMMENDATIONS.md        # Strategic guidance
├── app/                          # FastAPI application
│   ├── config.py                 # Settings & environment config
│   ├── database.py               # SQLAlchemy async engine
│   ├── models/                   # SQLAlchemy models
│   ├── schemas/                  # Pydantic schemas
│   ├── routers/                  # API route handlers
│   ├── services/                 # Business logic
│   │   └── tax_calculators/      # VAT, PAYE, CIT, WHT
│   └── tasks/                    # Celery background tasks
├── templates/                    # Jinja2 HTML templates
├── static/                       # CSS, JS, images
├── tests/                        # Test suites
├── main.py                       # FastAPI entry point
├── README.md                     # This file
├── LICENSE                       # Tekvwarho LTD Proprietary License
├── CONTRIBUTING.md               # Contribution guidelines
├── requirements.txt              # Python dependencies
├── pyproject.toml                # Python project config
└── alembic.ini                   # Database migration config
```

---

## Getting Started

**Project is currently in the documentation and planning phase.**

### Prerequisites (Planned)
- Python 3.11+
- PostgreSQL 15+
- NRS Developer Account (for e-invoicing sandbox)

### Installation (Coming Soon)

```bash
# Clone the repository
git clone https://github.com/EfeObus/TekVwarho-ProAudit.git
cd TekVwarho-ProAudit

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run database migrations
alembic upgrade head

# Start development server
uvicorn main:app --reload --port 8000
```

---

## System Statistics (v2.1.0)

| Metric | Value |
|--------|-------|
| **Total Routes** | 527 |
| **API Endpoints** | 471 |
| **View Routes** | 52 |
| **Database Models** | 84 exports |
| **Test Coverage** | 313 tests passing |
| **Security Middleware** | 6 layers |
| **Templates** | 26 HTML files |
| **Services** | 45+ service modules |
| **Routers** | 31 API routers |

---

## Compliance Certifications

- [x] NRS E-Invoicing Integration (Development & Production APIs)
- [x] NDPA 2023 Data Protection Compliance
- [x] NITDA Security Guidelines
- [ ] ISO 27001 Information Security (Planned)

---

## License

**PROPRIETARY - All Rights Reserved**

This software is the intellectual property of Tekvwarho LTD. It may not be sold, resold, redistributed, or sublicensed. Use is permitted for personal and educational purposes only.

See [LICENSE](LICENSE) for full terms and conditions.

This software complies with Nigerian law including:
- Companies and Allied Matters Act (CAMA) 2020
- Nigeria Data Protection Regulation (NDPR) 2019
- Nigeria Data Protection Act 2023
- Copyright Act (Cap C28, LFN 2004)

---

## Contact

- **Company:** Tekvwarho LTD
- **Email:** contact@tekvwarho.com
- **GitHub:** [EfeObus/TekVwarho-ProAudit](https://github.com/EfeObus/TekVwarho-ProAudit)

---

## Acknowledgments

- Nigeria Revenue Service (NRS) for the 2026 Tax Reform framework
- Federal Inland Revenue Service (FIRS) documentation
- Nigerian business community for feedback and validation

---

*Copyright (c) 2026 Tekvwarho LTD. All Rights Reserved.*
*Built for Nigerian businesses navigating the new tax landscape.*
