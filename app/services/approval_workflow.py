"""
M-of-N Approval Workflow Service
Multi-signature approval for sensitive operations

Supports configurable approval policies:
- Bulk payments over threshold require 2-of-3 approvers
- Payroll runs require Director + CFO
- Tax filings require CEO approval
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.orm import selectinload

from app.models.advanced_accounting import (
    ApprovalWorkflow,
    ApprovalWorkflowApprover,
    ApprovalRequest,
    ApprovalDecision,
    ApprovalStatus
)
from app.models.notification import Notification

logger = logging.getLogger(__name__)


class ApprovalWorkflowService:
    """
    Multi-signature approval workflow service
    """
    
    # Default workflow configurations
    DEFAULT_WORKFLOWS = {
        "bulk_payment": {
            "name": "Bulk Payment Approval",
            "description": "Requires 2-of-3 approvers for payments over threshold",
            "required_approvers": 2,
            "threshold_amount": Decimal("1000000"),  # 1M NGN
            "escalation_hours": 24
        },
        "payroll": {
            "name": "Payroll Run Approval",
            "description": "Requires Director and CFO approval",
            "required_approvers": 2,
            "threshold_amount": None,
            "escalation_hours": 48
        },
        "tax_filing": {
            "name": "Tax Filing Approval",
            "description": "Requires CEO approval for all tax filings",
            "required_approvers": 1,
            "threshold_amount": None,
            "escalation_hours": 72
        },
        "vendor_creation": {
            "name": "New Vendor Approval",
            "description": "Requires Finance Manager approval",
            "required_approvers": 1,
            "threshold_amount": None,
            "escalation_hours": 48
        },
        "credit_note": {
            "name": "Credit Note Approval",
            "description": "Requires 2 approvers for credit notes over 500K",
            "required_approvers": 2,
            "threshold_amount": Decimal("500000"),
            "escalation_hours": 24
        }
    }
    
    async def create_workflow(
        self,
        db: AsyncSession,
        entity_id: UUID,
        workflow_type: str,
        name: str,
        approvers: List[Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None,
        created_by: UUID = None
    ) -> ApprovalWorkflow:
        """Create a new approval workflow"""
        
        # Get default config
        default_config = self.DEFAULT_WORKFLOWS.get(workflow_type, {})
        merged_config = {**default_config, **(config or {})}
        
        workflow = ApprovalWorkflow(
            entity_id=entity_id,
            workflow_type=workflow_type,
            name=name,
            description=merged_config.get("description"),
            required_approvers=merged_config.get("required_approvers", 1),
            threshold_amount=merged_config.get("threshold_amount"),
            escalation_hours=merged_config.get("escalation_hours", 24),
            is_active=True,
            created_by_id=created_by
        )
        
        # Add approvers
        for i, approver_data in enumerate(approvers):
            approver = ApprovalWorkflowApprover(
                user_id=approver_data["user_id"],
                role=approver_data.get("role", "approver"),
                approval_order=approver_data.get("order", i + 1),
                can_delegate=approver_data.get("can_delegate", False),
                is_required=approver_data.get("is_required", False)
            )
            workflow.approvers.append(approver)
        
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)
        
        logger.info(f"Created workflow '{name}' with {len(approvers)} approvers")
        
        return workflow
    
    async def submit_for_approval(
        self,
        db: AsyncSession,
        entity_id: UUID,
        workflow_type: str,
        resource_type: str,
        resource_id: UUID,
        amount: Optional[Decimal] = None,
        submitted_by: UUID = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ApprovalRequest:
        """Submit a resource for approval"""
        
        # Find matching workflow
        workflow = await self._find_applicable_workflow(
            db, entity_id, workflow_type, amount
        )
        
        if not workflow:
            raise ValueError(f"No active workflow found for type '{workflow_type}'")
        
        # Check if already pending
        existing = await self._get_pending_request(db, resource_type, resource_id)
        if existing:
            raise ValueError(f"Resource {resource_id} already has a pending approval request")
        
        # Create approval request
        request = ApprovalRequest(
            entity_id=entity_id,
            workflow_id=workflow.id,
            resource_type=resource_type,
            resource_id=resource_id,
            amount=amount,
            status=ApprovalStatus.PENDING,
            submitted_by_id=submitted_by,
            context=context,
            expires_at=datetime.utcnow() + timedelta(hours=workflow.escalation_hours or 24)
        )
        
        db.add(request)
        await db.flush()
        
        # Notify approvers
        await self._notify_approvers(db, workflow, request)
        
        await db.commit()
        await db.refresh(request)
        
        logger.info(f"Submitted {resource_type} {resource_id} for approval via workflow {workflow.name}")
        
        return request
    
    async def approve(
        self,
        db: AsyncSession,
        request_id: UUID,
        approver_id: UUID,
        comments: Optional[str] = None
    ) -> ApprovalDecision:
        """Approve an approval request"""
        
        request = await db.get(
            ApprovalRequest, 
            request_id,
            options=[selectinload(ApprovalRequest.workflow).selectinload(ApprovalWorkflow.approvers)]
        )
        
        if not request:
            raise ValueError(f"Approval request {request_id} not found")
        
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request is not pending (status: {request.status})")
        
        # Validate approver
        if not await self._is_valid_approver(request.workflow, approver_id):
            raise ValueError(f"User {approver_id} is not authorized to approve this request")
        
        # Check for duplicate decision
        existing_decision = await self._get_user_decision(db, request_id, approver_id)
        if existing_decision:
            raise ValueError(f"User {approver_id} has already made a decision on this request")
        
        # Create decision
        decision = ApprovalDecision(
            request_id=request_id,
            approver_id=approver_id,
            decision="approved",
            comments=comments,
            decided_at=datetime.utcnow()
        )
        
        db.add(decision)
        await db.flush()
        
        # Check if request is fully approved
        approval_count = await self._count_approvals(db, request_id)
        required = request.workflow.required_approvers
        
        if approval_count >= required:
            request.status = ApprovalStatus.APPROVED
            request.completed_at = datetime.utcnow()
            
            # Execute post-approval action
            await self._execute_approved_action(db, request)
        
        await db.commit()
        await db.refresh(decision)
        
        logger.info(f"Request {request_id} approved by {approver_id} ({approval_count}/{required})")
        
        return decision
    
    async def reject(
        self,
        db: AsyncSession,
        request_id: UUID,
        approver_id: UUID,
        reason: str
    ) -> ApprovalDecision:
        """Reject an approval request"""
        
        request = await db.get(
            ApprovalRequest,
            request_id,
            options=[selectinload(ApprovalRequest.workflow).selectinload(ApprovalWorkflow.approvers)]
        )
        
        if not request:
            raise ValueError(f"Approval request {request_id} not found")
        
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request is not pending (status: {request.status})")
        
        # Validate approver
        if not await self._is_valid_approver(request.workflow, approver_id):
            raise ValueError(f"User {approver_id} is not authorized to reject this request")
        
        # Create decision
        decision = ApprovalDecision(
            request_id=request_id,
            approver_id=approver_id,
            decision="rejected",
            comments=reason,
            decided_at=datetime.utcnow()
        )
        
        db.add(decision)
        
        # Reject the request immediately
        request.status = ApprovalStatus.REJECTED
        request.completed_at = datetime.utcnow()
        
        # Notify submitter
        await self._notify_rejection(db, request, reason)
        
        await db.commit()
        await db.refresh(decision)
        
        logger.info(f"Request {request_id} rejected by {approver_id}: {reason}")
        
        return decision
    
    async def delegate(
        self,
        db: AsyncSession,
        request_id: UUID,
        delegator_id: UUID,
        delegate_to_id: UUID,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delegate approval authority to another user"""
        
        request = await db.get(
            ApprovalRequest,
            request_id,
            options=[selectinload(ApprovalRequest.workflow).selectinload(ApprovalWorkflow.approvers)]
        )
        
        if not request:
            raise ValueError(f"Approval request {request_id} not found")
        
        # Check if delegator can delegate
        workflow_approver = next(
            (a for a in request.workflow.approvers if str(a.user_id) == str(delegator_id)),
            None
        )
        
        if not workflow_approver or not workflow_approver.can_delegate:
            raise ValueError(f"User {delegator_id} cannot delegate for this workflow")
        
        # Add delegate as temporary approver
        temp_approver = ApprovalWorkflowApprover(
            workflow_id=request.workflow.id,
            user_id=delegate_to_id,
            role="delegate",
            approval_order=workflow_approver.approval_order,
            delegated_from_id=delegator_id,
            delegation_expires=datetime.utcnow() + timedelta(days=7),
            is_required=False
        )
        
        db.add(temp_approver)
        
        # Notify delegate
        notification = Notification(
            entity_id=request.entity_id,
            user_id=delegate_to_id,
            notification_type="approval_delegated",
            title="Approval Delegated to You",
            message=f"You have been delegated approval authority for {request.resource_type}",
            data={
                "request_id": str(request_id),
                "delegated_by": str(delegator_id),
                "reason": reason
            }
        )
        db.add(notification)
        
        await db.commit()
        
        return {
            "request_id": str(request_id),
            "delegated_to": str(delegate_to_id),
            "delegated_by": str(delegator_id),
            "expires": temp_approver.delegation_expires.isoformat()
        }
    
    async def get_pending_approvals(
        self,
        db: AsyncSession,
        entity_id: UUID,
        approver_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get pending approval requests"""
        
        query = select(ApprovalRequest).where(
            and_(
                ApprovalRequest.entity_id == entity_id,
                ApprovalRequest.status == ApprovalStatus.PENDING
            )
        ).options(
            selectinload(ApprovalRequest.workflow).selectinload(ApprovalWorkflow.approvers),
            selectinload(ApprovalRequest.decisions)
        ).order_by(ApprovalRequest.created_at.desc())
        
        result = await db.execute(query)
        requests = result.scalars().all()
        
        pending = []
        for req in requests:
            # Filter by approver if specified
            if approver_id:
                approver_ids = [str(a.user_id) for a in req.workflow.approvers]
                if str(approver_id) not in approver_ids:
                    continue
                
                # Check if already decided
                decided_by = [str(d.approver_id) for d in req.decisions]
                if str(approver_id) in decided_by:
                    continue
            
            # Count approvals
            approval_count = sum(1 for d in req.decisions if d.decision == "approved")
            
            pending.append({
                "id": str(req.id),
                "workflow_name": req.workflow.name,
                "workflow_type": req.workflow.workflow_type,
                "resource_type": req.resource_type,
                "resource_id": str(req.resource_id),
                "amount": str(req.amount) if req.amount else None,
                "submitted_at": req.created_at.isoformat(),
                "submitted_by": str(req.submitted_by_id) if req.submitted_by_id else None,
                "expires_at": req.expires_at.isoformat() if req.expires_at else None,
                "approvals": {
                    "received": approval_count,
                    "required": req.workflow.required_approvers
                },
                "context": req.context
            })
        
        return pending
    
    async def get_approval_history(
        self,
        db: AsyncSession,
        entity_id: UUID,
        start_date: date,
        end_date: date,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get approval history with statistics"""
        
        query = select(ApprovalRequest).where(
            and_(
                ApprovalRequest.entity_id == entity_id,
                ApprovalRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
                ApprovalRequest.created_at <= datetime.combine(end_date, datetime.max.time())
            )
        ).options(
            selectinload(ApprovalRequest.workflow),
            selectinload(ApprovalRequest.decisions)
        )
        
        if status:
            query = query.where(ApprovalRequest.status == ApprovalStatus(status))
        
        result = await db.execute(query)
        requests = result.scalars().all()
        
        # Calculate statistics
        stats = {
            "total": len(requests),
            "approved": 0,
            "rejected": 0,
            "pending": 0,
            "expired": 0,
            "avg_approval_time_hours": 0
        }
        
        approval_times = []
        
        for req in requests:
            if req.status == ApprovalStatus.APPROVED:
                stats["approved"] += 1
                if req.completed_at:
                    delta = req.completed_at - req.created_at
                    approval_times.append(delta.total_seconds() / 3600)
            elif req.status == ApprovalStatus.REJECTED:
                stats["rejected"] += 1
            elif req.status == ApprovalStatus.PENDING:
                stats["pending"] += 1
            elif req.status == ApprovalStatus.EXPIRED:
                stats["expired"] += 1
        
        if approval_times:
            stats["avg_approval_time_hours"] = round(sum(approval_times) / len(approval_times), 1)
        
        # Group by workflow type
        by_workflow = {}
        for req in requests:
            wf_type = req.workflow.workflow_type
            if wf_type not in by_workflow:
                by_workflow[wf_type] = {"approved": 0, "rejected": 0, "pending": 0}
            by_workflow[wf_type][req.status.value] = by_workflow[wf_type].get(req.status.value, 0) + 1
        
        return {
            "entity_id": str(entity_id),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "statistics": stats,
            "by_workflow_type": by_workflow,
            "requests": [
                {
                    "id": str(req.id),
                    "workflow_type": req.workflow.workflow_type,
                    "resource_type": req.resource_type,
                    "amount": str(req.amount) if req.amount else None,
                    "status": req.status.value,
                    "submitted_at": req.created_at.isoformat(),
                    "completed_at": req.completed_at.isoformat() if req.completed_at else None
                }
                for req in requests[:100]
            ],
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def check_expired_requests(self, db: AsyncSession) -> int:
        """Check and expire overdue requests"""
        
        query = update(ApprovalRequest).where(
            and_(
                ApprovalRequest.status == ApprovalStatus.PENDING,
                ApprovalRequest.expires_at < datetime.utcnow()
            )
        ).values(
            status=ApprovalStatus.EXPIRED,
            completed_at=datetime.utcnow()
        )
        
        result = await db.execute(query)
        await db.commit()
        
        expired_count = result.rowcount
        if expired_count > 0:
            logger.warning(f"Expired {expired_count} approval requests")
        
        return expired_count
    
    async def _find_applicable_workflow(
        self,
        db: AsyncSession,
        entity_id: UUID,
        workflow_type: str,
        amount: Optional[Decimal]
    ) -> Optional[ApprovalWorkflow]:
        """Find the applicable workflow for a request"""
        
        query = select(ApprovalWorkflow).where(
            and_(
                ApprovalWorkflow.entity_id == entity_id,
                ApprovalWorkflow.workflow_type == workflow_type,
                ApprovalWorkflow.is_active == True
            )
        ).options(selectinload(ApprovalWorkflow.approvers))
        
        if amount:
            # Find workflow with threshold <= amount
            query = query.where(
                or_(
                    ApprovalWorkflow.threshold_amount == None,
                    ApprovalWorkflow.threshold_amount <= amount
                )
            ).order_by(ApprovalWorkflow.threshold_amount.desc())
        
        result = await db.execute(query)
        return result.scalar()
    
    async def _get_pending_request(
        self,
        db: AsyncSession,
        resource_type: str,
        resource_id: UUID
    ) -> Optional[ApprovalRequest]:
        """Get pending approval request for a resource"""
        
        query = select(ApprovalRequest).where(
            and_(
                ApprovalRequest.resource_type == resource_type,
                ApprovalRequest.resource_id == resource_id,
                ApprovalRequest.status == ApprovalStatus.PENDING
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def _is_valid_approver(
        self,
        workflow: ApprovalWorkflow,
        user_id: UUID
    ) -> bool:
        """Check if user is a valid approver for the workflow"""
        
        approver_ids = [str(a.user_id) for a in workflow.approvers]
        return str(user_id) in approver_ids
    
    async def _get_user_decision(
        self,
        db: AsyncSession,
        request_id: UUID,
        user_id: UUID
    ) -> Optional[ApprovalDecision]:
        """Get user's decision on a request"""
        
        query = select(ApprovalDecision).where(
            and_(
                ApprovalDecision.request_id == request_id,
                ApprovalDecision.approver_id == user_id
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def _count_approvals(self, db: AsyncSession, request_id: UUID) -> int:
        """Count approvals for a request"""
        
        query = select(func.count(ApprovalDecision.id)).where(
            and_(
                ApprovalDecision.request_id == request_id,
                ApprovalDecision.decision == "approved"
            )
        )
        result = await db.execute(query)
        return result.scalar_one()
    
    async def _notify_approvers(
        self,
        db: AsyncSession,
        workflow: ApprovalWorkflow,
        request: ApprovalRequest
    ):
        """Notify all approvers of a new request"""
        
        for approver in workflow.approvers:
            notification = Notification(
                entity_id=request.entity_id,
                user_id=approver.user_id,
                notification_type="approval_required",
                title=f"Approval Required: {workflow.name}",
                message=f"A new {request.resource_type} requires your approval",
                data={
                    "request_id": str(request.id),
                    "workflow_type": workflow.workflow_type,
                    "amount": str(request.amount) if request.amount else None
                },
                priority="high" if request.amount and request.amount > Decimal("1000000") else "normal"
            )
            db.add(notification)
    
    async def _notify_rejection(
        self,
        db: AsyncSession,
        request: ApprovalRequest,
        reason: str
    ):
        """Notify submitter of rejection"""
        
        if request.submitted_by_id:
            notification = Notification(
                entity_id=request.entity_id,
                user_id=request.submitted_by_id,
                notification_type="approval_rejected",
                title=f"Approval Rejected",
                message=f"Your {request.resource_type} request was rejected: {reason}",
                data={
                    "request_id": str(request.id),
                    "reason": reason
                },
                priority="high"
            )
            db.add(notification)
    
    async def _execute_approved_action(
        self,
        db: AsyncSession,
        request: ApprovalRequest
    ):
        """Execute action after approval is complete"""
        
        # Notify submitter
        if request.submitted_by_id:
            notification = Notification(
                entity_id=request.entity_id,
                user_id=request.submitted_by_id,
                notification_type="approval_completed",
                title=f"Approval Completed",
                message=f"Your {request.resource_type} has been approved",
                data={
                    "request_id": str(request.id),
                    "resource_type": request.resource_type,
                    "resource_id": str(request.resource_id)
                },
                priority="normal"
            )
            db.add(notification)
        
        # Additional actions based on resource type could be added here
        # e.g., trigger payment execution, submit tax filing, etc.
        logger.info(f"Approved action for {request.resource_type} {request.resource_id}")


# Singleton instance
approval_workflow_service = ApprovalWorkflowService()
