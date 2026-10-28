#!/usr/bin/env python3
"""
Stress test: enterprise_monorepo_stress.tf + 100 policies.
Tests Flash-Lite's ability to find the buried cross-resource chain.
"""
import sys, os, json, time, yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from gemini_client import call_gemini_json
from prompts import GROUNDED_PROMPT
from citation_gate import load_policy_library, apply_gate

with open(os.path.join(ROOT, "policies", "policy_library.yaml")) as f:
    raw_pol = json.dumps(yaml.safe_load(f))
policy_lib = load_policy_library(os.path.join(ROOT, "policies", "policy_library.yaml"))

with open(os.path.join(ROOT, "corpus", "enterprise_monorepo_stress.tf")) as f:
    source = f.read()

total_prompt = len(GROUNDED_PROMPT.format(
    policy_library_json=raw_pol,
    filename="enterprise_monorepo_stress.tf",
    terraform_source=source
))
print(f"Policy library: {len(policy_lib)} policies ({len(raw_pol)} chars / ~{len(raw_pol)//4} tokens)")
print(f"Terraform file: {len(source)} chars / ~{len(source)//4} tokens")
print(f"Total prompt: {total_prompt} chars (~{total_prompt//4} tokens)")
print()
print("Running 2 trials with 100-policy library on enterprise stress file...")
print("=" * 90)

for trial in range(1, 3):
    prompt = GROUNDED_PROMPT.format(
        policy_library_json=raw_pol,
        filename="enterprise_monorepo_stress.tf",
        terraform_source=source,
    )
    t0 = time.time()
    findings = call_gemini_json(prompt)
    elapsed = time.time() - t0

    accepted, dropped = apply_gate(findings, policy_lib)

    caught_s3 = any(
        "customer_data_exports" in str(f.get("resource", "")).lower()
        and f.get("policy_id") == "POL-S3-002"
        for f in accepted
    )
    caught_chain = any(
        (
            "data_exporter" in str(f.get("resource", "")).lower()
            or "customer_data_exports" in str(f.get("resource", "")).lower()
        )
        and f.get("policy_id") in ("POL-IAM-002", "POL-IAM-004")
        for f in accepted
    )

    decoy_cited = [
        f.get("policy_id")
        for f in findings
        if f.get("policy_id", "").startswith(
            ("POL-ECS-", "POL-ELB-", "POL-AGW-", "POL-CF-", "POL-VPC-",
             "POL-CW-", "POL-SQS-", "POL-SNS-", "POL-EKS-", "POL-RS-", "POL-EMR-")
        )
    ]

    s = "YES" if caught_s3 else "MISSED"
    c = "YES" if caught_chain else "MISSED"
    print(f"\nTrial {trial}: {len(findings)} raw -> {len(accepted)} acc / {len(dropped)} drop | GT-012(S3):{s} GT-013(chain):{c} | {elapsed:.1f}s")
    if decoy_cited:
        print(f"  WARNING: Decoy policies cited: {decoy_cited}")
    for f in findings:
        pid = f.get("policy_id", "NONE")
        res = str(f.get("resource", ""))[:70]
        iss = str(f.get("issue", ""))[:80]
        gate = "ACC" if f in accepted else "DROP"
        print(f"  {gate} | {pid} | {res}")
        print(f"        {iss}")

print()
print("=" * 90)

