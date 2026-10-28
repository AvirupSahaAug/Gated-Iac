"""
The verification gate at the heart of the P16 project.

A finding from the grounded LLM pass is only accepted if:
  1. It names a policy_id that actually exists in policy_library.yaml
  2. Its cited_fragment is an actual substring of that policy's text
     (normalized for whitespace/case), not a paraphrase.

Everything that fails is logged to `results/dropped_findings.json` so you can
report exactly how many hallucinated findings the gate caught — that log is
your primary evidence for the hallucination-rate metric.
"""

import json
import re
import yaml


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def load_policy_library(path: str) -> dict:
    with open(path) as f:
        policies = yaml.safe_load(f)
    return {p["policy_id"]: p for p in policies}


def verify_finding(finding: dict, policy_library: dict) -> tuple[bool, str]:
    """Returns (accepted: bool, reason: str)."""
    if finding.get("parse_error"):
        return False, "model_output_not_valid_json"

    policy_id = finding.get("policy_id")
    fragment = finding.get("cited_fragment")

    if not policy_id or not fragment:
        return False, "missing_policy_id_or_cited_fragment"

    policy = policy_library.get(policy_id)
    if policy is None:
        return False, f"cited_policy_id_does_not_exist: {policy_id}"

    clean_quote = _normalize(fragment)
    if len(clean_quote) < 15:
        return False, f"cited_fragment_too_short: {len(clean_quote)} chars (minimum 15)"

    if clean_quote not in _normalize(policy["text"]):
        return False, f"cited_fragment_not_found_in_policy_text: {policy_id}"

    return True, "ok"


def apply_gate(findings: list, policy_library: dict) -> tuple[list, list]:
    """Splits findings into (accepted, dropped_with_reason)."""
    accepted, dropped = [], []
    for finding in findings:
        ok, reason = verify_finding(finding, policy_library)
        if ok:
            accepted.append(finding)
        else:
            dropped.append({**finding, "drop_reason": reason})
    return accepted, dropped


if __name__ == "__main__":
    import sys

    lib = load_policy_library("policies/policy_library.yaml")
    with open(sys.argv[1]) as f:
        raw_findings = json.load(f)

    accepted, dropped = apply_gate(raw_findings, lib)

    print(f"Accepted: {len(accepted)}  Dropped: {len(dropped)}")
    with open("results/dropped_findings.json", "w") as f:
        json.dump(dropped, f, indent=2)
