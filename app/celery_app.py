"""
TekVwarho ProAudit - Celery Configuration

Celery configuration for background task processing.
Uses Redis as the message broker and result backend.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings


# Get Redis URL from settings or use default
redis_url = getattr(settings, 'redis_url', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'tekvwarho_proaudit',
    broker=redis_url,
    backend=redis_url,
    include=['app.tasks.celery_tasks'],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Timezone
    timezone='Africa/Lagos',
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes (warning before hard limit)
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    
    # Result backend settings
    result_expires=86400,  # 24 hours
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # Check for overdue invoices every day at 8 AM
        'check-overdue-invoices': {
            'task': 'app.tasks.celery_tasks.check_overdue_invoices_task',
            'schedule': crontab(hour=8, minute=0),
        },
        
        # Check low stock items every day at 9 AM
        'check-low-stock': {
            'task': 'app.tasks.celery_tasks.check_low_stock_task',
            'schedule': crontab(hour=9, minute=0),
        },
        
        # VAT filing reminders on the 15th and 19th of each month
        'vat-filing-reminder-15th': {
            'task': 'app.tasks.celery_tasks.check_vat_deadlines_task',
            'schedule': crontab(day_of_month=15, hour=9, minute=0),
        },
        'vat-filing-reminder-19th': {
            'task': 'app.tasks.celery_tasks.check_vat_deadlines_task',
            'schedule': crontab(day_of_month=19, hour=9, minute=0),
        },
        
        # PAYE reminders on the 5th and 8th of each month
        'paye-reminder-5th': {
            'task': 'app.tasks.celery_tasks.check_paye_deadlines_task',
            'schedule': crontab(day_of_month=5, hour=9, minute=0),
        },
        'paye-reminder-8th': {
            'task': 'app.tasks.celery_tasks.check_paye_deadlines_task',
            'schedule': crontab(day_of_month=8, hour=9, minute=0),
        },
        
        # Retry failed NRS submissions every hour
        'retry-nrs-submissions': {
            'task': 'app.tasks.celery_tasks.retry_failed_nrs_submissions_task',
            'schedule': crontab(minute=0),  # Every hour
        },
        
        # Clean up old notifications weekly
        'cleanup-old-notifications': {
            'task': 'app.tasks.celery_tasks.cleanup_notifications_task',
            'schedule': crontab(day_of_week=0, hour=2, minute=0),  # Sunday 2 AM
        },
        
        # Archive old audit logs monthly
        'archive-audit-logs': {
            'task': 'app.tasks.celery_tasks.archive_audit_logs_task',
            'schedule': crontab(day_of_month=1, hour=3, minute=0),  # 1st of month 3 AM
        },
        
        # Generate monthly tax summary reports
        'monthly-tax-summary': {
            'task': 'app.tasks.celery_tasks.generate_monthly_tax_summary_task',
            'schedule': crontab(day_of_month=1, hour=6, minute=0),  # 1st of month 6 AM
        },
    },
)


# Task routing (optional - for scaling specific task types)
celery_app.conf.task_routes = {
    'app.tasks.celery_tasks.send_email_*': {'queue': 'email'},
    'app.tasks.celery_tasks.nrs_*': {'queue': 'nrs'},
    'app.tasks.celery_tasks.*': {'queue': 'default'},
}
