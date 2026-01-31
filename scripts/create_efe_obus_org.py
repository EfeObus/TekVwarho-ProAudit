#!/usr/bin/env python3
"""Create Efe Obus Furniture org and assign user."""

import psycopg2
import uuid
from datetime import datetime

DATABASE_URL = 'postgresql://postgres:eKFYCXhJUxqIFcXQjZnLmZlQBBNEbsNy@turntable.proxy.rlwy.net:28165/railway'

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("Creating Efe Obus Furniture Organization...")
    now = datetime.utcnow()
    
    # Check if org already exists
    cursor.execute("SELECT id FROM organizations WHERE slug = 'efe-obus-furniture'")
    existing = cursor.fetchone()
    
    if existing:
        org_id = str(existing[0])
        print(f"Organization already exists with ID: {org_id}")
    else:
        # Create the org
        org_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO organizations (
                id, name, slug, email, phone,
                organization_type, subscription_tier, verification_status,
                is_emergency_suspended, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            RETURNING id, name
        """, (
            org_id,
            'Efe Obus Furniture Manufacturing LTD',
            'efe-obus-furniture',
            'efeobukohwo64@gmail.com',
            '+234-803-123-4567',
            'SME',
            'PROFESSIONAL',
            'VERIFIED',
            False,
            now,
            now
        ))
        result = cursor.fetchone()
        print(f"✅ Created organization: {result[1]} (ID: {result[0]})")
        org_id = str(result[0])
    
    # Check if business entity exists
    cursor.execute("SELECT id FROM business_entities WHERE organization_id = %s", (org_id,))
    existing_entity = cursor.fetchone()
    
    if existing_entity:
        entity_id = existing_entity[0]
        print(f"Business entity already exists with ID: {entity_id}")
    else:
        # Create business entity
        entity_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO business_entities (
                id, organization_id, name, country,
                fiscal_year_start_month, currency, is_vat_registered,
                annual_turnover_threshold, business_type, 
                is_development_levy_exempt, b2c_realtime_reporting_enabled, b2c_reporting_threshold,
                is_active, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            RETURNING id
        """, (
            entity_id,
            org_id,
            'Efe Obus Furniture',
            'Nigeria',
            1,  # fiscal_year_start_month
            'NGN',
            True,  # is_vat_registered
            False,  # annual_turnover_threshold
            'LIMITED_COMPANY',  # business_type
            False,  # is_development_levy_exempt
            False,  # b2c_realtime_reporting_enabled
            0,  # b2c_reporting_threshold
            True,  # is_active
            now,
            now
        ))
        entity_id = cursor.fetchone()[0]
        print(f"✅ Created business entity (ID: {entity_id})")
    
    # Update user to belong to this org
    cursor.execute("""
        UPDATE users 
        SET organization_id = %s
        WHERE email = 'efeobukohwo64@gmail.com'
        RETURNING email
    """, (org_id,))
    result = cursor.fetchone()
    print(f"✅ Updated user {result[0]} to new org")
    
    conn.commit()
    
    # Verify
    cursor.execute("""
        SELECT u.email, u.role, o.name
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE u.email = 'efeobukohwo64@gmail.com'
    """)
    result = cursor.fetchone()
    print(f"\n📋 Final state:")
    print(f"  User: {result[0]}")
    print(f"  Role: {result[1]}")
    print(f"  Organization: {result[2]}")
    
    cursor.close()
    conn.close()
    print("\n✅ All done!")

if __name__ == '__main__':
    main()
