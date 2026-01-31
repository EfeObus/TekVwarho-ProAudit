#!/usr/bin/env python3
"""Debug login issue on Railway - sync version."""

import psycopg2
from passlib.context import CryptContext

DATABASE_URL = "postgresql://postgres:eKFYCXhJUxqIFcXQjZnLmZlQBBNEbsNy@turntable.proxy.rlwy.net:28165/railway"

def check_user():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Check if superadmin exists
    cursor.execute("SELECT email, hashed_password, is_active, is_verified FROM users WHERE email = 'superadmin@tekvwarho.com'")
    row = cursor.fetchone()
    
    if row:
        email, hashed_password, is_active, is_verified = row
        print("User found!")
        print(f"  Email: {email}")
        print(f"  Hash: {hashed_password[:50]}...")
        print(f"  Is Active: {is_active}")
        print(f"  Is Verified: {is_verified}")
        
        # Now test password verification with passlib
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)
        
        password = "SuperAdmin@TekVwarho2026!"
        try:
            verify_result = pwd_context.verify(password, hashed_password)
            print(f"  Password verification: {verify_result}")
        except Exception as e:
            print(f"  Password verification error: {e}")
        
        # Also test with truncation (like the app does)
        truncated_password = password[:72] if password else password
        try:
            verify_truncated = pwd_context.verify(truncated_password, hashed_password)
            print(f"  Truncated password verification: {verify_truncated}")
        except Exception as e:
            print(f"  Truncated password verification error: {e}")
    else:
        print("User NOT found!")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_user()
