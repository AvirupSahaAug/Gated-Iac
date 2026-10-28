"""Unit tests for the Citation Verification Gate."""

import os
import sys
import pytest

# Add pipeline to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "pipeline"))

from citation_gate import verify_finding, load_policy_library, apply_gate, _normalize


# Load the real policy library for integration-style tests
POLICY_LIB_PATH = os.path.join(ROOT_DIR, "policies", "policy_library.yaml")


@pytest.fixture
def policy_lib():
    return load_policy_library(POLICY_LIB_PATH)


@pytest.fixture
def mock_policy_lib():
    return {
        "POL-TEST-001": {
            "policy_id": "POL-TEST-001",
            "title": "Test policy for unit tests",
            "text": "S3 buckets must not be configured with a public-read or public-read-write ACL.",
        }
    }


class TestNormalize:
    def test_strips_whitespace(self):
        assert _normalize("  hello  world  ") == "hello world"

    def test_lowercases(self):
        assert _normalize("Hello World") == "hello world"

    def test_collapses_newlines(self):
        assert _normalize("hello\n  world\n") == "hello world"


class TestVerifyFinding:
    def test_accepts_valid_finding(self, mock_policy_lib):
        finding = {
            "resource": "aws_s3_bucket.test",
            "issue": "S3 bucket has public ACL",
            "policy_id": "POL-TEST-001",
            "cited_fragment": "must not be configured with a public-read",
        }
        ok, reason = verify_finding(finding, mock_policy_lib)
        assert ok is True
        assert reason == "ok"

    def test_rejects_missing_policy_id(self, mock_policy_lib):
        finding = {
            "resource": "aws_s3_bucket.test",
            "issue": "test",
            "cited_fragment": "some fragment",
        }
        ok, reason = verify_finding(finding, mock_policy_lib)
        assert ok is False
        assert "missing_policy_id" in reason

    def test_rejects_missing_fragment(self, mock_policy_lib):
        finding = {
            "resource": "aws_s3_bucket.test",
            "issue": "test",
            "policy_id": "POL-TEST-001",
        }
        ok, reason = verify_finding(finding, mock_policy_lib)
        assert ok is False
        assert "missing" in reason

    def test_rejects_nonexistent_policy_id(self, mock_policy_lib):
        finding = {
            "resource": "aws_s3_bucket.test",
            "issue": "test",
            "policy_id": "POL-FAKE-999",
            "cited_fragment": "some long fragment here for testing",
        }
        ok, reason = verify_finding(finding, mock_policy_lib)
        assert ok is False
        assert "does_not_exist" in reason

    def test_rejects_fragment_too_short(self, mock_policy_lib):
        finding = {
            "resource": "aws_s3_bucket.test",
            "issue": "test",
            "policy_id": "POL-TEST-001",
            "cited_fragment": "must not",  # Only 8 chars normalized
        }
        ok, reason = verify_finding(finding, mock_policy_lib)
        assert ok is False
        assert "too_short" in reason

    def test_rejects_paraphrased_fragment(self, mock_policy_lib):
        finding = {
            "resource": "aws_s3_bucket.test",
            "issue": "test",
            "policy_id": "POL-TEST-001",
            "cited_fragment": "S3 buckets should never have public ACLs configured",  # Paraphrased
        }
        ok, reason = verify_finding(finding, mock_policy_lib)
        assert ok is False
        assert "not_found_in_policy" in reason

    def test_rejects_parse_error(self, mock_policy_lib):
        finding = {"parse_error": True}
        ok, reason = verify_finding(finding, mock_policy_lib)
        assert ok is False
        assert "not_valid_json" in reason

    def test_case_insensitive_matching(self, mock_policy_lib):
        finding = {
            "resource": "aws_s3_bucket.test",
            "issue": "test",
            "policy_id": "POL-TEST-001",
            "cited_fragment": "MUST NOT BE CONFIGURED WITH A PUBLIC-READ",
        }
        ok, reason = verify_finding(finding, mock_policy_lib)
        assert ok is True


class TestApplyGate:
    def test_splits_findings_correctly(self, mock_policy_lib):
        findings = [
            {
                "resource": "r1",
                "issue": "i1",
                "policy_id": "POL-TEST-001",
                "cited_fragment": "must not be configured with a public-read",
            },
            {
                "resource": "r2",
                "issue": "i2",
                "policy_id": "POL-FAKE-999",
                "cited_fragment": "this policy does not exist at all",
            },
        ]
        accepted, dropped = apply_gate(findings, mock_policy_lib)
        assert len(accepted) == 1
        assert len(dropped) == 1
        assert accepted[0]["resource"] == "r1"
        assert "drop_reason" in dropped[0]

    def test_empty_findings(self, mock_policy_lib):
        accepted, dropped = apply_gate([], mock_policy_lib)
        assert accepted == []
        assert dropped == []


class TestWithRealPolicyLibrary:
    """Integration tests using the actual policy_library.yaml."""

    def test_valid_pol_iam_002_finding(self, policy_lib):
        finding = {
            "resource": "aws_instance.web_app",
            "issue": "Internet-facing instance with IAM secrets access",
            "policy_id": "POL-IAM-002",
            "cited_fragment": "A compute resource that is reachable from 0.0.0.0/0 on any port must not be attached to an IAM role",
        }
        ok, reason = verify_finding(finding, policy_lib)
        assert ok is True, f"Expected acceptance but got: {reason}"

    def test_valid_pol_s3_001_finding(self, policy_lib):
        finding = {
            "resource": "aws_s3_bucket_acl.logs_acl",
            "issue": "S3 bucket has public ACL",
            "policy_id": "POL-S3-001",
            "cited_fragment": "must not be configured with a public-read or public-read-write ACL",
        }
        ok, reason = verify_finding(finding, policy_lib)
        assert ok is True, f"Expected acceptance but got: {reason}"

    def test_fabricated_policy_id_rejected(self, policy_lib):
        finding = {
            "resource": "aws_s3_bucket.test",
            "issue": "test",
            "policy_id": "POL-EKS-001",  # Removed from library
            "cited_fragment": "Kubernetes cluster API server endpoints must not be exposed",
        }
        ok, reason = verify_finding(finding, policy_lib)
        assert ok is False

    def test_all_policy_ids_exist(self, policy_lib):
        """Verify the policy library loaded successfully with expected policies."""
        expected_ids = [
            "POL-S3-001", "POL-S3-002", "POL-SG-001", "POL-IAM-002",
            "POL-IAM-003", "POL-DDB-001", "POL-IAM-004", "POL-RDS-001",
            "POL-RDS-002", "POL-IAM-005", "POL-EC2-002", "POL-EC2-003",
        ]
        for pid in expected_ids:
            assert pid in policy_lib, f"Missing policy {pid} in library"
        # EKS policies should NOT be present (removed)
        assert "POL-EKS-001" not in policy_lib
        assert "POL-EKS-002" not in policy_lib
