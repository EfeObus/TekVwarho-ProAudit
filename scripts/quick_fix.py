#!/usr/bin/env python3
"""Quick fix for Railway database issues."""

import psycopg2
from passlib.context import CryptContext

DATABASE_URL = 'postgresql://postgres:eKFYCXhJUxqIFcXQjZnLmZlQBBNEbsNy@turntable.proxy.rlwy.net:28165/railway'

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto', bcrypt__truncate_error=False)

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # 1. Check current state
    print("=" * 60)
    print("CHECKING CURRENT STATE")
    print("=" * 60)
    
    cursor.execute("""
        SELECT u.email, u.role, u.is_platform_staff, u.platform_role, u.organization_id, o.name
        FROM users u
        LEFT JOIN organizations o ON u.organization_id = o.id
        WHERE u.email = 'efeobukohwo64@gmail.com'
    """)
    result = cursor.fetchone()
    print(f"User: {result[0]}")
    print(f"  role: {result[1]}")
    print(f"  is_platform_staff: {result[2]}")
    print(f"  platform_role: {result[3]}")
    print(f"  organization_id: {result[4]}")
    print(f"  org_name: {result[5]}")
    
    # Check if Efe Obus org exists
    cursor.execute("SELECT id, name FROM organizations WHERE slug = 'efe-obus-furniture'")
    org = cursor.fetchone()
    print(f"\nEfe Obus org: {org}")
    
    if org:
        org_id = str(org[0])
        print(f"\nUsing existing org: {org_id}")
    else:
        print("\nNo org found - need to check for orphan orgs")
        cursor.execute("SELECT id, name, slug FROM organizations WHERE name LIKE '%Efe%' OR name LIKE '%Obus%'")
        orgs = cursor.fetchall()
        for o in orgs:
            print(f"  Found: {o}")
    
    print("\n" + "=" * 60)
    print("FIXING USER")
    print("=" * 60)
    
    # If no org exists, get any org for Efe Obus or use Okonkwo's org temporarily
    if not org:
        cursor.execute("SELECT id FROM organizations WHERE slug = 'okonkwo-sons-trading'")
        org = cursor.fetchone()
        if org:
            org_id = str(org[0])
            print(f"Using Okonkwo org temporarily: {org_id}")
    else:
        org_id = str(org[0])
    
    # Fix the user - change from platform admin to org owner
    new_hash = pwd_context.hash('Efeobus12345')
    cursor.execute("""
        UPDATE users 
        SET role = 'OWNER',
            is_platform_staff = false,
            platform_role = NULL,
            organization_id = %s,
            is_superuser = false,
            hashed_password = %s
        WHERE email = 'efeobukohwo64@gmail.com'
        RETURNING email, role, is_platform_staff, organization_id
    """, (org_id, new_hash))
    
    result = cursor.fetchone()
    if result:
        print(f"Updated user: {result[0]}")
        print(f"  role: {result[1]}")
        print(f"  is_platform_staff: {result[2]}")
        print(f"  organization_id: {result[3]}")
    
    conn.commit()
    
    # Verify the fix
    print("\n" + "=" * 60)
    print("VERIFYING FIX")
    print("=" * 60)
    
    cursor.execute("""
        SELECT u.email, u.role, u.is_platform_staff, u.platform_role, o.name
        FROM users u
        LEFT JOIN organizations o ON u.organization_id = o.id
        WHERE u.email = 'efeobukohwo64@gmail.com'
    """)
    result = cursor.fetchone()
    print(f"User: {result[0]}")
    print(f"  role: {result[1]}")
    print(f"  is_platform_staff: {result[2]}")
    print(f"  platform_role: {result[3]}")
    print(f"  org_name: {result[4]}")
    
    cursor.close()
    conn.close()
    
    print("\n✅ Done!")

if __name__ == '__main__':
    main()
