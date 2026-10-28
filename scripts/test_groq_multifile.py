#!/usr/bin/env python3
"""
Multi-file Terraform Stress Test via Groq API:
Executes the identical multi-file 10-module benchmark on Groq
and evaluates the findings through the GateIaC Citation Gate.
"""

import sys
import os
import json
import time
import yaml
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from groq_client import call_groq_json
from prompts import GROUNDED_PROMPT
from citation_gate import load_policy_library, apply_gate

# Load 100 policies
with open(os.path.join(ROOT, "policies", "policy_library.yaml")) as f:
    raw_pol = json.dumps(yaml.safe_load(f))
policy_lib = load_policy_library(os.path.join(ROOT, "policies", "policy_library.yaml"))

# Concatenate all 10 multifile Terraform manifests
tf_dir = os.path.join(ROOT, "corpus", "multifile_enterprise")
tf_files = sorted(glob.glob(os.path.join(tf_dir, "*.tf")))
combined = ""
for fpath in tf_files:
    with open(fpath) as fh:
        combined += f"\n# ==========================================================\n"
        combined += f"# FILE: {os.path.basename(fpath)}\n"
        combined += f"# ==========================================================\n"
        combined += fh.read()
        combined += "\n"

total_prompt = len(GROUNDED_PROMPT.format(
    policy_library_json=raw_pol,
    filename="multifile_enterprise (10 separate modular .tf files)",
    terraform_source=combined,
))

print(f"Loaded {len(tf_files)} Terraform files ({len(combined)} chars, ~{len(combined)//4} tokens)")
print(f"Policy Library: {len(policy_lib)} policies (~{len(raw_pol)//4} tokens)")
print(f"Total Prompt Size: {total_prompt} chars (~{total_prompt//4} tokens)")
print()
print("=" * 90)
print("  TEST: Evaluating Multi-File Cross-Resource Privileges with GROQ API (2 trials)")
print("=" * 90)

for trial in range(1, 3):
    prompt = GROUNDED_PROMPT.format(
        policy_library_json=raw_pol,
        filename="multifile_enterprise (10 modular .tf files)",
        terraform_source=combined,
    )
    t0 = time.time()
    try:
        findings = call_groq_json(prompt, model_name="qwen/qwen3.8-27b")
    except Exception as e:
        print(f"Trial {trial} failed: {e}")
        continue
    elapsed = time.time() - t0

    accepted, dropped = apply_gate(findings, policy_lib)

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

print("\n" + "=" * 90)

