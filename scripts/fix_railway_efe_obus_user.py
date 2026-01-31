#!/usr/bin/env python3
"""
Fix efeobukohwo64@gmail.com user in Railway database.
This user was incorrectly set as a platform SUPER_ADMIN but should be an organization OWNER.
"""

import psycopg2
import uuid
from passlib.context import CryptContext

# Railway Database URL
DATABASE_URL = 'postgresql://postgres:eKFYCXhJUxqIFcXQjZnLmZlQBBNEbsNy@turntable.proxy.rlwy.net:28165/railway'

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto', bcrypt__truncate_error=False)

def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("=" * 60)
    print("Fixing efeobukohwo64@gmail.com User")
    print("=" * 60)
    
    # Step 1: Check if Efe Obus Furniture organization already exists
    cursor.execute("""
        SELECT id, name FROM organizations 
        WHERE slug = 'efe-obus-furniture'
    """)
    existing_org = cursor.fetchone()
    
    if existing_org:
        org_id = str(existing_org[0])
        print(f"\n✅ Organization already exists: {existing_org[1]}")
        print(f"   ID: {org_id}")
    else:
        # Create the organization
        org_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO organizations (
                id, name, slug, organization_type, email, phone, 
                subscription_tier, verification_status, is_emergency_suspended
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            org_id,
            'Efe Obus Furniture Manufacturing LTD',
            'efe-obus-furniture',
            'CORPORATION',
            'info@efeobusfurniture.com.ng',
            '+234 802 345 6789',
            'ENTERPRISE',
            'VERIFIED',
            False
        ))
        print(f"\n✅ Created organization: Efe Obus Furniture Manufacturing LTD")
        print(f"   ID: {org_id}")
    
    # Step 2: Check if business entity exists
    cursor.execute("""
        SELECT id, name FROM business_entities 
        WHERE organization_id = %s
    """, (org_id,))
    existing_entity = cursor.fetchone()
    
    if existing_entity:
        entity_id = str(existing_entity[0])
        print(f"\n✅ Business entity already exists: {existing_entity[1]}")
        print(f"   ID: {entity_id}")
    else:
        # Create the business entity with all required fields
        entity_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO business_entities (
                id, organization_id, name, legal_name, tin, rc_number,
                address_line1, address_line2, city, state, lga, country,
                email, phone, website,
                fiscal_year_start_month, currency, is_vat_registered,
                vat_registration_date, annual_turnover_threshold,
                business_type, annual_turnover, fixed_assets_value,
                is_development_levy_exempt, b2c_realtime_reporting_enabled, b2c_reporting_threshold,
                is_active
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s
            )
            RETURNING id
        """, (
            entity_id, org_id,
            'Efe Obus Furniture Manufacturing LTD',
            'Efe Obus Furniture Manufacturing Limited',
            '12345678-0001', 'RC 1234567',
            'Plot 45, Industrial Layout', 'Agbor-Obi Road',
            'Agbor', 'Delta', 'Ika South', 'Nigeria',
            'info@efeobusfurniture.com.ng', '+234 802 345 6789', 'https://efeobusfurniture.com.ng',
            1, 'NGN', True,
            '2020-01-15', False,  # VAT registration date and annual_turnover_threshold (boolean)
            'LIMITED_COMPANY', 850000000.00, 450000000.00,
            False, True, 1000000.00,  # dev levy exempt, b2c reporting, b2c threshold
            True
        ))
        print(f"\n✅ Created business entity: Efe Obus Furniture Manufacturing LTD")
        print(f"   ID: {entity_id}")
    
    # Step 3: Update the user to be organization OWNER instead of platform SUPER_ADMIN
    # Also reset the password
    new_password_hash = hash_password('Efeobus12345')
    
    cursor.execute("""
        UPDATE users 
        SET role = 'OWNER',
            is_platform_staff = false,
            platform_role = NULL,
            organization_id = %s,
            is_superuser = false,
            hashed_password = %s
        WHERE email = %s
        RETURNING id, email
    """, (org_id, new_password_hash, 'efeobukohwo64@gmail.com'))
    
    result = cursor.fetchone()
    if result:
        print(f"\n✅ Updated user: efeobukohwo64@gmail.com")
        print(f"   ID: {result[0]}")
        print(f"   role: OWNER")
        print(f"   is_platform_staff: false")
        print(f"   platform_role: NULL")
        print(f"   organization_id: {org_id}")
        print(f"   password: Efeobus12345")
    else:
        print(f"\n❌ User efeobukohwo64@gmail.com not found!")
    
    # Step 4: Create TenantSKU for commercial feature gating if not exists
    cursor.execute("""
        SELECT id FROM tenant_skus WHERE organization_id = %s
    """, (org_id,))
    existing_sku = cursor.fetchone()
    
    if not existing_sku:
        sku_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO tenant_skus (
                id, organization_id, tier, intelligence_addon, billing_cycle,
                is_active, current_period_start, current_period_end, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE, CURRENT_DATE + INTERVAL '1 year', %s)
        """, (
            sku_id, org_id, 'ENTERPRISE', 'ADVANCED', 'annual', True,
            'Efe Obus Furniture Manufacturing LTD - Demo organization'
        ))
        print(f"\n✅ Created TenantSKU for organization")
    else:
        print(f"\n✅ TenantSKU already exists")
    
    conn.commit()
    
    print("\n" + "=" * 60)
    print("✅ ALL FIXES APPLIED SUCCESSFULLY!")
    print("=" * 60)
    print("\n📋 LOGIN CREDENTIALS:")
    print("-" * 60)
    print("  Email:    efeobukohwo64@gmail.com")
    print("  Password: Efeobus12345")
    print("  Role:     OWNER (Organization Owner)")
    print("  Company:  Efe Obus Furniture Manufacturing LTD")
    print("-" * 60)
    
    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
