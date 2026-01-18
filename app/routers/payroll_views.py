"""
Payroll Views Router - HTML page routes for payroll management
"""
import uuid
from typing import Optional, Tuple

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models.user import User
from app.services.auth_service import AuthService

router = APIRouter()
templates = Jinja2Templates(directory="templates")


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


def get_entity_id_from_session(request: Request) -> Optional[uuid.UUID]:
    """Get the current entity ID from session/cookie."""
    entity_id = request.cookies.get("entity_id")
    if entity_id:
        try:
            return uuid.UUID(entity_id)
        except ValueError:
            return None
    return None


async def require_auth_for_payroll(
    request: Request, 
    db: AsyncSession,
) -> Tuple[Optional[User], Optional[uuid.UUID], Optional[RedirectResponse]]:
    """Check authentication for payroll pages."""
    user = await get_user_from_token(request, db)
    
    if not user:
        return None, None, RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    entity_id = get_entity_id_from_session(request)
    
    # If no entity selected and user has entity access, use first one
    if not entity_id and user.entity_access:
        entity_id = user.entity_access[0].entity_id
    
    if not entity_id:
        return None, None, RedirectResponse(url="/select_entity", status_code=status.HTTP_302_FOUND)
    
    return user, entity_id, None


@router.get("/payroll", response_class=HTMLResponse)
async def payroll_page(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """Main payroll management page"""
    user, entity_id, redirect = await require_auth_for_payroll(request, db)
    if redirect:
        return redirect
    
    response = templates.TemplateResponse(
        "payroll.html",
        {
            "request": request,
            "user": user,
            "entity_id": str(entity_id),
            "page_title": "Payroll Management"
        }
    )
    # Set entity_id cookie if not already set
    if entity_id:
        existing_entity = request.cookies.get("entity_id")
        if not existing_entity or existing_entity != str(entity_id):
            response.set_cookie(
                key="entity_id",
                value=str(entity_id),
                max_age=86400 * 30,
                httponly=False,
                samesite="lax"
            )
    return response


@router.get("/payroll/employees/{employee_id}/payslips", response_class=HTMLResponse)
async def employee_payslips_page(
    request: Request,
    employee_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """View payslips for a specific employee"""
    user, entity_id, redirect = await require_auth_for_payroll(request, db)
    if redirect:
        return redirect
    
    return templates.TemplateResponse(
        "payroll_employee_payslips.html",
        {
            "request": request,
            "user": user,
            "entity_id": str(entity_id),
            "employee_id": employee_id,
            "page_title": "Employee Payslips"
        }
    )


@router.get("/payroll/runs/{run_id}", response_class=HTMLResponse)
async def payroll_run_details_page(
    request: Request,
    run_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """View details of a specific payroll run"""
    user, entity_id, redirect = await require_auth_for_payroll(request, db)
    if redirect:
        return redirect
    
    return templates.TemplateResponse(
        "payroll_run_details.html",
        {
            "request": request,
            "user": user,
            "entity_id": str(entity_id),
            "run_id": run_id,
            "page_title": "Payroll Run Details"
        }
    )


@router.get("/payroll/reports", response_class=HTMLResponse)
async def payroll_reports_page(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """Payroll reports and analytics"""
    user, entity_id, redirect = await require_auth_for_payroll(request, db)
    if redirect:
        return redirect
    
    return templates.TemplateResponse(
        "payroll_reports.html",
        {
            "request": request,
            "user": user,
            "entity_id": str(entity_id),
            "page_title": "Payroll Reports"
        }
    )


@router.get("/payroll/calculator", response_class=HTMLResponse)
async def salary_calculator_page(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """Standalone salary calculator page - publicly accessible"""
    user = await get_user_from_token(request, db)
    
    return templates.TemplateResponse(
        "salary_calculator.html",
        {
            "request": request,
            "user": user,  # May be None for unauthenticated users
            "page_title": "Nigerian Salary Calculator (2026 Tax Reform)"
        }
    )
