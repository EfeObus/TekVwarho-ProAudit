"""
Tests for Advanced Audit System - 5 Critical Features

Tests cover:
1. Auditor Read-Only Role (Hard-Enforced)
2. Evidence Immutability (Files + Records)
3. Reproducible Audit Runs
4. Human-Readable Findings
5. Exportable Audit Output

Nigerian Compliance: NTAA 2025, FIRS, CAMA 2020
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
import hashlib
import json
import uuid

# Import models
from app.models.audit_system import (
    AuditRun, AuditRunStatus, AuditRunType,
    AuditFinding, FindingRiskLevel, FindingCategory,
    AuditEvidence, EvidenceType,
    AuditorSession, AuditorActionLog, AuditorAction,
)
from app.models.user import UserRole

# Import services
from app.services.audit_system_service import (
    AuditorRoleEnforcer,
    EvidenceImmutabilityService,
    ReproducibleAuditService,
    AuditFindingsService,
    AuditorSessionService,
    AdvancedAuditSystemService,
    AuditorPermissionError,
    EvidenceImmutabilityError,
    AuditRunError,
)


# ===========================================
# 1. AUDITOR READ-ONLY ROLE TESTS
# ===========================================

class TestAuditorRoleEnforcer:
    """Tests for Auditor Read-Only Role (Hard-Enforced)"""
    
    def test_auditor_role_enforcer_class_exists(self):
        """Test that AuditorRoleEnforcer class exists"""
        assert AuditorRoleEnforcer is not None
    
    def test_forbidden_actions_is_set(self):
        """Test that FORBIDDEN_ACTIONS is defined"""
        assert hasattr(AuditorRoleEnforcer, 'FORBIDDEN_ACTIONS')
        assert isinstance(AuditorRoleEnforcer.FORBIDDEN_ACTIONS, set)
    
    def test_forbidden_actions_contains_create_transaction(self):
        """Test that create_transaction is forbidden"""
        assert "create_transaction" in AuditorRoleEnforcer.FORBIDDEN_ACTIONS
    
    def test_forbidden_actions_contains_update_transaction(self):
        """Test that update_transaction is forbidden"""
        assert "update_transaction" in AuditorRoleEnforcer.FORBIDDEN_ACTIONS
    
    def test_forbidden_actions_contains_delete_transaction(self):
        """Test that delete_transaction is forbidden"""
        assert "delete_transaction" in AuditorRoleEnforcer.FORBIDDEN_ACTIONS
    
    def test_forbidden_actions_contains_approve_transaction(self):
        """Test that approve_transaction is forbidden"""
        assert "approve_transaction" in AuditorRoleEnforcer.FORBIDDEN_ACTIONS
    
    def test_forbidden_actions_contains_submit_tax_filing(self):
        """Test that submit_tax_filing is forbidden"""
        assert "submit_tax_filing" in AuditorRoleEnforcer.FORBIDDEN_ACTIONS
    
    def test_forbidden_actions_contains_manage_payroll(self):
        """Test that manage_payroll is forbidden"""
        assert "manage_payroll" in AuditorRoleEnforcer.FORBIDDEN_ACTIONS
    
    def test_forbidden_actions_contains_invoice_operations(self):
        """Test that invoice operations are forbidden"""
        assert "create_invoice" in AuditorRoleEnforcer.FORBIDDEN_ACTIONS
        assert "update_invoice" in AuditorRoleEnforcer.FORBIDDEN_ACTIONS
        assert "delete_invoice" in AuditorRoleEnforcer.FORBIDDEN_ACTIONS
    
    def test_auditor_role_enum_exists(self):
        """Test that AUDITOR role exists in UserRole enum"""
        assert hasattr(UserRole, 'AUDITOR')
        assert UserRole.AUDITOR.value == 'auditor'
    
    def test_is_auditor_method_exists(self):
        """Test that is_auditor method exists"""
        assert hasattr(AuditorRoleEnforcer, 'is_auditor')
        assert callable(getattr(AuditorRoleEnforcer, 'is_auditor'))
    
    def test_enforce_read_only_method_exists(self):
        """Test that enforce_read_only method exists"""
        assert hasattr(AuditorRoleEnforcer, 'enforce_read_only')
        assert callable(getattr(AuditorRoleEnforcer, 'enforce_read_only'))
    
    def test_auditor_permission_error_exists(self):
        """Test that AuditorPermissionError exception exists"""
        assert AuditorPermissionError is not None


class TestAuditorSessionModel:
    """Tests for AuditorSession model"""
    
    def test_auditor_session_model_exists(self):
        """Test that AuditorSession model exists"""
        assert AuditorSession is not None
    
    def test_auditor_session_has_id(self):
        """Test that AuditorSession has id field"""
        assert hasattr(AuditorSession, 'id')
    
    def test_auditor_session_has_entity_id(self):
        """Test that AuditorSession has entity_id field"""
        assert hasattr(AuditorSession, 'entity_id')
    
    def test_auditor_session_has_auditor_user_id(self):
        """Test that AuditorSession has auditor_user_id field"""
        assert hasattr(AuditorSession, 'auditor_user_id')
    
    def test_auditor_session_has_ip_address(self):
        """Test that AuditorSession has ip_address field"""
        assert hasattr(AuditorSession, 'ip_address')
    
    def test_auditor_session_has_is_active(self):
        """Test that AuditorSession has is_active field"""
        assert hasattr(AuditorSession, 'is_active')
    
    def test_auditor_session_has_actions_count(self):
        """Test that AuditorSession has actions_count field"""
        assert hasattr(AuditorSession, 'actions_count')


class TestAuditorActionLog:
    """Tests for AuditorActionLog model"""
    
    def test_auditor_action_log_model_exists(self):
        """Test that AuditorActionLog model exists"""
        assert AuditorActionLog is not None
    
    def test_auditor_action_log_has_session_id(self):
        """Test that AuditorActionLog has session_id field"""
        assert hasattr(AuditorActionLog, 'session_id')
    
    def test_auditor_action_log_has_action(self):
        """Test that AuditorActionLog has action field"""
        assert hasattr(AuditorActionLog, 'action')
    
    def test_auditor_action_log_has_resource_type(self):
        """Test that AuditorActionLog has resource_type field"""
        assert hasattr(AuditorActionLog, 'resource_type')
    
    def test_auditor_action_log_has_resource_id(self):
        """Test that AuditorActionLog has resource_id field"""
        assert hasattr(AuditorActionLog, 'resource_id')


class TestAuditorActionEnum:
    """Tests for AuditorAction enum"""
    
    def test_auditor_action_enum_exists(self):
        """Test that AuditorAction enum exists"""
        assert AuditorAction is not None
    
    def test_auditor_action_has_view_transaction(self):
        """Test that VIEW_TRANSACTION action exists"""
        assert hasattr(AuditorAction, 'VIEW_TRANSACTION')
    
    def test_auditor_action_has_view_invoice(self):
        """Test that VIEW_INVOICE action exists"""
        assert hasattr(AuditorAction, 'VIEW_INVOICE')
    
    def test_auditor_action_has_run_analysis(self):
        """Test that RUN_ANALYSIS action exists"""
        assert hasattr(AuditorAction, 'RUN_ANALYSIS')
    
    def test_auditor_action_has_export_data(self):
        """Test that EXPORT_DATA action exists"""
        assert hasattr(AuditorAction, 'EXPORT_DATA')
    
    def test_auditor_action_has_add_finding(self):
        """Test that ADD_FINDING action exists"""
        assert hasattr(AuditorAction, 'ADD_FINDING')
    
    def test_auditor_action_has_add_evidence(self):
        """Test that ADD_EVIDENCE action exists"""
        assert hasattr(AuditorAction, 'ADD_EVIDENCE')


# ===========================================
# 2. EVIDENCE IMMUTABILITY TESTS
# ===========================================

class TestAuditEvidenceModel:
    """Tests for AuditEvidence model"""
    
    def test_audit_evidence_model_exists(self):
        """Test that AuditEvidence model exists"""
        assert AuditEvidence is not None
    
    def test_audit_evidence_has_id(self):
        """Test that AuditEvidence has id field"""
        assert hasattr(AuditEvidence, 'id')
    
    def test_audit_evidence_has_entity_id(self):
        """Test that AuditEvidence has entity_id field"""
        assert hasattr(AuditEvidence, 'entity_id')
    
    def test_audit_evidence_has_finding_id(self):
        """Test that AuditEvidence has finding_id for linking to findings"""
        assert hasattr(AuditEvidence, 'finding_id')
    
    def test_audit_evidence_has_evidence_type(self):
        """Test that AuditEvidence has evidence_type field"""
        assert hasattr(AuditEvidence, 'evidence_type')
    
    def test_audit_evidence_has_title(self):
        """Test that AuditEvidence has title field"""
        assert hasattr(AuditEvidence, 'title')
    
    def test_audit_evidence_has_description(self):
        """Test that AuditEvidence has description field"""
        assert hasattr(AuditEvidence, 'description')
    
    def test_audit_evidence_has_content_hash(self):
        """Test that AuditEvidence has content_hash field for immutability"""
        assert hasattr(AuditEvidence, 'content_hash')


class TestEvidenceTypeEnum:
    """Tests for EvidenceType enum"""
    
    def test_evidence_type_enum_exists(self):
        """Test that EvidenceType enum exists"""
        assert EvidenceType is not None
    
    def test_evidence_type_has_document(self):
        """Test that DOCUMENT type exists"""
        assert hasattr(EvidenceType, 'DOCUMENT')
        assert EvidenceType.DOCUMENT.value == 'document'
    
    def test_evidence_type_has_transaction(self):
        """Test that TRANSACTION type exists"""
        assert hasattr(EvidenceType, 'TRANSACTION')
        assert EvidenceType.TRANSACTION.value == 'transaction'
    
    def test_evidence_type_has_calculation(self):
        """Test that CALCULATION type exists"""
        assert hasattr(EvidenceType, 'CALCULATION')
        assert EvidenceType.CALCULATION.value == 'calculation'
    
    def test_evidence_type_has_screenshot(self):
        """Test that SCREENSHOT type exists"""
        assert hasattr(EvidenceType, 'SCREENSHOT')
        assert EvidenceType.SCREENSHOT.value == 'screenshot'
    
    def test_evidence_type_has_external_confirmation(self):
        """Test that EXTERNAL_CONFIRMATION type exists"""
        assert hasattr(EvidenceType, 'EXTERNAL_CONFIRMATION')
        assert EvidenceType.EXTERNAL_CONFIRMATION.value == 'external_confirmation'


class TestEvidenceImmutabilityService:
    """Tests for EvidenceImmutabilityService"""
    
    def test_evidence_immutability_service_exists(self):
        """Test that EvidenceImmutabilityService exists"""
        assert EvidenceImmutabilityService is not None
    
    def test_evidence_immutability_error_exists(self):
        """Test that EvidenceImmutabilityError exists"""
        assert EvidenceImmutabilityError is not None


class TestHashVerification:
    """Tests for SHA-256 hash verification"""
    
    def test_sha256_produces_correct_length(self):
        """Test that SHA-256 produces 64-character hex string"""
        test_data = b"Test data for hash verification"
        hash_result = hashlib.sha256(test_data).hexdigest()
        assert len(hash_result) == 64
    
    def test_sha256_is_deterministic(self):
        """Test that same input always produces same hash"""
        test_data = b"Deterministic hash test"
        hash1 = hashlib.sha256(test_data).hexdigest()
        hash2 = hashlib.sha256(test_data).hexdigest()
        hash3 = hashlib.sha256(test_data).hexdigest()
        
        assert hash1 == hash2 == hash3
    
    def test_sha256_detects_tampering(self):
        """Test that any change produces different hash"""
        original = b"Original financial record data"
        tampered = b"Original financial record Data"  # Capital D
        
        hash_original = hashlib.sha256(original).hexdigest()
        hash_tampered = hashlib.sha256(tampered).hexdigest()
        
        assert hash_original != hash_tampered
    
    def test_sha256_empty_input(self):
        """Test SHA-256 behavior with empty input"""
        empty_hash = hashlib.sha256(b"").hexdigest()
        assert len(empty_hash) == 64
        # Known SHA-256 of empty string
        assert empty_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    
    def test_json_serialization_for_hashing(self):
        """Test that JSON serialization is consistent for hashing"""
        data = {
            "entity_id": "123",
            "amount": "5000.00",
            "date": "2026-01-07"
        }
        
        json1 = json.dumps(data, sort_keys=True)
        json2 = json.dumps(data, sort_keys=True)
        
        assert json1 == json2
        assert hashlib.sha256(json1.encode()).hexdigest() == hashlib.sha256(json2.encode()).hexdigest()
    
    def test_hash_changes_with_different_content(self):
        """Test that different content produces different hashes"""
        content1 = b"Original content"
        content2 = b"Modified content"
        
        hash1 = hashlib.sha256(content1).hexdigest()
        hash2 = hashlib.sha256(content2).hexdigest()
        
        assert hash1 != hash2


# ===========================================
# 3. REPRODUCIBLE AUDIT RUNS TESTS
# ===========================================

class TestAuditRunModel:
    """Tests for AuditRun model"""
    
    def test_audit_run_model_exists(self):
        """Test that AuditRun model exists"""
        assert AuditRun is not None
    
    def test_audit_run_has_id(self):
        """Test that AuditRun has id field"""
        assert hasattr(AuditRun, 'id')
    
    def test_audit_run_has_entity_id(self):
        """Test that AuditRun has entity_id field"""
        assert hasattr(AuditRun, 'entity_id')
    
    def test_audit_run_has_run_type(self):
        """Test that AuditRun has run_type field"""
        assert hasattr(AuditRun, 'run_type')
    
    def test_audit_run_has_status(self):
        """Test that AuditRun has status field"""
        assert hasattr(AuditRun, 'status')
    
    def test_audit_run_has_period_start(self):
        """Test that AuditRun has period_start field"""
        assert hasattr(AuditRun, 'period_start')
    
    def test_audit_run_has_period_end(self):
        """Test that AuditRun has period_end field"""
        assert hasattr(AuditRun, 'period_end')
    
    def test_audit_run_has_rule_version(self):
        """Test that AuditRun has rule_version for reproducibility"""
        assert hasattr(AuditRun, 'rule_version')
    
    def test_audit_run_has_rule_config(self):
        """Test that AuditRun has rule_config field"""
        assert hasattr(AuditRun, 'rule_config')
    
    def test_audit_run_has_data_snapshot_id(self):
        """Test that AuditRun has data_snapshot_id field"""
        assert hasattr(AuditRun, 'data_snapshot_id')
    
    def test_audit_run_has_data_snapshot_hash(self):
        """Test that AuditRun has data_snapshot_hash field"""
        assert hasattr(AuditRun, 'data_snapshot_hash')
    
    def test_audit_run_has_completed_at(self):
        """Test that AuditRun has completed_at field"""
        assert hasattr(AuditRun, 'completed_at')
    
    def test_audit_run_has_executed_by(self):
        """Test that AuditRun has executed_by field"""
        assert hasattr(AuditRun, 'executed_by')


class TestAuditRunStatusEnum:
    """Tests for AuditRunStatus enum"""
    
    def test_audit_run_status_enum_exists(self):
        """Test that AuditRunStatus enum exists"""
        assert AuditRunStatus is not None
    
    def test_audit_run_status_has_pending(self):
        """Test that PENDING status exists"""
        assert hasattr(AuditRunStatus, 'PENDING')
        assert AuditRunStatus.PENDING.value == 'pending'
    
    def test_audit_run_status_has_running(self):
        """Test that RUNNING status exists"""
        assert hasattr(AuditRunStatus, 'RUNNING')
        assert AuditRunStatus.RUNNING.value == 'running'
    
    def test_audit_run_status_has_completed(self):
        """Test that COMPLETED status exists"""
        assert hasattr(AuditRunStatus, 'COMPLETED')
        assert AuditRunStatus.COMPLETED.value == 'completed'
    
    def test_audit_run_status_has_failed(self):
        """Test that FAILED status exists"""
        assert hasattr(AuditRunStatus, 'FAILED')
        assert AuditRunStatus.FAILED.value == 'failed'
    
    def test_audit_run_status_has_cancelled(self):
        """Test that CANCELLED status exists"""
        assert hasattr(AuditRunStatus, 'CANCELLED')
        assert AuditRunStatus.CANCELLED.value == 'cancelled'


class TestAuditRunTypeEnum:
    """Tests for AuditRunType enum"""
    
    def test_audit_run_type_enum_exists(self):
        """Test that AuditRunType enum exists"""
        assert AuditRunType is not None
    
    def test_audit_run_type_has_benfords_law(self):
        """Test that BENFORDS_LAW type exists"""
        assert hasattr(AuditRunType, 'BENFORDS_LAW')
        assert AuditRunType.BENFORDS_LAW.value == 'benfords_law'
    
    def test_audit_run_type_has_zscore_anomaly(self):
        """Test that ZSCORE_ANOMALY type exists"""
        assert hasattr(AuditRunType, 'ZSCORE_ANOMALY')
        assert AuditRunType.ZSCORE_ANOMALY.value == 'zscore_anomaly'
    
    def test_audit_run_type_has_nrs_gap_analysis(self):
        """Test that NRS_GAP_ANALYSIS type exists"""
        assert hasattr(AuditRunType, 'NRS_GAP_ANALYSIS')
        assert AuditRunType.NRS_GAP_ANALYSIS.value == 'nrs_gap_analysis'
    
    def test_audit_run_type_has_three_way_matching(self):
        """Test that THREE_WAY_MATCHING type exists"""
        assert hasattr(AuditRunType, 'THREE_WAY_MATCHING')
        assert AuditRunType.THREE_WAY_MATCHING.value == 'three_way_matching'
    
    def test_audit_run_type_has_full_forensic(self):
        """Test that FULL_FORENSIC type exists"""
        assert hasattr(AuditRunType, 'FULL_FORENSIC')
        assert AuditRunType.FULL_FORENSIC.value == 'full_forensic'
    
    def test_audit_run_type_has_custom(self):
        """Test that CUSTOM type exists"""
        assert hasattr(AuditRunType, 'CUSTOM')
        assert AuditRunType.CUSTOM.value == 'custom'


class TestReproducibleAuditService:
    """Tests for ReproducibleAuditService"""
    
    def test_reproducible_audit_service_exists(self):
        """Test that ReproducibleAuditService exists"""
        assert ReproducibleAuditService is not None
    
    def test_audit_run_error_exists(self):
        """Test that AuditRunError exists"""
        assert AuditRunError is not None


# ===========================================
# 4. HUMAN-READABLE FINDINGS TESTS
# ===========================================

class TestAuditFindingModel:
    """Tests for AuditFinding model"""
    
    def test_audit_finding_model_exists(self):
        """Test that AuditFinding model exists"""
        assert AuditFinding is not None
    
    def test_audit_finding_has_id(self):
        """Test that AuditFinding has id field"""
        assert hasattr(AuditFinding, 'id')
    
    def test_audit_finding_has_audit_run_id(self):
        """Test that AuditFinding has audit_run_id field"""
        assert hasattr(AuditFinding, 'audit_run_id')
    
    def test_audit_finding_has_risk_level(self):
        """Test that AuditFinding has risk_level field"""
        assert hasattr(AuditFinding, 'risk_level')
    
    def test_audit_finding_has_category(self):
        """Test that AuditFinding has category field"""
        assert hasattr(AuditFinding, 'category')
    
    def test_audit_finding_has_title(self):
        """Test that AuditFinding has title field"""
        assert hasattr(AuditFinding, 'title')
    
    def test_audit_finding_has_description(self):
        """Test that AuditFinding has description field"""
        assert hasattr(AuditFinding, 'description')
    
    def test_audit_finding_has_recommendation(self):
        """Test that AuditFinding has recommendation field"""
        assert hasattr(AuditFinding, 'recommendation')
    
    def test_audit_finding_has_regulatory_reference(self):
        """Test that AuditFinding has regulatory_reference field"""
        assert hasattr(AuditFinding, 'regulatory_reference')
    
    def test_audit_finding_has_to_human_readable_method(self):
        """Test that AuditFinding has to_human_readable method"""
        assert hasattr(AuditFinding, 'to_human_readable')
        assert callable(getattr(AuditFinding, 'to_human_readable'))


class TestFindingRiskLevelEnum:
    """Tests for FindingRiskLevel enum"""
    
    def test_finding_risk_level_enum_exists(self):
        """Test that FindingRiskLevel enum exists"""
        assert FindingRiskLevel is not None
    
    def test_finding_risk_level_has_critical(self):
        """Test that CRITICAL level exists"""
        assert hasattr(FindingRiskLevel, 'CRITICAL')
        assert FindingRiskLevel.CRITICAL.value == 'critical'
    
    def test_finding_risk_level_has_high(self):
        """Test that HIGH level exists"""
        assert hasattr(FindingRiskLevel, 'HIGH')
        assert FindingRiskLevel.HIGH.value == 'high'
    
    def test_finding_risk_level_has_medium(self):
        """Test that MEDIUM level exists"""
        assert hasattr(FindingRiskLevel, 'MEDIUM')
        assert FindingRiskLevel.MEDIUM.value == 'medium'
    
    def test_finding_risk_level_has_low(self):
        """Test that LOW level exists"""
        assert hasattr(FindingRiskLevel, 'LOW')
        assert FindingRiskLevel.LOW.value == 'low'
    
    def test_finding_risk_level_has_informational(self):
        """Test that INFORMATIONAL level exists"""
        assert hasattr(FindingRiskLevel, 'INFORMATIONAL')
        assert FindingRiskLevel.INFORMATIONAL.value == 'informational'


class TestFindingCategoryEnum:
    """Tests for FindingCategory enum"""
    
    def test_finding_category_enum_exists(self):
        """Test that FindingCategory enum exists"""
        assert FindingCategory is not None
    
    def test_finding_category_has_fraud_indicator(self):
        """Test that FRAUD_INDICATOR category exists"""
        assert hasattr(FindingCategory, 'FRAUD_INDICATOR')
        assert FindingCategory.FRAUD_INDICATOR.value == 'fraud_indicator'
    
    def test_finding_category_has_compliance_gap(self):
        """Test that COMPLIANCE_GAP category exists"""
        assert hasattr(FindingCategory, 'COMPLIANCE_GAP')
        assert FindingCategory.COMPLIANCE_GAP.value == 'compliance_gap'
    
    def test_finding_category_has_data_integrity(self):
        """Test that DATA_INTEGRITY category exists"""
        assert hasattr(FindingCategory, 'DATA_INTEGRITY')
        assert FindingCategory.DATA_INTEGRITY.value == 'data_integrity'
    
    def test_finding_category_has_tax_discrepancy(self):
        """Test that TAX_DISCREPANCY category exists"""
        assert hasattr(FindingCategory, 'TAX_DISCREPANCY')
        assert FindingCategory.TAX_DISCREPANCY.value == 'tax_discrepancy'
    
    def test_finding_category_has_control_deficiency(self):
        """Test that CONTROL_DEFICIENCY category exists"""
        assert hasattr(FindingCategory, 'CONTROL_DEFICIENCY')
        assert FindingCategory.CONTROL_DEFICIENCY.value == 'control_deficiency'


class TestAuditFindingsService:
    """Tests for AuditFindingsService"""
    
    def test_audit_findings_service_exists(self):
        """Test that AuditFindingsService exists"""
        assert AuditFindingsService is not None


# ===========================================
# 5. EXPORTABLE AUDIT OUTPUT TESTS
# ===========================================

class TestAdvancedAuditSystemService:
    """Tests for AdvancedAuditSystemService (unified service)"""
    
    def test_advanced_audit_system_service_exists(self):
        """Test that AdvancedAuditSystemService exists"""
        assert AdvancedAuditSystemService is not None


class TestAuditorSessionService:
    """Tests for AuditorSessionService"""
    
    def test_auditor_session_service_exists(self):
        """Test that AuditorSessionService exists"""
        assert AuditorSessionService is not None


# ===========================================
# SERVICE LAYER TESTS
# ===========================================

class TestServiceLayerIntegration:
    """Tests for service layer components"""
    
    def test_all_core_services_exist(self):
        """Test that all core services are available"""
        assert AuditorRoleEnforcer is not None
        assert EvidenceImmutabilityService is not None
        assert ReproducibleAuditService is not None
        assert AuditFindingsService is not None
        assert AuditorSessionService is not None
        assert AdvancedAuditSystemService is not None
    
    def test_all_exception_types_exist(self):
        """Test that all exception types are available"""
        assert AuditorPermissionError is not None
        assert EvidenceImmutabilityError is not None
        assert AuditRunError is not None


# ===========================================
# DATA INTEGRITY TESTS
# ===========================================

class TestDataIntegrity:
    """Tests for data integrity"""
    
    def test_uuid_generation_format(self):
        """Test that UUID follows proper format"""
        test_uuid = str(uuid.uuid4())
        assert len(test_uuid) == 36
        assert test_uuid.count('-') == 4
    
    def test_uuid_uniqueness(self):
        """Test that UUIDs are unique"""
        uuids = [str(uuid.uuid4()) for _ in range(100)]
        assert len(set(uuids)) == 100


# ===========================================
# COMPLIANCE TESTS
# ===========================================

class TestNigerianCompliance:
    """Tests for Nigerian regulatory compliance"""
    
    def test_has_nrs_gap_analysis_type(self):
        """Test that NRS gap analysis is supported"""
        assert hasattr(AuditRunType, 'NRS_GAP_ANALYSIS')
    
    def test_has_tax_discrepancy_category(self):
        """Test that tax discrepancy findings are supported"""
        assert hasattr(FindingCategory, 'TAX_DISCREPANCY')
    
    def test_has_compliance_gap_category(self):
        """Test that compliance gap findings are supported"""
        assert hasattr(FindingCategory, 'COMPLIANCE_GAP')
    
    def test_audit_finding_has_regulatory_reference(self):
        """Test that findings can reference regulations"""
        assert hasattr(AuditFinding, 'regulatory_reference')


# ===========================================
# MODEL TABLENAME TESTS
# ===========================================

class TestModelTablenames:
    """Tests for model tablenames"""
    
    def test_audit_run_tablename(self):
        """Test that AuditRun has correct tablename"""
        assert AuditRun.__tablename__ == 'audit_runs'
    
    def test_audit_finding_tablename(self):
        """Test that AuditFinding has correct tablename"""
        assert AuditFinding.__tablename__ == 'audit_findings'
    
    def test_audit_evidence_tablename(self):
        """Test that AuditEvidence has correct tablename"""
        assert AuditEvidence.__tablename__ == 'audit_evidence'
    
    def test_auditor_session_tablename(self):
        """Test that AuditorSession has correct tablename"""
        assert AuditorSession.__tablename__ == 'auditor_sessions'
    
    def test_auditor_action_log_tablename(self):
        """Test that AuditorActionLog has correct tablename"""
        assert AuditorActionLog.__tablename__ == 'auditor_action_logs'
