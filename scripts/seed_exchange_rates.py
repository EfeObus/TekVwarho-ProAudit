"""
Seed Exchange Rates for Multi-Currency Billing Support

This script adds default exchange rates to the database for 
NGN, USD, EUR, and GBP currencies. Exchange rates are used
for billing display and currency conversion.
"""

import asyncio
from datetime import date
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import sys
import os
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


# Current exchange rates as of January 2026 (approximate)
# Base currency: NGN
EXCHANGE_RATES = [
    # NGN to foreign
    ("NGN", "USD", Decimal("0.00062")),   # 1 NGN = ~0.00062 USD
    ("NGN", "EUR", Decimal("0.00058")),   # 1 NGN = ~0.00058 EUR
    ("NGN", "GBP", Decimal("0.00049")),   # 1 NGN = ~0.00049 GBP
    ("NGN", "NGN", Decimal("1.0")),       # 1 NGN = 1 NGN
    # Foreign to NGN
    ("USD", "NGN", Decimal("1610.0")),    # 1 USD = ~1610 NGN
    ("EUR", "NGN", Decimal("1725.0")),    # 1 EUR = ~1725 NGN
    ("GBP", "NGN", Decimal("2040.0")),    # 1 GBP = ~2040 NGN
]


async def seed_exchange_rates():
    """Seed the exchange_rates table with default values."""
    engine = create_async_engine(settings.database_url_async)
    
    async with engine.begin() as conn:
        # Check current count
        result = await conn.execute(text("SELECT COUNT(*) FROM exchange_rates"))
        count = result.scalar()
        print(f"Current exchange rates count: {count}")
        
        if count > 0:
            # Delete existing to start fresh
            await conn.execute(text("DELETE FROM exchange_rates"))
            print("Cleared existing exchange rates")
        
        # Insert rates using simple INSERT with all required columns
        for from_currency, to_currency, rate in EXCHANGE_RATES:
            try:
                await conn.execute(
                    text("""
                        INSERT INTO exchange_rates 
                            (id, from_currency, to_currency, rate, is_billing_rate, rate_date, created_at, updated_at)
                        VALUES 
                            (:id, :from_curr, :to_curr, :rate, true, :rate_date, NOW(), NOW())
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "from_curr": from_currency,
                        "to_curr": to_currency,
                        "rate": float(rate),
                        "rate_date": date.today(),
                    }
                )
                print(f"  ✓ {from_currency} -> {to_currency}: {rate}")
            except Exception as e:
                print(f"  ✗ {from_currency} -> {to_currency}: {e}")
        
        # Verify final count
        result = await conn.execute(text("SELECT COUNT(*) FROM exchange_rates"))
        count = result.scalar()
        print(f"\nExchange rates after seeding: {count}")
        
        # Show all rates
        result = await conn.execute(
            text("SELECT from_currency, to_currency, rate, is_billing_rate FROM exchange_rates ORDER BY from_currency, to_currency")
        )
        print("\nAll exchange rates:")
        for row in result.fetchall():
            print(f"  {row[0]} -> {row[1]}: {row[2]} (billing: {row[3]})")
    
    await engine.dispose()
    print("\n✓ Exchange rates seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed_exchange_rates())
