"""
TekVwarho ProAudit - Audit Trail Router

API endpoints for audit logs and compliance tracking.
"""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.services.audit_service import AuditService
from app.models.user import User
from app.models.audit import AuditAction

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


@router.get("/{entity_id}/logs")
async def get_audit_logs(
    entity_id: uuid.UUID,
    target_entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    target_entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by user"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get audit logs with optional filtering.
    
    Supports filtering by:
    - Entity type (transaction, invoice, etc.)
    - Specific entity ID
    - Action type (create, update, delete, etc.)
    - User who performed the action
    - Date range
    """
    action_enum = None
    if action:
        try:
            action_enum = AuditAction(action)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action. Must be one of: {[a.value for a in AuditAction]}",
            )
    
    service = AuditService(db)
    logs = await service.get_audit_logs(
        entity_id=entity_id,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        action=action_enum,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )
    
    return {
        "items": [
            {
                "id": str(log.id),
                "timestamp": log.created_at.isoformat(),
                "target_entity_type": log.target_entity_type,
                "target_entity_id": log.target_entity_id,
                "action": log.action.value,
                "user_id": str(log.user_id) if log.user_id else None,
                "changes": log.changes,
                "ip_address": log.ip_address,
            }
            for log in logs
        ],
        "skip": skip,
        "limit": limit,
    }


@router.get("/{entity_id}/history/{target_entity_type}/{target_entity_id}")
async def get_entity_history(
    entity_id: uuid.UUID,
    target_entity_type: str,
    target_entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get complete history of changes for a specific entity.
    
    Returns chronological list of all changes made to the entity,
    useful for compliance audits and debugging.
    """
    service = AuditService(db)
    history = await service.get_entity_history(
        entity_id=entity_id,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
    )
    
    return {
        "entity_type": target_entity_type,
        "entity_id": target_entity_id,
        "history": history,
    }


@router.get("/{entity_id}/user-activity/{user_id}")
async def get_user_activity(
    entity_id: uuid.UUID,
    user_id: uuid.UUID,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get activity summary for a specific user.
    
    Shows breakdown of actions performed by entity type.
    """
    service = AuditService(db)
    activity = await service.get_user_activity(
        entity_id=entity_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    return activity


@router.get("/{entity_id}/summary")
async def get_audit_summary(
    entity_id: uuid.UUID,
    start_date: date = Query(..., description="Report period start"),
    end_date: date = Query(..., description="Report period end"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate audit summary report.
    
    Shows:
    - Total events
    - Breakdown by action type
    - Breakdown by entity type
    - Breakdown by user
    """
    service = AuditService(db)
    summary = await service.get_audit_summary(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    return summary


@router.get("/actions")
async def list_audit_actions():
    """List all available audit action types."""
    return {
        "actions": [
            {
                "value": action.value,
                "description": _get_action_description(action),
            }
            for action in AuditAction
        ]
    }


def _get_action_description(action: AuditAction) -> str:
    """Get human-readable description for audit action."""
    descriptions = {
        AuditAction.CREATE: "Record created",
        AuditAction.UPDATE: "Record updated",
        AuditAction.DELETE: "Record deleted",
        AuditAction.VIEW: "Record viewed",
        AuditAction.EXPORT: "Data exported",
        AuditAction.LOGIN: "User logged in",
        AuditAction.LOGOUT: "User logged out",
        AuditAction.LOGIN_FAILED: "Login attempt failed",
        AuditAction.NRS_SUBMIT: "E-invoice submitted to NRS",
        AuditAction.NRS_CANCEL: "E-invoice cancelled in NRS",
        AuditAction.UPLOAD: "Document uploaded",
        AuditAction.DOWNLOAD: "Document downloaded",
    }
    return descriptions.get(action, action.value)
