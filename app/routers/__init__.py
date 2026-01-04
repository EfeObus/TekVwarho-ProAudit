"""
TekVwarho ProAudit - Routers Package

FastAPI route handlers.

Routers:
- auth: Authentication (login, register, password reset)
- staff: Platform staff management (RBAC for internal users)
- organization_users: Organization user management
- entities: Business entity management
- categories: Transaction categories
- vendors: Vendor management
- customers: Customer management  
- transactions: Transaction management
- invoices: Invoice management
- inventory: Inventory management
- receipts: Receipt/file management
- reports: Reports and dashboard
- audit: Audit trail
- tax: Tax management
- tax_2026: 2026 Tax Reform APIs
- fixed_assets: Fixed Asset Register (2026)
- views: HTML page views
"""

from app.routers import (
    auth,
    staff,
    organization_users,
    entities,
    categories,
    vendors,
    customers,
    transactions,
    invoices,
    inventory,
    receipts,
    reports,
    audit,
    tax,
    tax_2026,
    fixed_assets,
    views,
)

__all__ = [
    "auth",
    "staff",
    "organization_users",
    "entities",
    "categories",
    "vendors",
    "customers",
    "transactions",
    "invoices",
    "inventory",
    "receipts",
    "reports",
    "audit",
    "tax",
    "tax_2026",
    "fixed_assets",
    "views",
]
