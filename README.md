# TekVwarho ProAudit

> **Nigeria's Premier Tax Compliance & Business Management Platform for the 2026 Tax Reform Era**

[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
[![Nigeria Tax Compliant](https://img.shields.io/badge/NRS-2026%20Compliant-blue.svg)](#)
[![Status](https://img.shields.io/badge/Status-In%20Development-orange.svg)](#)

---

## Overview

TekVwarho ProAudit is a comprehensive financial management and tax compliance solution designed specifically for Nigerian businesses navigating the **2026 Tax Reform landscape**. The platform integrates real-time NRS (Nigeria Revenue Service) e-invoicing, automated tax calculations, and audit-ready financial reporting into a single, unified system.

**Copyright (c) 2026 Tekvwarho LTD. All Rights Reserved.**

### Why TekVwarho ProAudit?

With Nigeria's historic 2026 tax reforms introducing:
- **Progressive PAYE brackets** (starting with ₦800,000 tax-free threshold)
- **Mandatory e-invoicing** via the NRS portal
- **Input VAT recovery** on services and fixed assets
- **Small business exemptions** (0% CIT for turnover ≤ ₦50M-₦100M)
- **4% Development Levy** for larger enterprises

...businesses need a modern, integrated solution that handles compliance automatically while providing actionable financial insights.

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

### 2026 Tax Compliance Engine

| Feature | Description |
|---------|-------------|
| **NRS E-Invoicing** | Real-time B2B invoice validation, automatic IRN (Invoice Reference Number) and QR Code generation |
| **Input VAT Recovery** | Track VAT paid on services and fixed assets as credits to reduce final VAT liability |
| **Smart Tax Logic** | Automatic 0% CIT for small businesses, 4% Development Levy calculation for larger companies |
| **Progressive PAYE** | Payroll module with 2026 tax bands (₦800,000 tax-free bracket support) |
| **72-Hour Dispute Monitor** | Track buyer rejections within the 72-hour window to prevent phantom income taxation |

### Advanced Financial Pipeline

| Feature | Description |
|---------|-------------|
| **Audit Vault** | 5-year digital record keeping compliant with NTAA requirements |
| **Asset Register** | Depreciation tracking and Capital Gains Tax (30%) merged into income reporting |
| **Self-Assessment** | Pre-fills NRS forms based on yearly data for TaxPro Max upload |
| **TaxPro Max Export** | Ready-file CSV/Excel exports formatted for TaxPro Max upload requirements |
| **WHT Manager** | Automatic Withholding Tax exemption for small business transactions under ₦2M |

---

## Target Users

1. **Small & Medium Enterprises (SMEs)** - Simplified compliance for the 0% CIT bracket
2. **Large Corporations** - Complex multi-entity management with Development Levy tracking
3. **Tax Consultants/Auditors** - Read-only audit views and export capabilities
4. **Accountants** - Day-to-day financial management and reconciliation
5. **Government Agencies** - Potential integration partners for compliance verification

---

## Technical Stack

```
Backend:        Python 3.11+ with FastAPI 0.110+
Database:       PostgreSQL 15+
ORM:            SQLAlchemy 2.0 + Alembic (Migrations)
Frontend:       Jinja2 Templates + HTMX (Server-side rendering)
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

## Compliance Certifications (Planned)

- [ ] NRS E-Invoicing Certification
- [ ] NITDA Data Protection Compliance (NDPR/NDPA)
- [ ] ISO 27001 Information Security (Long-term)

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
