"""
TekVwarho ProAudit - Email Service

Handles transactional email sending.
Supports SendGrid, Mailgun, or SMTP.
"""

import logging
from typing import Any, Dict, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Email message data structure."""
    to: List[str]
    subject: str
    body_text: str
    body_html: Optional[str] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    reply_to: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class EmailService:
    """Service for sending transactional emails."""
    
    def __init__(self):
        self.from_email = getattr(settings, 'email_from', 'noreply@tekvwarho.com')
        self.from_name = getattr(settings, 'email_from_name', 'TekVwarho ProAudit')
    
    async def send_email(self, message: EmailMessage) -> bool:
        """
        Send an email.
        
        In production, integrate with SendGrid, Mailgun, or AWS SES.
        """
        try:
            # For development, just log the email
            logger.info(f"Email to {message.to}: {message.subject}")
            
            # TODO: Implement actual email sending
            # Options:
            # 1. SendGrid
            # 2. Mailgun
            # 3. AWS SES
            # 4. SMTP
            
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    # ===========================================
    # TRANSACTIONAL EMAIL TEMPLATES
    # ===========================================
    
    async def send_welcome_email(
        self,
        to_email: str,
        first_name: str,
    ) -> bool:
        """Send welcome email to new users."""
        subject = "Welcome to TekVwarho ProAudit!"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #16a34a;">Welcome to TekVwarho ProAudit!</h1>
                <p>Hi {first_name},</p>
                <p>Thank you for joining TekVwarho ProAudit, Nigeria's premier tax compliance and business management platform.</p>
                <p>Here's what you can do next:</p>
                <ul>
                    <li>Set up your business entity</li>
                    <li>Connect your NRS e-invoicing</li>
                    <li>Start tracking income and expenses</li>
                    <li>Generate tax-compliant reports</li>
                </ul>
                <p>
                    <a href="https://app.tekvwarho.com/dashboard" 
                       style="display: inline-block; background-color: #16a34a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                        Go to Dashboard
                    </a>
                </p>
                <p>If you have any questions, our support team is here to help.</p>
                <p>Best regards,<br>The TekVwarho Team</p>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        Welcome to TekVwarho ProAudit!
        
        Hi {first_name},
        
        Thank you for joining TekVwarho ProAudit, Nigeria's premier tax compliance and business management platform.
        
        Here's what you can do next:
        - Set up your business entity
        - Connect your NRS e-invoicing
        - Start tracking income and expenses
        - Generate tax-compliant reports
        
        Visit your dashboard: https://app.tekvwarho.com/dashboard
        
        Best regards,
        The TekVwarho Team
        """
        
        return await self.send_email(EmailMessage(
            to=[to_email],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        ))
    
    async def send_invoice_email(
        self,
        to_email: str,
        customer_name: str,
        invoice_number: str,
        amount: float,
        due_date: str,
        invoice_url: str,
    ) -> bool:
        """Send invoice to customer."""
        subject = f"Invoice {invoice_number} from TekVwarho"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #16a34a;">Invoice {invoice_number}</h1>
                <p>Dear {customer_name},</p>
                <p>Please find attached your invoice for ₦{amount:,.2f}.</p>
                <p><strong>Due Date:</strong> {due_date}</p>
                <p>
                    <a href="{invoice_url}" 
                       style="display: inline-block; background-color: #16a34a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                        View Invoice
                    </a>
                </p>
                <p>Thank you for your business.</p>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        Invoice {invoice_number}
        
        Dear {customer_name},
        
        Please find attached your invoice for ₦{amount:,.2f}.
        
        Due Date: {due_date}
        
        View your invoice: {invoice_url}
        
        Thank you for your business.
        """
        
        return await self.send_email(EmailMessage(
            to=[to_email],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        ))
    
    async def send_payment_confirmation(
        self,
        to_email: str,
        customer_name: str,
        invoice_number: str,
        amount: float,
        payment_date: str,
    ) -> bool:
        """Send payment confirmation to customer."""
        subject = f"Payment Received - Invoice {invoice_number}"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #16a34a;">Payment Received</h1>
                <p>Dear {customer_name},</p>
                <p>We have received your payment of ₦{amount:,.2f} for invoice {invoice_number}.</p>
                <p><strong>Payment Date:</strong> {payment_date}</p>
                <p>Thank you for your prompt payment.</p>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        Payment Received
        
        Dear {customer_name},
        
        We have received your payment of ₦{amount:,.2f} for invoice {invoice_number}.
        
        Payment Date: {payment_date}
        
        Thank you for your prompt payment.
        """
        
        return await self.send_email(EmailMessage(
            to=[to_email],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        ))
    
    async def send_overdue_reminder(
        self,
        to_email: str,
        customer_name: str,
        invoice_number: str,
        amount: float,
        days_overdue: int,
        invoice_url: str,
    ) -> bool:
        """Send overdue invoice reminder to customer."""
        subject = f"Payment Reminder - Invoice {invoice_number} ({days_overdue} days overdue)"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #dc2626;">Payment Reminder</h1>
                <p>Dear {customer_name},</p>
                <p>This is a friendly reminder that invoice {invoice_number} for ₦{amount:,.2f} is now <strong>{days_overdue} days overdue</strong>.</p>
                <p>Please arrange for payment at your earliest convenience.</p>
                <p>
                    <a href="{invoice_url}" 
                       style="display: inline-block; background-color: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                        View Invoice & Pay
                    </a>
                </p>
                <p>If you have already made payment, please disregard this reminder.</p>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        Payment Reminder
        
        Dear {customer_name},
        
        This is a friendly reminder that invoice {invoice_number} for ₦{amount:,.2f} is now {days_overdue} days overdue.
        
        Please arrange for payment at your earliest convenience.
        
        View invoice: {invoice_url}
        
        If you have already made payment, please disregard this reminder.
        """
        
        return await self.send_email(EmailMessage(
            to=[to_email],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        ))
    
    async def send_vat_reminder(
        self,
        to_email: str,
        business_name: str,
        period: str,
        deadline: str,
        vat_amount: float,
    ) -> bool:
        """Send VAT filing reminder."""
        subject = f"VAT Filing Reminder - {period}"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #16a34a;">VAT Filing Reminder</h1>
                <p>Dear {business_name},</p>
                <p>This is a reminder that your VAT return for <strong>{period}</strong> is due on <strong>{deadline}</strong>.</p>
                <p>Estimated VAT payable: <strong>₦{vat_amount:,.2f}</strong></p>
                <p>
                    <a href="https://app.tekvwarho.com/reports?tab=tax" 
                       style="display: inline-block; background-color: #16a34a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                        View VAT Report
                    </a>
                </p>
                <p>Don't forget to file on time to avoid penalties.</p>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        VAT Filing Reminder
        
        Dear {business_name},
        
        This is a reminder that your VAT return for {period} is due on {deadline}.
        
        Estimated VAT payable: ₦{vat_amount:,.2f}
        
        View VAT report: https://app.tekvwarho.com/reports?tab=tax
        
        Don't forget to file on time to avoid penalties.
        """
        
        return await self.send_email(EmailMessage(
            to=[to_email],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        ))
    
    async def send_password_reset(
        self,
        to_email: str,
        reset_url: str,
    ) -> bool:
        """Send password reset email."""
        subject = "Reset Your Password - TekVwarho ProAudit"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #16a34a;">Reset Your Password</h1>
                <p>You requested to reset your password. Click the button below to set a new password:</p>
                <p>
                    <a href="{reset_url}" 
                       style="display: inline-block; background-color: #16a34a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                        Reset Password
                    </a>
                </p>
                <p>This link will expire in 1 hour.</p>
                <p>If you didn't request this, you can safely ignore this email.</p>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        Reset Your Password
        
        You requested to reset your password. Visit the link below to set a new password:
        
        {reset_url}
        
        This link will expire in 1 hour.
        
        If you didn't request this, you can safely ignore this email.
        """
        
        return await self.send_email(EmailMessage(
            to=[to_email],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        ))
