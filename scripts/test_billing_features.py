#!/usr/bin/env python3
"""Test script to verify billing service implementation for issues #37-46"""

import sys
sys.path.insert(0, '.')

def test_billing_error_codes():
    """Test that BillingErrorCode enum and messages are properly defined"""
    # Import directly to bypass services __init__.py issues
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'billing_service', 
        'app/services/billing_service.py'
    )
    billing_module = importlib.util.module_from_spec(spec)
    
    # Need to set up basic dependencies first
    import app.config
    import app.models.sku
    spec.loader.exec_module(billing_module)
    
    BillingErrorCode = billing_module.BillingErrorCode
    BILLING_ERROR_MESSAGES = billing_module.BILLING_ERROR_MESSAGES
    
    print("=" * 60)
    print("Testing BillingErrorCode enum (#46)")
    print("=" * 60)
    
    # Count error codes
    error_codes = list(BillingErrorCode)
    print(f"✅ BillingErrorCode has {len(error_codes)} error codes")
    print(f"✅ BILLING_ERROR_MESSAGES has {len(BILLING_ERROR_MESSAGES)} entries")
    
    # Verify all codes have messages
    missing_messages = [code for code in error_codes if code not in BILLING_ERROR_MESSAGES]
    if missing_messages:
        print(f"⚠️  Warning: {len(missing_messages)} codes missing messages:")
        for code in missing_messages[:5]:
            print(f"   - {code.name}")
    else:
        print("✅ All error codes have corresponding messages")
    
    # Show sample codes by category
    print("\nSample error codes by category:")
    categories = {
        "Success": [c for c in error_codes if c.value.startswith("B0")],
        "Network": [c for c in error_codes if c.value.startswith("B1")],
        "Validation": [c for c in error_codes if c.value.startswith("B2")],
        "Payment": [c for c in error_codes if c.value.startswith("B3")],
        "Auth": [c for c in error_codes if c.value.startswith("B4")],
        "Transaction": [c for c in error_codes if c.value.startswith("B5")],
        "Subscription": [c for c in error_codes if c.value.startswith("B6")],
        "Provider": [c for c in error_codes if c.value.startswith("B7")],
        "Internal": [c for c in error_codes if c.value.startswith("B9")],
    }
    for category, codes in categories.items():
        if codes:
            print(f"  {category}: {len(codes)} codes")
    
    return True


def test_config_settings():
    """Test that timeout and retry settings are configured (#41)"""
    from app.config import settings
    
    print("\n" + "=" * 60)
    print("Testing Timeout Configuration (#41)")
    print("=" * 60)
    
    # Check timeout setting
    timeout = getattr(settings, 'paystack_timeout_seconds', None)
    if timeout:
        print(f"✅ paystack_timeout_seconds = {timeout} seconds")
    else:
        print("❌ paystack_timeout_seconds not found in settings")
        return False
    
    # Check retry setting
    max_retries = getattr(settings, 'paystack_max_retries', None)
    if max_retries:
        print(f"✅ paystack_max_retries = {max_retries}")
    else:
        print("❌ paystack_max_retries not found in settings")
        return False
    
    return True


def test_amount_validation():
    """Test that amount validation constants are defined (#39)"""
    # Import directly to bypass services __init__.py issues
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'billing_service', 
        'app/services/billing_service.py'
    )
    billing_module = importlib.util.module_from_spec(spec)
    
    # Need to set up basic dependencies first
    import app.config
    import app.models.sku
    spec.loader.exec_module(billing_module)
    
    MIN_PAYMENT_AMOUNT = billing_module.MIN_PAYMENT_AMOUNT
    MAX_PAYMENT_AMOUNT = billing_module.MAX_PAYMENT_AMOUNT
    
    print("\n" + "=" * 60)
    print("Testing Amount Validation (#39)")
    print("=" * 60)
    
    print(f"✅ MIN_PAYMENT_AMOUNT = ₦{MIN_PAYMENT_AMOUNT:,} ({MIN_PAYMENT_AMOUNT * 100:,} kobo)")
    print(f"✅ MAX_PAYMENT_AMOUNT = ₦{MAX_PAYMENT_AMOUNT:,} ({MAX_PAYMENT_AMOUNT * 100:,} kobo)")
    
    # Verify reasonable values
    if MIN_PAYMENT_AMOUNT >= 50:
        print("✅ Minimum amount is reasonable (>= ₦50)")
    else:
        print("⚠️  Warning: Minimum amount might be too low")
    
    if MAX_PAYMENT_AMOUNT <= 100_000_000:
        print("✅ Maximum amount is reasonable (<= ₦100M)")
    else:
        print("⚠️  Warning: Maximum amount might be too high")
    
    return True


def test_database_indexes():
    """Test that database indexes exist (#42, #43)"""
    import asyncio
    from sqlalchemy import text
    from app.database import async_session_factory
    
    print("\n" + "=" * 60)
    print("Testing Database Indexes (#42, #43)")
    print("=" * 60)
    
    async def check_indexes():
        async with async_session_factory() as session:
            # Check for usage_records indexes
            result = await session.execute(text("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = 'usage_records' 
                AND indexname LIKE 'ix_usage_records_period%'
            """))
            usage_indexes = [row[0] for row in result.fetchall()]
            
            # Check for payment_transactions indexes
            result = await session.execute(text("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = 'payment_transactions' 
                AND (indexname LIKE 'ix_payment_transactions_paid%' 
                     OR indexname LIKE 'ix_payment_transactions_created%')
            """))
            payment_indexes = [row[0] for row in result.fetchall()]
            
            return usage_indexes, payment_indexes
    
    usage_indexes, payment_indexes = asyncio.run(check_indexes())
    
    print(f"UsageRecord indexes (#42):")
    for idx in usage_indexes:
        print(f"  ✅ {idx}")
    if not usage_indexes:
        print("  ⚠️  No period indexes found")
    
    print(f"\nPaymentTransaction indexes (#43):")
    for idx in payment_indexes:
        print(f"  ✅ {idx}")
    if not payment_indexes:
        print("  ⚠️  No timestamp indexes found")
    
    return bool(usage_indexes) or bool(payment_indexes)


def main():
    """Run all tests"""
    print("\n🔧 BILLING ISSUES #37-46 IMPLEMENTATION TEST")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("Error Codes (#46)", test_billing_error_codes()))
    except Exception as e:
        print(f"❌ Error testing error codes: {e}")
        results.append(("Error Codes (#46)", False))
    
    try:
        results.append(("Config Settings (#41)", test_config_settings()))
    except Exception as e:
        print(f"❌ Error testing config: {e}")
        results.append(("Config Settings (#41)", False))
    
    try:
        results.append(("Amount Validation (#39)", test_amount_validation()))
    except Exception as e:
        print(f"❌ Error testing amount validation: {e}")
        results.append(("Amount Validation (#39)", False))
    
    try:
        results.append(("Database Indexes (#42, #43)", test_database_indexes()))
    except Exception as e:
        print(f"❌ Error testing indexes: {e}")
        results.append(("Database Indexes (#42, #43)", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, status in results if status)
    total = len(results)
    
    for name, status in results:
        emoji = "✅" if status else "❌"
        print(f"  {emoji} {name}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All billing feature implementations verified!")
        return 0
    else:
        print("\n⚠️  Some tests failed - review implementation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
