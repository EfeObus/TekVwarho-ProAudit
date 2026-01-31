#!/usr/bin/env python3
"""
Reset superadmin password on Railway database.
Uses the same password hashing as the app to ensure compatibility.
"""

import psycopg2
from passlib.context import CryptContext

DATABASE_URL = "postgresql://postgres:eKFYCXhJUxqIFcXQjZnLmZlQBBNEbsNy@turntable.proxy.rlwy.net:28165/railway"

# Use the EXACT same hashing configuration as the app
pwd_context = CryptContext(
    schemes=["bcrypt"], 
    deprecated="auto",
    bcrypt__truncate_error=False
)

def reset_superadmin_password():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    password = "SuperAdmin@TekVwarho2026!"
    
    # Hash the password using passlib (same as app)
    truncated_password = password[:72] if password else password
    new_hash = pwd_context.hash(truncated_password)
    
    print(f"New password hash: {new_hash[:50]}...")
    
    # Update the superadmin password
    cursor.execute(
        "UPDATE users SET hashed_password = %s WHERE email = %s RETURNING email",
        (new_hash, "superadmin@tekvwarho.com")
    )
    
    result = cursor.fetchone()
    if result:
        conn.commit()
        print(f"✅ Password reset for: {result[0]}")
        
        # Verify it works
        cursor.execute(
            "SELECT hashed_password FROM users WHERE email = %s",
            ("superadmin@tekvwarho.com",)
        )
        stored_hash = cursor.fetchone()[0]
        
        verify_result = pwd_context.verify(truncated_password, stored_hash)
        print(f"✅ Verification test: {verify_result}")
    else:
        print("❌ User not found!")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    reset_superadmin_password()
