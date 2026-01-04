# TekVwarho ProAudit - Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.3.0] - 2026-01-03

### 🇳🇬 2026 Nigeria Tax Reform - Full Compliance Update

This release implements comprehensive 2026 Nigeria Tax Reform compliance features including Fixed Asset Register, Enhanced Dashboard with Compliance Health Indicator, and B2C Real-time Reporting.

### Added

#### Fixed Asset Register (Capital Asset Tracking)
- **New Model**: `FixedAsset` for tracking capital assets
  - Asset categories: Land, Buildings, Plant & Machinery, Motor Vehicles, Computer Equipment, Furniture & Fittings, Intangible Assets
  - Depreciation methods: Straight Line, Reducing Balance, Units of Production
  - Standard depreciation rates per Nigerian tax law (Land 0%, Buildings 10%, Motor Vehicles 25%, Computer Equipment 25%, etc.)
  - Disposal tracking with automatic capital gain/loss calculation
  - VAT recovery on capital assets via vendor IRN validation
- **New Model**: `DepreciationEntry` for period-by-period depreciation tracking
- **New Service**: `FixedAssetService` with:
  - Full CRUD operations for assets
  - `run_depreciation()` - Batch depreciation posting for fiscal periods
  - `dispose_asset()` - Asset disposal with capital gain/loss calculation (taxed at CIT rate under 2026 reform)
  - `get_depreciation_schedule()` - Fiscal year depreciation schedule
  - `get_capital_gains_report()` - Capital gains report for CIT calculation
  - Auto-update of entity's `fixed_assets_value` for Development Levy threshold
- **New Router**: `/api/v1/fixed-assets` with endpoints:
  - `POST /` - Create fixed asset
  - `GET /entity/{entity_id}` - List assets for entity
  - `GET /{asset_id}` - Get asset details
  - `PATCH /{asset_id}` - Update asset
  - `POST /depreciation/run` - Run depreciation for period
  - `GET /entity/{entity_id}/depreciation-schedule` - Get depreciation schedule
  - `POST /{asset_id}/dispose` - Dispose of asset
  - `GET /entity/{entity_id}/summary` - Get asset register summary
  - `GET /entity/{entity_id}/capital-gains` - Get capital gains report

#### TIN/CAC Vault Dashboard Display
- Prominent display of Tax Identification Number (TIN) in dashboard
- Prominent display of CAC RC/BN Number in dashboard
- Verification status indicators (verified/missing) with warnings
- Business type display with tax implication (PIT vs CIT)
- VAT registration status display

#### Compliance Health Indicator
- Overall compliance score (0-100%)
- Status levels: Excellent, Good, Warning, Critical
- Automated compliance checks:
  - TIN Registration status
  - CAC Registration status
  - Small Company Status (0% CIT eligibility: turnover ≤ ₦50M, assets ≤ ₦250M)
  - Development Levy Exemption status (turnover ≤ ₦100M, assets ≤ ₦250M)
  - VAT Registration threshold check (₦25M threshold)
- Color-coded progress bar and status icons

#### B2C Real-time Reporting (24-Hour Reporting)
- New fields in BusinessEntity model:
  - `b2c_realtime_reporting_enabled`: Toggle for B2C real-time reporting
  - `b2c_reporting_threshold`: Configurable threshold (default ₦50,000)
- New NRS service methods:
  - `submit_b2c_transaction_report()` - Submit B2C transactions over threshold to NRS
  - `get_b2c_reporting_status()` - Check B2C reporting compliance status

### Enhanced

#### Dashboard Service
- New helper methods:
  - `_get_tin_cac_vault()` - TIN/CAC vault data for dashboard
  - `_get_compliance_health()` - Compliance health indicator data
- Updated `get_organization_dashboard()` to include:
  - TIN/CAC Vault section
  - Compliance Health indicator
  - Small Company Status
  - Development Levy status

#### Dashboard UI Template
- Added TIN/CAC Vault section with verification status indicators
- Added Compliance Health indicator with progress bar
- Added compliance checks display with color-coded status icons
- Business type and tax implication display

#### Auth Router
- Added `GET /api/v1/auth/dashboard` endpoint for full dashboard data with compliance information

### Database Migrations

- Added migration `20260103_1600_add_fixed_assets.py`:
  - Creates `fixed_assets` table with depreciation and disposal fields
  - Creates `depreciation_entries` table for period-by-period tracking
  - Creates enums: `assetcategory`, `assetstatus`, `depreciationmethod`, `disposaltype`
  - Creates indexes for efficient querying

### Tax Calculation System (Verified)

All 28 tax calculator tests passing:
- **VAT**: 7.5% standard rate, zero-rated, and exempt categories
- **PAYE**: 2026 progressive bands (0%/15%/20%/25%/30%)
- **WHT**: Professional services, consultancy, construction, rent, dividends, royalties, contract supply
- **CIT**: Small (0%), Medium (20%), Large (30%) based on turnover thresholds

---

## [1.2.0] - 2026-01-03

### 🇳🇬 NTAA 2025 Compliance Update

This release implements critical Nigeria Tax Administration Act (NTAA) 2025 compliance features to ensure the platform is "Nigeria 2026-Ready."

### Added

#### 72-Hour Legal Lock (Invoice State Lock)
- **NRS Submission Lock**: Once an invoice is submitted to NRS, it is locked and cannot be edited or deleted
- **Owner-Only Cancellation**: Only the `Owner` role can cancel an NRS submission during the 72-hour window
- **Credit Note Requirement**: Any post-submission modifications require a formal NRS-tracked Credit Note
- New fields in Invoice model:
  - `is_nrs_locked`: Boolean flag for lock status
  - `nrs_lock_expires_at`: 72-hour window expiry timestamp
  - `nrs_cancelled_by_id`: UUID of Owner who cancelled (if any)
  - `nrs_cancellation_reason`: Reason for cancellation
  - `nrs_cryptographic_stamp`: NRS cryptographic signature for audit verification
- New permission: `CANCEL_NRS_SUBMISSION` (Owner only)

#### Maker-Checker Segregation of Duties (SoD) for WREN Expenses
- **Segregation of Duties**: Accountant cannot verify WREN status on expenses they created
- **Maker**: Person who creates/uploads the expense
- **Checker**: Person who verifies WREN status (must be different from Maker)
- New fields in Transaction model:
  - `created_by_id`: UUID of user who created the transaction (Maker)
  - `wren_verified_by_id`: UUID of user who verified WREN status (Checker)
  - `wren_verified_at`: Timestamp of WREN verification
  - `original_category_id`: Original category for audit trail
  - `category_change_history`: JSONB history of category changes (before/after snapshots)
- New permission: `VERIFY_WREN` for WREN verification

#### External Accountant Role
- New role `EXTERNAL_ACCOUNTANT` for outsourced accounting firms (like QuickBooks "Invite Accountant")
- Permissions include:
  - `MANAGE_TAX_FILINGS` - File returns for client
  - `VIEW_REPORTS` - View reports
  - `EXPORT_DATA` - Export data
  - `VERIFY_WREN` - Verify WREN status
  - `VIEW_ALL_TRANSACTIONS` - View transactions
  - `VIEW_INVOICES` - View invoices
  - `VIEW_CUSTOMERS` / `VIEW_VENDORS` - View contacts
- Does NOT have:
  - `MANAGE_PAYROLL` - Cannot access payroll
  - `MANAGE_INVENTORY` - Cannot manage inventory
  - `MANAGE_INVOICES` - Cannot edit invoices
  - Any fund movement permissions

#### Enhanced Audit Log (NTAA 2025 Compliant)
- **IP & Device Fingerprint**: Mandatory for proving who submitted tax returns
- **Before/After Snapshots**: Stores original values when categories change (e.g., Personal → Business)
- **NRS Server Response Storage**: Stores IRN and Cryptographic Stamp directly in audit log
- **Impersonation Tracking**: Logs when CSR is impersonating a user
- New fields in AuditLog model:
  - `organization_id`: For multi-tenant queries
  - `impersonated_by_id`: CSR user ID if impersonating
  - `device_fingerprint`: Browser/device fingerprint
  - `session_id`: Session ID for tracking related actions
  - `geo_location`: Approximate location from IP
  - `nrs_irn`: NRS Invoice Reference Number
  - `nrs_response`: Full NRS server response
  - `description`: Human-readable description
- New audit actions:
  - `NRS_CREDIT_NOTE`
  - `WREN_VERIFY`
  - `WREN_REJECT`
  - `CATEGORY_CHANGE`
  - `IMPERSONATION_START`
  - `IMPERSONATION_END`
  - `IMPERSONATION_GRANT`
  - `IMPERSONATION_REVOKE`

#### Time-Limited CSR Impersonation (NDPA Compliance)
- **24-Hour Maximum**: Impersonation permission expires after 24 hours (per Nigeria Data Protection Act)
- **User-Granted**: Users explicitly grant access for a specific duration
- **Audit Trail**: All impersonation actions are logged
- New fields in User model:
  - `impersonation_expires_at`: When impersonation permission expires
  - `impersonation_granted_at`: When impersonation was granted

#### New NTAA Compliance Service
- `app/services/ntaa_compliance_service.py` - Centralized service for:
  - 72-hour legal lock management
  - Maker-Checker WREN verification
  - Time-limited impersonation
  - Enhanced audit logging

### Changed

#### User Model
- Added datetime imports for impersonation expiry
- Updated docstring with NTAA 2025 compliance features
- Added `EXTERNAL_ACCOUNTANT` to `UserRole` enum

#### Invoice Model
- Changed `nrs_response` from Text to JSONB for structured storage
- Added comprehensive NRS lock fields

#### Transaction Model
- Added datetime imports
- Added JSONB import for category change history
- Added Maker-Checker fields

#### Permissions System
- Updated permission matrix to include External Accountant
- Added `VERIFY_WREN` permission
- Added `CANCEL_NRS_SUBMISSION` permission (Owner only)
- Updated role hierarchy to include External Accountant at level 4

### Security

#### Credential Security
- **REMOVED** hardcoded Super Admin credentials from documentation
- Super Admin credentials are now **exclusively** stored in environment variables
- Updated documentation to reference `.env.example` for configuration

### Documentation

- Updated RBAC_DOCUMENTATION.md with:
  - Removed hardcoded credentials (security fix)
  - Added External Accountant role documentation
  - Updated permission matrix with NTAA 2025 permissions
  - Added NTAA 2025 compliance section

---

## [1.1.0] - 2026-01-02

### Added

#### Role-Based Access Control (RBAC)
- Two-tier RBAC system implemented:
  1. **Platform Staff** (Internal TekVwarho employees)
     - Super Admin, Admin, IT/Developer, Customer Service, Marketing
  2. **Organization Users** (External customers)
     - Owner, Admin, Accountant, Auditor, Payroll Manager, Inventory Manager, Viewer

#### Platform Staff Management
- Staff onboarding with hierarchy enforcement
- Staff deactivation/reactivation
- Role updates (Super Admin only)
- Organization verification workflow

#### Organization Verification
- Verification status tracking (Pending, Submitted, Under Review, Verified, Rejected)
- Document upload (CAC, TIN, additional documents)
- Admin approval workflow
- Referral code system

#### Dashboard System
- Role-specific dashboards for all user types
- Platform staff dashboards with operational metrics
- Organization user dashboards with financial metrics

---

## [1.0.0] - 2025-12-15

### Added

- Initial release of TekVwarho ProAudit
- Core accounting features (transactions, invoices, inventory)
- NRS e-invoicing integration
- VAT, PAYE, CIT, WHT calculators (2026 Tax Reform compliant)
- Multi-entity support
- Customer and vendor management
- Receipt scanning and OCR
- Financial reporting

---

## Migration Notes

### Upgrading to 1.2.0

1. **Database Migration Required**
   ```bash
   # Run the NTAA 2025 migration
   alembic upgrade head
   ```

2. **Environment Variables**
   Ensure your `.env` file includes:
   ```env
   SUPER_ADMIN_EMAIL=your-admin@domain.com
   SUPER_ADMIN_PASSWORD=your-secure-password
   ```

3. **Breaking Changes**
   - External Accountant role added - update any role-based logic
   - Invoice editing now checks NRS lock status
   - WREN verification requires Maker-Checker validation

4. **New Dependencies**
   No new external dependencies required.

---

## Compliance Reference

### NTAA 2025 Sections Addressed

| Section | Requirement | Implementation |
|---------|-------------|----------------|
| CTC (Continuous Transaction Controls) | Real-time invoice validation | 72-Hour Legal Lock |
| Strict Liability | Director accountability | Enhanced Audit Trail |
| WREN | Expense deductibility | Maker-Checker SoD |
| E-Invoicing | NRS integration | IRN + Crypto Stamp storage |

### NDPA Compliance

| Requirement | Implementation |
|-------------|----------------|
| Time-limited data access | 24-hour impersonation tokens |
| Audit trail | Impersonation logging |
| User consent | Explicit grant required |
