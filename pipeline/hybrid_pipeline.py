"""
End-to-end hybrid pipeline (this is the "Method X" in the hypothesis).

Usage:
    export GEMINI_API_KEY=...
    python pipeline/hybrid_pipeline.py corpus/complex_misconfig.tf

Produces results/<filename>_hybrid_findings.json with both the accepted
(grounded) findings and a record of what the gate dropped.
"""

import json
import subprocess
import sys
import os

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from gemini_client import call_gemini_json
from prompts import GROUNDED_PROMPT
from citation_gate import load_policy_library, apply_gate

POLICY_LIBRARY_PATH = os.path.join(os.path.dirname(__file__), "..", "policies", "policy_library.yaml")


def run_opa_deterministic(tf_plan_json_path: str) -> list:
    """
    Runs conftest against the Rego policies for the deterministic pass.
    Requires a `terraform show -json` plan file — see README for how to
    generate one. Returns a list of deny messages (strings).
    """
    policies_dir = os.path.join(os.path.dirname(__file__), "..", "policies")
    result = subprocess.run(
        ["conftest", "test", "--policy", policies_dir, "--all-namespaces", tf_plan_json_path, "--output", "json"],
        capture_output=True,
        text=True,
    )
    findings = []
    try:
        parsed = json.loads(result.stdout)
        for file_result in parsed:
            for failure in file_result.get("failures", []):
                findings.append(failure.get("msg", str(failure)))
    except json.JSONDecodeError:
        # conftest not runnable in this environment / no plan yet — non-fatal,
        # the contextual (LLM) pass still runs on the raw .tf source.
        pass
    return findings


def run_contextual_pass(tf_path: str, policy_library_raw: str) -> list:
    with open(tf_path) as f:
        source = f.read()

    prompt = GROUNDED_PROMPT.format(
        policy_library_json=policy_library_raw,
        filename=os.path.basename(tf_path),
        terraform_source=source,
    )
    return call_gemini_json(prompt)


def main(tf_path: str, tf_plan_json_path: str | None = None):
    os.makedirs("results", exist_ok=True)

    policy_library = load_policy_library(POLICY_LIBRARY_PATH)
    with open(POLICY_LIBRARY_PATH) as f:
        policy_library_raw = json.dumps(yaml.safe_load(f))

    deterministic_findings = (
        run_opa_deterministic(tf_plan_json_path) if tf_plan_json_path else []
    )

    raw_contextual_findings = run_contextual_pass(tf_path, policy_library_raw)
    accepted, dropped = apply_gate(raw_contextual_findings, policy_library)

    result = {
        "file": tf_path,
        "deterministic_findings": deterministic_findings,
        "contextual_findings_accepted": accepted,
        "contextual_findings_dropped": dropped,
        "raw_contextual_finding_count": len(raw_contextual_findings),
    }

    out_name = os.path.basename(tf_path).replace(".tf", "_hybrid_findings.json")
    out_path = os.path.join("results", out_name)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Deterministic findings: {len(deterministic_findings)}")
    print(f"Contextual findings — accepted: {len(accepted)}, dropped by gate: {len(dropped)}")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    tf_file = sys.argv[1]
    plan_json = sys.argv[2] if len(sys.argv) > 2 else None
    main(tf_file, plan_json)
