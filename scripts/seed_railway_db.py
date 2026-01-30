"""
TekVwarho ProAudit - Railway Database Seeder

Seeds the production Railway database with:
1. Super Admin user
2. Platform test staff
3. Two demo companies with full data
"""

import asyncio
import uuid
import random
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Railway Database URL
DATABASE_URL = "postgresql+asyncpg://postgres:eKFYCXhJUxqIFcXQjZnLmZlQBBNEbsNy@turntable.proxy.rlwy.net:28165/railway"

# Password hashing (bcrypt)
def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    import bcrypt
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


async def check_database_status(session: AsyncSession):
    """Check current database state."""
    print("\n📊 Current Database Status:")
    print("=" * 50)
    
    tables = [
        ("users", "Users"),
        ("organizations", "Organizations"),
        ("business_entities", "Business Entities"),
        ("tenant_skus", "Tenant SKUs"),
        ("transactions", "Transactions"),
        ("invoices", "Invoices"),
        ("inventory_items", "Inventory Items"),
        ("payroll_records", "Payroll Records"),
    ]
    
    for table, name in tables:
        try:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            print(f"  {name}: {count}")
            await session.commit()  # Commit after each successful query
        except Exception as e:
            await session.rollback()  # Rollback on error to clear failed transaction
            print(f"  {name}: Table not found or error")
    
    print("=" * 50)


async def seed_super_admin(session: AsyncSession):
    """Create the Super Admin user."""
    print("\n🔐 Creating Super Admin...")
    
    email = "superadmin@tekvwarho.com"
    
    # Check if exists
    result = await session.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": email}
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        print(f"  ✅ Super Admin already exists (ID: {existing})")
        return existing
    
    admin_id = str(uuid.uuid4())
    hashed_pw = hash_password("SuperAdmin@TekVwarho2026!")
    
    await session.execute(text("""
        INSERT INTO users (
            id, email, hashed_password, first_name, last_name,
            is_active, is_verified, is_superuser, is_platform_staff,
            platform_role, must_reset_password, is_invited_user, can_be_impersonated,
            created_at, updated_at
        ) VALUES (
            :id, :email, :password, 'Super', 'Admin',
            true, true, true, true,
            'SUPER_ADMIN', false, false, false,
            NOW(), NOW()
        )
    """), {
        "id": admin_id,
        "email": email,
        "password": hashed_pw
    })
    
    print(f"  ✅ Super Admin created: {email}")
    print(f"     Password: SuperAdmin@TekVwarho2026!")
    return admin_id


async def seed_platform_staff(session: AsyncSession):
    """Create platform test staff accounts."""
    print("\n👥 Creating Platform Staff...")
    
    staff = [
        {
            "email": "test.admin@tekvwarho.com",
            "password": "TestAdmin@2026!",
            "first_name": "Test",
            "last_name": "Admin",
            "platform_role": "ADMIN"
        },
        {
            "email": "it.dev@tekvwarho.com",
            "password": "ItDev@2026!",
            "first_name": "IT",
            "last_name": "Developer",
            "platform_role": "IT_DEVELOPER"
        },
        {
            "email": "support@tekvwarho.com",
            "password": "Support@2026!",
            "first_name": "Support",
            "last_name": "Staff",
            "platform_role": "CUSTOMER_SERVICE"
        }
    ]
    
    for s in staff:
        result = await session.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": s["email"]}
        )
        if result.scalar_one_or_none():
            print(f"  ⏭️  {s['email']} already exists")
            continue
        
        staff_id = str(uuid.uuid4())
        hashed_pw = hash_password(s["password"])
        
        await session.execute(text("""
            INSERT INTO users (
                id, email, hashed_password, first_name, last_name,
                is_active, is_verified, is_superuser, is_platform_staff,
                platform_role, must_reset_password, is_invited_user, can_be_impersonated,
                created_at, updated_at
            ) VALUES (
                :id, :email, :password, :first_name, :last_name,
                true, true, false, true,
                :platform_role, false, false, false,
                NOW(), NOW()
            )
        """), {
            "id": staff_id,
            "email": s["email"],
            "password": hashed_pw,
            "first_name": s["first_name"],
            "last_name": s["last_name"],
            "platform_role": s["platform_role"]
        })
        
        print(f"  ✅ Created: {s['email']} ({s['platform_role']})")


async def seed_platform_test_org(session: AsyncSession):
    """Create platform test organization."""
    print("\n🏢 Creating Platform Test Organization...")
    
    org_slug = "tekvwarho-platform-test"
    
    # Check if exists
    result = await session.execute(
        text("SELECT id FROM organizations WHERE slug = :slug"),
        {"slug": org_slug}
    )
    existing_org = result.scalar_one_or_none()
    
    if existing_org:
        print(f"  ✅ Platform Test Org already exists (ID: {existing_org})")
        return existing_org
    
    org_id = str(uuid.uuid4())
    
    await session.execute(text("""
        INSERT INTO organizations (
            id, name, slug, email, phone,
            organization_type, subscription_tier, verification_status,
            is_emergency_suspended, created_at, updated_at
        ) VALUES (
            :id, 'TekVwarho Platform Test', :slug, 'platform@tekvwarho.com', '+234 800 000 0000',
            'SME', 'PROFESSIONAL', 'VERIFIED',
            false, NOW(), NOW()
        )
    """), {"id": org_id, "slug": org_slug})
    
    print(f"  ✅ Platform Test Org created")
    return org_id


async def seed_demo_company(session: AsyncSession, company_config: dict, super_admin_id: str):
    """Create a demo company with full data."""
    print(f"\n🏪 Creating Demo Company: {company_config['name']}...")
    
    # Check if exists
    result = await session.execute(
        text("SELECT id FROM organizations WHERE slug = :slug"),
        {"slug": company_config["slug"]}
    )
    existing_org = result.scalar_one_or_none()
    
    if existing_org:
        print(f"  ⏭️  Company already exists (ID: {existing_org})")
        return existing_org
    
    # Create organization
    org_id = str(uuid.uuid4())
    await session.execute(text("""
        INSERT INTO organizations (
            id, name, slug, email, phone,
            organization_type, subscription_tier, verification_status,
            is_emergency_suspended, created_at, updated_at
        ) VALUES (
            :id, :name, :slug, :email, :phone,
            'SME', :tier, 'VERIFIED',
            false, NOW(), NOW()
        )
    """), {
        "id": org_id,
        "name": company_config["name"],
        "slug": company_config["slug"],
        "email": company_config["email"],
        "phone": company_config["phone"],
        "tier": company_config["subscription_tier"]
    })
    print(f"  ✅ Organization created (subscription_tier: {company_config['subscription_tier']})")
    
    # Create tenant_sku
    tenant_sku_id = str(uuid.uuid4())
    await session.execute(text("""
        INSERT INTO tenant_skus (
            id, organization_id, tier, billing_cycle,
            is_active, cancel_at_period_end, align_to_calendar_month,
            prorated_first_period, pause_credits_days, total_paused_days,
            pause_count_this_year, preferred_currency, created_at, updated_at
        ) VALUES (
            :id, :org_id, :tier, 'monthly',
            true, false, false,
            false, 0, 0,
            0, 'NGN', NOW(), NOW()
        )
    """), {
        "id": tenant_sku_id,
        "org_id": org_id,
        "tier": company_config["sku_tier"]
    })
    print(f"  ✅ Tenant SKU created (sku_tier: {company_config['sku_tier']})")
    
    # Create business entity
    entity_id = str(uuid.uuid4())
    await session.execute(text("""
        INSERT INTO business_entities (
            id, organization_id, name, country,
            business_type, fiscal_year_start_month, currency,
            is_vat_registered, annual_turnover_threshold,
            is_development_levy_exempt, b2c_realtime_reporting_enabled,
            b2c_reporting_threshold, is_active, created_at, updated_at
        ) VALUES (
            :id, :org_id, :name, 'Nigeria',
            'LIMITED_COMPANY', 1, 'NGN',
            false, false,
            false, false,
            25000000, true, NOW(), NOW()
        )
    """), {
        "id": entity_id,
        "org_id": org_id,
        "name": company_config["name"]
    })
    print(f"  ✅ Business Entity created")
    
    # Create admin user for the company
    admin = company_config["admin_user"]
    admin_id = str(uuid.uuid4())
    hashed_pw = hash_password(admin["password"])
    
    await session.execute(text("""
        INSERT INTO users (
            id, email, hashed_password, first_name, last_name, phone_number,
            organization_id, role, is_active, is_verified,
            is_superuser, is_platform_staff, must_reset_password, is_invited_user, can_be_impersonated,
            created_at, updated_at
        ) VALUES (
            :id, :email, :password, :first_name, :last_name, :phone,
            :org_id, 'ADMIN', true, true,
            false, false, false, false, false,
            NOW(), NOW()
        )
    """), {
        "id": admin_id,
        "email": admin["email"],
        "password": hashed_pw,
        "first_name": admin["first_name"],
        "last_name": admin["last_name"],
        "phone": admin["phone"],
        "org_id": org_id
    })
    print(f"  ✅ Admin user: {admin['email']} / {admin['password']}")
    
    # Create staff members
    for i, staff in enumerate(company_config.get("staff", [])[:5]):  # Limit to 5 for speed
        staff_id = str(uuid.uuid4())
        hashed_pw = hash_password("Staff@2024!")
        
        await session.execute(text("""
            INSERT INTO users (
                id, email, hashed_password, first_name, last_name,
                organization_id, role, is_active, is_verified,
                is_superuser, is_platform_staff, must_reset_password, is_invited_user, can_be_impersonated,
                created_at, updated_at
            ) VALUES (
                :id, :email, :password, :first_name, :last_name,
                :org_id, :role, true, true,
                false, false, false, false, false,
                NOW(), NOW()
            )
        """), {
            "id": staff_id,
            "email": staff["email"],
            "password": hashed_pw,
            "first_name": staff["first_name"],
            "last_name": staff["last_name"],
            "org_id": org_id,
            "role": staff.get("role", "VIEWER")
        })
    
    if company_config.get("staff"):
        print(f"  ✅ Created {min(5, len(company_config['staff']))} staff members")
    
    return org_id


# Demo company configurations
# Note: subscription_tier is the legacy enum (FREE, STARTER, PROFESSIONAL, ENTERPRISE)
#       sku_tier is the actual commercial tier (core, professional, enterprise)
CORE_COMPANY = {
    "name": "Okonkwo & Sons Trading",
    "slug": "okonkwo-sons-trading",
    "email": "info@okonkwotrading.com",
    "phone": "+234 802 345 6789",
    "subscription_tier": "STARTER",  # Legacy enum for organizations table
    "sku_tier": "core",              # Actual commercial tier for tenant_skus
    "location": {
        "address_line1": "45 Akpakpava Road",
        "address_line2": "Near First Bank",
        "city": "Benin City",
        "state": "Edo",
        "lga": "Oredo",
        "country": "Nigeria"
    },
    "business_type": "Trading & General Merchandise",
    "tin": "12345678-0001",
    "rc_number": "RC-BN-2018-001234",
    "admin_user": {
        "email": "admin@okonkwotrading.com",
        "password": "Okonkwo2024!",
        "first_name": "Chukwuemeka",
        "last_name": "Okonkwo",
        "phone": "+234 802 345 6789"
    },
    "staff": [
        {"first_name": "Osaze", "last_name": "Okonkwo", "email": "osaze@okonkwotrading.com", "role": "ACCOUNTANT"},
        {"first_name": "Ehi", "last_name": "Aigbe", "email": "ehi@okonkwotrading.com", "role": "VIEWER"},
        {"first_name": "Osamudiamen", "last_name": "Omoruyi", "email": "osamudiamen@okonkwotrading.com", "role": "VIEWER"},
    ]
}

PROFESSIONAL_COMPANY = {
    "name": "Lagos Prime Ventures Ltd",
    "slug": "lagos-prime-ventures",
    "email": "contact@lagosprime.com",
    "phone": "+234 812 987 6543",
    "subscription_tier": "PROFESSIONAL",  # Legacy enum for organizations table
    "sku_tier": "professional",           # Actual commercial tier for tenant_skus
    "location": {
        "address_line1": "12 Addo Road",
        "address_line2": "Abraham Adesanya Estate",
        "city": "Ajah",
        "state": "Lagos",
        "lga": "Eti-Osa",
        "country": "Nigeria"
    },
    "business_type": "Technology & Consulting Services",
    "tin": "98765432-0001",
    "rc_number": "RC-LG-2015-005678",
    "admin_user": {
        "email": "admin@lagosprime.com",
        "password": "LagosPrime2024!",
        "first_name": "Adebayo",
        "last_name": "Fashola",
        "phone": "+234 812 987 6543"
    },
    "staff": [
        {"first_name": "Tolulope", "last_name": "Adeyemi", "email": "tolu@lagosprime.com", "role": "ACCOUNTANT"},
        {"first_name": "Chidinma", "last_name": "Okoro", "email": "chidinma@lagosprime.com", "role": "VIEWER"},
        {"first_name": "Oluwaseun", "last_name": "Bakare", "email": "seun@lagosprime.com", "role": "VIEWER"},
    ]
}


async def main():
    """Main seeding function."""
    print("=" * 60)
    print("🚀 TekVwarho ProAudit - Railway Database Seeder")
    print("=" * 60)
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Check current status
            await check_database_status(session)
            
            # Seed data
            super_admin_id = await seed_super_admin(session)
            await session.commit()
            
            await seed_platform_staff(session)
            await session.commit()
            
            await seed_platform_test_org(session)
            await session.commit()
            
            await seed_demo_company(session, CORE_COMPANY, super_admin_id)
            await session.commit()
            
            await seed_demo_company(session, PROFESSIONAL_COMPANY, super_admin_id)
            await session.commit()
            
            # Final status
            print("\n" + "=" * 60)
            print("✅ DATABASE SEEDING COMPLETE!")
            print("=" * 60)
            
            await check_database_status(session)
            
            print("\n📝 Login Credentials:")
            print("-" * 50)
            print("SUPER ADMIN:")
            print("  Email: superadmin@tekvwarho.com")
            print("  Password: SuperAdmin@TekVwarho2026!")
            print("")
            print("DEMO COMPANIES:")
            print("  Okonkwo & Sons: admin@okonkwotrading.com / Okonkwo2024!")
            print("  Lagos Prime: admin@lagosprime.com / LagosPrime2024!")
            print("-" * 50)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await session.rollback()
            raise
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
