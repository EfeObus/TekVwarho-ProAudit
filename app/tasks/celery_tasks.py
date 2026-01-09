"""
TekVwarho ProAudit - Celery Tasks

Background tasks for scheduled operations.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List

from celery import shared_task

from app.database import async_session_factory

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async functions in Celery tasks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===========================================
# INVOICE TASKS
# ===========================================

@shared_task(name='app.tasks.celery_tasks.check_overdue_invoices_task')
def check_overdue_invoices_task() -> Dict[str, Any]:
    """Check for invoices that have become overdue and send notifications."""
    return run_async(_check_overdue_invoices())


async def _check_overdue_invoices() -> Dict[str, Any]:
    """Async implementation of overdue invoice check."""
    from app.models.invoice import Invoice, InvoiceStatus
    from app.models.user import User, UserEntityAccess
    from app.services.notification_service import NotificationService
    from sqlalchemy import select
    
    async with async_session_factory() as db:
        today = date.today()
        
        # Find finalized invoices past due date
        result = await db.execute(
            select(Invoice)
            .where(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.SUBMITTED, InvoiceStatus.ACCEPTED]))
            .where(Invoice.due_date < today)
        )
        
        overdue_invoices = result.scalars().all()
        notifications_sent = 0
        invoices_updated = 0
        
        notification_service = NotificationService(db)
        
        for invoice in overdue_invoices:
            days_overdue = (today - invoice.due_date).days
            
            # Update invoice status if needed
            if invoice.status != InvoiceStatus.OVERDUE:
                invoice.status = InvoiceStatus.OVERDUE
                invoices_updated += 1
            
            # Get users with access to this entity
            users_result = await db.execute(
                select(UserEntityAccess)
                .where(UserEntityAccess.entity_id == invoice.entity_id)
            )
            user_accesses = users_result.scalars().all()
            
            # Send notifications to all users with access
            for access in user_accesses:
                user_result = await db.execute(
                    select(User).where(User.id == access.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user and user.is_active:
                    customer_name = "Unknown"
                    if invoice.customer:
                        customer_name = invoice.customer.name
                    
                    await notification_service.notify_invoice_overdue(
                        user_id=user.id,
                        entity_id=invoice.entity_id,
                        invoice_number=invoice.invoice_number,
                        customer_name=customer_name,
                        amount=float(invoice.total_amount),
                        days_overdue=days_overdue,
                        email_address=user.email if days_overdue in [1, 7, 14, 30] else None,
                    )
                    notifications_sent += 1
        
        await db.commit()
        
        logger.info(f"Overdue check complete: {invoices_updated} invoices updated, {notifications_sent} notifications sent")
        return {
            "invoices_updated": invoices_updated,
            "notifications_sent": notifications_sent,
        }


# ===========================================
# INVENTORY TASKS
# ===========================================

@shared_task(name='app.tasks.celery_tasks.check_low_stock_task')
def check_low_stock_task() -> Dict[str, Any]:
    """Check for inventory items below reorder level and send notifications."""
    return run_async(_check_low_stock())


async def _check_low_stock() -> Dict[str, Any]:
    """Async implementation of low stock check."""
    from app.models.inventory import InventoryItem
    from app.models.user import User, UserEntityAccess
    from app.services.notification_service import NotificationService
    from sqlalchemy import select
    
    async with async_session_factory() as db:
        result = await db.execute(
            select(InventoryItem)
            .where(InventoryItem.quantity_on_hand <= InventoryItem.reorder_level)
            .where(InventoryItem.is_active == True)
        )
        
        low_stock_items = result.scalars().all()
        notifications_sent = 0
        
        notification_service = NotificationService(db)
        
        for item in low_stock_items:
            # Get users with access to this entity
            users_result = await db.execute(
                select(UserEntityAccess)
                .where(UserEntityAccess.entity_id == item.entity_id)
            )
            user_accesses = users_result.scalars().all()
            
            for access in user_accesses:
                user_result = await db.execute(
                    select(User).where(User.id == access.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user and user.is_active:
                    await notification_service.notify_low_stock(
                        user_id=user.id,
                        entity_id=item.entity_id,
                        item_name=item.name,
                        current_stock=item.quantity_on_hand,
                        reorder_level=item.reorder_level,
                        item_id=item.id,
                    )
                    notifications_sent += 1
        
        await db.commit()
        
        logger.info(f"Low stock check complete: {len(low_stock_items)} items low, {notifications_sent} notifications sent")
        return {
            "low_stock_count": len(low_stock_items),
            "notifications_sent": notifications_sent,
        }


# ===========================================
# TAX DEADLINE TASKS
# ===========================================

@shared_task(name='app.tasks.celery_tasks.check_vat_deadlines_task')
def check_vat_deadlines_task() -> Dict[str, Any]:
    """Check for upcoming VAT filing deadlines and send reminders."""
    return run_async(_check_vat_deadlines())


async def _check_vat_deadlines() -> Dict[str, Any]:
    """Async implementation of VAT deadline check."""
    from app.models.entity import BusinessEntity
    from app.models.user import User, UserEntityAccess
    from app.services.notification_service import NotificationService
    from sqlalchemy import select
    
    async with async_session_factory() as db:
        today = date.today()
        
        # VAT is due by 21st of the following month
        if today.month == 12:
            deadline = date(today.year + 1, 1, 21)
            period = f"December {today.year}"
        else:
            deadline = date(today.year, today.month + 1, 21)
            period = f"{date(today.year, today.month, 1).strftime('%B')} {today.year}"
        
        days_until = (deadline - today).days
        
        if days_until > 7 or days_until < 0:
            return {"status": "no_action_needed", "days_until": days_until}
        
        notification_service = NotificationService(db)
        notifications_sent = 0
        
        # Get all active VAT-registered entities
        result = await db.execute(
            select(BusinessEntity)
            .where(BusinessEntity.is_active == True)
            .where(BusinessEntity.is_vat_registered == True)
        )
        entities = result.scalars().all()
        
        for entity in entities:
            # Get users with access
            users_result = await db.execute(
                select(UserEntityAccess)
                .where(UserEntityAccess.entity_id == entity.id)
            )
            user_accesses = users_result.scalars().all()
            
            for access in user_accesses:
                user_result = await db.execute(
                    select(User).where(User.id == access.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user and user.is_active:
                    await notification_service.notify_vat_reminder(
                        user_id=user.id,
                        entity_id=entity.id,
                        period=period,
                        deadline=deadline.strftime('%B %d, %Y'),
                        days_until=days_until,
                        email_address=user.email if days_until <= 3 else None,
                    )
                    notifications_sent += 1
        
        await db.commit()
        
        logger.info(f"VAT reminder sent: {notifications_sent} notifications, {days_until} days until deadline")
        return {
            "deadline": deadline.isoformat(),
            "days_until": days_until,
            "notifications_sent": notifications_sent,
        }


@shared_task(name='app.tasks.celery_tasks.check_paye_deadlines_task')
def check_paye_deadlines_task() -> Dict[str, Any]:
    """Check for upcoming PAYE filing deadlines and send reminders."""
    return run_async(_check_paye_deadlines())


async def _check_paye_deadlines() -> Dict[str, Any]:
    """Async implementation of PAYE deadline check."""
    from app.models.entity import BusinessEntity
    from app.models.user import User, UserEntityAccess
    from app.services.notification_service import NotificationService
    from app.models.notification import NotificationType
    from sqlalchemy import select
    
    async with async_session_factory() as db:
        today = date.today()
        
        # PAYE is due by 10th of the following month
        if today.month == 12:
            deadline = date(today.year + 1, 1, 10)
            period = f"December {today.year}"
        else:
            deadline = date(today.year, today.month + 1, 10)
            period = f"{date(today.year, today.month, 1).strftime('%B')} {today.year}"
        
        days_until = (deadline - today).days
        
        if days_until > 7 or days_until < 0:
            return {"status": "no_action_needed", "days_until": days_until}
        
        notification_service = NotificationService(db)
        notifications_sent = 0
        
        # Get all active entities
        result = await db.execute(
            select(BusinessEntity)
            .where(BusinessEntity.is_active == True)
        )
        entities = result.scalars().all()
        
        for entity in entities:
            users_result = await db.execute(
                select(UserEntityAccess)
                .where(UserEntityAccess.entity_id == entity.id)
            )
            user_accesses = users_result.scalars().all()
            
            for access in user_accesses:
                user_result = await db.execute(
                    select(User).where(User.id == access.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user and user.is_active:
                    await notification_service.create_notification(
                        user_id=user.id,
                        entity_id=entity.id,
                        notification_type=NotificationType.PAYE_REMINDER,
                        title="PAYE Filing Reminder",
                        message=f"PAYE remittance for {period} is due on {deadline.strftime('%B %d, %Y')} ({days_until} days remaining).",
                        action_url="/reports?tab=tax",
                        action_label="View PAYE Report",
                        send_email=days_until <= 3,
                        email_address=user.email if days_until <= 3 else None,
                    )
                    notifications_sent += 1
        
        await db.commit()
        
        logger.info(f"PAYE reminder sent: {notifications_sent} notifications")
        return {
            "deadline": deadline.isoformat(),
            "days_until": days_until,
            "notifications_sent": notifications_sent,
        }


# ===========================================
# NRS TASKS
# ===========================================

@shared_task(name='app.tasks.celery_tasks.retry_failed_nrs_submissions_task')
def retry_failed_nrs_submissions_task() -> Dict[str, Any]:
    """Retry failed NRS invoice submissions."""
    return run_async(_retry_failed_nrs_submissions())


async def _retry_failed_nrs_submissions() -> Dict[str, Any]:
    """Async implementation of NRS submission retry."""
    from app.models.invoice import Invoice, InvoiceStatus
    from app.services.nrs_service import NRSService
    from sqlalchemy import select
    
    async with async_session_factory() as db:
        # Find invoices pending NRS submission (failed previously)
        result = await db.execute(
            select(Invoice)
            .where(Invoice.status == InvoiceStatus.PENDING)
            .where(Invoice.nrs_irn == None)
            .where(Invoice.nrs_submission_attempts < 5)  # Max 5 retries
        )
        
        pending_invoices = result.scalars().all()
        successful = 0
        failed = 0
        
        nrs_service = NRSService()
        
        for invoice in pending_invoices:
            try:
                # Attempt submission
                response = await nrs_service.submit_invoice(invoice)
                
                if response.success and response.irn:
                    invoice.nrs_irn = response.irn
                    invoice.nrs_qr_code_data = response.qr_code_data
                    invoice.nrs_submission_date = datetime.utcnow()
                    invoice.status = InvoiceStatus.SUBMITTED
                    successful += 1
                else:
                    invoice.nrs_submission_attempts = (invoice.nrs_submission_attempts or 0) + 1
                    invoice.nrs_last_error = response.message
                    failed += 1
            except Exception as e:
                invoice.nrs_submission_attempts = (invoice.nrs_submission_attempts or 0) + 1
                invoice.nrs_last_error = str(e)
                failed += 1
        
        await db.commit()
        
        logger.info(f"NRS retry complete: {successful} successful, {failed} failed")
        return {
            "successful": successful,
            "failed": failed,
            "total_pending": len(pending_invoices),
        }


# ===========================================
# CLEANUP TASKS
# ===========================================

@shared_task(name='app.tasks.celery_tasks.cleanup_notifications_task')
def cleanup_notifications_task() -> Dict[str, Any]:
    """Clean up old notifications."""
    return run_async(_cleanup_notifications())


async def _cleanup_notifications() -> Dict[str, Any]:
    """Delete notifications older than 90 days."""
    from app.services.notification_service import NotificationService
    
    async with async_session_factory() as db:
        notification_service = NotificationService(db)
        deleted_count = await notification_service.delete_old_notifications(days_old=90)
        
        logger.info(f"Cleaned up {deleted_count} old notifications")
        return {"deleted_count": deleted_count}


@shared_task(name='app.tasks.celery_tasks.archive_audit_logs_task')
def archive_audit_logs_task() -> Dict[str, Any]:
    """Archive old audit logs."""
    return run_async(_archive_audit_logs())


async def _archive_audit_logs() -> Dict[str, Any]:
    """Archive audit logs older than 5 years (NTAA requirement)."""
    from app.models.audit_consolidated import AuditLog
    from sqlalchemy import select, func
    
    async with async_session_factory() as db:
        cutoff = datetime.utcnow() - timedelta(days=365 * 5)
        
        # Count logs to archive (but don't delete - NTAA requires 5-year retention)
        result = await db.execute(
            select(func.count(AuditLog.id))
            .where(AuditLog.created_at < cutoff)
        )
        count = result.scalar() or 0
        
        # In production, these would be archived to cold storage
        logger.info(f"Found {count} audit logs eligible for archival")
        
        return {"eligible_for_archive": count}


# ===========================================
# REPORT GENERATION TASKS
# ===========================================

@shared_task(name='app.tasks.celery_tasks.generate_monthly_tax_summary_task')
def generate_monthly_tax_summary_task() -> Dict[str, Any]:
    """Generate monthly tax summary reports for all entities."""
    return run_async(_generate_monthly_tax_summary())


async def _generate_monthly_tax_summary() -> Dict[str, Any]:
    """Generate monthly tax summaries."""
    from app.models.entity import BusinessEntity
    from app.models.user import User, UserEntityAccess
    from app.services.notification_service import NotificationService
    from app.models.notification import NotificationType
    from sqlalchemy import select
    
    async with async_session_factory() as db:
        today = date.today()
        
        # Generate for previous month
        if today.month == 1:
            report_month = 12
            report_year = today.year - 1
        else:
            report_month = today.month - 1
            report_year = today.year
        
        period = f"{date(report_year, report_month, 1).strftime('%B')} {report_year}"
        
        notification_service = NotificationService(db)
        reports_generated = 0
        
        result = await db.execute(
            select(BusinessEntity)
            .where(BusinessEntity.is_active == True)
        )
        entities = result.scalars().all()
        
        for entity in entities:
            # Notify entity users that monthly summary is ready
            users_result = await db.execute(
                select(UserEntityAccess)
                .where(UserEntityAccess.entity_id == entity.id)
                .where(UserEntityAccess.can_write == True)
            )
            user_accesses = users_result.scalars().all()
            
            for access in user_accesses:
                user_result = await db.execute(
                    select(User).where(User.id == access.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user and user.is_active:
                    await notification_service.create_notification(
                        user_id=user.id,
                        entity_id=entity.id,
                        notification_type=NotificationType.INFO,
                        title=f"Monthly Tax Summary Ready",
                        message=f"Your tax summary for {period} is now available in the Reports section.",
                        action_url="/reports?tab=tax",
                        action_label="View Report",
                    )
            
            reports_generated += 1
        
        await db.commit()
        
        logger.info(f"Generated {reports_generated} monthly tax summary notifications")
        return {
            "period": period,
            "reports_generated": reports_generated,
        }


# ===========================================
# EMAIL TASKS
# ===========================================

@shared_task(name='app.tasks.celery_tasks.send_email_task', bind=True, max_retries=3)
def send_email_task(self, to: List[str], subject: str, body_text: str, body_html: str = None) -> bool:
    """Send an email asynchronously."""
    return run_async(_send_email(to, subject, body_text, body_html))


async def _send_email(to: List[str], subject: str, body_text: str, body_html: str = None) -> bool:
    """Async email sending."""
    from app.services.email_service import EmailService, EmailMessage
    
    email_service = EmailService()
    return await email_service.send_email(EmailMessage(
        to=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    ))
