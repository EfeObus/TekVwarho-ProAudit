"""
Test script for FX fields validation
"""
from datetime import date
from uuid import uuid4

# Test 1: Invoice Model Fields
print("=" * 60)
print("TEST 1: Invoice Model FX Fields")
print("=" * 60)
from app.models.invoice import Invoice
fx_fields = [c for c in Invoice.__table__.columns.keys() if 'currency' in c or 'fx' in c or 'exchange' in c or 'functional' in c or 'revaluation' in c]
print(f"Invoice FX fields: {fx_fields}")
assert 'currency' in fx_fields, "Missing currency field"
assert 'exchange_rate' in fx_fields, "Missing exchange_rate field"
assert 'functional_total_amount' in fx_fields, "Missing functional_total_amount field"
assert 'realized_fx_gain_loss' in fx_fields, "Missing realized_fx_gain_loss field"
print("✅ Invoice model FX fields OK")

# Test 2: Transaction Model Fields
print("\n" + "=" * 60)
print("TEST 2: Transaction Model FX Fields")
print("=" * 60)
from app.models.transaction import Transaction
fx_fields = [c for c in Transaction.__table__.columns.keys() if 'currency' in c or 'fx' in c or 'exchange' in c or 'functional' in c or 'settlement' in c]
print(f"Transaction FX fields: {fx_fields}")
assert 'currency' in fx_fields, "Missing currency field"
assert 'exchange_rate' in fx_fields, "Missing exchange_rate field"
assert 'functional_total_amount' in fx_fields, "Missing functional_total_amount field"
assert 'settlement_exchange_rate' in fx_fields, "Missing settlement_exchange_rate field"
print("✅ Transaction model FX fields OK")

# Test 3: Invoice Schema Validation
print("\n" + "=" * 60)
print("TEST 3: Invoice Schema with FX Fields")
print("=" * 60)
from app.schemas.invoice import InvoiceCreateRequest, InvoiceLineItemCreate

invoice_data = {
    'invoice_date': date.today(),
    'due_date': date.today(),
    'currency': 'USD',
    'exchange_rate': 1550.50,
    'exchange_rate_source': 'CBN',
    'vat_treatment': 'standard',
    'line_items': [{'description': 'Test item', 'quantity': 1.0, 'unit_price': 100.0}]
}
invoice = InvoiceCreateRequest(**invoice_data)
print(f"Invoice: currency={invoice.currency}, rate={invoice.exchange_rate}, source={invoice.exchange_rate_source}")
assert invoice.currency == 'USD'
assert invoice.exchange_rate == 1550.50
print("✅ Invoice schema with FX fields OK")

# Test 4: Transaction Schema Validation
print("\n" + "=" * 60)
print("TEST 4: Transaction Schema with FX Fields")
print("=" * 60)
from app.schemas.transaction import TransactionCreateRequest

txn_data = {
    'transaction_type': 'expense',
    'date': date.today(),
    'currency': 'EUR',
    'exchange_rate': 1680.25,
    'exchange_rate_source': 'manual',
    'amount': 500.0,
    'description': 'Test EUR expense',
    'category_id': uuid4()
}
txn = TransactionCreateRequest(**txn_data)
print(f"Transaction: currency={txn.currency}, rate={txn.exchange_rate}, source={txn.exchange_rate_source}")
assert txn.currency == 'EUR'
assert txn.exchange_rate == 1680.25
print("✅ Transaction schema with FX fields OK")

# Test 5: Default values (NGN)
print("\n" + "=" * 60)
print("TEST 5: Default Values (NGN)")
print("=" * 60)
ngn_invoice = InvoiceCreateRequest(
    invoice_date=date.today(),
    due_date=date.today(),
    line_items=[{'description': 'NGN item', 'quantity': 1.0, 'unit_price': 50000.0}]
)
print(f"NGN Invoice: currency={ngn_invoice.currency}, rate={ngn_invoice.exchange_rate}")
assert ngn_invoice.currency == 'NGN'
assert ngn_invoice.exchange_rate is None  # Will be set to 1.0 by service
print("✅ Default NGN values OK")

print("\n" + "=" * 60)
print("ALL TESTS PASSED ✅")
print("=" * 60)
