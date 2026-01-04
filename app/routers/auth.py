"""
TekVwarho ProAudit - Authentication Router

API endpoints for user authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.dependencies import get_current_user, get_current_active_user
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenRefreshRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    TokenResponse,
    UserResponse,
    UserWithTokenResponse,
    CurrentUserResponse,
    OrganizationResponse,
    EntityAccessResponse,
    MessageResponse,
    EmailVerificationRequest,
    ResendVerificationRequest,
)
from app.config import settings
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.utils.security import verify_refresh_token


router = APIRouter()


@router.post(
    "/register",
    response_model=UserWithTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user with organization. Creates user, organization, and default business entity. Sends verification email.",
)
async def register(
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Register a new user with organization."""
    auth_service = AuthService(db)
    email_service = EmailService()
    
    try:
        user, organization, entity = await auth_service.register_user(
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            organization_name=request.organization_name,
            phone_number=request.phone_number,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    # Send verification email
    try:
        verification_token = auth_service.create_email_verification_token(user)
        verification_url = f"{settings.base_url}/verify-email?token={verification_token}"
        await email_service.send_verification_email(
            to_email=user.email,
            user_name=user.first_name,
            verification_url=verification_url,
        )
    except Exception:
        # Log the error but don't fail registration
        pass
    
    # Create tokens
    tokens = auth_service.create_tokens(user)
    
    return UserWithTokenResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone_number=user.phone_number,
            role=user.role.value if user.role else None,
            is_active=user.is_active,
            is_verified=user.is_verified,
            must_reset_password=getattr(user, 'must_reset_password', False),
            organization_id=user.organization_id,
            is_platform_staff=user.is_platform_staff,
            platform_role=user.platform_role.value if user.platform_role else None,
            created_at=user.created_at,
        ),
        tokens=TokenResponse(**tokens),
    )


@router.post(
    "/login",
    response_model=UserWithTokenResponse,
    summary="Login user",
    description="Authenticate user with email and password. Works for both organization users and platform staff.",
)
async def login(
    request: UserLoginRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Login with email and password."""
    auth_service = AuthService(db)
    
    user = await auth_service.authenticate_user(
        email=request.email,
        password=request.password,
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    
    # Create tokens
    tokens = auth_service.create_tokens(user)
    
    return UserWithTokenResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone_number=user.phone_number,
            role=user.role.value if user.role else None,
            is_active=user.is_active,
            is_verified=user.is_verified,
            must_reset_password=getattr(user, 'must_reset_password', False),
            organization_id=user.organization_id,
            is_platform_staff=user.is_platform_staff,
            platform_role=user.platform_role.value if user.platform_role else None,
            created_at=user.created_at,
        ),
        tokens=TokenResponse(**tokens),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get a new access token using refresh token.",
)
async def refresh_token(
    request: TokenRefreshRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Refresh access token."""
    payload = verify_refresh_token(request.refresh_token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    
    auth_service = AuthService(db)
    
    import uuid
    user_id = uuid.UUID(payload.get("sub"))
    user = await auth_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    
    # Create new tokens
    tokens = auth_service.create_tokens(user)
    
    return TokenResponse(**tokens)


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get current user",
    description="Get the current authenticated user with organization and entity access. Works for both org users and platform staff.",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """Get current authenticated user."""
    from app.utils.permissions import (
        get_platform_permissions,
        get_organization_permissions,
    )
    
    # Build entity access list (only for org users)
    entity_access_list = []
    if not current_user.is_platform_staff:
        for access in current_user.entity_access:
            entity_access_list.append(
                EntityAccessResponse(
                    entity_id=access.entity_id,
                    entity_name=access.entity.name if access.entity else "Unknown",
                    can_write=access.can_write,
                    can_delete=access.can_delete,
                )
            )
    
    # Get permissions based on user type
    permissions = []
    if current_user.is_platform_staff and current_user.platform_role:
        permissions = [p.value for p in get_platform_permissions(current_user.platform_role)]
    elif current_user.role:
        permissions = [p.value for p in get_organization_permissions(current_user.role)]
    
    # Build organization response (only for org users)
    org_response = None
    if current_user.organization:
        org_response = OrganizationResponse(
            id=current_user.organization.id,
            name=current_user.organization.name,
            slug=current_user.organization.slug,
            subscription_tier=current_user.organization.subscription_tier.value,
            organization_type=current_user.organization.organization_type.value if hasattr(current_user.organization, 'organization_type') and current_user.organization.organization_type else None,
            verification_status=current_user.organization.verification_status.value if hasattr(current_user.organization, 'verification_status') and current_user.organization.verification_status else None,
            is_verified=current_user.organization.is_verified if hasattr(current_user.organization, 'is_verified') else False,
            created_at=current_user.organization.created_at,
        )
    
    return CurrentUserResponse(
        user=UserResponse(
            id=current_user.id,
            email=current_user.email,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            phone_number=current_user.phone_number,
            role=current_user.role.value if current_user.role else None,
            is_active=current_user.is_active,
            is_verified=current_user.is_verified,
            must_reset_password=getattr(current_user, 'must_reset_password', False),
            organization_id=current_user.organization_id,
            is_platform_staff=current_user.is_platform_staff,
            platform_role=current_user.platform_role.value if current_user.platform_role else None,
            created_at=current_user.created_at,
        ),
        organization=org_response,
        entity_access=entity_access_list,
        permissions=permissions,
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password",
    description="Change the current user's password.",
)
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Change user password."""
    auth_service = AuthService(db)
    
    try:
        await auth_service.change_password(
            user=current_user,
            current_password=request.current_password,
            new_password=request.new_password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return MessageResponse(
        message="Password changed successfully",
        success=True,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout user",
    description="Logout the current user (client should discard tokens).",
)
async def logout(
    current_user: User = Depends(get_current_active_user),
):
    """
    Logout user.
    
    Note: JWT tokens are stateless, so logout is handled client-side
    by discarding the tokens. This endpoint is for consistency and
    future token blacklisting implementation.
    """
    return MessageResponse(
        message="Logged out successfully",
        success=True,
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request password reset",
    description="Send a password reset email to the user.",
)
async def forgot_password(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Request password reset email."""
    auth_service = AuthService(db)
    email_service = EmailService()
    
    user = await auth_service.get_user_by_email(request.email)
    
    # Always return success to prevent email enumeration attacks
    if user:
        reset_token = auth_service.create_password_reset_token(user)
        reset_url = f"{settings.base_url}/reset-password?token={reset_token}"
        
        try:
            await email_service.send_password_reset(
                to_email=user.email,
                user_name=user.first_name,
                reset_url=reset_url,
            )
        except Exception:
            # Log the error but don't expose to user
            pass
    
    return MessageResponse(
        message="If an account with that email exists, a password reset link has been sent.",
        success=True,
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password with token",
    description="Reset the user's password using a valid reset token.",
)
async def reset_password(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_async_session),
):
    """Reset password using reset token."""
    auth_service = AuthService(db)
    
    try:
        await auth_service.reset_password_with_token(
            token=request.token,
            new_password=request.new_password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return MessageResponse(
        message="Password reset successfully",
        success=True,
    )


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify email address",
    description="Verify user's email address using the verification token sent to their email.",
)
async def verify_email(
    request: EmailVerificationRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Verify email address using verification token."""
    auth_service = AuthService(db)
    
    try:
        await auth_service.verify_email_with_token(token=request.token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return MessageResponse(
        message="Email verified successfully. You can now access all features.",
        success=True,
    )


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Resend verification email",
    description="Resend the email verification link to the user's email address.",
)
async def resend_verification(
    request: ResendVerificationRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Resend verification email."""
    auth_service = AuthService(db)
    email_service = EmailService()
    
    user = await auth_service.resend_verification_email(request.email)
    
    # Always return success to prevent email enumeration attacks
    if user:
        verification_token = auth_service.create_email_verification_token(user)
        verification_url = f"{settings.base_url}/verify-email?token={verification_token}"
        
        try:
            await email_service.send_verification_email(
                to_email=user.email,
                user_name=user.first_name,
                verification_url=verification_url,
            )
        except Exception:
            # Log the error but don't expose to user
            pass
    
    return MessageResponse(
        message="If an unverified account with that email exists, a verification link has been sent.",
        success=True,
    )


# ===========================================
# DASHBOARD API
# ===========================================

@router.get(
    "/dashboard",
    summary="Get user dashboard",
    description="Get the full dashboard for the current user including 2026 compliance data.",
)
async def get_dashboard(
    entity_id: str = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get dashboard with 2026 compliance features.
    
    Includes:
    - TIN/CAC Vault display
    - Compliance Health indicator
    - Financial metrics
    - Recent transactions
    """
    from app.services.dashboard_service import DashboardService
    import uuid as uuid_module
    
    dashboard_service = DashboardService(db)
    
    # Parse entity_id if provided
    parsed_entity_id = None
    if entity_id:
        try:
            parsed_entity_id = uuid_module.UUID(entity_id)
        except ValueError:
            pass
    
    dashboard_data = await dashboard_service.get_dashboard(current_user, parsed_entity_id)
    
    return dashboard_data
