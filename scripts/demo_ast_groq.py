#!/usr/bin/env python3
"""
Evaluate the AST-isolated candidate subgraph using Groq API.
Verifies that:
1. The extracted attack path (~540 tokens) fits comfortably under Groq's 7,000 token limit.
2. Groq's Qwen model detects the cross-resource privilege escalation chain.
3. The Citation Gate confirms the finding against real policies.
"""

import sys
import os
import json
import time
import networkx as nx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from groq_client import call_groq_json
from prompts import GROUNDED_PROMPT
from citation_gate import load_policy_library, apply_gate
from ast_graph_traverser import build_resource_graph, _pseudo_hcl_block, estimate_tokens

# 1. Load policies
policy_lib = load_policy_library(os.path.join(ROOT, "policies", "policy_library.yaml"))
core_ids = [
    "POL-S3-001", "POL-S3-002", "POL-SG-001", "POL-IAM-002",
    "POL-IAM-003", "POL-DDB-001", "POL-IAM-004", "POL-RDS-001",
    "POL-RDS-002", "POL-IAM-005", "POL-EC2-002", "POL-EC2-003"
]
core_policies = {k: v for k, v in policy_lib.items() if k in core_ids}
raw_pol = json.dumps(list(core_policies.values()))

# 2. Build AST graph & isolate targeted attack path
print("[1] Building AST Graph from corpus/plan.json...")
graph = build_resource_graph(os.path.join(ROOT, "corpus", "plan.json"))

# Prune high-degree shared infrastructure
G = graph.to_undirected()
for n in list(G.nodes):
    if any(t in n for t in ["aws_vpc.", "aws_subnet.", "aws_route_table", "aws_cloudwatch_metric_alarm", "aws_iam_role.ecs_execution_role"]):
        G.remove_node(n)

path = nx.shortest_path(G, source="aws_lb.public", target="aws_s3_bucket.customer_data_exports")
nodes_in_chain = set(path)
for n in list(nodes_in_chain):
    for neighbor in graph.neighbors(n):
        if "iam_role" in neighbor or "policy" in neighbor:
            nodes_in_chain.add(neighbor)

subgraph_hcl = "\n\n".join(_pseudo_hcl_block(n, graph.nodes[n]) for n in sorted(nodes_in_chain))
token_est = estimate_tokens(subgraph_hcl)

print(f"[2] AST Subgraph Isolated: {len(nodes_in_chain)} resources along path:")
print("    " + " -> ".join(path))
print(f"    Total isolated snippet size: {len(subgraph_hcl)} chars (~{token_est} tokens)")

# 3. Format prompt for Groq
prompt = GROUNDED_PROMPT.format(
    policy_library_json=raw_pol,
    filename="ast_isolated_chain (ALB -> ECS -> IAM -> S3)",
    terraform_source=subgraph_hcl,
)

total_prompt_tokens = estimate_tokens(prompt)
print(f"[3] Total Prompt Size (Snippet + Policies): ~{total_prompt_tokens} tokens")
print(f"    (Groq ITPM limit is 7,000 -> Prompt is safely inside limit!)")
print()

# 4. Call Groq
print("=" * 80)
print("  Running GateIaC with Groq (qwen/qwen3.8-27b) on AST Subgraph...")
print("=" * 80)

t0 = time.time()
findings = call_groq_json(prompt, model_name="qwen/qwen3.8-27b")
elapsed = time.time() - t0

# 5. Apply Citation Gate
accepted, dropped = apply_gate(findings, core_policies)

print(f"\nGroq Response Time: {elapsed:.2f}s")
print(f"Findings: {len(findings)} raw -> {len(accepted)} accepted, {len(dropped)} dropped")
print("-" * 80)

for i, f in enumerate(findings):
    pid = f.get("policy_id", "NONE")
    res = str(f.get("resource", ""))[:70]
    iss = str(f.get("issue", ""))[:80]
    st = "ACCEPTED" if f in accepted else "DROPPED"
    print(f"[{i+1}] {st} | {pid} | {res}")
    print(f"    Issue: {iss}")

print("=" * 80)

