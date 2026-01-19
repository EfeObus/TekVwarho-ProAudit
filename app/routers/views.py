"""
TekVwarho ProAudit - Views Router

Server-side rendered pages using Jinja2 templates.
Authentication is persistent across all pages via HTTP-only cookies.
"""

import uuid
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, get_async_session
from app.dependencies import get_optional_user
from app.models.user import User
from app.services.dashboard_service import DashboardService
from app.services.auth_service import AuthService

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_entity_id_from_session(request: Request) -> Optional[uuid.UUID]:
    """Get the current entity ID from session/cookie."""
    entity_id = request.cookies.get("entity_id")
    if entity_id:
        try:
            return uuid.UUID(entity_id)
        except ValueError:
            return None
    return None


def set_entity_cookie_if_needed(
    response, 
    request: Request, 
    entity_id: Optional[uuid.UUID]
) -> None:
    """
    Set the entity_id cookie if needed (e.g., for platform staff auto-assignment).
    
    This is called after require_auth to persist the auto-assigned entity.
    """
    if entity_id:
        current_cookie = request.cookies.get("entity_id")
        if current_cookie != str(entity_id):
            response.set_cookie(
                key="entity_id",
                value=str(entity_id),
                httponly=True,
                max_age=60 * 60 * 24 * 30,  # 30 days
                samesite="lax"
            )


async def get_user_from_token(request: Request, db: AsyncSession) -> Optional[User]:
    """Get the authenticated user from the access token cookie."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    # Remove 'Bearer ' prefix if present
    if token.startswith("Bearer "):
        token = token[7:]
    
    auth_service = AuthService(db)
    try:
        user = await auth_service.get_current_user_from_token(token)
        return user
    except Exception:
        return None


async def require_auth(
    request: Request, 
    db: AsyncSession,
    require_entity: bool = True
) -> Tuple[Optional[User], Optional[uuid.UUID], Optional[RedirectResponse]]:
    """
    Check authentication for protected pages.
    
    For platform staff:
    - They don't need to manually select an entity
    - If they access entity-requiring pages, they get the test entity automatically
    
    Returns:
        Tuple of (user, entity_id, redirect_response)
        If redirect_response is not None, the caller should return it.
    """
    from app.services.staff_management_service import StaffManagementService
    
    user = await get_user_from_token(request, db)
    
    if not user:
        return None, None, RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    entity_id = get_entity_id_from_session(request)
    
    # Platform staff handling
    if user.is_platform_staff:
        if require_entity and not entity_id:
            # Auto-assign the test entity for platform staff
            try:
                service = StaffManagementService(db)
                demo_entity = await service.ensure_staff_has_test_entity_access(user)
                # Return the demo entity ID - caller should set cookie
                return user, demo_entity.id, None
            except Exception as e:
                # If test entity creation fails, continue without entity
                print(f"Could not assign test entity to staff: {e}")
                return user, None, None
        return user, entity_id, None
    
    # Organization users need entity (unless require_entity is False)
    if require_entity and not entity_id:
        return user, None, RedirectResponse(url="/select-entity", status_code=status.HTTP_302_FOUND)
    
    return user, entity_id, None


def get_auth_context(user: Optional[User], entity_id: Optional[uuid.UUID]) -> dict:
    """
    Get common authentication context for templates.
    
    This ensures user info is available across all pages.
    """
    return {
        "user": user,
        "is_authenticated": user is not None,
        "is_platform_staff": user.is_platform_staff if user else False,
        "user_role": user.effective_role if user else None,
        "entity_id": str(entity_id) if entity_id else None,
    }


# ===========================================
# PUBLIC PAGES
# ===========================================

@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_async_session)):
    """Home/landing page. Redirect to dashboard if logged in."""
    user = await get_user_from_token(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@router.get("/logout")
async def logout(request: Request):
    """Logout - clear session and redirect to login."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("entity_id")
    response.delete_cookie("access_token")
    return response


# ===========================================
# PROTECTED PAGES (require authentication)
# ===========================================

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Unified dashboard page.
    Routes to appropriate dashboard based on user type:
    - Platform Staff: Staff dashboard with platform metrics
    - Organization Users: Business dashboard with financial metrics
    """
    # Use consistent authentication
    user, entity_id, redirect = await require_auth(request, db, require_entity=False)
    if redirect:
        return redirect
    
    # Get dashboard data
    dashboard_service = DashboardService(db)
    
    try:
        if user.is_platform_staff:
            # Platform staff - use staff dashboard
            dashboard_data = await dashboard_service.get_dashboard(user)
            return templates.TemplateResponse("staff_dashboard.html", {
                "request": request,
                "dashboard": dashboard_data,
                **get_auth_context(user, None),
            })
        else:
            # Organization user - use business dashboard
            # If no entity selected, redirect to entity selection
            if not entity_id:
                # Check if user has any entities
                if user.entity_access and len(user.entity_access) > 0:
                    return RedirectResponse(url="/select-entity", status_code=status.HTTP_302_FOUND)
            
            dashboard_data = await dashboard_service.get_dashboard(user, entity_id)
            
            # Use enhanced dashboard template
            return templates.TemplateResponse("dashboard_v2.html", {
                "request": request,
                "dashboard": dashboard_data,
                "entity_id": str(entity_id) if entity_id else None,
                **get_auth_context(user, entity_id),
            })
    except PermissionError as e:
        return RedirectResponse(url="/login?error=permission", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        # Fallback to basic dashboard
        if not entity_id and not user.is_platform_staff:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
        return templates.TemplateResponse("dashboard_v2.html", {
            "request": request,
            "error": str(e),
            "entity_id": str(entity_id) if entity_id else None,
            **get_auth_context(user, entity_id),
        })


@router.get("/transactions", response_class=HTMLResponse)
async def transactions_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Transactions list page."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("transactions.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/transactions/new", response_class=HTMLResponse)
async def new_transaction_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """New transaction page - redirects to transactions with modal open."""
    return RedirectResponse(url="/transactions#new", status_code=status.HTTP_302_FOUND)


@router.get("/invoices", response_class=HTMLResponse)
async def invoices_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Invoices list page."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("invoices.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/invoices/new", response_class=HTMLResponse)
async def new_invoice_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """New invoice page - redirects to invoices with modal open."""
    return RedirectResponse(url="/invoices#new", status_code=status.HTTP_302_FOUND)


@router.get("/sales", response_class=HTMLResponse)
async def sales_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sales recording page - POS-style sales management."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("sales.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/receipts/upload", response_class=HTMLResponse)
async def receipt_upload_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receipt upload/scan page."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("receipts.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reports page."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("reports.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/vendors", response_class=HTMLResponse)
async def vendors_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Vendors list page."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("vendors.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/customers", response_class=HTMLResponse)
async def customers_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Customers list page."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("customers.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Inventory management page."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("inventory.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/accounting", response_class=HTMLResponse)
async def accounting_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Chart of Accounts & General Ledger management page."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("accounting.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/fixed-assets", response_class=HTMLResponse)
async def fixed_assets_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Fixed Asset Register management page."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("fixed_assets.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/bank-reconciliation", response_class=HTMLResponse)
async def bank_reconciliation_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Bank Reconciliation page - Match transactions with bank statements."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("bank_reconciliation.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/expense-claims", response_class=HTMLResponse)
async def expense_claims_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Expense Claims page - Submit and manage expense reimbursements."""
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("expense_claims.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Settings page."""
    user, entity_id, redirect = await require_auth(request, db)
    if redirect:
        return redirect
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })


# ===========================================
# ENTITY SELECTION
# ===========================================

@router.get("/select-entity", response_class=HTMLResponse)
async def select_entity_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Entity selection page."""
    # Check authentication but don't require entity
    user, _, redirect = await require_auth(request, db, require_entity=False)
    if redirect:
        return redirect
    
    return templates.TemplateResponse("select_entity.html", {
        "request": request,
        **get_auth_context(user, None),
    })


@router.post("/select-entity/{entity_id}")
async def set_entity(
    entity_id: uuid.UUID,
    request: Request,
):
    """Set the current entity in session."""
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="entity_id",
        value=str(entity_id),
        httponly=True,
        max_age=60 * 60 * 24 * 30,  # 30 days
        samesite="lax",
    )
    return response


# ===========================================
# LEGAL & POLICY PAGES
# ===========================================

@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    """Terms and Conditions page."""
    return templates.TemplateResponse("legal/terms.html", {"request": request})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """Privacy Policy page."""
    return templates.TemplateResponse("legal/privacy.html", {"request": request})


@router.get("/cookies", response_class=HTMLResponse)
async def cookies_page(request: Request):
    """Cookie Policy page."""
    return templates.TemplateResponse("legal/cookies.html", {"request": request})


@router.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    """FAQ page."""
    return templates.TemplateResponse("legal/faq.html", {"request": request})


@router.get("/security", response_class=HTMLResponse)
async def security_page(request: Request):
    """Security Policy page."""
    return templates.TemplateResponse("legal/security.html", {"request": request})


# ===========================================
# 2026 TAX REFORM
# ===========================================

@router.get("/tax-2026", response_class=HTMLResponse)
async def tax_2026_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """2026 Tax Reform compliance page."""
    # Require entity selection - redirect to select-entity if not selected
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("tax_2026.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


# ===========================================
# PASSWORD RESET
# ===========================================

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Forgot password page."""
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = None):
    """Reset password page."""
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})


# ===========================================
# EMAIL VERIFICATION
# ===========================================

@router.get("/verify-email", response_class=HTMLResponse)
async def verify_email_page(request: Request, token: str = None):
    """Email verification page."""
    return templates.TemplateResponse("verify_email.html", {"request": request, "token": token})


# ===========================================
# WORLD-CLASS AUDIT PAGES
# ===========================================

@router.get("/audit", response_class=HTMLResponse)
async def audit_unified_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Unified Audit Center - Comprehensive audit tools.
    
    Provides access to:
    - Audit Dashboard with integrity verification
    - Audit Logs with filtering and export
    - Forensic Analysis (Benford's Law, Z-Score Anomalies)
    - Audit Runs management
    - Findings and Evidence tracking
    - Tax Explainability (PAYE, VAT)
    - Audit Vault with NTAA 2025 compliance
    - Payroll Decisions audit trail
    """
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("audit_unified.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/audit-dashboard", response_class=HTMLResponse)
async def audit_dashboard_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Legacy audit dashboard - redirects to unified audit."""
    return RedirectResponse(url="/audit", status_code=status.HTTP_302_FOUND)


@router.get("/audit-old", response_class=HTMLResponse)
async def audit_old_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Legacy Audit Dashboard for backwards compatibility.
    """
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("audit_dashboard.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response


@router.get("/audit-logs", response_class=HTMLResponse)
async def audit_logs_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Redirect to unified audit page - Logs tab."""
    return RedirectResponse(url="/audit?tab=logs", status_code=302)


@router.get("/forensic-audit", response_class=HTMLResponse)
async def forensic_audit_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Redirect to unified audit page - Forensic tab."""
    return RedirectResponse(url="/audit?tab=forensic", status_code=302)


@router.get("/advanced-audit", response_class=HTMLResponse)
async def advanced_audit_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Redirect to unified audit page - Advanced tab."""
    return RedirectResponse(url="/audit?tab=advanced", status_code=302)


@router.get("/worm-storage", response_class=HTMLResponse)
async def worm_storage_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Redirect to unified audit page - WORM Storage tab."""
    return RedirectResponse(url="/audit?tab=worm", status_code=302)


# ===========================================
# MACHINE LEARNING & AI PAGES
# ===========================================

@router.get("/business-insights", response_class=HTMLResponse)
async def business_insights_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Business Insights Dashboard.
    
    AI-powered analytics providing:
    - Cash Flow Forecasting (ARIMA, Holt-Winters, LSTM)
    - Growth Prediction (Linear, Polynomial, Neural Network)
    - NLP Analysis (Sentiment, Entities, Keywords, Classification)
    - OCR Document Processing (Azure, Tesseract, Internal)
    - Custom Model Training (Neural Networks, LSTM)
    """
    user, entity_id, redirect = await require_auth(request, db, require_entity=True)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse("business_insights.html", {
        "request": request,
        **get_auth_context(user, entity_id),
    })
    set_entity_cookie_if_needed(response, request, entity_id)
    return response
