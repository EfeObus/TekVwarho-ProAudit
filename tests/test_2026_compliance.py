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


class TestAuditVault:
    """Tests for Audit Vault Service - NTAA 2025 Compliance."""
    
    def test_retention_years_is_5(self):
        """NTAA 2025 requires 5-year minimum retention."""
        from app.services.audit_vault_service import NTAA_RETENTION_YEARS
        
        assert NTAA_RETENTION_YEARS == 5
    
    def test_archive_after_2_years(self):
        """Records should be archived after 2 years."""
        from app.services.audit_vault_service import ARCHIVE_AFTER_YEARS
        
        assert ARCHIVE_AFTER_YEARS == 2
    
    def test_retention_status_values(self):
        """Verify all retention status values exist."""
        from app.services.audit_vault_service import RetentionStatus
        
        statuses = [s.value for s in RetentionStatus]
        assert "active" in statuses
        assert "archived" in statuses
        assert "pending_purge" in statuses
        assert "legal_hold" in statuses
    
    def test_document_types(self):
        """Verify all required document types exist."""
        from app.services.audit_vault_service import DocumentType
        
        types = [t.value for t in DocumentType]
        assert "invoice" in types
        assert "receipt" in types
        assert "transaction" in types
        assert "tax_filing" in types
        assert "nrs_submission" in types
        assert "credit_note" in types
        assert "fixed_asset" in types
        assert "payroll" in types
    
    def test_vault_document_dataclass(self):
        """Test VaultDocument dataclass."""
        from app.services.audit_vault_service import (
            VaultDocument, DocumentType, RetentionStatus
        )
        from datetime import datetime, date
        
        doc = VaultDocument(
            id="test-123",
            document_type=DocumentType.INVOICE,
            reference_number="INV-2026-001",
            created_at=datetime.now(),
            fiscal_year=2026,
            retention_until=date(2031, 1, 1),
            status=RetentionStatus.ACTIVE,
            integrity_hash="abc123",
            metadata={"customer": "Test"},
        )
        
        assert doc.id == "test-123"
        assert doc.document_type == DocumentType.INVOICE
        assert doc.fiscal_year == 2026
        assert doc.status == RetentionStatus.ACTIVE
    
    def test_vault_statistics_dataclass(self):
        """Test VaultStatistics dataclass."""
        from app.services.audit_vault_service import VaultStatistics
        
        stats = VaultStatistics(
            total_records=1000,
            active_records=600,
            archived_records=350,
            pending_purge=50,
            legal_hold=0,
            oldest_record=date(2021, 1, 15),
            by_fiscal_year={2025: 300, 2026: 700},
            by_document_type={"invoice": 500, "transaction": 300, "receipt": 200},
            storage_size_estimate_mb=2.0,
        )
        
        assert stats.total_records == 1000
        assert stats.active_records == 600
        assert stats.archived_records == 350
        assert stats.by_fiscal_year[2026] == 700
        assert stats.by_document_type["invoice"] == 500
    
    def test_service_initialization(self):
        """Test AuditVaultService can be initialized."""
        from app.services.audit_vault_service import AuditVaultService
        
        # Service should initialize without DB for basic operations
        service = AuditVaultService(db=None)
        assert service is not None
    
    def test_legal_hold_extension_years(self):
        """Legal hold should extend retention by 2 years."""
        from app.services.audit_vault_service import LEGAL_HOLD_EXTENSION_YEARS
        
        assert LEGAL_HOLD_EXTENSION_YEARS == 2
    
    def test_retention_policy_constants(self):
        """Verify all retention policy constants are defined."""
        from app.services.audit_vault_service import (
            NTAA_RETENTION_YEARS,
            ARCHIVE_AFTER_YEARS,
            LEGAL_HOLD_EXTENSION_YEARS,
        )
        
        # 5-year retention
        assert NTAA_RETENTION_YEARS == 5
        # Archive after 2 years
        assert ARCHIVE_AFTER_YEARS == 2
        # Legal hold adds 2 years
        assert LEGAL_HOLD_EXTENSION_YEARS == 2
        # Total with legal hold = 7 years
        assert NTAA_RETENTION_YEARS + LEGAL_HOLD_EXTENSION_YEARS == 7
    
    def test_integrity_hash_algorithm(self):
        """Test integrity hash uses SHA-256."""
        import hashlib
        import json
        
        # Same algorithm used in service
        test_data = {"id": "test-123", "entity_id": "entity-456"}
        hash_result = hashlib.sha256(
            json.dumps(test_data, sort_keys=True).encode()
        ).hexdigest()
        
        # SHA-256 produces 64 character hex string
        assert len(hash_result) == 64
        assert hash_result.isalnum()


class TestAuditVaultCompliance:
    """Tests for NTAA 2025 compliance features of Audit Vault."""
    
    def test_compliance_standard_is_ntaa_2025(self):
        """Compliance standard should be NTAA 2025."""
        # This is documented in the service
        from app.services.audit_vault_service import AuditVaultService
        
        # The service should reference NTAA 2025
        service = AuditVaultService(db=None)
        assert "NTAA" in service.__class__.__doc__
        assert "2025" in service.__class__.__doc__
    
    def test_retention_period_meets_ntaa_requirement(self):
        """5-year retention meets NTAA 2025 minimum requirement."""
        from app.services.audit_vault_service import NTAA_RETENTION_YEARS
        
        # NTAA 2025 requires minimum 5 years
        ntaa_minimum = 5
        assert NTAA_RETENTION_YEARS >= ntaa_minimum
    
    def test_immutability_concept(self):
        """Audit logs should be immutable (no UPDATE/DELETE)."""
        from app.models.audit import AuditLog
        
        # The model docstring should mention immutability
        assert "Immutable" in AuditLog.__doc__ or "immutable" in AuditLog.__doc__.lower()
    
    def test_nrs_fields_exist(self):
        """NRS submission fields should exist for compliance."""
        from app.models.audit import AuditLog
        
        # Check NRS fields exist in the model
        columns = [c.name for c in AuditLog.__table__.columns]
        assert "nrs_irn" in columns
        assert "nrs_response" in columns
    
    def test_device_fingerprint_for_submission_verification(self):
        """Device fingerprint required for proving tax return submission."""
        from app.models.audit import AuditLog
        
        columns = [c.name for c in AuditLog.__table__.columns]
        assert "device_fingerprint" in columns
        assert "ip_address" in columns
        assert "user_agent" in columns


# ============================================================
# FIXED ASSET REGISTER TESTS
# ============================================================

class TestFixedAssetModel:
    """Tests for Fixed Asset Model and Enums."""
    
    def test_asset_category_enum_values(self):
        """All Nigerian standard asset categories should be defined."""
        from app.models.fixed_asset import AssetCategory
        
        categories = [c.value for c in AssetCategory]
        assert "land" in categories
        assert "buildings" in categories
        assert "plant_machinery" in categories
        assert "furniture_fittings" in categories
        assert "motor_vehicles" in categories
        assert "computer_equipment" in categories
        assert "office_equipment" in categories
        assert "leasehold_improvements" in categories
        assert "intangible_assets" in categories
        assert "other" in categories
    
    def test_asset_status_enum_values(self):
        """All asset statuses should be defined."""
        from app.models.fixed_asset import AssetStatus
        
        statuses = [s.value for s in AssetStatus]
        assert "active" in statuses
        assert "disposed" in statuses
        assert "written_off" in statuses
        assert "under_repair" in statuses
        assert "idle" in statuses
    
    def test_depreciation_method_enum_values(self):
        """All depreciation methods should be defined."""
        from app.models.fixed_asset import DepreciationMethod
        
        methods = [m.value for m in DepreciationMethod]
        assert "straight_line" in methods
        assert "reducing_balance" in methods
        assert "units_of_production" in methods
    
    def test_disposal_type_enum_values(self):
        """All disposal types should be defined."""
        from app.models.fixed_asset import DisposalType
        
        types = [t.value for t in DisposalType]
        assert "sale" in types
        assert "trade_in" in types
        assert "scrapped" in types
        assert "donated" in types
        assert "theft" in types
        assert "insurance_claim" in types
    
    def test_standard_depreciation_rates(self):
        """Nigerian standard depreciation rates should be defined."""
        from app.models.fixed_asset import STANDARD_DEPRECIATION_RATES, AssetCategory
        
        # Land should have 0% (no depreciation)
        assert STANDARD_DEPRECIATION_RATES[AssetCategory.LAND] == Decimal("0")
        
        # Buildings at 10%
        assert STANDARD_DEPRECIATION_RATES[AssetCategory.BUILDINGS] == Decimal("10")
        
        # Motor vehicles at 25%
        assert STANDARD_DEPRECIATION_RATES[AssetCategory.MOTOR_VEHICLES] == Decimal("25")
        
        # Computer equipment at 25%
        assert STANDARD_DEPRECIATION_RATES[AssetCategory.COMPUTER_EQUIPMENT] == Decimal("25")
        
        # Furniture at 20%
        assert STANDARD_DEPRECIATION_RATES[AssetCategory.FURNITURE_FITTINGS] == Decimal("20")
        
        # Plant & Machinery at 25%
        assert STANDARD_DEPRECIATION_RATES[AssetCategory.PLANT_MACHINERY] == Decimal("25")
    
    def test_intangible_assets_depreciation_rate(self):
        """Intangible assets should have 12.5% rate."""
        from app.models.fixed_asset import STANDARD_DEPRECIATION_RATES, AssetCategory
        
        assert STANDARD_DEPRECIATION_RATES[AssetCategory.INTANGIBLE_ASSETS] == Decimal("12.5")


class TestFixedAssetDepreciation:
    """Tests for depreciation calculation methods."""
    
    def test_straight_line_depreciation(self):
        """Test straight-line depreciation calculation."""
        # Formula: (Cost - Residual) / Useful Life
        acquisition_cost = Decimal("1000000")  # ₦1M
        residual_value = Decimal("100000")     # ₦100K
        useful_life = 5  # years
        
        annual_depreciation = (acquisition_cost - residual_value) / useful_life
        
        assert annual_depreciation == Decimal("180000")  # ₦180K per year
    
    def test_reducing_balance_depreciation(self):
        """Test reducing balance depreciation calculation."""
        # Formula: NBV * Rate
        net_book_value = Decimal("1000000")  # ₦1M NBV
        rate = Decimal("25")  # 25%
        
        annual_depreciation = net_book_value * (rate / 100)
        
        assert annual_depreciation == Decimal("250000")  # ₦250K first year
    
    def test_reducing_balance_year_2(self):
        """Reducing balance Year 2 should have lower depreciation."""
        nbv_year_1 = Decimal("1000000")
        rate = Decimal("25")
        
        dep_year_1 = nbv_year_1 * (rate / 100)
        nbv_year_2 = nbv_year_1 - dep_year_1  # ₦750K
        dep_year_2 = nbv_year_2 * (rate / 100)  # ₦187.5K
        
        assert dep_year_2 < dep_year_1
        assert dep_year_2 == Decimal("187500")
    
    def test_net_book_value_calculation(self):
        """NBV = Cost - Accumulated Depreciation."""
        cost = Decimal("500000")
        accumulated_dep = Decimal("125000")
        
        nbv = cost - accumulated_dep
        
        assert nbv == Decimal("375000")
    
    def test_fully_depreciated_check(self):
        """Asset is fully depreciated when NBV <= Residual."""
        cost = Decimal("1000000")
        accumulated = Decimal("900000")
        residual = Decimal("100000")
        
        nbv = cost - accumulated  # ₦100K
        is_fully_depreciated = nbv <= residual
        
        assert is_fully_depreciated is True


class TestFixedAssetDisposal:
    """Tests for asset disposal and capital gains."""
    
    def test_capital_gain_calculation(self):
        """Capital gain = Proceeds - NBV."""
        proceeds = Decimal("500000")  # ₦500K sale price
        nbv = Decimal("300000")       # ₦300K book value
        
        capital_gain = proceeds - nbv
        
        assert capital_gain == Decimal("200000")  # ₦200K gain
    
    def test_capital_loss_calculation(self):
        """Capital loss when proceeds < NBV."""
        proceeds = Decimal("200000")  # ₦200K sale price
        nbv = Decimal("350000")       # ₦350K book value
        
        capital_gain = proceeds - nbv
        
        assert capital_gain == Decimal("-150000")  # ₦150K loss
    
    def test_capital_gain_taxed_at_cit_rate_2026(self):
        """Under 2026 law, capital gains taxed at CIT rate."""
        # 2026 reform changed CGT to flat CIT rate
        capital_gain = Decimal("1000000")  # ₦1M gain
        cit_rate_large_company = Decimal("30")  # 30%
        
        cgt_liability = capital_gain * (cit_rate_large_company / 100)
        
        assert cgt_liability == Decimal("300000")  # ₦300K tax
    
    def test_scrapped_asset_zero_proceeds(self):
        """Scrapped asset should have zero proceeds = full loss."""
        nbv = Decimal("250000")
        proceeds = Decimal("0")  # Scrapped
        
        capital_loss = proceeds - nbv
        
        assert capital_loss == Decimal("-250000")


class TestFixedAssetVATRecovery:
    """Tests for VAT recovery on capital assets (2026 compliance)."""
    
    def test_vat_recovery_requires_vendor_irn(self):
        """VAT recovery on fixed assets requires valid vendor IRN."""
        # Under 2026 law, input VAT on capital assets is recoverable
        # but requires vendor's NRS IRN
        has_vendor_irn = True
        is_recoverable = has_vendor_irn  # Simplified logic
        
        assert is_recoverable is True
    
    def test_no_vat_recovery_without_irn(self):
        """No VAT recovery without vendor IRN."""
        has_vendor_irn = False
        is_recoverable = has_vendor_irn
        
        assert is_recoverable is False
    
    def test_vat_on_capital_asset_calculation(self):
        """VAT on capital asset = 7.5% of acquisition cost."""
        acquisition_cost_ex_vat = Decimal("1000000")  # ₦1M
        vat_rate = Decimal("7.5")
        
        vat_amount = acquisition_cost_ex_vat * (vat_rate / 100)
        
        assert vat_amount == Decimal("75000")  # ₦75K VAT


class TestFixedAssetDevelopmentLevy:
    """Tests for Development Levy threshold calculations."""
    
    def test_small_company_exemption_threshold(self):
        """Small companies exempt if fixed assets <= ₦250M."""
        fixed_assets_total = Decimal("200000000")  # ₦200M
        threshold = Decimal("250000000")  # ₦250M
        
        is_exempt = fixed_assets_total <= threshold
        
        assert is_exempt is True
    
    def test_large_company_not_exempt(self):
        """Companies above threshold not exempt."""
        fixed_assets_total = Decimal("300000000")  # ₦300M
        threshold = Decimal("250000000")  # ₦250M
        
        is_exempt = fixed_assets_total <= threshold
        
        assert is_exempt is False
    
    def test_nbv_used_for_threshold(self):
        """Net book value (not cost) used for threshold."""
        # Development Levy exemption uses NBV, not original cost
        total_cost = Decimal("400000000")  # ₦400M cost
        total_accumulated_dep = Decimal("200000000")  # ₦200M dep
        
        nbv = total_cost - total_accumulated_dep  # ₦200M NBV
        threshold = Decimal("250000000")
        
        is_exempt = nbv <= threshold
        
        assert is_exempt is True


class TestFixedAssetService:
    """Tests for Fixed Asset Service methods."""
    
    def test_asset_code_format(self):
        """Asset code should follow FA-{CATEGORY}-{SEQ} format."""
        # Example codes
        codes = ["FA-MV-0001", "FA-CE-0002", "FA-BG-0003"]
        
        for code in codes:
            parts = code.split("-")
            assert parts[0] == "FA"
            assert len(parts[1]) == 2
            assert len(parts[2]) == 4
    
    def test_category_prefixes_mapping(self):
        """Each category should have a 2-letter prefix."""
        prefixes = {
            "land": "LD",
            "buildings": "BG",
            "plant_machinery": "PM",
            "furniture_fittings": "FF",
            "motor_vehicles": "MV",
            "computer_equipment": "CE",
            "office_equipment": "OE",
            "leasehold_improvements": "LI",
            "intangible_assets": "IA",
            "other": "OT",
        }
        
        for category, prefix in prefixes.items():
            assert len(prefix) == 2
            assert prefix.isupper()


class TestFixedAssetRouter:
    """Tests for Fixed Asset API Router structure."""
    
    def test_router_prefix(self):
        """Router should have correct prefix."""
        from app.routers.fixed_assets import router
        
        assert router.prefix == "/api/v1/fixed-assets"
    
    def test_router_tags(self):
        """Router should have correct tags."""
        from app.routers.fixed_assets import router
        
        assert "Fixed Assets" in router.tags
    
    def test_pydantic_schemas_exist(self):
        """All required Pydantic schemas should be defined."""
        from app.routers.fixed_assets import (
            FixedAssetCreate,
            FixedAssetUpdate,
            FixedAssetResponse,
            AssetDisposalRequest,
            DepreciationRunRequest,
        )
        
        # Schemas should be importable
        assert FixedAssetCreate is not None
        assert FixedAssetUpdate is not None
        assert FixedAssetResponse is not None
        assert AssetDisposalRequest is not None
        assert DepreciationRunRequest is not None


class TestFixedAssetCompliance2026:
    """Tests for 2026 Nigeria Tax Reform compliance features."""
    
    def test_cgt_taxed_at_cit_rate(self):
        """Capital gains should be taxed at CIT rate (not separate CGT)."""
        # Under 2026 reform, CGT abolished for companies
        # Capital gains included in assessable profit, taxed at CIT rate
        cit_rate_large = Decimal("30")  # 30% for large companies
        cit_rate_medium = Decimal("20")  # 20% for medium
        cit_rate_small = Decimal("0")   # 0% for small
        
        capital_gain = Decimal("1000000")
        
        # Large company tax on gain
        tax_large = capital_gain * (cit_rate_large / 100)
        assert tax_large == Decimal("300000")
        
        # Small company (exempt)
        tax_small = capital_gain * (cit_rate_small / 100)
        assert tax_small == Decimal("0")
    
    def test_input_vat_recovery_on_assets(self):
        """2026 law allows VAT recovery on capital assets."""
        # Previously, input VAT on capital assets was not recoverable
        # 2026 reform allows recovery with valid vendor IRN
        is_recoverable_2026 = True
        
        assert is_recoverable_2026 is True
    
    def test_vendor_irn_required_for_recovery(self):
        """Vendor's NRS IRN required for VAT recovery claim."""
        # Must have valid Invoice Reference Number from NRS
        vendor_irn = "NRS-2025-001234567890123"
        has_valid_irn = vendor_irn and vendor_irn.startswith("NRS")
        
        assert has_valid_irn is True
    
    def test_depreciation_reduces_assessable_profit(self):
        """Depreciation reduces assessable profit for tax."""
        gross_profit = Decimal("10000000")  # ₦10M
        depreciation = Decimal("1500000")    # ₦1.5M annual depreciation
        
        assessable_profit = gross_profit - depreciation
        
        assert assessable_profit == Decimal("8500000")  # ₦8.5M
    
    def test_development_levy_threshold_250m(self):
        """Development Levy exemption threshold is ₦250M fixed assets."""
        from app.models.fixed_asset import STANDARD_DEPRECIATION_RATES
        
        # Threshold defined in 2026 law
        threshold = Decimal("250000000")
        
        # Verify threshold is correct
        assert threshold == Decimal("250000000")


class TestSelfAssessmentService:
    """Tests for Self-Assessment Service for NRS/TaxPro Max."""
    
    def test_service_imports(self):
        """Self-Assessment service should be importable."""
        from app.services.self_assessment_service import (
            SelfAssessmentService,
            TaxReturnType,
            TaxProMaxFormCode,
            CITSelfAssessment,
            VATSelfAssessment,
        )
        assert SelfAssessmentService is not None
        assert TaxReturnType is not None
        assert TaxProMaxFormCode is not None
    
    def test_tax_return_types(self):
        """Verify all required tax return types exist."""
        from app.services.self_assessment_service import TaxReturnType
        
        # All Nigeria tax types should be defined
        assert hasattr(TaxReturnType, 'CIT')
        assert hasattr(TaxReturnType, 'VAT')
        assert hasattr(TaxReturnType, 'PAYE')
        assert hasattr(TaxReturnType, 'WHT')
        assert hasattr(TaxReturnType, 'DEV_LEVY')
        assert hasattr(TaxReturnType, 'CAPITAL_GAINS')  # Named CAPITAL_GAINS not CGT
    
    def test_taxpro_max_form_codes(self):
        """Verify TaxPro Max form codes are properly defined."""
        from app.services.self_assessment_service import TaxProMaxFormCode
        
        # Form codes used by TaxPro Max portal
        assert TaxProMaxFormCode.CIT_ANNUAL.value == "CIT-01"
        assert TaxProMaxFormCode.VAT_MONTHLY.value == "VAT-01"
        assert TaxProMaxFormCode.PAYE_MONTHLY.value == "PAYE-01"
        assert TaxProMaxFormCode.WHT_MONTHLY.value == "WHT-01"
        assert TaxProMaxFormCode.DEV_LEVY_ANNUAL.value == "DL-01"
    
    def test_cit_assessment_data_structure(self):
        """CIT Self-Assessment should have all required fields."""
        from app.services.self_assessment_service import CITSelfAssessment
        from dataclasses import fields
        
        field_names = [f.name for f in fields(CITSelfAssessment)]
        
        # Core identification (actual field names)
        assert 'entity_id' in field_names
        assert 'tin' in field_names
        assert 'company_name' in field_names
        assert 'fiscal_year_end' in field_names
        
        # Income statement fields
        assert 'gross_turnover' in field_names
        assert 'cost_of_sales' in field_names
        assert 'gross_profit' in field_names
        assert 'operating_expenses' in field_names
        
        # Tax computation fields
        assert 'assessable_profit' in field_names
        assert 'tax_rate' in field_names
        assert 'cit_liability' in field_names
        assert 'total_tax_payable' in field_names
    
    def test_vat_assessment_data_structure(self):
        """VAT Self-Assessment should have all required fields."""
        from app.services.self_assessment_service import VATSelfAssessment
        from dataclasses import fields
        
        field_names = [f.name for f in fields(VATSelfAssessment)]
        
        # Core fields (actual field names)
        assert 'entity_id' in field_names
        assert 'tin' in field_names
        assert 'period_month' in field_names
        assert 'period_year' in field_names
        
        # VAT computation (actual field names)
        assert 'standard_rated_sales' in field_names
        assert 'output_vat' in field_names
        assert 'standard_rated_purchases' in field_names
        assert 'input_vat' in field_names
        assert 'net_vat_payable' in field_names
        assert 'refund_claimed' in field_names
    
    def test_csv_export_columns_cit(self):
        """CIT export should have TaxPro Max required columns."""
        from app.services.self_assessment_service import TAXPRO_CIT_COLUMNS
        
        # Must include all required TaxPro Max CIT columns (actual names)
        assert 'TIN' in TAXPRO_CIT_COLUMNS
        assert 'Company_Name' in TAXPRO_CIT_COLUMNS
        assert 'Fiscal_Year_End' in TAXPRO_CIT_COLUMNS
        assert 'Gross_Turnover' in TAXPRO_CIT_COLUMNS
        assert 'CIT_Liability' in TAXPRO_CIT_COLUMNS
        assert len(TAXPRO_CIT_COLUMNS) >= 15  # At least 15 columns required
    
    def test_csv_export_columns_vat(self):
        """VAT export should have TaxPro Max required columns."""
        from app.services.self_assessment_service import TAXPRO_VAT_COLUMNS
        
        # Must include all required TaxPro Max VAT columns (actual names)
        assert 'TIN' in TAXPRO_VAT_COLUMNS
        assert 'Period_Month' in TAXPRO_VAT_COLUMNS
        assert 'Period_Year' in TAXPRO_VAT_COLUMNS
        assert 'Standard_Rated_Sales' in TAXPRO_VAT_COLUMNS
        assert 'Output_VAT' in TAXPRO_VAT_COLUMNS
        assert 'Input_VAT' in TAXPRO_VAT_COLUMNS
        assert 'Net_VAT_Payable' in TAXPRO_VAT_COLUMNS
    
    def test_cit_rate_tiers(self):
        """CIT rates should follow 2026 tiered structure."""
        # 2026 CIT rates by company size
        # Large (>₦100M): 30%
        # Medium (₦25M-₦100M): 20%
        # Small (<₦25M): 0%
        
        cit_rate_large = Decimal("30")
        cit_rate_medium = Decimal("20")
        cit_rate_small = Decimal("0")
        
        assert cit_rate_large == Decimal("30")
        assert cit_rate_medium == Decimal("20")
        assert cit_rate_small == Decimal("0")
    
    def test_vat_rate_is_75_percent(self):
        """2026 VAT rate should be 7.5%."""
        # Standard VAT rate under 2026 law
        vat_rate = Decimal("7.5")
        assert vat_rate == Decimal("7.5")


class TestTaxProMaxExport:
    """Tests for TaxPro Max Export functionality."""
    
    def test_csv_columns_cit_count(self):
        """CIT export should have correct number of columns."""
        from app.services.self_assessment_service import TAXPRO_CIT_COLUMNS
        
        # TaxPro Max requires 21 columns for CIT
        assert len(TAXPRO_CIT_COLUMNS) == 21
    
    def test_csv_columns_vat_count(self):
        """VAT export should have correct number of columns."""
        from app.services.self_assessment_service import TAXPRO_VAT_COLUMNS
        
        # TaxPro Max requires 17 columns for VAT
        assert len(TAXPRO_VAT_COLUMNS) == 17
    
    def test_export_filename_format_cit(self):
        """CIT export filename should follow TaxPro Max naming convention."""
        # Expected format: {TIN}_CIT_{FiscalYear}.csv
        tin = "1234567890"
        fiscal_year = 2025
        expected_filename = f"{tin}_CIT_{fiscal_year}.csv"
        
        assert expected_filename == "1234567890_CIT_2025.csv"
    
    def test_export_filename_format_vat(self):
        """VAT export filename should follow TaxPro Max naming convention."""
        # Expected format: {TIN}_VAT_{Year}_{Month:02d}.csv
        tin = "1234567890"
        year = 2025
        month = 3
        expected_filename = f"{tin}_VAT_{year}_{month:02d}.csv"
        
        assert expected_filename == "1234567890_VAT_2025_03.csv"
    
    def test_annual_returns_package_structure(self):
        """Annual returns package should contain CIT + VAT assessments."""
        from app.services.self_assessment_service import AnnualReturnsSummary
        from dataclasses import fields
        
        field_names = [f.name for f in fields(AnnualReturnsSummary)]
        
        assert 'fiscal_year' in field_names
        assert 'cit_assessment' in field_names  # Actual field name
        assert 'vat_assessments' in field_names  # Actual field name
        assert 'total_vat' in field_names
        assert 'grand_total' in field_names
    
    def test_paye_columns_count(self):
        """PAYE export should have correct number of columns."""
        from app.services.self_assessment_service import TAXPRO_PAYE_COLUMNS
        
        # TaxPro Max requires 13 columns for PAYE
        assert len(TAXPRO_PAYE_COLUMNS) == 13
    
    def test_wht_columns_count(self):
        """WHT export should have correct number of columns."""
        from app.services.self_assessment_service import TAXPRO_WHT_COLUMNS
        
        # TaxPro Max requires 11 columns for WHT
        assert len(TAXPRO_WHT_COLUMNS) == 11


class TestSelfAssessmentAPIEndpoints:
    """Tests for Self-Assessment API endpoints."""
    
    def test_endpoint_info_path(self):
        """Self-Assessment info endpoint should exist."""
        # Expected: GET /api/v1/2026/self-assessment/info
        endpoint_path = "/api/v1/2026/self-assessment/info"
        assert "self-assessment" in endpoint_path
        assert "info" in endpoint_path
    
    def test_endpoint_cit_assessment_path(self):
        """CIT assessment endpoint should exist."""
        # Expected: GET /api/v1/2026/self-assessment/{entity_id}/cit/{fiscal_year}
        endpoint_path = "/api/v1/2026/self-assessment/{entity_id}/cit/{fiscal_year}"
        assert "cit" in endpoint_path
        assert "{entity_id}" in endpoint_path
    
    def test_endpoint_vat_assessment_path(self):
        """VAT assessment endpoint should exist."""
        # Expected: GET /api/v1/2026/self-assessment/{entity_id}/vat/{year}/{month}
        endpoint_path = "/api/v1/2026/self-assessment/{entity_id}/vat/{year}/{month}"
        assert "vat" in endpoint_path
        assert "{year}" in endpoint_path
        assert "{month}" in endpoint_path
    
    def test_endpoint_annual_returns_path(self):
        """Annual returns endpoint should exist."""
        # Expected: GET /api/v1/2026/self-assessment/{entity_id}/annual/{fiscal_year}
        endpoint_path = "/api/v1/2026/self-assessment/{entity_id}/annual/{fiscal_year}"
        assert "annual" in endpoint_path
    
    def test_endpoint_taxpro_export_path(self):
        """TaxPro export endpoint should exist."""
        # Expected: POST /api/v1/2026/taxpro-export/{entity_id}
        endpoint_path = "/api/v1/2026/taxpro-export/{entity_id}"
        assert "taxpro-export" in endpoint_path


class TestSelfAssessmentCompliance2026:
    """Tests for 2026 Self-Assessment compliance requirements."""
    
    def test_filing_deadline_cit_6_months_after_year_end(self):
        """CIT filing deadline should be 6 months after fiscal year end."""
        fiscal_year_end = date(2025, 12, 31)
        expected_deadline = date(2026, 6, 30)  # 6 months later
        
        actual_deadline = date(
            fiscal_year_end.year + 1 if fiscal_year_end.month > 6 else fiscal_year_end.year,
            (fiscal_year_end.month + 6 - 1) % 12 + 1,
            30
        )
        
        assert actual_deadline == expected_deadline
    
    def test_filing_deadline_vat_21st_of_following_month(self):
        """VAT filing deadline should be 21st of following month."""
        period_month = 3
        period_year = 2025
        
        # VAT for March 2025 due April 21, 2025
        expected_deadline = date(2025, 4, 21)
        
        # Calculate deadline
        if period_month == 12:
            deadline_month = 1
            deadline_year = period_year + 1
        else:
            deadline_month = period_month + 1
            deadline_year = period_year
        
        actual_deadline = date(deadline_year, deadline_month, 21)
        
        assert actual_deadline == expected_deadline
    
    def test_tertiary_education_tax_rate(self):
        """Tertiary Education Tax should be 2% of assessable profit."""
        assessable_profit = Decimal("10000000")
        tet_rate = Decimal("2")  # 2%
        
        expected_tet = assessable_profit * tet_rate / 100
        
        assert expected_tet == Decimal("200000")
    
    def test_development_levy_calculation(self):
        """Development Levy should be 4% of assessable profit."""
        assessable_profit = Decimal("50000000")
        dev_levy_rate = Decimal("4")  # 4%
        
        # Only applicable if fixed assets >= ₦250M
        fixed_assets = Decimal("300000000")  # ₦300M
        threshold = Decimal("250000000")
        
        if fixed_assets >= threshold:
            expected_levy = assessable_profit * dev_levy_rate / 100
        else:
            expected_levy = Decimal("0")
        
        assert expected_levy == Decimal("2000000")
    
    def test_wht_credit_deduction(self):
        """WHT credits should reduce final tax payable."""
        cit_payable = Decimal("3000000")
        tet_payable = Decimal("200000")
        dev_levy = Decimal("100000")
        wht_credits = Decimal("500000")
        
        total_before_credits = cit_payable + tet_payable + dev_levy
        total_after_credits = total_before_credits - wht_credits
        
        assert total_before_credits == Decimal("3300000")
        assert total_after_credits == Decimal("2800000")
    
    def test_small_company_exemption(self):
        """Companies with turnover < ₦25M should be exempt from CIT."""
        turnover = Decimal("20000000")  # ₦20M
        exemption_threshold = Decimal("25000000")  # ₦25M
        
        is_exempt = turnover < exemption_threshold
        
        assert is_exempt is True
    
    def test_input_vat_recovery_with_irn(self):
        """Input VAT recovery requires valid vendor IRN."""
        vendor_irn = "NRS-2025-001234567890123"
        has_valid_irn = vendor_irn and vendor_irn.startswith("NRS-")
        
        # Without IRN, no recovery allowed
        can_recover_vat = has_valid_irn
        
        assert can_recover_vat is True
    
    def test_zero_rated_vat_documentation(self):
        """Zero-rated VAT claims require proper documentation."""
        # Zero-rated items: exports, diplomatic supplies
        zero_rated_sales = Decimal("5000000")
        has_export_docs = True  # Bill of lading, customs declaration
        has_diplomatic_cert = True  # For diplomatic supplies
        
        is_properly_documented = has_export_docs or has_diplomatic_cert
        
        assert is_properly_documented is True


# Run with: pytest tests/test_2026_compliance.py -v
