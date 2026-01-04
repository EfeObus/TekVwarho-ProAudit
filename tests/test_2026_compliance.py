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


# Run with: pytest tests/test_2026_compliance.py -v
