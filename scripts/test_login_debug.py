#!/usr/bin/env python3
"""Debug login issue on Railway."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://postgres:eKFYCXhJUxqIFcXQjZnLmZlQBBNEbsNy@turntable.proxy.rlwy.net:28165/railway"

async def check_user():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Check if superadmin exists
        result = await session.execute(
            text("SELECT email, hashed_password, is_active, is_verified FROM users WHERE email = 'superadmin@tekvwarho.com'")
        )
        row = result.first()
        if row:
            print("User found!")
            print(f"  Email: {row.email}")
            print(f"  Hash: {row.hashed_password[:50]}...")
            print(f"  Is Active: {row.is_active}")
            print(f"  Is Verified: {row.is_verified}")
            
            # Now test password verification with passlib
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)
            
            password = "SuperAdmin@TekVwarho2026!"
            verify_result = pwd_context.verify(password, row.hashed_password)
            print(f"  Password verification: {verify_result}")
            
            # Also test with truncation (like the app does)
            truncated_password = password[:72] if password else password
            verify_truncated = pwd_context.verify(truncated_password, row.hashed_password)
            print(f"  Truncated password verification: {verify_truncated}")
        else:
            print("User NOT found!")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_user())
