"""
TekVwarho ProAudit - Billing Router

API endpoints for billing, subscription management, and payments.
Uses Paystack as the primary payment provider for Nigerian Naira.
"""

import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, EmailStr

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.sku import SKUTier, IntelligenceAddon, PaymentTransaction
from app.services.billing_service import (
    BillingService,
    BillingCycle,
    PaymentStatus,
)
from app.services.invoice_pdf_service import InvoicePDFService
from app.services.dunning_service import DunningService, DunningLevel
from app.services.billing_email_service import BillingEmailService
from app.config.sku_config import TIER_PRICING, INTELLIGENCE_PRICING
from sqlalchemy import select, desc, func


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreatePaymentIntentRequest(BaseModel):
    """Request to create a payment intent."""
    tier: SKUTier = Field(..., description="Target SKU tier")
    billing_cycle: str = Field("monthly", description="monthly or annual")
    intelligence_addon: Optional[IntelligenceAddon] = Field(None, description="Intelligence add-on")
    additional_users: int = Field(0, ge=0, description="Additional users beyond base")
    callback_url: Optional[str] = Field(None, description="Custom callback URL")


class PaymentIntentResponse(BaseModel):
    """Response for payment intent creation."""
    id: str
    reference: str
    amount_naira: int
    amount_formatted: str
    currency: str
    status: str
    authorization_url: Optional[str]
    tier: str
    billing_cycle: str
    expires_at: str


class PricingTierResponse(BaseModel):
    """Pricing information for a tier."""
    tier: str
    name: str
    tagline: str
    monthly_amount: int
    monthly_formatted: str
    annual_amount: int
    annual_formatted: str
    annual_savings: int
    annual_savings_formatted: str
    base_users: int
    per_user_amount: int
    per_user_formatted: str


class SubscriptionResponse(BaseModel):
    """Current subscription information."""
    tier: str
    tier_display: str
    intelligence_addon: Optional[str]
    billing_cycle: str
    status: str
    is_trial: bool
    trial_days_remaining: Optional[int]
    current_period_start: Optional[str]
    current_period_end: Optional[str]
    next_billing_date: Optional[str]
    amount_naira: int
    amount_formatted: str


class WebhookPayload(BaseModel):
    """Paystack webhook payload."""
    event: str
    data: dict


class PaymentTransactionResponse(BaseModel):
    """Response for a payment transaction."""
    id: str
    reference: str
    status: str
    amount_naira: int
    amount_formatted: str
    currency: str
    tier: Optional[str]
    billing_cycle: Optional[str]
    payment_method: Optional[str]
    card_last4: Optional[str]
    card_brand: Optional[str]
    gateway_response: Optional[str]
    created_at: str
    paid_at: Optional[str]
    
    class Config:
        from_attributes = True


class PaymentHistoryResponse(BaseModel):
    """Response for payment history."""
    payments: List[PaymentTransactionResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class SubscriptionAccessResponse(BaseModel):
    """Response for subscription access check."""
    has_access: bool
    status: str
    tier: Optional[str]
    message: str
    days_remaining: int
    grace_period_remaining: int
    is_trial: bool


class DunningStatusResponse(BaseModel):
    """Response for dunning status."""
    organization_id: str
    level: str
    amount_naira: int
    amount_formatted: str
    first_failure_at: Optional[str]
    last_retry_at: Optional[str]
    retry_count: int
    next_retry_at: Optional[str]
    days_until_suspension: int
    notes: Optional[str]
    is_in_dunning: bool


# =============================================================================
# PRICING ENDPOINTS
# =============================================================================

@router.get(
    "/pricing",
    response_model=List[PricingTierResponse],
    summary="Get all tier pricing",
)
async def get_pricing():
    """
    Get pricing information for all tiers.
    
    Returns pricing in Nigerian Naira (₦) with monthly and annual options.
    """
    pricing_list = []
    
    for tier in [SKUTier.CORE, SKUTier.PROFESSIONAL, SKUTier.ENTERPRISE]:
        pricing = TIER_PRICING.get(tier)
        if not pricing:
            continue
        
        monthly = int(pricing.monthly_min)
        annual = int(pricing.annual_min)
        savings = (monthly * 12) - annual
        
        pricing_list.append(PricingTierResponse(
            tier=tier.value,
            name=pricing.name,
            tagline=pricing.tagline,
            monthly_amount=monthly,
            monthly_formatted=f"₦{monthly:,}",
            annual_amount=annual,
            annual_formatted=f"₦{annual:,}",
            annual_savings=savings,
            annual_savings_formatted=f"₦{savings:,}",
            base_users=pricing.base_users_included,
            per_user_amount=int(pricing.price_per_additional_user),
            per_user_formatted=f"₦{int(pricing.price_per_additional_user):,}",
        ))
    
    return pricing_list


@router.get(
    "/pricing/{tier}",
    response_model=PricingTierResponse,
    summary="Get pricing for specific tier",
)
async def get_tier_pricing(
    tier: SKUTier = Path(..., description="SKU tier"),
):
    """Get pricing information for a specific tier."""
    pricing = TIER_PRICING.get(tier)
    if not pricing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pricing not found for tier: {tier.value}",
        )
    
    monthly = int(pricing.monthly_min)
    annual = int(pricing.annual_min)
    savings = (monthly * 12) - annual
    
    return PricingTierResponse(
        tier=tier.value,
        name=pricing.name,
        tagline=pricing.tagline,
        monthly_amount=monthly,
        monthly_formatted=f"₦{monthly:,}",
        annual_amount=annual,
        annual_formatted=f"₦{annual:,}",
        annual_savings=savings,
        annual_savings_formatted=f"₦{savings:,}",
        base_users=pricing.base_users_included,
        per_user_amount=int(pricing.price_per_additional_user),
        per_user_formatted=f"₦{int(pricing.price_per_additional_user):,}",
    )


@router.get(
    "/calculate-price",
    summary="Calculate subscription price",
)
async def calculate_price(
    tier: SKUTier = Query(..., description="Target tier"),
    billing_cycle: str = Query("monthly", description="monthly or annual"),
    intelligence_addon: Optional[IntelligenceAddon] = Query(None),
    additional_users: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate total subscription price based on options.
    
    Useful for showing price before checkout.
    """
    service = BillingService(db)
    
    cycle = BillingCycle.ANNUAL if billing_cycle == "annual" else BillingCycle.MONTHLY
    
    amount = service.calculate_subscription_price(
        tier=tier,
        billing_cycle=cycle,
        intelligence_addon=intelligence_addon,
        additional_users=additional_users,
    )
    
    return {
        "tier": tier.value,
        "billing_cycle": billing_cycle,
        "intelligence_addon": intelligence_addon.value if intelligence_addon else None,
        "additional_users": additional_users,
        "amount_naira": amount,
        "amount_formatted": f"₦{amount:,}",
        "currency": "NGN",
    }


# =============================================================================
# SUBSCRIPTION ENDPOINTS
# =============================================================================

@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Get current subscription",
)
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current user's organization subscription.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization",
        )
    
    service = BillingService(db)
    info = await service.get_subscription_info(current_user.organization_id)
    
    if not info:
        # Return default Core tier info
        return SubscriptionResponse(
            tier="core",
            tier_display="Core",
            intelligence_addon=None,
            billing_cycle="monthly",
            status="trial",
            is_trial=True,
            trial_days_remaining=14,
            current_period_start=None,
            current_period_end=None,
            next_billing_date=None,
            amount_naira=50000,
            amount_formatted="₦50,000",
        )
    
    # Calculate trial days remaining
    trial_days = None
    if info.trial_ends_at:
        delta = info.trial_ends_at - datetime.utcnow()
        trial_days = max(0, delta.days)
    
    tier_display = {
        SKUTier.CORE: "Core",
        SKUTier.PROFESSIONAL: "Professional",
        SKUTier.ENTERPRISE: "Enterprise",
    }.get(info.tier, "Core")
    
    return SubscriptionResponse(
        tier=info.tier.value,
        tier_display=tier_display,
        intelligence_addon=info.intelligence_addon.value if info.intelligence_addon else None,
        billing_cycle=info.billing_cycle.value,
        status=info.status,
        is_trial=info.is_trial,
        trial_days_remaining=trial_days,
        current_period_start=info.current_period_start.isoformat() if info.current_period_start else None,
        current_period_end=info.current_period_end.isoformat() if info.current_period_end else None,
        next_billing_date=info.next_billing_date.isoformat() if info.next_billing_date else None,
        amount_naira=info.amount_naira,
        amount_formatted=f"₦{info.amount_naira:,}",
    )


# =============================================================================
# PAYMENT HISTORY ENDPOINT
# =============================================================================

@router.get(
    "/payments",
    response_model=PaymentHistoryResponse,
    summary="Get payment history",
)
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
):
    """
    Get payment transaction history for the current user's organization.
    
    Returns a paginated list of payment transactions with details
    including amounts, status, payment method, and timestamps.
    
    Filter options:
    - status_filter: pending, processing, success, failed, cancelled, refunded
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization",
        )
    
    # Build query
    query = select(PaymentTransaction).where(
        PaymentTransaction.organization_id == current_user.organization_id
    )
    
    # Apply status filter if provided
    if status_filter:
        query = query.where(PaymentTransaction.status == status_filter)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply ordering and pagination
    query = query.order_by(desc(PaymentTransaction.created_at))
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    # Format response
    payments = []
    for tx in transactions:
        payments.append(PaymentTransactionResponse(
            id=str(tx.id),
            reference=tx.reference,
            status=tx.status,
            amount_naira=tx.amount_kobo // 100,
            amount_formatted=f"₦{tx.amount_kobo // 100:,}",
            currency=tx.currency or "NGN",
            tier=tx.tier,
            billing_cycle=tx.billing_cycle,
            payment_method=tx.payment_method or tx.channel,
            card_last4=tx.card_last4,
            card_brand=tx.card_brand,
            gateway_response=tx.gateway_response,
            created_at=tx.created_at.isoformat() if tx.created_at else None,
            paid_at=tx.paid_at.isoformat() if tx.paid_at else None,
        ))
    
    return PaymentHistoryResponse(
        payments=payments,
        total=total,
        page=page,
        per_page=per_page,
        has_more=(offset + len(transactions)) < total,
    )


@router.get(
    "/payments/{payment_id}",
    response_model=PaymentTransactionResponse,
    summary="Get payment details",
)
async def get_payment_detail(
    payment_id: UUID = Path(..., description="Payment transaction ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details for a specific payment transaction.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization",
        )
    
    # Get payment transaction
    result = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.id == payment_id,
            PaymentTransaction.organization_id == current_user.organization_id,
        )
    )
    tx = result.scalar_one_or_none()
    
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment transaction not found",
        )
    
    return PaymentTransactionResponse(
        id=str(tx.id),
        reference=tx.reference,
        status=tx.status,
        amount_naira=tx.amount_kobo // 100,
        amount_formatted=f"₦{tx.amount_kobo // 100:,}",
        currency=tx.currency or "NGN",
        tier=tx.tier,
        billing_cycle=tx.billing_cycle,
        payment_method=tx.payment_method or tx.channel,
        card_last4=tx.card_last4,
        card_brand=tx.card_brand,
        gateway_response=tx.gateway_response,
        created_at=tx.created_at.isoformat() if tx.created_at else None,
        paid_at=tx.paid_at.isoformat() if tx.paid_at else None,
    )


# =============================================================================
# PAYMENT ENDPOINTS
# =============================================================================

@router.post(
    "/checkout",
    response_model=PaymentIntentResponse,
    summary="Create checkout session",
)
async def create_checkout_session(
    request: CreatePaymentIntentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a payment intent and get Paystack checkout URL.
    
    The user should be redirected to the authorization_url to complete payment.
    After payment, Paystack will redirect to the callback_url.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization",
        )
    
    if not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email is required for payment",
        )
    
    service = BillingService(db)
    
    try:
        cycle = BillingCycle.ANNUAL if request.billing_cycle == "annual" else BillingCycle.MONTHLY
        
        intent = await service.create_payment_intent(
            organization_id=current_user.organization_id,
            tier=request.tier,
            billing_cycle=cycle,
            admin_email=current_user.email,
            intelligence_addon=request.intelligence_addon,
            additional_users=request.additional_users,
            callback_url=request.callback_url,
        )
        
        return PaymentIntentResponse(
            id=intent.id,
            reference=intent.reference,
            amount_naira=intent.amount_naira,
            amount_formatted=f"₦{intent.amount_naira:,}",
            currency=intent.currency,
            status=intent.status.value,
            authorization_url=intent.authorization_url,
            tier=intent.tier.value,
            billing_cycle=intent.billing_cycle.value,
            expires_at=intent.expires_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/verify/{reference}",
    summary="Verify payment",
)
async def verify_payment(
    reference: str = Path(..., description="Payment reference"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a payment after returning from Paystack checkout.
    
    This should be called after the customer completes payment
    and is redirected back to the application.
    """
    service = BillingService(db)
    
    result = await service.verify_and_process_payment(reference)
    
    return {
        "success": result.success,
        "reference": result.reference,
        "status": result.status.value,
        "message": result.message,
        "amount_naira": result.amount_naira,
        "amount_formatted": f"₦{result.amount_naira:,}",
        "paid_at": result.paid_at.isoformat() if result.paid_at else None,
    }


@router.post(
    "/cancel",
    summary="Cancel subscription",
)
async def cancel_subscription(
    reason: Optional[str] = Query(None, max_length=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel the current subscription.
    
    The subscription will remain active until the end of the current
    billing period, then downgrade to Core tier.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization",
        )
    
    service = BillingService(db)
    
    result = await service.cancel_subscription(
        organization_id=current_user.organization_id,
        reason=reason,
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Failed to cancel subscription"),
        )
    
    await db.commit()
    
    return result


# =============================================================================
# WEBHOOK ENDPOINT
# =============================================================================

import hmac
import hashlib


def verify_paystack_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify Paystack webhook signature using HMAC-SHA512.
    
    Paystack signs all webhook requests with your secret key.
    The signature is sent in the X-Paystack-Signature header.
    
    Args:
        payload: Raw request body bytes
        signature: X-Paystack-Signature header value
        secret: Paystack webhook secret key
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not signature or not secret:
        return False
    
    # Calculate expected signature
    expected = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected, signature)


@router.post(
    "/webhook/paystack",
    summary="Paystack webhook handler",
    include_in_schema=False,  # Hide from OpenAPI docs
)
async def paystack_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Paystack webhook events.
    
    This endpoint receives payment notifications from Paystack.
    It should be configured in the Paystack dashboard.
    
    Security:
    - Verifies X-Paystack-Signature using HMAC-SHA512
    - Uses constant-time comparison to prevent timing attacks
    - Returns 400 for invalid signatures
    
    Supported events:
    - charge.success: Payment completed
    - charge.failed: Payment failed
    - subscription.create: New subscription
    - subscription.disable: Subscription cancelled
    - transfer.success: Payout completed
    - refund.processed: Refund completed
    """
    from app.config import settings
    
    # Get raw body for signature verification
    body = await request.body()
    signature = request.headers.get("X-Paystack-Signature", "")
    
    # Verify signature if webhook secret is configured
    webhook_secret = settings.paystack_webhook_secret
    if webhook_secret:
        if not verify_paystack_signature(body, signature, webhook_secret):
            logger.warning(f"Paystack webhook signature verification failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature"
            )
        logger.debug("Paystack webhook signature verified successfully")
    else:
        # Log warning in production if no secret configured
        if settings.paystack_secret_key and settings.paystack_secret_key.startswith("sk_live_"):
            logger.warning(
                "SECURITY WARNING: Paystack webhook secret not configured. "
                "Set PAYSTACK_WEBHOOK_SECRET in .env for production!"
            )
    
    try:
        # Parse JSON payload
        payload = await request.json() if not body else __import__('json').loads(body)
        event_type = payload.get("event")
        
        if not event_type:
            logger.debug("Paystack webhook received with no event type")
            return {"status": "ignored", "reason": "No event type"}
        
        # Log event (without sensitive data)
        event_data = payload.get("data", {})
        logger.info(
            f"Paystack webhook received: event={event_type}, "
            f"reference={event_data.get('reference', 'N/A')}"
        )
        
        service = BillingService(db)
        result = await service.process_payment_webhook(event_type, payload)
        
        if result.get("handled"):
            await db.commit()
            logger.info(f"Paystack webhook processed successfully: {event_type}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        # Return 200 to acknowledge receipt (prevents retries for parsing errors)
        return {"status": "error", "message": str(e)}


# =============================================================================
# SUBSCRIPTION ACCESS ENDPOINT
# =============================================================================

@router.get(
    "/subscription-access",
    response_model=SubscriptionAccessResponse,
    summary="Check subscription access status",
)
async def check_subscription_access(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Check if the current organization has valid subscription access.
    
    Returns access status including:
    - has_access: Whether the organization can access the application
    - status: Current subscription status (active, trial, grace_period, suspended, etc.)
    - tier: Current subscription tier
    - message: Human-readable status message
    - days_remaining: Days until subscription expires or trial ends
    - grace_period_remaining: Days remaining in grace period (if applicable)
    - is_trial: Whether currently in trial period
    
    This endpoint is used by the frontend to display subscription status
    banners and handle access restrictions.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization",
        )
    
    service = BillingService(db)
    access_info = await service.check_subscription_access(current_user.organization_id)
    
    return SubscriptionAccessResponse(
        has_access=access_info.get("has_access", False),
        status=access_info.get("status", "unknown"),
        tier=access_info.get("tier"),
        message=access_info.get("message", ""),
        days_remaining=access_info.get("days_remaining", 0),
        grace_period_remaining=access_info.get("grace_period_remaining", 0),
        is_trial=access_info.get("is_trial", False),
    )


# =============================================================================
# DUNNING STATUS ENDPOINT
# =============================================================================

@router.get(
    "/dunning-status",
    response_model=DunningStatusResponse,
    summary="Get dunning/payment failure status",
)
async def get_dunning_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current dunning status for the organization.
    
    Dunning is the process of handling failed payments with escalating
    notifications and retry attempts.
    
    Returns:
    - is_in_dunning: Whether the organization has any failed payments
    - level: Current dunning level (initial, warning, urgent, final, suspended)
    - amount_naira: Amount that failed to process
    - retry_count: Number of payment retry attempts
    - days_until_suspension: Days remaining before account suspension
    
    If the organization is not in dunning, is_in_dunning will be False
    and other fields will have default/empty values.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization",
        )
    
    dunning_service = DunningService(db)
    dunning_record = await dunning_service.get_dunning_status(current_user.organization_id)
    
    if not dunning_record:
        return DunningStatusResponse(
            organization_id=str(current_user.organization_id),
            level="none",
            amount_naira=0,
            amount_formatted="₦0",
            first_failure_at=None,
            last_retry_at=None,
            retry_count=0,
            next_retry_at=None,
            days_until_suspension=0,
            notes=None,
            is_in_dunning=False,
        )
    
    return DunningStatusResponse(
        organization_id=str(dunning_record.organization_id),
        level=dunning_record.level.value,
        amount_naira=dunning_record.amount_naira,
        amount_formatted=f"₦{dunning_record.amount_naira:,}",
        first_failure_at=dunning_record.first_failure_at.isoformat() if dunning_record.first_failure_at else None,
        last_retry_at=dunning_record.last_retry_at.isoformat() if dunning_record.last_retry_at else None,
        retry_count=dunning_record.retry_count,
        next_retry_at=dunning_record.next_retry_at.isoformat() if dunning_record.next_retry_at else None,
        days_until_suspension=dunning_record.days_until_suspension,
        notes=dunning_record.notes,
        is_in_dunning=True,
    )


# =============================================================================
# INVOICE PDF ENDPOINT
# =============================================================================

@router.get(
    "/invoice/{payment_id}/pdf",
    summary="Download invoice PDF",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF invoice file",
        }
    },
)
async def download_invoice_pdf(
    payment_id: UUID = Path(..., description="Payment transaction ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download a PDF invoice for a specific payment transaction.
    
    The invoice includes:
    - Company and customer details
    - Line items with subscription details
    - VAT breakdown (7.5% Nigerian standard)
    - Payment reference and status
    - Bank details for wire transfers (if unpaid)
    
    Returns a PDF file that can be saved or printed.
    """
    import io
    
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization",
        )
    
    # Get the payment transaction
    result = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.id == payment_id,
            PaymentTransaction.organization_id == current_user.organization_id,
        )
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment transaction not found",
        )
    
    # Generate PDF invoice
    pdf_service = InvoicePDFService(db)
    
    try:
        pdf_bytes = await pdf_service.generate_subscription_invoice(
            organization_id=current_user.organization_id,
            tier=transaction.tier or "professional",
            billing_cycle=transaction.billing_cycle or "monthly",
            amount_naira=transaction.amount_kobo // 100,
            payment_reference=transaction.reference,
            paid_at=transaction.paid_at,
        )
        
        # Create filename
        invoice_date = transaction.created_at.strftime("%Y%m%d") if transaction.created_at else "invoice"
        filename = f"TekVwarho_Invoice_{invoice_date}_{transaction.reference[:8].upper()}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate invoice PDF: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate invoice PDF",
        )


# =============================================================================
# RESEND INVOICE EMAIL ENDPOINT
# =============================================================================

@router.post(
    "/invoice/{payment_id}/resend",
    summary="Resend invoice email",
)
async def resend_invoice_email(
    payment_id: UUID = Path(..., description="Payment transaction ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Resend the invoice email for a specific payment transaction.
    
    This will send a copy of the invoice to the organization's
    billing contact email.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization",
        )
    
    # Get the payment transaction
    result = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.id == payment_id,
            PaymentTransaction.organization_id == current_user.organization_id,
        )
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment transaction not found",
        )
    
    # Send invoice email
    email_service = BillingEmailService(db)
    
    try:
        await email_service.send_payment_success_email(
            organization_id=current_user.organization_id,
            tier=transaction.tier or "professional",
            amount_naira=transaction.amount_kobo // 100,
            next_billing_date=None,  # Will be calculated from subscription
            payment_reference=transaction.reference,
        )
        
        return {"message": "Invoice email sent successfully", "sent_to": current_user.email}
    except Exception as e:
        logger.error(f"Failed to send invoice email: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send invoice email",
        )

