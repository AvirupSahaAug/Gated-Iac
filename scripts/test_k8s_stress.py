#!/usr/bin/env python3
"""
Stress test: 7 interconnected K8s manifests + 100 policies → whole-file LLM.
Tests whether Flash-Lite can detect cross-file vulnerabilities when all files
are concatenated into a single prompt.
"""
import sys, os, json, time, yaml, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from gemini_client import call_gemini_json
from citation_gate import load_policy_library, apply_gate

# Load policy library
with open(os.path.join(ROOT, "policies", "policy_library.yaml")) as f:
    raw_pol = json.dumps(yaml.safe_load(f))
policy_lib = load_policy_library(os.path.join(ROOT, "policies", "policy_library.yaml"))

# Concatenate all K8s files
k8s_dir = os.path.join(ROOT, "corpus", "k8s_multifile_stress")
k8s_files = sorted(glob.glob(os.path.join(k8s_dir, "*.yaml")))
combined = ""
for fpath in k8s_files:
    with open(fpath) as fh:
        combined += f"# ===== FILE: {os.path.basename(fpath)} =====\n"
        combined += fh.read()
        combined += "\n\n"

# K8s-adapted prompt
prompt = f"""You are an expert cloud infrastructure security auditor.

Below is a POLICY LIBRARY containing organization security policies:

{raw_pol}

Below are 7 interconnected Kubernetes manifest files defining a production microservices platform.
Your task: find CROSS-RESOURCE vulnerabilities where the combination of resources across multiple files
creates a security risk. Focus on:
- RBAC privilege escalation (ServiceAccounts bound to overprivileged ClusterRoles)
- Container security (hostNetwork, hostPID, Docker socket mounts, running as root)
- Missing NetworkPolicies that allow unrestricted pod-to-pod communication
- Secrets exposure through overprivileged ServiceAccounts

For each finding, return a JSON array. Each finding must include:
- "resource": exact Kubernetes resource names involved
- "issue": one-sentence description of the security vulnerability
- "policy_id": the most relevant policy ID from the library above
- "cited_fragment": an EXACT verbatim quote from the policy text (minimum 15 characters)

Only report findings where you can cite a real policy. Return [] if no issues found.

=== KUBERNETES MANIFESTS ===
{combined}
"""

print(f"K8s files: {len(k8s_files)} files, {len(combined)} chars (~{len(combined)//4} tokens)")
print(f"Policy library: {len(policy_lib)} policies (~{len(raw_pol)//4} tokens)")
print(f"Total prompt: {len(prompt)} chars (~{len(prompt)//4} tokens)")
print()
print("Running 2 trials with K8s-adapted prompt + 100 policies...")
print("=" * 90)

for trial in range(1, 3):
    t0 = time.time()
    findings = call_gemini_json(prompt)
    elapsed = time.time() - t0

    accepted, dropped = apply_gate(findings, policy_lib)

    print(f"\nTrial {trial}: {len(findings)} raw -> {len(accepted)} accepted / {len(dropped)} dropped | {elapsed:.1f}s")
    print("-" * 90)

    for i, f in enumerate(findings):
        pid = f.get("policy_id", "NONE")
        res = str(f.get("resource", ""))[:80]
        iss = str(f.get("issue", ""))[:100]
        gate = "ACC" if f in accepted else "DROP"
        print(f"  [{i+1}] {gate} | {pid}")
        print(f"      Resource: {res}")
        print(f"      Issue: {iss}")

    all_text = " ".join(json.dumps(f) for f in findings).lower()
    found_secrets = "secret" in all_text and ("cluster" in all_text or "wide" in all_text)
    found_hostnet = any(x in all_text for x in ["hostnetwork", "host_network", "host network"])
    found_docker = any(x in all_text for x in ["docker", "sock"])
    found_root = any(x in all_text for x in ["root", "nonroot", "non-root", "privilege"])
    found_netpol = any(x in all_text for x in ["networkpolicy", "network policy"])

    print(f"\n  Cross-file detections:")
    print(f"    Cluster-wide secrets access:  {'YES' if found_secrets else 'MISSED'}")
    print(f"    hostNetwork bypass:           {'YES' if found_hostnet else 'MISSED'}")
    print(f"    Docker socket mount:          {'YES' if found_docker else 'MISSED'}")
    print(f"    Runs as root / privilege:     {'YES' if found_root else 'MISSED'}")
    print(f"    Missing NetworkPolicy:        {'YES' if found_netpol else 'MISSED'}")
    score = sum([found_secrets, found_hostnet, found_docker, found_root, found_netpol])
    print(f"    Score: {score}/5")

print()
print("=" * 90)

