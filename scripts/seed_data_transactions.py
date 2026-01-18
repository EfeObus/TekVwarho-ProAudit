"""
Seed Data: Transactions for Efe Obus Furniture Manufacturing LTD
=================================================================
Sample transactions including income, expenses, and invoices
"""

import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionType, WRENStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.category import Category


async def create_sample_transactions(
    session: AsyncSession,
    entity_id: uuid.UUID,
    categories: List[Category],
    customers: List,
    vendors: List,
    owner_id: uuid.UUID
):
    """Create sample transactions and invoices for the company."""
    
    # Separate categories by type
    income_categories = [c for c in categories if "INC" in (c.code or "")]
    expense_categories = [c for c in categories if "EXP" in (c.code or "")]
    
    # Create transactions for the past 12 months
    today = date(2026, 1, 10)  # Current date
    start_date = date(2025, 1, 1)  # Start from Jan 2025
    
    transactions_created = 0
    invoices_created = 0
    
    # =========================================================================
    # INCOME TRANSACTIONS & INVOICES
    # =========================================================================
    
    # Sample furniture sales data
    furniture_sales = [
        {"desc": "Executive 7-Seater Sofa Set", "amount": Decimal("1350000.00")},
        {"desc": "6-Seater Dining Set", "amount": Decimal("650000.00")},
        {"desc": "King Size Bed Frame", "amount": Decimal("480000.00")},
        {"desc": "Executive Desk", "amount": Decimal("480000.00")},
        {"desc": "Conference Table - 12 Seater", "amount": Decimal("850000.00")},
        {"desc": "Standard 5-Seater Sofa Set", "amount": Decimal("750000.00")},
        {"desc": "8-Seater Dining Set", "amount": Decimal("950000.00")},
        {"desc": "3-Door Wardrobe", "amount": Decimal("550000.00")},
        {"desc": "L-Shaped Staff Desk (5 units)", "amount": Decimal("875000.00")},
        {"desc": "Executive Chair - Leather (10 units)", "amount": Decimal("2200000.00")},
        {"desc": "TV Console - 6ft", "amount": Decimal("220000.00")},
        {"desc": "Center Table - Glass Top", "amount": Decimal("145000.00")},
        {"desc": "Visitor Chair (20 units)", "amount": Decimal("1300000.00")},
        {"desc": "Reception Counter", "amount": Decimal("520000.00")},
        {"desc": "Patio Set - 4 Seater", "amount": Decimal("350000.00")},
    ]
    
    # Generate monthly sales transactions
    current_date = start_date
    invoice_number = 1000
    
    while current_date <= today:
        # Generate 8-15 sales per month
        num_sales = random.randint(8, 15)
        
        for _ in range(num_sales):
            sale = random.choice(furniture_sales)
            customer = random.choice(customers)
            category = random.choice(income_categories) if income_categories else None
            
            # Random day within the month
            day = random.randint(1, 28)
            trans_date = date(current_date.year, current_date.month, day)
            
            if trans_date > today:
                continue
            
            # Calculate VAT (7.5%)
            subtotal = sale["amount"]
            vat_amount = (subtotal * Decimal("0.075")).quantize(Decimal("0.01"))
            total_amount = subtotal + vat_amount
            
            # Create invoice
            invoice_number += 1
            invoice = Invoice(
                entity_id=entity_id,
                invoice_number=f"INV-{invoice_number}",
                customer_id=customer.id,
                invoice_date=trans_date,
                due_date=trans_date + timedelta(days=30),
                subtotal=subtotal,
                vat_amount=vat_amount,
                discount_amount=Decimal("0.00"),
                total_amount=total_amount,
                amount_paid=total_amount,  # Assume paid
                vat_rate=Decimal("7.50"),
                status=InvoiceStatus.PAID,
            )
            session.add(invoice)
            invoices_created += 1
            
            # Create income transaction
            transaction = Transaction(
                entity_id=entity_id,
                transaction_type=TransactionType.INCOME,
                transaction_date=trans_date,
                amount=subtotal,
                vat_amount=vat_amount,
                wht_amount=Decimal("0.00"),
                total_amount=total_amount,
                description=f"Sale: {sale['desc']} to {customer.name}",
                reference=f"INV-{invoice_number}",
                category_id=category.id if category else None,
                wren_status=WRENStatus.COMPLIANT,
                created_by_id=owner_id,
            )
            session.add(transaction)
            transactions_created += 1
        
        # Move to next month
        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, 1)
        else:
            current_date = date(current_date.year, current_date.month + 1, 1)
    
    # =========================================================================
    # EXPENSE TRANSACTIONS
    # =========================================================================
    
    # Monthly recurring expenses
    monthly_expenses = [
        {"desc": "Electricity Bill - BEDC", "category_code": "EXP005", "amount_range": (800000, 1500000)},
        {"desc": "Diesel for Generator", "category_code": "EXP006", "amount_range": (500000, 900000)},
        {"desc": "MTN Business Internet & Phone", "category_code": "EXP014", "amount_range": (150000, 200000)},
        {"desc": "Security Services - Andela Security", "category_code": "EXP019", "amount_range": (350000, 400000)},
        {"desc": "Cleaning Services - CleanMax", "category_code": "EXP020", "amount_range": (180000, 220000)},
        {"desc": "Bank Charges - GTBank", "category_code": "EXP015", "amount_range": (45000, 85000)},
        {"desc": "Vehicle Fuel - Company Cars", "category_code": "EXP006", "amount_range": (250000, 400000)},
    ]
    
    # Raw material purchases (quarterly/monthly)
    material_purchases = [
        {"desc": "Mahogany Timber Purchase", "category_code": "EXP001", "amount_range": (8000000, 15000000)},
        {"desc": "Iroko Timber Purchase", "category_code": "EXP001", "amount_range": (5000000, 10000000)},
        {"desc": "Plywood Sheets (100 units)", "category_code": "EXP001", "amount_range": (1800000, 2500000)},
        {"desc": "MDF Boards (80 units)", "category_code": "EXP001", "amount_range": (1600000, 2200000)},
        {"desc": "Premium Leather (50 sqm)", "category_code": "EXP002", "amount_range": (1750000, 2500000)},
        {"desc": "Velvet Fabric (100 meters)", "category_code": "EXP002", "amount_range": (850000, 1200000)},
        {"desc": "Foam Purchase - High Density", "category_code": "EXP002", "amount_range": (2500000, 4000000)},
        {"desc": "Hardware Supplies - Hinges, Handles", "category_code": "EXP003", "amount_range": (500000, 900000)},
        {"desc": "Wood Varnish & Finishing Materials", "category_code": "EXP003", "amount_range": (600000, 1000000)},
    ]
    
    # Periodic expenses
    periodic_expenses = [
        {"desc": "Vehicle Maintenance - Service", "category_code": "EXP007", "amount_range": (150000, 350000), "frequency": 3},
        {"desc": "Equipment Maintenance - CNC Machine", "category_code": "EXP008", "amount_range": (500000, 1200000), "frequency": 4},
        {"desc": "Insurance Premium - Annual", "category_code": "EXP010", "amount_range": (2500000, 4000000), "frequency": 12},
        {"desc": "Legal & Professional Fees", "category_code": "EXP011", "amount_range": (500000, 1500000), "frequency": 6},
        {"desc": "Advertising - Social Media & Print", "category_code": "EXP012", "amount_range": (300000, 800000), "frequency": 2},
        {"desc": "Staff Training & Development", "category_code": "EXP018", "amount_range": (400000, 800000), "frequency": 4},
    ]
    
    # Create category lookup
    category_lookup = {c.code: c for c in categories if c.code}
    
    # Generate monthly recurring expenses
    current_date = start_date
    while current_date <= today:
        for expense in monthly_expenses:
            category = category_lookup.get(expense["category_code"])
            vendor = random.choice(vendors) if vendors else None
            
            amount = Decimal(str(random.randint(*expense["amount_range"])))
            vat_amount = (amount * Decimal("0.075")).quantize(Decimal("0.01"))
            total_amount = amount + vat_amount
            
            # Random day in the month
            day = random.randint(1, 28)
            trans_date = date(current_date.year, current_date.month, day)
            
            if trans_date > today:
                continue
            
            transaction = Transaction(
                entity_id=entity_id,
                transaction_type=TransactionType.EXPENSE,
                transaction_date=trans_date,
                amount=amount,
                vat_amount=vat_amount,
                wht_amount=Decimal("0.00"),
                total_amount=total_amount,
                description=expense["desc"],
                reference=f"EXP-{current_date.year}{current_date.month:02d}-{random.randint(100, 999)}",
                category_id=category.id if category else None,
                vendor_id=vendor.id if vendor else None,
                wren_status=WRENStatus.COMPLIANT,
                created_by_id=owner_id,
                wren_verified_by_id=owner_id,
                wren_verified_at=datetime.now(),
            )
            session.add(transaction)
            transactions_created += 1
        
        # Material purchases (2-3 per month)
        for _ in range(random.randint(2, 3)):
            expense = random.choice(material_purchases)
            category = category_lookup.get(expense["category_code"])
            vendor = random.choice(vendors) if vendors else None
            
            amount = Decimal(str(random.randint(*expense["amount_range"])))
            vat_amount = (amount * Decimal("0.075")).quantize(Decimal("0.01"))
            total_amount = amount + vat_amount
            
            day = random.randint(1, 28)
            trans_date = date(current_date.year, current_date.month, day)
            
            if trans_date > today:
                continue
            
            transaction = Transaction(
                entity_id=entity_id,
                transaction_type=TransactionType.EXPENSE,
                transaction_date=trans_date,
                amount=amount,
                vat_amount=vat_amount,
                wht_amount=Decimal("0.00"),
                total_amount=total_amount,
                description=expense["desc"],
                reference=f"PO-{current_date.year}{current_date.month:02d}-{random.randint(100, 999)}",
                category_id=category.id if category else None,
                vendor_id=vendor.id if vendor else None,
                wren_status=WRENStatus.COMPLIANT,
                created_by_id=owner_id,
                wren_verified_by_id=owner_id,
                wren_verified_at=datetime.now(),
            )
            session.add(transaction)
            transactions_created += 1
        
        # Move to next month
        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, 1)
        else:
            current_date = date(current_date.year, current_date.month + 1, 1)
    
    # Generate periodic expenses
    for expense in periodic_expenses:
        category = category_lookup.get(expense["category_code"])
        vendor = random.choice(vendors) if vendors else None
        frequency = expense.get("frequency", 1)
        
        # Calculate how many times this expense occurs
        months_range = 12  # Last 12 months
        occurrences = months_range // frequency
        
        for i in range(occurrences):
            month = (i * frequency) + 1
            if month > 12:
                month = month % 12 or 12
            
            amount = Decimal(str(random.randint(*expense["amount_range"])))
            vat_amount = (amount * Decimal("0.075")).quantize(Decimal("0.01"))
            total_amount = amount + vat_amount
            
            trans_date = date(2025, month, random.randint(1, 28))
            
            if trans_date > today:
                continue
            
            transaction = Transaction(
                entity_id=entity_id,
                transaction_type=TransactionType.EXPENSE,
                transaction_date=trans_date,
                amount=amount,
                vat_amount=vat_amount,
                wht_amount=Decimal("0.00"),
                total_amount=total_amount,
                description=expense["desc"],
                reference=f"EXP-{trans_date.year}{trans_date.month:02d}-{random.randint(100, 999)}",
                category_id=category.id if category else None,
                vendor_id=vendor.id if vendor else None,
                wren_status=WRENStatus.COMPLIANT,
                created_by_id=owner_id,
                wren_verified_by_id=owner_id,
                wren_verified_at=datetime.now(),
            )
            session.add(transaction)
            transactions_created += 1
    
    # =========================================================================
    # PAYROLL TRANSACTIONS (Monthly)
    # =========================================================================
    
    # Total monthly payroll (approximate based on employees)
    monthly_payroll = Decimal("12500000.00")  # ~12.5M NGN per month
    
    current_date = start_date
    while current_date <= today:
        # Salaries expense
        salary_category = category_lookup.get("EXP004")
        
        trans_date = date(current_date.year, current_date.month, 25)  # Pay day
        if trans_date > today:
            break
        
        transaction = Transaction(
            entity_id=entity_id,
            transaction_type=TransactionType.EXPENSE,
            transaction_date=trans_date,
            amount=monthly_payroll,
            vat_amount=Decimal("0.00"),
            wht_amount=Decimal("0.00"),
            total_amount=monthly_payroll,
            description=f"Monthly Payroll - {current_date.strftime('%B %Y')}",
            reference=f"PAY-{current_date.year}{current_date.month:02d}",
            category_id=salary_category.id if salary_category else None,
            wren_status=WRENStatus.COMPLIANT,
            created_by_id=owner_id,
            wren_verified_by_id=owner_id,
            wren_verified_at=datetime.now(),
        )
        session.add(transaction)
        transactions_created += 1
        
        # Move to next month
        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, 1)
        else:
            current_date = date(current_date.year, current_date.month + 1, 1)
    
    await session.flush()
    
    print(f"    Created {transactions_created} transactions")
    print(f"    Created {invoices_created} invoices")
