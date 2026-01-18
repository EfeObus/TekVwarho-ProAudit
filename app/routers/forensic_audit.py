"""
TekVwarho ProAudit - Forensic Audit Router

World-Class Audit API Endpoints:
1. Benford's Law Analysis
2. Z-Score Anomaly Detection
3. NRS Gap Analysis
4. Full Population Testing
5. Data Integrity Verification (Hash Chain)
6. Match Summary Report

Nigerian Tax Reform 2026 Compliant
"""

import uuid
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.forensic_audit_service import (
    ForensicAuditService,
    BenfordsLawAnalyzer,
    ZScoreAnomalyDetector,
    NRSGapAnalyzer,
    worm_storage,
)
from app.services.three_way_matching import three_way_matching_service


router = APIRouter(prefix="/{entity_id}/forensic-audit", tags=["Forensic Audit"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class BenfordsAnalysisRequest(BaseModel):
    """Request model for Benford's Law analysis."""
    amounts: List[float] = Field(..., min_length=100, description="List of amounts to analyze (min 100)")
    analysis_type: str = Field("first_digit", description="'first_digit' or 'second_digit'")


class AnomalyDetectionRequest(BaseModel):
    """Request model for anomaly detection."""
    transactions: List[dict] = Field(..., description="List of transaction objects with 'amount' field")
    amount_field: str = Field("amount", description="Field name containing the amount")
    group_by: Optional[str] = Field(None, description="Optional field to group by (e.g., 'category')")
    threshold: float = Field(2.5, ge=1.5, le=5.0, description="Z-score threshold for anomalies")


class ForensicAuditRequest(BaseModel):
    """Request model for full forensic audit."""
    fiscal_year: int = Field(..., ge=2020, le=2030, description="Fiscal year to analyze")
    categories: Optional[List[str]] = Field(None, description="Optional category filter")


# =============================================================================
# INFO ENDPOINTS
# =============================================================================

@router.get("/info")
async def get_forensic_audit_info():
    """
    Get forensic audit capabilities and information.
    
    Describes all available world-class audit features.
    """
    return {
        "name": "TekVwarho ProAudit Forensic Audit Engine",
        "version": "1.0.0",
        "compliance_standards": ["NTAA 2025", "Nigerian Tax Reform 2026", "FIRS e-Invoicing"],
        "capabilities": {
            "benfords_law": {
                "description": "Detects fraud using digit distribution analysis",
                "methodology": "Compares first/second digit distribution against expected Benford's Law distribution",
                "use_cases": ["Expense fraud detection", "Invoice manipulation", "Revenue fabrication"],
                "minimum_sample": 100,
            },
            "z_score_anomaly": {
                "description": "Statistical outlier detection using Z-scores",
                "methodology": "Identifies transactions that deviate significantly from category/vendor averages",
                "use_cases": ["Unusual expense detection", "Vendor overcharging", "Category abuse"],
                "minimum_sample": 10,
            },
            "nrs_gap_analysis": {
                "description": "Compares local records against NRS government portal",
                "methodology": "Identifies invoices without IRNs and unreported B2C transactions",
                "use_cases": ["FIRS audit preparation", "IRN compliance", "B2C reporting compliance"],
                "compliance": "Mandatory for Nigerian businesses",
            },
            "ledger_integrity": {
                "description": "Cryptographic hash chain verification",
                "methodology": "SHA-256 hash chain ensures no retroactive modifications",
                "use_cases": ["Data tampering detection", "Audit trail verification", "Non-repudiation"],
                "standard": "Blockchain-like immutability",
            },
            "three_way_matching": {
                "description": "PO-GRN-Invoice matching for AP audit",
                "methodology": "Links Purchase Orders, Goods Received Notes, and Invoices",
                "use_cases": ["Accounts Payable audit", "Unauthorized payment detection", "Vendor fraud"],
            },
        },
        "outputs": [
            "Risk assessment with severity levels",
            "Specific flagged transactions",
            "Actionable recommendations",
            "Compliance status badges",
            "Export-ready audit reports",
        ],
    }


# =============================================================================
# BENFORD'S LAW ANALYSIS
# =============================================================================

@router.get("/benfords-law")
async def analyze_benfords_law(
    entity_id: uuid.UUID,
    fiscal_year: int = Query(..., ge=2020, le=2030, description="Fiscal year to analyze"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    analysis_type: str = Query("first_digit", description="'first_digit' or 'second_digit'"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Perform Benford's Law analysis on transactions.
    
    Benford's Law states that in naturally occurring numerical data,
    the leading digit follows a specific logarithmic distribution.
    Deviation from this pattern may indicate data manipulation or fraud.
    
    **Interpretation:**
    - Close conformity (MAD < 0.006): Low risk, data appears natural
    - Acceptable (MAD 0.006-0.012): Normal for financial data
    - Marginal (MAD 0.012-0.015): Warrants review
    - Non-conforming (MAD >= 0.015): Potential fraud indicator
    """
    from app.models.transaction import Transaction
    from sqlalchemy import select, and_
    from decimal import Decimal
    
    start_date = date(fiscal_year, 1, 1)
    end_date = date(fiscal_year, 12, 31)
    
    # Query transactions
    query = select(Transaction.amount).where(
        and_(
            Transaction.entity_id == entity_id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
            Transaction.amount > 0,  # Only positive amounts
        )
    )
    
    if transaction_type:
        query = query.where(Transaction.type == transaction_type)
    
    result = await db.execute(query)
    amounts = [Decimal(str(row[0])) for row in result.all() if row[0]]
    
    if len(amounts) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Benford's Law analysis requires minimum 100 transactions. Found: {len(amounts)}"
        )
    
    # Perform analysis
    analyzer = BenfordsLawAnalyzer()
    analysis = analyzer.analyze(amounts, analysis_type)
    
    return {
        "entity_id": str(entity_id),
        "fiscal_year": fiscal_year,
        "transaction_type": transaction_type or "all",
        **analysis,
    }


@router.post("/benfords-law/custom")
async def analyze_benfords_law_custom(
    entity_id: uuid.UUID,
    request: BenfordsAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Perform Benford's Law analysis on custom data.
    
    Allows analysis of specific datasets (e.g., specific vendor payments,
    category expenses, etc.)
    """
    from decimal import Decimal
    
    amounts = [Decimal(str(a)) for a in request.amounts if a > 0]
    
    if len(amounts) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum 100 positive amounts required. Found: {len(amounts)}"
        )
    
    analyzer = BenfordsLawAnalyzer()
    return analyzer.analyze(amounts, request.analysis_type)


# =============================================================================
# Z-SCORE ANOMALY DETECTION
# =============================================================================

@router.get("/anomaly-detection")
async def detect_anomalies(
    entity_id: uuid.UUID,
    fiscal_year: int = Query(..., ge=2020, le=2030),
    group_by: Optional[str] = Query(None, description="Group analysis by field (category, vendor)"),
    threshold: float = Query(2.5, ge=1.5, le=5.0, description="Z-score threshold"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Detect statistical anomalies in transactions using Z-scores.
    
    Z-score measures how many standard deviations a value is from the mean.
    Transactions with high Z-scores are statistically unusual.
    
    **Severity Levels:**
    - Warning (Z >= 2.0): ~2.3% probability in normal data
    - Critical (Z >= 3.0): ~0.1% probability in normal data
    - Extreme (Z >= 4.0): Virtually never in normal data
    
    **Use Cases:**
    - Detect unusually large expenses
    - Identify vendor overcharging
    - Find category anomalies
    """
    from app.models.transaction import Transaction
    from sqlalchemy import select, and_
    from sqlalchemy.orm import selectinload
    
    start_date = date(fiscal_year, 1, 1)
    end_date = date(fiscal_year, 12, 31)
    
    # Query transactions with related data
    query = select(Transaction).where(
        and_(
            Transaction.entity_id == entity_id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        )
    )
    
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    if len(transactions) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum 10 transactions required. Found: {len(transactions)}"
        )
    
    # Prepare transaction data
    txn_data = [
        {
            "id": str(txn.id),
            "amount": float(txn.amount) if txn.amount else 0,
            "transaction_date": txn.transaction_date.isoformat() if txn.transaction_date else None,
            "description": txn.description,
            "category": getattr(txn, 'category_name', None) or str(getattr(txn, 'category_id', '')),
            "vendor": getattr(txn, 'vendor_name', None) or str(getattr(txn, 'vendor_id', '')),
            "type": txn.type if hasattr(txn, 'type') else None,
        }
        for txn in transactions
    ]
    
    detector = ZScoreAnomalyDetector()
    return detector.detect_anomalies(
        txn_data,
        amount_field="amount",
        group_by=group_by,
        threshold=threshold
    )


@router.post("/anomaly-detection/custom")
async def detect_anomalies_custom(
    entity_id: uuid.UUID,
    request: AnomalyDetectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Detect anomalies in custom transaction data.
    
    Allows analysis of specific datasets or external data.
    """
    detector = ZScoreAnomalyDetector()
    return detector.detect_anomalies(
        request.transactions,
        amount_field=request.amount_field,
        group_by=request.group_by,
        threshold=request.threshold
    )


# =============================================================================
# NRS GAP ANALYSIS
# =============================================================================

@router.get("/nrs-gap-analysis")
async def analyze_nrs_gaps(
    entity_id: uuid.UUID,
    start_date: date = Query(..., description="Analysis period start"),
    end_date: date = Query(..., description="Analysis period end"),
    include_b2c: bool = Query(True, description="Include B2C high-value analysis"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Analyze gaps between local records and NRS government portal.
    
    This is the FIRST thing an FIRS/NRS auditor will check.
    
    **Identifies:**
    - Invoices without IRNs (non-compliant)
    - Pending IRN validations
    - High-value B2C transactions requiring reporting (2026 reform)
    
    **Compliance Levels:**
    - >= 95% validated: COMPLIANT
    - 80-95% validated: ATTENTION REQUIRED
    - < 80% validated: NON-COMPLIANT
    """
    analyzer = NRSGapAnalyzer()
    return await analyzer.analyze_gaps(
        db, entity_id, start_date, end_date, include_b2c
    )


@router.get("/nrs-gap-analysis/{fiscal_year}")
async def analyze_nrs_gaps_by_year(
    entity_id: uuid.UUID,
    fiscal_year: int,
    include_b2c: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Analyze NRS gaps for an entire fiscal year.
    """
    start_date = date(fiscal_year, 1, 1)
    end_date = date(fiscal_year, 12, 31)
    
    analyzer = NRSGapAnalyzer()
    return await analyzer.analyze_gaps(
        db, entity_id, start_date, end_date, include_b2c
    )


# =============================================================================
# DATA INTEGRITY VERIFICATION
# =============================================================================

@router.post("/verify-integrity")
async def verify_data_integrity(
    entity_id: uuid.UUID,
    fiscal_year: Optional[int] = Query(None, description="Optional fiscal year filter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verify data integrity using cryptographic hash chain.
    
    This is the "Verify Integrity" button feature.
    
    **How it works:**
    Every ledger entry stores SHA-256(entry_data + previous_hash).
    If ANY historical record is modified, ALL subsequent hashes break.
    
    **Returns:**
    - ✅ Green badge: Data integrity verified
    - ❌ Red badge: Integrity breach detected
    
    **Legal Weight:**
    Hash chain provides non-repudiation evidence for audit disputes.
    """
    service = ForensicAuditService(db)
    return await service.verify_data_integrity(entity_id, fiscal_year)


@router.get("/ledger-integrity-report")
async def get_ledger_integrity_report(
    entity_id: uuid.UUID,
    start_sequence: Optional[int] = Query(None, description="Start sequence number"),
    end_sequence: Optional[int] = Query(None, description="End sequence number"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate detailed ledger integrity report.
    
    Provides sequence-by-sequence verification of the hash chain.
    """
    from app.services.immutable_ledger import immutable_ledger_service
    
    is_valid, discrepancies = await immutable_ledger_service.verify_chain_integrity(
        db, entity_id, start_sequence, end_sequence
    )
    
    return {
        "entity_id": str(entity_id),
        "sequence_range": {
            "start": start_sequence,
            "end": end_sequence,
        },
        "integrity_status": "VERIFIED" if is_valid else "BREACH_DETECTED",
        "chain_valid": is_valid,
        "discrepancy_count": len(discrepancies),
        "discrepancies": discrepancies,
        "verification_time": date.today().isoformat(),
        "badge": "green" if is_valid else "red",
        "legal_statement": (
            "This report certifies the cryptographic integrity of the audit trail. "
            "All ledger entries are linked via SHA-256 hash chain, ensuring "
            "no retroactive modifications have occurred."
        ) if is_valid else (
            "⚠️ INTEGRITY BREACH: Discrepancies detected in hash chain. "
            "This indicates possible data tampering. Immediate investigation required."
        ),
    }


# =============================================================================
# 3-WAY MATCHING SUMMARY
# =============================================================================

@router.get("/three-way-matching/summary")
async def get_three_way_matching_summary(
    entity_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get 3-way matching summary report.
    
    Shows PO-GRN-Invoice matching status for auditor review.
    
    **Matched:** All three documents agree on quantity and price
    **Discrepancy:** Mismatch detected - requires investigation
    **Pending:** Awaiting review/resolution
    
    **Risk Indicator:**
    Invoices paid without 100% match = High-Risk Exception
    """
    summary = await three_way_matching_service.get_matching_summary(
        db, entity_id, start_date, end_date
    )
    
    # Add risk assessment
    discrepancy_count = summary.get("by_status", {}).get("discrepancy", {}).get("count", 0)
    total_count = summary.get("totals", {}).get("total_matches", 0)
    
    if total_count > 0:
        discrepancy_rate = discrepancy_count / total_count * 100
    else:
        discrepancy_rate = 0
    
    summary["risk_assessment"] = {
        "discrepancy_rate": round(discrepancy_rate, 2),
        "risk_level": "high" if discrepancy_rate > 10 else "medium" if discrepancy_rate > 5 else "low",
        "high_risk_exceptions": discrepancy_count,
        "auditor_note": (
            f"{discrepancy_count} invoices were paid without 100% match on "
            f"quantity and price. These are flagged as High-Risk Exceptions."
        ) if discrepancy_count > 0 else "All invoices matched successfully.",
    }
    
    return summary


@router.get("/three-way-matching/exceptions")
async def get_matching_exceptions(
    entity_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, description="Filter by status: discrepancy, pending_review"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get list of 3-way matching exceptions (High-Risk).
    
    These are invoices that were processed without perfect
    PO-GRN-Invoice matching and require auditor attention.
    """
    from app.models.advanced_accounting import ThreeWayMatch, MatchingStatus
    from sqlalchemy import select, and_
    
    query = select(ThreeWayMatch).where(
        ThreeWayMatch.entity_id == entity_id
    )
    
    if status_filter:
        try:
            status_enum = MatchingStatus(status_filter)
            query = query.where(ThreeWayMatch.status == status_enum)
        except ValueError:
            pass
    else:
        # Default to showing discrepancies and pending
        query = query.where(
            ThreeWayMatch.status.in_([
                MatchingStatus.DISCREPANCY,
                MatchingStatus.PENDING,
                MatchingStatus.DISPUTED,
            ])
        )
    
    result = await db.execute(query.order_by(ThreeWayMatch.created_at.desc()).limit(100))
    matches = result.scalars().all()
    
    return {
        "entity_id": str(entity_id),
        "exception_count": len(matches),
        "exceptions": [
            {
                "id": str(m.id),
                "purchase_order_id": str(m.purchase_order_id) if m.purchase_order_id else None,
                "grn_id": str(m.grn_id) if m.grn_id else None,
                "invoice_id": str(m.invoice_id) if m.invoice_id else None,
                "status": m.status.value if hasattr(m.status, 'value') else str(m.status),
                "po_amount": str(m.po_amount) if m.po_amount else None,
                "invoice_amount": str(m.invoice_amount) if m.invoice_amount else None,
                "discrepancies": m.discrepancies,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "resolved_at": m.resolved_at.isoformat() if hasattr(m, 'resolved_at') and m.resolved_at else None,
            }
            for m in matches
        ],
        "auditor_guidance": (
            "Review each exception to determine if the variance is acceptable. "
            "Document resolution with notes and approver signature."
        ),
    }


# =============================================================================
# FULL FORENSIC AUDIT
# =============================================================================

@router.post("/full-audit")
async def run_full_forensic_audit(
    entity_id: uuid.UUID,
    request: ForensicAuditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run comprehensive forensic audit (Full Population Testing).
    
    This is NOT sampling - it analyzes EVERY transaction.
    
    **Tests Performed:**
    1. Benford's Law (first & second digit)
    2. Z-score anomaly detection (overall & by category)
    3. NRS gap analysis
    4. Hash chain integrity verification
    
    **Returns:**
    - Overall risk assessment
    - Specific risk factors identified
    - Detailed results from each test
    - Actionable recommendations
    """
    service = ForensicAuditService(db)
    return await service.run_full_forensic_audit(
        entity_id,
        request.fiscal_year,
        request.categories
    )


@router.get("/audit-summary/{fiscal_year}")
async def get_audit_summary(
    entity_id: uuid.UUID,
    fiscal_year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get executive summary of audit status for a fiscal year.
    
    Quick overview for management and auditors.
    """
    # This would aggregate results from various services
    # For now, return a structured summary
    
    service = ForensicAuditService(db)
    integrity_result = await service.verify_data_integrity(entity_id, fiscal_year)
    
    start_date = date(fiscal_year, 1, 1)
    end_date = date(fiscal_year, 12, 31)
    
    nrs_analyzer = NRSGapAnalyzer()
    nrs_result = await nrs_analyzer.analyze_gaps(db, entity_id, start_date, end_date)
    
    matching_summary = await three_way_matching_service.get_matching_summary(
        db, entity_id, start_date, end_date
    )
    
    return {
        "entity_id": str(entity_id),
        "fiscal_year": fiscal_year,
        "summary": {
            "data_integrity": {
                "status": integrity_result.get("status"),
                "badge": integrity_result.get("badge"),
            },
            "nrs_compliance": {
                "rate": nrs_result.get("compliance", {}).get("rate"),
                "status": nrs_result.get("compliance", {}).get("status"),
                "risk_level": nrs_result.get("compliance", {}).get("risk_level"),
            },
            "three_way_matching": {
                "match_rate": matching_summary.get("totals", {}).get("match_rate"),
                "exceptions": matching_summary.get("by_status", {}).get("discrepancy", {}).get("count", 0),
            },
        },
        "quick_actions": [
            "Run Full Forensic Audit" if not integrity_result.get("verified") else None,
            "Submit pending invoices to NRS" if nrs_result.get("summary", {}).get("missing_irn", 0) > 0 else None,
            "Review matching exceptions" if matching_summary.get("by_status", {}).get("discrepancy", {}).get("count", 0) > 0 else None,
        ],
        "generated_at": date.today().isoformat(),
    }


# =============================================================================
# WORM STORAGE (AUDIT VAULT)
# =============================================================================

@router.get("/worm-storage/status")
async def get_worm_storage_status(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get WORM (Write-Once-Read-Many) storage status.
    
    WORM storage provides legal-grade document retention where
    files cannot be deleted or modified for the retention period.
    
    **Compliance:**
    - 7-year retention for Nigerian tax records
    - Object Lock prevents deletion even by admins
    - Provides legal weight for audit disputes
    """
    return {
        "enabled": worm_storage.enabled,
        "storage_type": "AWS S3 Object Lock" if worm_storage.enabled else "Not Configured",
        "retention_mode": "COMPLIANCE" if worm_storage.enabled else None,
        "default_retention_years": worm_storage.DEFAULT_RETENTION_YEARS,
        "legal_protection": (
            "Documents stored in WORM cannot be modified or deleted until "
            "the retention period expires. This provides legal-grade "
            "evidence for tax disputes and audits."
        ),
        "supported_documents": [
            "Tax filings",
            "NRS-validated invoices",
            "Financial statements",
            "Audit reports",
            "Bank statements",
            "Supporting documents",
        ],
        "configuration_status": "active" if worm_storage.enabled else "requires_setup",
    }


@router.post("/worm-storage/verify/{document_type}/{document_id}")
async def verify_worm_document(
    entity_id: uuid.UUID,
    document_type: str,
    document_id: str,
    expected_hash: Optional[str] = Query(None, description="Expected SHA-256 hash"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verify a document's integrity and legal lock status in WORM storage.
    
    Proves that the document is exactly the same as when it was stored.
    """
    return await worm_storage.verify_document(
        entity_id, document_type, document_id, expected_hash
    )
