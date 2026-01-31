#!/usr/bin/env python3
"""
Test authentication directly against the Railway deployment.
This simulates what happens when you call the login API.
"""

import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy import select

# Railway Database URL
DATABASE_URL = "postgresql+asyncpg://postgres:eKFYCXhJUxqIFcXQjZnLmZlQBBNEbsNy@turntable.proxy.rlwy.net:28165/railway"

async def test_auth():
    """Test the full authentication flow"""
    
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print("\n" + "="*60)
        print("TESTING AUTHENTICATION FLOW")
        print("="*60)
        
        # Import the models
        from app.models.user import User, UserEntityAccess
        
        # Test 1: Can we fetch the user with relationships?
        print("\n[1] Fetching user with relationships...")
        try:
            result = await session.execute(
                select(User)
                .options(
                    selectinload(User.organization),
                    selectinload(User.entity_access).selectinload(UserEntityAccess.entity)
                )
                .where(User.email == "superadmin@tekvwarho.com")
            )
            user = result.scalar_one_or_none()
            
            if user:
                print(f"   ✅ User found: {user.email}")
                print(f"      ID: {user.id}")
                print(f"      Organization ID: {user.organization_id}")
                print(f"      Is Active: {user.is_active}")
                print(f"      Is Verified: {user.is_verified}")
                print(f"      Is Platform Staff: {user.is_platform_staff}")
                print(f"      Platform Role: {user.platform_role}")
                print(f"      Role: {user.role}")
            else:
                print("   ❌ User NOT found!")
                return
        except Exception as e:
            print(f"   ❌ Error fetching user: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Test 2: Password verification
        print("\n[2] Testing password verification...")
        from app.utils.security import verify_password
        
        password = "SuperAdmin@TekVwarho2026!"
        try:
            result = verify_password(password, user.hashed_password)
            print(f"   Password verification result: {result}")
            if result:
                print("   ✅ Password is correct!")
            else:
                print("   ❌ Password is INCORRECT!")
        except Exception as e:
            print(f"   ❌ Error verifying password: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Test 3: Token creation
        print("\n[3] Testing token creation...")
        from app.services.auth_service import AuthService
        
        auth_service = AuthService(session)
        try:
            tokens = auth_service.create_tokens(user)
            print(f"   ✅ Tokens created successfully!")
            print(f"      Access Token (first 50 chars): {tokens['access_token'][:50]}...")
            print(f"      Token Type: {tokens['token_type']}")
        except Exception as e:
            print(f"   ❌ Error creating tokens: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Test 4: Audit logging
        print("\n[4] Testing audit logging...")
        from app.services.audit_service import AuditService
        from app.models.audit_consolidated import AuditAction
        from datetime import datetime
        
        audit_service = AuditService(session)
        try:
            await audit_service.log_action(
                business_entity_id=user.organization_id if user.organization_id else user.id,
                entity_type="user",
                entity_id=str(user.id),
                action=AuditAction.LOGIN,
                user_id=user.id,
                new_values={
                    "email": user.email,
                    "ip_address": "127.0.0.1",
                    "user_agent": "test-script",
                    "login_time": str(datetime.utcnow()),
                },
                ip_address="127.0.0.1",
                user_agent="test-script",
            )
            print("   ✅ Audit log created successfully!")
        except Exception as e:
            print(f"   ❌ Error creating audit log: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED! Authentication should work.")
        print("="*60)
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_auth())
