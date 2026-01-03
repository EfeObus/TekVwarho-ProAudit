"""
TekVwarho ProAudit - Views Router

Server-side rendered pages using Jinja2 templates.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_async_session
from app.dependencies import get_optional_user
from app.models.user import User

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


# ===========================================
# PUBLIC PAGES
# ===========================================

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home/landing page."""
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
    return response


# ===========================================
# PROTECTED PAGES (require authentication)
# ===========================================

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Dashboard page."""
    entity_id = get_entity_id_from_session(request)
    if not entity_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "entity_id": str(entity_id),
    })


@router.get("/transactions", response_class=HTMLResponse)
async def transactions_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Transactions list page."""
    entity_id = get_entity_id_from_session(request)
    if not entity_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("transactions.html", {
        "request": request,
        "entity_id": str(entity_id),
    })


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
    entity_id = get_entity_id_from_session(request)
    if not entity_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("invoices.html", {
        "request": request,
        "entity_id": str(entity_id),
    })


@router.get("/invoices/new", response_class=HTMLResponse)
async def new_invoice_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """New invoice page - redirects to invoices with modal open."""
    return RedirectResponse(url="/invoices#new", status_code=status.HTTP_302_FOUND)


@router.get("/receipts/upload", response_class=HTMLResponse)
async def receipt_upload_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receipt upload/scan page."""
    entity_id = get_entity_id_from_session(request)
    if not entity_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("receipts.html", {
        "request": request,
        "entity_id": str(entity_id),
    })


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reports page."""
    entity_id = get_entity_id_from_session(request)
    if not entity_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("reports.html", {
        "request": request,
        "entity_id": str(entity_id),
    })


@router.get("/vendors", response_class=HTMLResponse)
async def vendors_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Vendors list page."""
    entity_id = get_entity_id_from_session(request)
    if not entity_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("vendors.html", {
        "request": request,
        "entity_id": str(entity_id),
    })


@router.get("/customers", response_class=HTMLResponse)
async def customers_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Customers list page."""
    entity_id = get_entity_id_from_session(request)
    if not entity_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("customers.html", {
        "request": request,
        "entity_id": str(entity_id),
    })


@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Inventory management page."""
    entity_id = get_entity_id_from_session(request)
    if not entity_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "entity_id": str(entity_id),
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Settings page."""
    entity_id = get_entity_id_from_session(request)
    if not entity_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "entity_id": str(entity_id),
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
    return templates.TemplateResponse("select_entity.html", {
        "request": request,
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
    entity_id = get_entity_id_from_session(request)
    if not entity_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("tax_2026.html", {
        "request": request,
        "entity_id": str(entity_id),
    })


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
