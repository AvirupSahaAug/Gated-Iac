"""Tests to validate ground truth consistency with corpus files."""

import json
import os
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")


@pytest.fixture
def ground_truth():
    with open(os.path.join(CORPUS_DIR, "ground_truth.json")) as f:
        return json.load(f)


@pytest.fixture
def corpus_files():
    return [f for f in os.listdir(CORPUS_DIR) if f.endswith(".tf")]


class TestGroundTruthStructure:
    def test_all_gt_keys_are_real_files(self, ground_truth, corpus_files):
        """Every key in ground_truth.json must correspond to an actual .tf file."""
        for key in ground_truth:
            assert key in corpus_files, f"Ground truth key '{key}' has no corresponding .tf file"

    def test_all_corpus_files_have_gt_entry(self, ground_truth, corpus_files):
        """Every .tf file (except provider.tf) should have a ground truth entry."""
        for f in corpus_files:
            if f == "provider.tf":
                continue
            assert f in ground_truth, f"Corpus file '{f}' has no ground truth entry"

    def test_gt_ids_are_unique(self, ground_truth):
        """All GT IDs must be globally unique."""
        all_ids = []
        for items in ground_truth.values():
            for item in items:
                all_ids.append(item["id"])
        assert len(all_ids) == len(set(all_ids)), f"Duplicate GT IDs found: {all_ids}"

    def test_simple_misconfig_has_simple_flaws(self, ground_truth):
        """simple_misconfig.tf should have GT-001 and GT-002 as simple flaws."""
        items = ground_truth.get("simple_misconfig.tf", [])
        ids = {item["id"] for item in items}
        assert "GT-001" in ids, "GT-001 should be in simple_misconfig.tf"
        assert "GT-002" in ids, "GT-002 should be in simple_misconfig.tf"
        for item in items:
            assert item["class"] == "simple", f"{item['id']} should be class 'simple'"

    def test_complex_misconfig_has_gt003(self, ground_truth):
        """complex_misconfig.tf should have GT-003 as a complex flaw."""
        items = ground_truth.get("complex_misconfig.tf", [])
        ids = {item["id"] for item in items}
        assert "GT-003" in ids, "GT-003 should be in complex_misconfig.tf"
        # GT-001 and GT-002 should NOT be here
        assert "GT-001" not in ids, "GT-001 should NOT be in complex_misconfig.tf"
        assert "GT-002" not in ids, "GT-002 should NOT be in complex_misconfig.tf"

    def test_secure_reference_has_no_flaws(self, ground_truth):
        """secure_hardened_reference.tf should have zero ground truth flaws."""
        items = ground_truth.get("secure_hardened_reference.tf", [])
        assert len(items) == 0, "Secure reference should have no flaws"

    def test_each_item_has_required_fields(self, ground_truth):
        """Every GT item must have id, resource, issue, class, policy_id."""
        required = {"id", "resource", "issue", "class", "policy_id"}
        for scenario, items in ground_truth.items():
            for item in items:
                missing = required - set(item.keys())
                assert not missing, f"{item.get('id', '?')} in {scenario} missing fields: {missing}"

    def test_resource_exists_in_tf_file(self, ground_truth):
        """Each GT resource address should appear in its corresponding .tf file."""
        for scenario, items in ground_truth.items():
            tf_path = os.path.join(CORPUS_DIR, scenario)
            if not os.path.exists(tf_path):
                continue
            with open(tf_path) as f:
                tf_content = f.read()
            for item in items:
                # For multi-resource items like 'res_a + res_b', check each part
                resources = [r.strip() for r in item["resource"].split("+")]
                for res in resources:
                    # Extract the resource name (after the dot)
                    parts = res.split(".")
                    if len(parts) >= 2:
                        res_name = parts[-1]
                        assert res_name in tf_content, (
                            f"Resource '{res}' from {item['id']} not found in {scenario}"
                        )
