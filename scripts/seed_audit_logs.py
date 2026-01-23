"""
Seed Audit Logs for Testing Vault Features.
Creates sample audit log entries across multiple fiscal years.
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import async_session_maker

# Entity ID for Efe Obu's Furniture Company
ENTITY_ID = "453f0f12-202a-48b2-8c72-91526deeee56"
ORG_ID = "b3345541-b9cf-4686-a41b-3fe4bf699bf3"
USER_ID = "1839e254-0d36-456c-8bff-34f12b207bd1"
USER_EMAIL = "admin@efeobu.com"  # User email for audit logs

# Document types for audit logs (map to table_name)
TABLE_NAMES = [
    "invoices", "receipts", "transactions", "tax_filings",
    "nrs_submissions", "credit_notes", "fixed_assets",
    "payroll_runs", "bank_statements", "documents"
]

# Map document types to target_entity_type
DOCUMENT_TYPE_MAP = {
    "invoices": "invoice",
    "receipts": "receipt", 
    "transactions": "transaction",
    "tax_filings": "tax_filing",
    "nrs_submissions": "nrs_submission",
    "credit_notes": "credit_note",
    "fixed_assets": "fixed_asset",
    "payroll_runs": "payroll",
    "bank_statements": "bank_statement",
    "documents": "supporting_doc"
}

# Actions
ACTIONS = ["create", "update", "delete", "submit", "approve", "reject"]

# Sample descriptions by table name
DESCRIPTIONS = {
    "invoices": ["Invoice #{} created", "Invoice #{} updated with new items", "Invoice #{} voided", "Invoice #{} submitted to NRS"],
    "receipts": ["Receipt #{} recorded", "Receipt #{} modified", "Receipt #{} cancelled", "Receipt #{} attached to transaction"],
    "transactions": ["Transaction #{} recorded", "Transaction #{} reconciled", "Transaction #{} updated", "Transaction #{} deleted"],
    "tax_filings": ["VAT return #{} filed", "Withholding tax #{} submitted", "Tax filing #{} amended", "Tax assessment #{} responded"],
    "nrs_submissions": ["NRS invoice #{} submitted", "NRS credit note #{} submitted", "NRS submission #{} acknowledged"],
    "credit_notes": ["Credit note #{} issued", "Credit note #{} applied", "Credit note #{} modified"],
    "fixed_assets": ["Asset #{} registered", "Asset #{} depreciated", "Asset #{} disposed", "Asset #{} revalued"],
    "payroll_runs": ["Payroll #{} processed", "Salary slip #{} generated", "Payroll #{} approved", "Payroll adjustment #{}"],
    "bank_statements": ["Bank statement #{} imported", "Bank reconciliation #{} completed", "Statement #{} matched"],
    "documents": ["Document #{} attached", "Document #{} verified", "Document #{} replaced"]
}

# Sample old/new values for different table types
def generate_values(table_name, is_old=False):
    if table_name == "invoices":
        return {
            "amount": random.randint(10000, 500000) if not is_old else random.randint(10000, 500000),
            "customer": f"Customer {random.randint(1, 100)}",
            "status": "draft" if is_old else random.choice(["approved", "submitted", "paid"]),
            "vat_amount": random.randint(750, 37500),
            "items_count": random.randint(1, 10)
        }
    elif table_name == "transactions":
        return {
            "debit_account": f"{random.randint(1000, 9999)}",
            "credit_account": f"{random.randint(1000, 9999)}",
            "amount": random.randint(5000, 1000000),
            "reference": f"TXN-{random.randint(10000, 99999)}"
        }
    elif table_name == "payroll_runs":
        return {
            "employee_count": random.randint(5, 50),
            "gross_salary": random.randint(500000, 5000000),
            "net_salary": random.randint(400000, 4500000),
            "tax_deducted": random.randint(50000, 500000),
            "period": random.choice(["January 2024", "February 2024", "March 2024"])
        }
    elif table_name == "tax_filings":
        return {
            "tax_type": random.choice(["VAT", "WHT", "CIT", "PAYE"]),
            "tax_period": random.choice(["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"]),
            "tax_amount": random.randint(10000, 1000000),
            "status": "pending" if is_old else random.choice(["submitted", "acknowledged", "paid"])
        }
    else:
        return {
            "status": "draft" if is_old else "active",
            "amount": random.randint(1000, 100000)
        }


def generate_nrs_response():
    """Generate a sample NRS response."""
    irn = f"NIG{random.randint(100000000000, 999999999999)}"
    return {
        "irn": irn,
        "cryptographic_stamp": f"SHA256:{uuid.uuid4().hex}",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "acknowledged",
        "submission_id": str(uuid.uuid4())
    }


async def seed_audit_logs():
    """Seed audit logs across multiple fiscal years."""
    async with async_session_maker() as db:
        # Check if logs already exist
        result = await db.execute(
            text("SELECT COUNT(*) FROM audit_logs WHERE entity_id = :entity_id"),
            {"entity_id": ENTITY_ID}
        )
        existing_count = result.scalar()
        
        if existing_count > 0:
            print(f"[WARNING]  Found {existing_count} existing audit logs for entity. Skipping seed.")
            return
        
        print("🌱 Seeding audit logs...")
        
        # Generate logs across 5 fiscal years (2020-2025)
        logs_created = 0
        
        # Generate ~750 logs spread across 6 years
        for year in range(2020, 2026):
            # More logs in recent years
            num_logs = 50 + (year - 2020) * 30  # 50, 80, 110, 140, 170, 200
            
            for i in range(num_logs):
                table_name = random.choice(TABLE_NAMES)
                action = random.choice(ACTIONS)
                
                # Random date within the year
                days_offset = random.randint(0, 364)
                created_at = datetime(year, 1, 1) + timedelta(days=days_offset)
                
                # Generate ID for the record
                record_id = str(uuid.uuid4())
                target_entity_id = record_id  # Same as record_id
                target_entity_type = DOCUMENT_TYPE_MAP.get(table_name, table_name)
                
                # Get description
                desc_template = random.choice(DESCRIPTIONS.get(table_name, ["Item #{} processed"]))
                description = desc_template.format(random.randint(1000, 9999))
                
                # Generate values
                old_values = generate_values(table_name, is_old=True) if action in ["update", "delete"] else None
                new_values = generate_values(table_name, is_old=False) if action in ["create", "update"] else None
                
                # Calculate changes for updates
                changes = None
                if action == "update" and old_values and new_values:
                    changes = {
                        k: {"old": old_values.get(k), "new": new_values.get(k)}
                        for k in set(old_values.keys()) | set(new_values.keys())
                        if old_values.get(k) != new_values.get(k)
                    }
                
                # NRS data for nrs_submission type
                nrs_irn = None
                nrs_response = None
                if table_name == "nrs_submissions" or (table_name == "invoices" and random.random() > 0.5):
                    nrs_response = generate_nrs_response()
                    nrs_irn = nrs_response["irn"]
                
                # Device fingerprint
                device_fp = f"fp_{uuid.uuid4().hex[:16]}"
                
                # Convert dicts to JSON strings
                import json
                old_values_json = json.dumps(old_values) if old_values else None
                new_values_json = json.dumps(new_values) if new_values else None
                changes_json = json.dumps(changes) if changes else None
                nrs_response_json = json.dumps(nrs_response) if nrs_response else None
                geo_location_json = json.dumps({"country": "Nigeria", "city": random.choice(["Lagos", "Abuja", "Port Harcourt", "Kano"])})
                
                # Insert the log using the actual table schema
                await db.execute(
                    text("""
                        INSERT INTO audit_logs (
                            id, entity_id, organization_id, user_id, user_email, action,
                            table_name, record_id, old_values, new_values,
                            changes, ip_address, user_agent, device_fingerprint, session_id,
                            nrs_irn, nrs_response, created_at, description,
                            target_entity_type, target_entity_id, geo_location
                        ) VALUES (
                            :id, :entity_id, :organization_id, :user_id, :user_email, :action,
                            :table_name, :record_id, :old_values::jsonb, :new_values::jsonb,
                            :changes::jsonb, :ip_address::inet, :user_agent, :device_fingerprint, :session_id,
                            :nrs_irn, :nrs_response::jsonb, :created_at, :description,
                            :target_entity_type, :target_entity_id, :geo_location::jsonb
                        )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "entity_id": ENTITY_ID,
                        "organization_id": ORG_ID,
                        "user_id": USER_ID,
                        "user_email": USER_EMAIL,
                        "action": action,
                        "table_name": table_name,
                        "record_id": record_id,
                        "old_values": old_values_json,
                        "new_values": new_values_json,
                        "changes": changes_json,
                        "ip_address": f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}",
                        "user_agent": random.choice([
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X) Safari/17.2",
                            "Mozilla/5.0 (X11; Linux x86_64) Firefox/121.0"
                        ]),
                        "device_fingerprint": device_fp,
                        "session_id": f"sess_{uuid.uuid4().hex[:12]}",
                        "nrs_irn": nrs_irn,
                        "nrs_response": nrs_response_json,
                        "created_at": created_at,
                        "description": description,
                        "target_entity_type": target_entity_type,
                        "target_entity_id": target_entity_id,
                        "geo_location": geo_location_json
                    }
                )
                logs_created += 1
                
                if logs_created % 100 == 0:
                    print(f"   Created {logs_created} logs...")
        
        await db.commit()
        print(f"[OK] Successfully seeded {logs_created} audit logs!")
        
        # Show summary
        result = await db.execute(
            text("""
                SELECT EXTRACT(year FROM created_at) as year, COUNT(*) as cnt
                FROM audit_logs 
                WHERE entity_id = :entity_id
                GROUP BY EXTRACT(year FROM created_at)
                ORDER BY year
            """),
            {"entity_id": ENTITY_ID}
        )
        rows = result.fetchall()
        
        print("\n Logs by year:")
        for row in rows:
            print(f"  {int(row[0])}: {row[1]} records")


if __name__ == "__main__":
    asyncio.run(seed_audit_logs())
