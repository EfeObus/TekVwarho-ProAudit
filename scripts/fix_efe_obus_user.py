#!/usr/bin/env python3
"""
Fix efeobukohwo64@gmail.com user - should be org owner, not platform admin.
"""

import psycopg2
import uuid

DATABASE_URL = 'postgresql://postgres:eKFYCXhJUxqIFcXQjZnLmZlQBBNEbsNy@turntable.proxy.rlwy.net:28165/railway'

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Create the Efe Obus Furniture organization
    org_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO organizations (id, name, slug, organization_type, email, phone, subscription_tier, verification_status, is_emergency_suspended)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
    print(f'✅ Created organization: Efe Obus Furniture Manufacturing LTD')
    print(f'   ID: {org_id}')
    
    # Update the user to be an OWNER of this organization
    cursor.execute("""
        UPDATE users 
        SET role = 'OWNER',
            is_platform_staff = false,
            platform_role = NULL,
            organization_id = %s,
            is_superuser = false
        WHERE email = %s
        RETURNING email
    """, (org_id, 'efeobukohwo64@gmail.com'))
    
    result = cursor.fetchone()
    if result:
        print(f'✅ Updated user efeobukohwo64@gmail.com:')
        print(f'   role: OWNER')
        print(f'   is_platform_staff: false')
        print(f'   organization_id: {org_id}')
    
    # Create a business entity for the organization
    entity_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO business_entities (
            id, organization_id, name, legal_name, tin, rc_number,
            address_line1, city, state, lga, country,
            email, phone, website,
            fiscal_year_start_month, currency, is_vat_registered,
            business_type, annual_turnover, fixed_assets_value,
            is_active
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s,
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
        'Plot 45, Industrial Layout, Agbor-Obi Road, Agbor',
        'Agbor', 'Delta', 'Ika South', 'Nigeria',
        'info@efeobusfurniture.com.ng', '+234 802 345 6789', 'https://efeobusfurniture.com.ng',
        1, 'NGN', True,
        'limited_company', 850000000.00, 450000000.00,
        True
    ))
    print(f'✅ Created business entity: Efe Obus Furniture Manufacturing LTD')
    print(f'   ID: {entity_id}')
    
    conn.commit()
    print('\n✅ All changes committed successfully!')
    print('\nUser efeobukohwo64@gmail.com can now login as OWNER of Efe Obus Furniture')
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
