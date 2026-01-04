"""
TekVwarho ProAudit - Customers Router

API endpoints for customer management.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.customer import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    CustomerResponse,
    CustomerListResponse,
)
from app.services.customer_service import CustomerService
from app.services.entity_service import EntityService


router = APIRouter()


@router.get(
    "/{entity_id}/customers",
    response_model=CustomerListResponse,
    summary="List customers",
    description="Get all customers for a business entity.",
)
async def list_customers(
    entity_id: UUID,
    search: Optional[str] = Query(None, description="Search by name, TIN, or email"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all customers for an entity."""
    # Verify entity access
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    customer_service = CustomerService(db)
    customers = await customer_service.get_customers_for_entity(
        entity_id,
        search=search,
    )
    
    customer_responses = []
    for customer in customers:
        stats = await customer_service.get_customer_stats(customer)
        customer_responses.append(
            CustomerResponse(
                id=customer.id,
                entity_id=customer.entity_id,
                name=customer.name,
                tin=customer.tin,
                contact_person=customer.contact_person,
                email=customer.email,
                phone=customer.phone,
                address=customer.address,
                city=customer.city,
                state=customer.state,
                is_business=customer.is_business,
                total_invoiced=stats["total_invoiced"],
                total_paid=stats["total_paid"],
                outstanding_balance=stats["outstanding_balance"],
                invoice_count=stats["invoice_count"],
                notes=customer.notes,
                is_active=customer.is_active,
                created_at=customer.created_at,
                updated_at=customer.updated_at,
            )
        )
    
    return CustomerListResponse(
        customers=customer_responses,
        total=len(customer_responses),
    )


@router.post(
    "/{entity_id}/customers",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer",
    description="Create a new customer for a business entity.",
)
async def create_customer(
    entity_id: UUID,
    request: CustomerCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new customer."""
    # Verify entity access and write permission
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    can_write = await entity_service.check_user_can_write(current_user, entity_id)
    if not can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access denied for this entity",
        )
    
    customer_service = CustomerService(db)
    
    customer = await customer_service.create_customer(
        entity_id=entity_id,
        name=request.name,
        tin=request.tin,
        contact_person=request.contact_person,
        email=request.email,
        phone=request.phone,
        address=request.address,
        city=request.city,
        state=request.state,
        is_business=request.is_business,
        notes=request.notes,
    )
    
    return CustomerResponse(
        id=customer.id,
        entity_id=customer.entity_id,
        name=customer.name,
        tin=customer.tin,
        contact_person=customer.contact_person,
        email=customer.email,
        phone=customer.phone,
        address=customer.address,
        city=customer.city,
        state=customer.state,
        is_business=customer.is_business,
        total_invoiced=0.0,
        total_paid=0.0,
        outstanding_balance=0.0,
        invoice_count=0,
        notes=customer.notes,
        is_active=customer.is_active,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


@router.get(
    "/{entity_id}/customers/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer",
    description="Get a specific customer by ID.",
)
async def get_customer(
    entity_id: UUID,
    customer_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific customer."""
    # Verify entity access
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    customer_service = CustomerService(db)
    customer = await customer_service.get_customer_by_id(customer_id, entity_id)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    
    stats = await customer_service.get_customer_stats(customer)
    
    return CustomerResponse(
        id=customer.id,
        entity_id=customer.entity_id,
        name=customer.name,
        tin=customer.tin,
        contact_person=customer.contact_person,
        email=customer.email,
        phone=customer.phone,
        address=customer.address,
        city=customer.city,
        state=customer.state,
        is_business=customer.is_business,
        total_invoiced=stats["total_invoiced"],
        total_paid=stats["total_paid"],
        outstanding_balance=stats["outstanding_balance"],
        invoice_count=stats["invoice_count"],
        notes=customer.notes,
        is_active=customer.is_active,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


@router.patch(
    "/{entity_id}/customers/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer",
    description="Update a customer.",
)
async def update_customer(
    entity_id: UUID,
    customer_id: UUID,
    request: CustomerUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update a customer."""
    # Verify entity access and write permission
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    can_write = await entity_service.check_user_can_write(current_user, entity_id)
    if not can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access denied for this entity",
        )
    
    customer_service = CustomerService(db)
    customer = await customer_service.get_customer_by_id(customer_id, entity_id)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    
    update_data = request.model_dump(exclude_unset=True)
    customer = await customer_service.update_customer(customer, **update_data)
    stats = await customer_service.get_customer_stats(customer)
    
    return CustomerResponse(
        id=customer.id,
        entity_id=customer.entity_id,
        name=customer.name,
        tin=customer.tin,
        contact_person=customer.contact_person,
        email=customer.email,
        phone=customer.phone,
        address=customer.address,
        city=customer.city,
        state=customer.state,
        is_business=customer.is_business,
        total_invoiced=stats["total_invoiced"],
        total_paid=stats["total_paid"],
        outstanding_balance=stats["outstanding_balance"],
        invoice_count=stats["invoice_count"],
        notes=customer.notes,
        is_active=customer.is_active,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


@router.delete(
    "/{entity_id}/customers/{customer_id}",
    response_model=MessageResponse,
    summary="Delete customer",
    description="Soft delete a customer.",
)
async def delete_customer(
    entity_id: UUID,
    customer_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a customer."""
    # Verify entity access and write permission
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    can_write = await entity_service.check_user_can_write(current_user, entity_id)
    if not can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access denied for this entity",
        )
    
    customer_service = CustomerService(db)
    customer = await customer_service.get_customer_by_id(customer_id, entity_id)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    
    await customer_service.delete_customer(customer)
    
    return MessageResponse(
        message="Customer deleted successfully",
        success=True,
    )
