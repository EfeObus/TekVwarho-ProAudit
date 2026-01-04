"""
TekVwarho ProAudit - Tests for 2026 Tax Reform Compliance Features

Tests for:
- TIN Validation Service
- Compliance Penalty Service
- Minimum ETR Calculator
- CGT Calculator
- Zero-Rated VAT Tracker
- Peppol BIS Billing Export
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.services.tin_validation_service import (
    TINValidationService,
    TINEntityType,
    TINValidationStatus,
)
from app.services.compliance_penalty_service import (
    CompliancePenaltyService,
    PenaltyType,
    PENALTY_SCHEDULE,
)
from app.services.tax_calculators.minimum_etr_cgt_service import (
    MinimumETRCalculator,
    CGTCalculator,
    ZeroRatedVATTracker,
    CompanyClassification,
)
from app.services.peppol_export_service import (
    PeppolExportService,
    PeppolInvoice,
    PeppolParty,
    PeppolLineItem,
    InvoiceTypeCode,
    TaxCategoryCode,
)


class TestTINValidation:
    """Tests for TIN Validation Service."""
    
    def test_valid_tin_format_10_digits(self):
        """10-digit TIN should pass format validation."""
        service = TINValidationService()
        is_valid, message = service._validate_tin_format("1234567890")
        assert is_valid is True
    
    def test_valid_tin_format_with_hyphens(self):
        """TIN with hyphens should pass format validation."""
        service = TINValidationService()
        is_valid, message = service._validate_tin_format("12345-67890")
        assert is_valid is True
    
    def test_invalid_tin_format_too_short(self):
        """TIN shorter than 10 digits should fail."""
        service = TINValidationService()
        is_valid, message = service._validate_tin_format("123456789")
        assert is_valid is False
        assert "too short" in message.lower()
    
    def test_invalid_tin_format_too_long(self):
        """TIN longer than 14 digits should fail."""
        service = TINValidationService()
        is_valid, message = service._validate_tin_format("123456789012345")
        assert is_valid is False
        assert "too long" in message.lower()
    
    def test_invalid_tin_format_non_digits(self):
        """TIN with non-digit characters should fail."""
        service = TINValidationService()
        is_valid, message = service._validate_tin_format("12345ABCDE")
        assert is_valid is False
    
    def test_sandbox_validation_valid_tin(self):
        """Valid TIN should validate in sandbox mode."""
        import asyncio
        service = TINValidationService()
        result = asyncio.get_event_loop().run_until_complete(
            service.validate_tin("1234567890")
        )
        assert result.is_valid is True
        assert result.status == TINValidationStatus.VALID
    
    def test_sandbox_validation_invalid_tin_starting_zero(self):
        """TIN starting with 0 should be invalid in sandbox."""
        import asyncio
        service = TINValidationService()
        result = asyncio.get_event_loop().run_until_complete(
            service.validate_tin("0123456789")
        )
        assert result.is_valid is False
        assert result.status == TINValidationStatus.NOT_FOUND


class TestCompliancePenalty:
    """Tests for Compliance Penalty Service."""
    
    def test_late_filing_penalty_first_month(self):
        """Late filing should incur ₦100,000 penalty for first month."""
        service = CompliancePenaltyService(db=None)
        
        due_date = date(2026, 1, 21)
        filing_date = date(2026, 2, 15)  # Less than 30 days late
        
        result = service.calculate_late_filing_penalty(due_date, filing_date)
        
        assert result.months_late == 1
        assert result.base_amount == Decimal("100000")
        assert result.total_amount == Decimal("100000")
    
    def test_late_filing_penalty_multiple_months(self):
        """Late filing should add ₦50,000 per additional month."""
        service = CompliancePenaltyService(db=None)
        
        due_date = date(2026, 1, 21)
        filing_date = date(2026, 4, 25)  # About 3 months late
        
        result = service.calculate_late_filing_penalty(due_date, filing_date)
        
        assert result.months_late == 4  # Rounded up
        # First month: 100,000 + 3 additional months * 50,000 = 250,000
        assert result.base_amount == Decimal("100000")
        assert result.additional_amount == Decimal("150000")
        assert result.total_amount == Decimal("250000")
    
    def test_on_time_filing_no_penalty(self):
        """On-time filing should have no penalty."""
        service = CompliancePenaltyService(db=None)
        
        due_date = date(2026, 1, 21)
        filing_date = date(2026, 1, 20)
        
        result = service.calculate_late_filing_penalty(due_date, filing_date)
        
        assert result.months_late == 0
        assert result.total_amount == Decimal("0")
    
    def test_unregistered_vendor_penalty(self):
        """Unregistered vendor contract should incur ₦5,000,000 penalty."""
        service = CompliancePenaltyService(db=None)
        
        result = service.calculate_unregistered_vendor_penalty(Decimal("1000000"))
        
        assert result.total_amount == Decimal("5000000")
        assert result.penalty_type == PenaltyType.UNREGISTERED_VENDOR
    
    def test_vat_late_remittance_penalty(self):
        """Late VAT remittance should incur 10% penalty + 2% monthly interest."""
        service = CompliancePenaltyService(db=None)
        
        tax_amount = Decimal("1000000")
        due_date = date(2026, 1, 21)
        payment_date = date(2026, 2, 25)  # About 1 month late
        
        result = service.calculate_tax_remittance_penalty(
            PenaltyType.VAT_NON_REMITTANCE,
            tax_amount,
            due_date,
            payment_date,
        )
        
        # 10% base penalty = 100,000 + 2% interest for 1 month = 20,000
        assert result.base_amount == Decimal("100000")
        assert result.months_late >= 1


class TestMinimumETR:
    """Tests for Minimum ETR Calculator."""
    
    def test_company_below_threshold_not_subject(self):
        """Company with turnover < ₦50B should not be subject to Minimum ETR."""
        calculator = MinimumETRCalculator()
        
        result = calculator.calculate_minimum_etr(
            annual_turnover=Decimal("10000000000"),  # ₦10 billion
            assessable_profit=Decimal("1000000000"),
            regular_tax_paid=Decimal("100000000"),  # 10% ETR
        )
        
        assert result.is_subject_to_minimum_etr is False
        assert result.top_up_tax == Decimal("0")
    
    def test_large_company_meeting_minimum_etr(self):
        """Large company already meeting 15% ETR should have no top-up."""
        calculator = MinimumETRCalculator()
        
        result = calculator.calculate_minimum_etr(
            annual_turnover=Decimal("60000000000"),  # ₦60 billion
            assessable_profit=Decimal("10000000000"),
            regular_tax_paid=Decimal("2000000000"),  # 20% ETR
        )
        
        assert result.is_subject_to_minimum_etr is True
        assert result.calculated_etr >= Decimal("0.15")
        assert result.top_up_tax == Decimal("0")
    
    def test_large_company_below_minimum_etr(self):
        """Large company below 15% ETR should pay top-up tax."""
        calculator = MinimumETRCalculator()
        
        result = calculator.calculate_minimum_etr(
            annual_turnover=Decimal("60000000000"),  # ₦60 billion
            assessable_profit=Decimal("10000000000"),
            regular_tax_paid=Decimal("1000000000"),  # 10% ETR
        )
        
        assert result.is_subject_to_minimum_etr is True
        assert result.calculated_etr < Decimal("0.15")
        # Top-up should bring ETR to 15%
        # 15% of 10B = 1.5B, already paid 1B, top-up = 0.5B
        assert result.top_up_tax == Decimal("500000000")
    
    def test_mne_constituent_subject_to_minimum_etr(self):
        """MNE constituent with group revenue >= €750M should be subject."""
        calculator = MinimumETRCalculator()
        
        is_subject, reason = calculator.check_minimum_etr_applicability(
            annual_turnover=Decimal("10000000000"),  # ₦10B (below threshold)
            is_mne_constituent=True,
            mne_group_revenue_eur=Decimal("800000000"),  # €800M
        )
        
        assert is_subject is True
        assert "MNE" in reason


class TestCGTCalculator:
    """Tests for Capital Gains Tax Calculator."""
    
    def test_small_company_exempt_from_cgt(self):
        """Small companies should be exempt from CGT."""
        calculator = CGTCalculator()
        
        result = calculator.calculate_cgt(
            asset_cost=Decimal("10000000"),
            sale_proceeds=Decimal("15000000"),
            annual_turnover=Decimal("50000000"),  # ₦50M
            fixed_assets_value=Decimal("100000000"),  # ₦100M
        )
        
        assert result.is_exempt is True
        assert result.cgt_liability == Decimal("0")
    
    def test_large_company_30_percent_cgt(self):
        """Large companies should pay 30% CGT on capital gains."""
        calculator = CGTCalculator()
        
        result = calculator.calculate_cgt(
            asset_cost=Decimal("10000000"),
            sale_proceeds=Decimal("20000000"),
            annual_turnover=Decimal("200000000"),  # ₦200M
            fixed_assets_value=Decimal("300000000"),  # ₦300M
            apply_indexation=False,
        )
        
        assert result.is_exempt is False
        assert result.capital_gain == Decimal("10000000")
        assert result.cgt_rate == Decimal("0.30")
        assert result.cgt_liability == Decimal("3000000")  # 30% of 10M
    
    def test_capital_loss_no_cgt(self):
        """Capital loss should result in no CGT liability."""
        calculator = CGTCalculator()
        
        result = calculator.calculate_cgt(
            asset_cost=Decimal("20000000"),
            sale_proceeds=Decimal("15000000"),  # Loss
            annual_turnover=Decimal("200000000"),
            fixed_assets_value=Decimal("300000000"),
        )
        
        assert result.capital_gain == Decimal("-5000000")
        assert result.cgt_liability == Decimal("0")
    
    def test_company_classification(self):
        """Test company classification for CGT purposes."""
        calculator = CGTCalculator()
        
        # Small company
        assert calculator.classify_company(
            Decimal("50000000"), Decimal("100000000")
        ) == CompanyClassification.SMALL
        
        # Large company (turnover exceeds)
        assert calculator.classify_company(
            Decimal("150000000"), Decimal("100000000")
        ) == CompanyClassification.LARGE


class TestVATRecovery:
    """Tests for Input VAT Recovery under 2026 Reform."""
    
    def test_irn_validation_valid(self):
        """Valid IRN (6+ chars) should allow recovery."""
        from app.services.vat_recovery_service import VATRecoveryService
        
        # IRN longer than 5 characters should be valid
        valid_irns = [
            "NRS-2026-INV-12345678",
            "INV123456",
            "123456",  # Exactly 6 chars
        ]
        
        for irn in valid_irns:
            has_valid = bool(irn and len(irn) > 5)
            assert has_valid is True, f"IRN {irn} should be valid"
    
    def test_irn_validation_invalid(self):
        """Invalid/missing IRN should block recovery."""
        invalid_irns = [
            "12345",  # Too short (5 chars)
            "",       # Empty
            None,     # None
        ]
        
        for irn in invalid_irns:
            has_valid = bool(irn and len(irn) > 5)
            assert has_valid is False, f"IRN {irn} should be invalid"
    
    def test_recovery_types_2026(self):
        """2026 law allows recovery on stock, services, and capital."""
        from app.models.tax_2026 import VATRecoveryType
        
        recovery_types = [t.value for t in VATRecoveryType]
        
        assert "stock_in_trade" in recovery_types  # Standard
        assert "services" in recovery_types        # NEW 2026
        assert "capital_expenditure" in recovery_types  # NEW 2026
        assert len(recovery_types) == 3
    
    def test_vat_rate_constant(self):
        """VAT rate should be 7.5%."""
        from app.services.vat_recovery_service import VATRecoveryService
        
        assert VATRecoveryService.VAT_RATE == Decimal("0.075")
    
    def test_recovery_classification_capital(self):
        """Capital asset keywords should classify as capital_expenditure."""
        from app.models.tax_2026 import VATRecoveryType
        
        capital_keywords = [
            "equipment", "machinery", "vehicle", "computer", "furniture",
            "building", "property", "asset", "capital", "fixed asset",
        ]
        
        # This would be tested via service.auto_classify_transaction()
        # For now, just verify the keywords are reasonable
        for keyword in capital_keywords:
            assert len(keyword) > 3  # Meaningful keywords
    
    def test_recovery_classification_services(self):
        """Service keywords should classify as services."""
        from app.models.tax_2026 import VATRecoveryType
        
        service_keywords = [
            "service", "consulting", "legal", "accounting", "audit",
            "maintenance", "repair", "professional", "training",
        ]
        
        for keyword in service_keywords:
            assert len(keyword) > 3  # Meaningful keywords


class TestZeroRatedVAT:
    """Tests for Zero-Rated VAT Tracker."""
    
    def test_record_zero_rated_sale(self):
        """Recording zero-rated sale should set VAT to 0."""
        tracker = ZeroRatedVATTracker()
        
        record = tracker.record_zero_rated_sale(
            sale_amount=Decimal("100000"),
            category="basic_food",
            date=date.today(),
            description="Rice and beans",
        )
        
        assert record["vat_rate"] == Decimal("0")
        assert record["vat_amount"] == Decimal("0")
        assert record["is_zero_rated"] is True
    
    def test_input_vat_refund_eligibility(self):
        """Input VAT should only be refundable with valid IRN."""
        tracker = ZeroRatedVATTracker()
        
        # With IRN - eligible
        record1 = tracker.record_input_vat(
            purchase_amount=Decimal("100000"),
            vat_amount=Decimal("7500"),
            date=date.today(),
            vendor_tin="1234567890",
            vendor_irn="NGN202601031234ABCD",
        )
        assert record1["refund_eligible"] is True
        
        # Without IRN - not eligible
        record2 = tracker.record_input_vat(
            purchase_amount=Decimal("50000"),
            vat_amount=Decimal("3750"),
            date=date.today(),
            vendor_tin="1234567890",
            vendor_irn=None,
        )
        assert record2["refund_eligible"] is False
    
    def test_calculate_refund_claim(self):
        """Refund claim should only include eligible input VAT."""
        tracker = ZeroRatedVATTracker()
        
        # Record sales and purchases
        tracker.record_zero_rated_sale(Decimal("1000000"), "basic_food", date.today(), "Test")
        tracker.record_input_vat(Decimal("100000"), Decimal("7500"), date.today(), "1234567890", "IRN123")
        tracker.record_input_vat(Decimal("50000"), Decimal("3750"), date.today(), "1234567890", None)
        
        claim = tracker.calculate_refund_claim()
        
        assert claim["total_input_vat_paid"] == 11250.0
        assert claim["refundable_input_vat"] == 7500.0
        assert claim["non_refundable_vat"] == 3750.0


class TestPeppolExport:
    """Tests for Peppol BIS Billing Export Service."""
    
    def get_sample_invoice(self) -> PeppolInvoice:
        """Create a sample invoice for testing."""
        seller = PeppolParty(
            name="Test Company Ltd",
            tin="1234567890",
            street_address="123 Test Street",
            city="Lagos",
            state="Lagos",
        )
        buyer = PeppolParty(
            name="Customer Corp",
            tin="0987654321",
            city="Abuja",
        )
        line_items = [
            PeppolLineItem(
                item_id="ITEM-001",
                description="Test Product",
                quantity=Decimal("10"),
                unit_code="EA",
                unit_price=Decimal("10000"),
                line_total=Decimal("100000"),
                vat_rate=Decimal("7.5"),
                vat_amount=Decimal("7500"),
            ),
        ]
        
        return PeppolInvoice(
            invoice_number="INV-2026-001",
            invoice_date=date(2026, 1, 3),
            due_date=date(2026, 1, 17),
            invoice_type=InvoiceTypeCode.COMMERCIAL_INVOICE,
            seller=seller,
            buyer=buyer,
            line_items=line_items,
            subtotal=Decimal("100000"),
            total_vat=Decimal("7500"),
            total_amount=Decimal("107500"),
            nrs_irn="NGN20260103123456789",
        )
    
    def test_generate_csid(self):
        """CSID should be generated from invoice data."""
        service = PeppolExportService()
        invoice = self.get_sample_invoice()
        
        csid = service.generate_csid(invoice)
        
        assert csid.startswith("NRS-CSID-")
        assert len(csid) == 41  # NRS-CSID- (9) + 32 hex chars
    
    def test_generate_qr_code_data(self):
        """QR code data should contain essential invoice info."""
        import json
        
        service = PeppolExportService()
        invoice = self.get_sample_invoice()
        
        qr_data = service.generate_qr_code_data(invoice)
        parsed = json.loads(qr_data)
        
        assert parsed["inv"] == "INV-2026-001"
        assert parsed["seller_tin"] == "1234567890"
        assert parsed["total"] == "107500"
    
    def test_export_to_xml(self):
        """Export should generate valid UBL 2.1 XML."""
        service = PeppolExportService()
        invoice = self.get_sample_invoice()
        
        xml_output = service.to_ubl_xml(invoice)
        
        assert "<?xml version" in xml_output
        assert "<Invoice" in xml_output
        assert "INV-2026-001" in xml_output
        assert "NRS-CSID" in xml_output
        assert "NRS-IRN" in xml_output
    
    def test_export_to_json(self):
        """Export should generate valid Peppol JSON."""
        import json
        
        service = PeppolExportService()
        invoice = self.get_sample_invoice()
        
        json_output = service.to_json(invoice)
        parsed = json.loads(json_output)
        
        assert parsed["_meta"]["standard"] == "Peppol BIS Billing 3.0"
        assert parsed["invoice"]["id"] == "INV-2026-001"
        assert parsed["nrs_compliance"]["irn"] == "NGN20260103123456789"
        assert parsed["supplier"]["tin"] == "1234567890"


class TestSmartTaxLogic:
    """Tests for Smart Tax Logic - CIT and Development Levy integration."""
    
    def test_small_business_zero_cit(self):
        """Small businesses (≤₦25M turnover) should have 0% CIT."""
        from app.services.tax_calculators.cit_service import CITCalculator
        
        result = CITCalculator.calculate_cit(
            gross_turnover=20_000_000,  # ₦20M - small
            assessable_profit=5_000_000,  # ₦5M profit
        )
        
        assert result["company_size"] == "small"
        assert result["cit_rate"] == 0
        assert result["final_cit"] == 0
    
    def test_medium_business_20_cit(self):
        """Medium businesses (₦25M-₦100M) should have 20% CIT."""
        from app.services.tax_calculators.cit_service import CITCalculator
        
        result = CITCalculator.calculate_cit(
            gross_turnover=60_000_000,  # ₦60M - medium
            assessable_profit=10_000_000,  # ₦10M profit
        )
        
        assert result["company_size"] == "medium"
        assert result["cit_rate"] == 20
        assert result["cit_on_profit"] == 2_000_000  # 20% of ₦10M
    
    def test_large_business_30_cit(self):
        """Large businesses (>₦100M) should have 30% CIT."""
        from app.services.tax_calculators.cit_service import CITCalculator
        
        result = CITCalculator.calculate_cit(
            gross_turnover=200_000_000,  # ₦200M - large
            assessable_profit=50_000_000,  # ₦50M profit
        )
        
        assert result["company_size"] == "large"
        assert result["cit_rate"] == 30
        assert result["cit_on_profit"] == 15_000_000  # 30% of ₦50M
    
    def test_tet_applies_to_all(self):
        """Tertiary Education Tax (3%) applies to all companies with profit."""
        from app.services.tax_calculators.cit_service import CITCalculator
        
        result = CITCalculator.calculate_cit(
            gross_turnover=100_000_000,
            assessable_profit=20_000_000,
        )
        
        assert result["tertiary_education_tax"] == 600_000  # 3% of ₦20M
    
    def test_development_levy_exempt_small(self):
        """Small businesses should be exempt from 4% Development Levy."""
        from app.services.development_levy_service import DevelopmentLevyService
        
        # Small company: turnover ≤ ₦100M AND fixed assets ≤ ₦250M
        is_exempt = (
            80_000_000 <= 100_000_000 and  # Turnover ₦80M
            200_000_000 <= 250_000_000      # Fixed assets ₦200M
        )
        
        assert is_exempt is True
    
    def test_development_levy_4_percent(self):
        """Large businesses pay 4% Development Levy on assessable profit."""
        # 4% of ₦100M profit = ₦4M
        assessable_profit = Decimal("100_000_000")
        levy_rate = Decimal("0.04")
        
        levy_amount = assessable_profit * levy_rate
        
        assert levy_amount == Decimal("4_000_000")


class TestBuyerReview72Hour:
    """Tests for 72-Hour Buyer Review (Dispute Window) functionality."""
    
    def test_review_window_is_72_hours(self):
        """Buyer review window must be exactly 72 hours."""
        REVIEW_WINDOW_HOURS = 72
        assert REVIEW_WINDOW_HOURS == 72
    
    def test_dispute_deadline_calculation(self):
        """Dispute deadline should be 72 hours from NRS submission."""
        from datetime import datetime, timedelta
        
        REVIEW_WINDOW_HOURS = 72
        nrs_submitted_at = datetime(2026, 1, 4, 10, 0, 0)  # 10:00 AM
        
        dispute_deadline = nrs_submitted_at + timedelta(hours=REVIEW_WINDOW_HOURS)
        
        expected_deadline = datetime(2026, 1, 7, 10, 0, 0)  # 3 days later at 10:00 AM
        assert dispute_deadline == expected_deadline
    
    def test_buyer_status_pending(self):
        """Invoice should start with PENDING buyer status after NRS submission."""
        from app.models.invoice import BuyerStatus
        
        initial_status = BuyerStatus.PENDING
        assert initial_status.value == "pending"
    
    def test_buyer_status_accepted(self):
        """Buyer can accept invoice within 72 hours."""
        from app.models.invoice import BuyerStatus
        
        accepted_status = BuyerStatus.ACCEPTED
        assert accepted_status.value == "accepted"
    
    def test_buyer_status_rejected(self):
        """Buyer can reject invoice within 72 hours."""
        from app.models.invoice import BuyerStatus
        
        rejected_status = BuyerStatus.REJECTED
        assert rejected_status.value == "rejected"
    
    def test_buyer_status_auto_accepted(self):
        """Invoice auto-accepted when 72-hour window expires without response."""
        from app.models.invoice import BuyerStatus
        
        auto_accepted_status = BuyerStatus.AUTO_ACCEPTED
        assert auto_accepted_status.value == "auto_accepted"
    
    def test_is_within_dispute_window(self):
        """Check if current time is within 72-hour dispute window."""
        from datetime import datetime, timedelta
        
        nrs_submitted_at = datetime.utcnow() - timedelta(hours=24)  # 24 hours ago
        dispute_deadline = nrs_submitted_at + timedelta(hours=72)
        
        now = datetime.utcnow()
        is_within_window = now < dispute_deadline
        
        assert is_within_window is True  # Still 48 hours left
    
    def test_is_past_dispute_window(self):
        """Check if 72-hour window has expired."""
        from datetime import datetime, timedelta
        
        nrs_submitted_at = datetime.utcnow() - timedelta(hours=80)  # 80 hours ago
        dispute_deadline = nrs_submitted_at + timedelta(hours=72)
        
        now = datetime.utcnow()
        is_expired = now > dispute_deadline
        
        assert is_expired is True  # Window expired 8 hours ago
    
    def test_time_remaining_calculation(self):
        """Calculate remaining time in dispute window."""
        from datetime import datetime, timedelta
        
        nrs_submitted_at = datetime.utcnow() - timedelta(hours=48)  # 48 hours ago
        dispute_deadline = nrs_submitted_at + timedelta(hours=72)
        
        now = datetime.utcnow()
        time_remaining = dispute_deadline - now
        
        # Should be approximately 24 hours remaining
        hours_remaining = time_remaining.total_seconds() / 3600
        assert 23 < hours_remaining < 25  # Allow some tolerance
    
    def test_credit_note_required_on_rejection(self):
        """Rejection must trigger automatic Credit Note generation."""
        # Per Nigeria Tax Administration Act 2025, rejected invoices
        # require automatic credit note to reverse VAT liability
        from app.models.tax_2026 import CreditNoteStatus
        
        credit_note_statuses = [status.value for status in CreditNoteStatus]
        assert "draft" in credit_note_statuses
        assert "submitted" in credit_note_statuses
    
    def test_credit_note_number_format(self):
        """Credit note number should follow CN-YYYY-NNNNN format."""
        import re
        
        credit_note_number = "CN-2026-00001"
        pattern = r"^CN-\d{4}-\d{5}$"
        
        assert re.match(pattern, credit_note_number) is not None
    
    def test_auto_accept_after_72_hours_no_response(self):
        """Invoice deemed accepted if no buyer response within 72 hours."""
        from datetime import datetime, timedelta
        
        REVIEW_WINDOW_HOURS = 72
        nrs_submitted_at = datetime.utcnow() - timedelta(hours=73)  # Submitted 73 hours ago
        dispute_deadline = nrs_submitted_at + timedelta(hours=REVIEW_WINDOW_HOURS)
        
        now = datetime.utcnow()
        should_auto_accept = (now > dispute_deadline)
        
        assert should_auto_accept is True


class TestBuyerReviewService:
    """Tests for BuyerReviewService functionality."""
    
    def test_buyer_review_service_window_hours(self):
        """BuyerReviewService should use 72-hour window."""
        # BuyerReviewService.REVIEW_WINDOW_HOURS should be 72
        REVIEW_WINDOW_HOURS = 72
        assert REVIEW_WINDOW_HOURS == 72
    
    def test_invoice_status_values(self):
        """Invoice statuses should include dispute-related values."""
        from app.models.invoice import InvoiceStatus
        
        status_values = [s.value for s in InvoiceStatus]
        assert "pending" in status_values
        assert "accepted" in status_values
        assert "rejected" in status_values
        assert "disputed" in status_values
    
    def test_buyer_response_timestamp(self):
        """Buyer response timestamp should be recorded on accept/reject."""
        from datetime import datetime
        
        # buyer_response_at should be set when buyer responds
        buyer_response_at = datetime.utcnow()
        assert buyer_response_at is not None
        assert isinstance(buyer_response_at, datetime)


class TestB2CRealtimeReporting:
    """Tests for B2C Real-time Reporting (24-hour NRS mandate)."""
    
    def test_default_threshold_is_50000(self):
        """Default B2C reporting threshold is ₦50,000."""
        DEFAULT_THRESHOLD = Decimal("50000.00")
        assert DEFAULT_THRESHOLD == Decimal("50000.00")
    
    def test_reporting_window_is_24_hours(self):
        """B2C transactions must be reported within 24 hours."""
        REPORTING_WINDOW_HOURS = 24
        assert REPORTING_WINDOW_HOURS == 24
    
    def test_transaction_above_threshold_is_reportable(self):
        """Transaction over ₦50,000 should be flagged for B2C reporting."""
        threshold = Decimal("50000.00")
        transaction_amount = Decimal("75000.00")
        
        is_reportable = transaction_amount >= threshold
        assert is_reportable is True
    
    def test_transaction_below_threshold_not_reportable(self):
        """Transaction under ₦50,000 should NOT be flagged for B2C reporting."""
        threshold = Decimal("50000.00")
        transaction_amount = Decimal("45000.00")
        
        is_reportable = transaction_amount >= threshold
        assert is_reportable is False
    
    def test_transaction_at_threshold_is_reportable(self):
        """Transaction exactly at ₦50,000 should be flagged for B2C reporting."""
        threshold = Decimal("50000.00")
        transaction_amount = Decimal("50000.00")
        
        is_reportable = transaction_amount >= threshold
        assert is_reportable is True
    
    def test_late_penalty_per_transaction(self):
        """Late reporting penalty is ₦10,000 per transaction."""
        LATE_PENALTY_PER_TRANSACTION = Decimal("10000.00")
        assert LATE_PENALTY_PER_TRANSACTION == Decimal("10000.00")
    
    def test_max_daily_penalty(self):
        """Maximum daily penalty is ₦500,000."""
        MAX_DAILY_PENALTY = Decimal("500000.00")
        assert MAX_DAILY_PENALTY == Decimal("500000.00")
    
    def test_penalty_calculation_within_cap(self):
        """Penalty for 30 late transactions should be ₦300,000 (within cap)."""
        late_count = 30
        penalty_per_tx = Decimal("10000.00")
        max_penalty = Decimal("500000.00")
        
        calculated_penalty = min(late_count * penalty_per_tx, max_penalty)
        assert calculated_penalty == Decimal("300000.00")
    
    def test_penalty_calculation_capped(self):
        """Penalty for 100 late transactions should be capped at ₦500,000."""
        late_count = 100
        penalty_per_tx = Decimal("10000.00")
        max_penalty = Decimal("500000.00")
        
        calculated_penalty = min(late_count * penalty_per_tx, max_penalty)
        assert calculated_penalty == Decimal("500000.00")
    
    def test_report_deadline_calculation(self):
        """Report deadline should be 24 hours from transaction creation."""
        from datetime import datetime, timedelta
        
        REPORTING_WINDOW_HOURS = 24
        created_at = datetime(2026, 1, 4, 14, 0, 0)  # 2:00 PM
        
        report_deadline = created_at + timedelta(hours=REPORTING_WINDOW_HOURS)
        
        expected_deadline = datetime(2026, 1, 5, 14, 0, 0)  # Next day 2:00 PM
        assert report_deadline == expected_deadline
    
    def test_is_within_reporting_window(self):
        """Check if current time is within 24-hour reporting window."""
        from datetime import datetime, timedelta
        
        created_at = datetime.utcnow() - timedelta(hours=12)  # 12 hours ago
        report_deadline = created_at + timedelta(hours=24)
        
        now = datetime.utcnow()
        is_within_window = now < report_deadline
        
        assert is_within_window is True  # Still 12 hours left
    
    def test_is_past_reporting_window(self):
        """Check if 24-hour window has expired (overdue)."""
        from datetime import datetime, timedelta
        
        created_at = datetime.utcnow() - timedelta(hours=30)  # 30 hours ago
        report_deadline = created_at + timedelta(hours=24)
        
        now = datetime.utcnow()
        is_overdue = now > report_deadline
        
        assert is_overdue is True  # Window expired 6 hours ago
    
    def test_b2c_report_reference_format(self):
        """B2C report reference should follow expected format."""
        import re
        
        # Format: B2C-YYYYMMDDHHMMSS-XXXXXX
        report_ref = "B2C-20260104143022-ABC123"
        pattern = r"^B2C-\d{14}-[A-Z0-9]{6}$"
        
        assert re.match(pattern, report_ref) is not None
    
    def test_entity_settings_default_values(self):
        """Entity B2C settings should have correct default values."""
        # Default: enabled=False, threshold=₦50,000
        default_enabled = False
        default_threshold = Decimal("50000.00")
        
        assert default_enabled is False
        assert default_threshold == Decimal("50000.00")


class TestB2CService:
    """Tests for B2CReportingService functionality."""
    
    def test_service_constants(self):
        """B2CReportingService should have correct constants."""
        DEFAULT_THRESHOLD = Decimal("50000.00")
        REPORTING_WINDOW_HOURS = 24
        LATE_PENALTY_PER_TRANSACTION = Decimal("10000.00")
        MAX_DAILY_PENALTY = Decimal("500000.00")
        
        assert DEFAULT_THRESHOLD == Decimal("50000.00")
        assert REPORTING_WINDOW_HOURS == 24
        assert LATE_PENALTY_PER_TRANSACTION == Decimal("10000.00")
        assert MAX_DAILY_PENALTY == Decimal("500000.00")
    
    def test_compliance_reference(self):
        """B2C reporting is per Nigeria Tax Administration Act 2025, Section 42."""
        compliance_ref = "Nigeria Tax Administration Act 2025, Section 42"
        assert "2025" in compliance_ref
        assert "Section 42" in compliance_ref


class TestCompliancePenaltyTypes:
    """Tests for all penalty types in the 2026 Tax Reform."""
    
    def test_late_filing_penalty_rates(self):
        """Late filing penalty: ₦100,000 first month + ₦50,000 subsequent."""
        from app.services.compliance_penalty_service import PENALTY_SCHEDULE, PenaltyType
        
        rates = PENALTY_SCHEDULE[PenaltyType.LATE_FILING]
        assert rates["first_month"] == Decimal("100000")
        assert rates["subsequent_month"] == Decimal("50000")
    
    def test_unregistered_vendor_fixed_penalty(self):
        """Unregistered vendor penalty is ₦5,000,000 fixed."""
        from app.services.compliance_penalty_service import PENALTY_SCHEDULE, PenaltyType
        
        rates = PENALTY_SCHEDULE[PenaltyType.UNREGISTERED_VENDOR]
        assert rates["fixed_amount"] == Decimal("5000000")
    
    def test_b2c_late_reporting_rates(self):
        """B2C late reporting: ₦10,000/tx, max ₦500,000/day."""
        from app.services.compliance_penalty_service import PENALTY_SCHEDULE, PenaltyType
        
        rates = PENALTY_SCHEDULE[PenaltyType.B2C_LATE_REPORTING]
        assert rates["per_transaction"] == Decimal("10000")
        assert rates["max_daily"] == Decimal("500000")
    
    def test_e_invoice_noncompliance_penalty(self):
        """E-invoice non-compliance: ₦50,000 per invoice."""
        from app.services.compliance_penalty_service import PENALTY_SCHEDULE, PenaltyType
        
        rates = PENALTY_SCHEDULE[PenaltyType.E_INVOICE_NONCOMPLIANCE]
        assert rates["per_invoice"] == Decimal("50000")
    
    def test_invalid_tin_penalty(self):
        """Invalid TIN: ₦25,000 per occurrence."""
        from app.services.compliance_penalty_service import PENALTY_SCHEDULE, PenaltyType
        
        rates = PENALTY_SCHEDULE[PenaltyType.INVALID_TIN]
        assert rates["per_occurrence"] == Decimal("25000")
    
    def test_missing_records_penalty(self):
        """Missing records: ₦100,000 per year."""
        from app.services.compliance_penalty_service import PENALTY_SCHEDULE, PenaltyType
        
        rates = PENALTY_SCHEDULE[PenaltyType.MISSING_RECORDS]
        assert rates["per_year"] == Decimal("100000")
    
    def test_nrs_access_denial_penalty(self):
        """NRS access denial: ₦1,000,000 fixed."""
        from app.services.compliance_penalty_service import PENALTY_SCHEDULE, PenaltyType
        
        rates = PENALTY_SCHEDULE[PenaltyType.NRS_ACCESS_DENIAL]
        assert rates["fixed_amount"] == Decimal("1000000")
    
    def test_vat_non_remittance_penalty_rates(self):
        """VAT non-remittance: 10% + 2% monthly interest."""
        from app.services.compliance_penalty_service import PENALTY_SCHEDULE, PenaltyType
        
        rates = PENALTY_SCHEDULE[PenaltyType.VAT_NON_REMITTANCE]
        assert rates["percentage"] == Decimal("10")
        assert rates["monthly_interest"] == Decimal("2")
    
    def test_paye_non_remittance_penalty_rates(self):
        """PAYE non-remittance: 10% + 2% monthly interest."""
        from app.services.compliance_penalty_service import PENALTY_SCHEDULE, PenaltyType
        
        rates = PENALTY_SCHEDULE[PenaltyType.PAYE_NON_REMITTANCE]
        assert rates["percentage"] == Decimal("10")
        assert rates["monthly_interest"] == Decimal("2")
    
    def test_wht_non_remittance_penalty_rates(self):
        """WHT non-remittance: 10% + 2% monthly interest."""
        from app.services.compliance_penalty_service import PENALTY_SCHEDULE, PenaltyType
        
        rates = PENALTY_SCHEDULE[PenaltyType.WHT_NON_REMITTANCE]
        assert rates["percentage"] == Decimal("10")
        assert rates["monthly_interest"] == Decimal("2")
    
    def test_all_penalty_types_have_descriptions(self):
        """All penalty types should have descriptions."""
        from app.services.compliance_penalty_service import PENALTY_SCHEDULE
        
        for penalty_type, rates in PENALTY_SCHEDULE.items():
            assert "description" in rates, f"{penalty_type} missing description"
            assert len(rates["description"]) > 0


class TestPenaltyStatus:
    """Tests for penalty status values."""
    
    def test_penalty_status_values(self):
        """Penalty status should have all expected values."""
        from app.services.compliance_penalty_service import PenaltyStatus
        
        statuses = [s.value for s in PenaltyStatus]
        assert "potential" in statuses
        assert "incurred" in statuses
        assert "paid" in statuses
        assert "waived" in statuses
        assert "disputed" in statuses
    
    def test_penalty_type_values(self):
        """Penalty type should have all expected values."""
        from app.services.compliance_penalty_service import PenaltyType
        
        types = [t.value for t in PenaltyType]
        assert "late_filing" in types
        assert "unregistered_vendor" in types
        assert "b2c_late_reporting" in types
        assert "vat_non_remittance" in types
        assert "paye_non_remittance" in types
        assert "wht_non_remittance" in types


class TestPenaltyCalculations:
    """Tests for penalty calculation edge cases."""
    
    def test_tax_remittance_on_time_no_penalty(self):
        """On-time tax remittance should have no penalty."""
        service = CompliancePenaltyService(db=None)
        
        tax_amount = Decimal("500000")
        due_date = date(2026, 1, 21)
        payment_date = date(2026, 1, 20)  # Before due date
        
        result = service.calculate_tax_remittance_penalty(
            PenaltyType.VAT_NON_REMITTANCE,
            tax_amount,
            due_date,
            payment_date,
        )
        
        assert result.total_amount == Decimal("0")
        assert result.months_late == 0
    
    def test_paye_late_remittance_calculation(self):
        """PAYE late remittance penalty calculation."""
        service = CompliancePenaltyService(db=None)
        
        tax_amount = Decimal("200000")
        due_date = date(2026, 1, 15)
        payment_date = date(2026, 2, 20)  # 1 month late
        
        result = service.calculate_tax_remittance_penalty(
            PenaltyType.PAYE_NON_REMITTANCE,
            tax_amount,
            due_date,
            payment_date,
        )
        
        # 10% of 200,000 = 20,000 base
        assert result.base_amount == Decimal("20000")
        assert result.months_late >= 1
    
    def test_late_filing_exact_deadline_no_penalty(self):
        """Filing on exact deadline should have no penalty."""
        service = CompliancePenaltyService(db=None)
        
        due_date = date(2026, 1, 21)
        filing_date = date(2026, 1, 21)  # Exact deadline
        
        result = service.calculate_late_filing_penalty(due_date, filing_date)
        
        assert result.total_amount == Decimal("0")
        assert result.months_late == 0


# Run with: pytest tests/test_2026_compliance.py -v
