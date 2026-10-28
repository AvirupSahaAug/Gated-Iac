#!/usr/bin/env python3
"""
Multi-file Terraform Test on Groq (Fitting Free-Tier ITPM limit < 7000 tokens):
We test the 4 core interconnected files that make up the privilege chain:
  - 07-alb.tf (public entry point)
  - 06-ecs.tf (data exporter service)
  - 03-iam.tf (overprivileged task role)
  - 05-s3.tf  (unencrypted customer PII bucket)
evaluated against the core policy library (12 policies) to stay under the 7000 token limit.
"""

import sys
import os
import json
import time
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from groq_client import call_groq_json
from prompts import GROUNDED_PROMPT
from citation_gate import load_policy_library, apply_gate

# Load original 12 policies to fit prompt in token limit
policy_lib = load_policy_library(os.path.join(ROOT, "policies", "policy_library.yaml"))
# Keep only core 12 policies
core_ids = [
    "POL-S3-001", "POL-S3-002", "POL-SG-001", "POL-IAM-002",
    "POL-IAM-003", "POL-DDB-001", "POL-IAM-004", "POL-RDS-001",
    "POL-RDS-002", "POL-IAM-005", "POL-EC2-002", "POL-EC2-003"
]
core_policies = {k: v for k, v in policy_lib.items() if k in core_ids}
raw_pol = json.dumps(list(core_policies.values()))

# Read the 4 critical interconnected files in the multi-file vulnerability chain
tf_dir = os.path.join(ROOT, "corpus", "multifile_enterprise")
chain_files = ["07-alb.tf", "06-ecs.tf", "03-iam.tf", "05-s3.tf"]

combined = ""
for fname in chain_files:
    fpath = os.path.join(tf_dir, fname)
    with open(fpath) as fh:
        combined += f"\n# ==========================================================\n"
        combined += f"# FILE: {fname}\n"
        combined += f"# ==========================================================\n"
        combined += fh.read()
        combined += "\n"

prompt = GROUNDED_PROMPT.format(
    policy_library_json=raw_pol,
    filename="multifile_chain (4 separate modular .tf files: 07-alb, 06-ecs, 03-iam, 05-s3)",
    terraform_source=combined,
)

print(f"Loaded {len(chain_files)} interconnected Terraform files ({len(combined)} chars, ~{len(combined)//4} tokens)")
print(f"Policy Library: {len(core_policies)} core policies (~{len(raw_pol)//4} tokens)")
print(f"Total Prompt Size: {len(prompt)} chars (~{len(prompt)//4} tokens)")
print(f"Groq Free Tier ITPM Limit: 7000 tokens")
print()
print("=" * 90)
print("  TEST: Evaluating Multi-File Cross-Resource Chain on Groq (qwen/qwen3.8-27b)")
print("=" * 90)

for trial in range(1, 3):
    t0 = time.time()
    try:
        findings = call_groq_json(prompt, model_name="qwen/qwen3.8-27b")
    except Exception as e:
        print(f"Trial {trial} failed: {e}")
        continue
    elapsed = time.time() - t0

    accepted, dropped = apply_gate(findings, core_policies)

    caught_s3 = any(
        "customer_exports" in str(f.get("resource", "")).lower()
        and f.get("policy_id") == "POL-S3-002"
        for f in accepted
    )

    caught_chain = any(
        (
            "exporter" in str(f.get("resource", "")).lower()
            or "customer_exports" in str(f.get("resource", "")).lower()
        )
        and f.get("policy_id") in ("POL-IAM-002", "POL-IAM-004")
        for f in accepted
    )

    caught_dynamo_wildcard = any(
        "exporter" in str(f.get("resource", "")).lower()
        and f.get("policy_id") == "POL-IAM-003"
        for f in accepted
    )

    print(f"\nTrial {trial}: {len(findings)} raw -> {len(accepted)} accepted / {len(dropped)} dropped ({elapsed:.2f}s)")
    print("-" * 90)
    for i, f in enumerate(findings):
        pid = f.get("policy_id", "NONE")
        res = str(f.get("resource", ""))[:70]
        iss = str(f.get("issue", ""))[:80]
        st = "ACCEPTED [PASS]" if f in accepted else "DROPPED [FAIL]"
        print(f"  [{i+1}] {st} | {pid} | {res}")
        print(f"       Issue: {iss}")

    print("\n  Detection Matrix:")
    print(f"    - S3 Missing Encryption (05-s3.tf):                   {'DETECTED' if caught_s3 else 'MISSED'}")
    print(f"    - Multi-file ALB->ECS->IAM->S3 Chain (07,06,03,05):   {'DETECTED' if caught_chain else 'MISSED'}")
    print(f"    - Wildcard DynamoDB Permission (03-iam.tf):           {'DETECTED' if caught_dynamo_wildcard else 'MISSED'}")

    if trial < 2:
        print("\nWaiting 15s before trial 2 to respect Groq rate limits...")
        time.sleep(15)

print("\n" + "=" * 90)

