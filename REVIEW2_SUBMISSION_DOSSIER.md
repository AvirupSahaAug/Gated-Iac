# Project P16: Review 2 Official Submission Dossier
**GateIaC: Grounded Hybrid Detection of Infrastructure-as-Code Misconfigurations Using Policy Rules and a Language Model**

---

## 1. Executive Summary

GateIaC is a three-stage hybrid pipeline for detecting security misconfigurations in Terraform Infrastructure-as-Code:

1. **OPA/Rego Deterministic Engine** — catches syntactic, single-resource flaws with zero false positives.
2. **LLM Contextual Pass** (Gemini Flash-Lite) — reasons over multi-resource privilege-escalation chains that static rules cannot express.
3. **Citation Verification Gate** — drops any LLM finding that cannot quote a real policy verbatim, guaranteeing zero hallucinated output.

Review 2 deliverables span corpus design, ablation study, scalability stress testing (12 → 100 policies, single-file → multi-file), cross-provider benchmarking (Gemini vs Groq), and an AST-based dependency graph traverser that reduces prompts by 90% to fit token-limited inference APIs.

---

## 2. Corpus & Ground Truth

### 2.1 Core Benchmark Scenarios (7 files, 11 labeled flaws)

| # | File | Cloud Services | Flaws | Description |
|---|------|---------------|-------|-------------|
| 1 | `simple_misconfig.tf` | S3, SG | GT-001, GT-002 | Public-read S3 ACL; SSH open to 0.0.0.0/0. |
| 2 | `complex_misconfig.tf` | EC2, SG, IAM, S3 | GT-003 | Internet-facing EC2 with IAM role granting S3 secrets access (Capital One SSRF pattern). |
| 3 | `serverless_dynamo_privilege.tf` | Lambda URL, DynamoDB, IAM | GT-004, GT-005 | Unauthenticated Lambda URL with wildcard DynamoDB write over unencrypted PII table. |
| 4 | `rds_public_subnet_leak.tf` | RDS, SG | GT-006, GT-007 | Public RDS PostgreSQL with `publicly_accessible = true` and 0.0.0.0/0 ingress. |
| 5 | `cross_account_iam_assume.tf` | IAM Trust, S3 | GT-008, GT-009 | Wildcard principal (`AWS: *`) cross-account trust policy attached to backup bucket access. |
| 6 | `ssrf_imds_v1_vulnerable.tf` | EC2, IMDSv1, IAM | GT-010, GT-011 | Public EC2 with legacy IMDSv1 enabling SSRF credential theft of Parameter Store secrets. |
| 7 | `secure_hardened_reference.tf` | Private EC2, Bastion, S3 | *(none)* | **Negative control** — fully hardened CIS-compliant architecture. Zero expected violations. |

### 2.2 Stress-Test Corpus: Enterprise Monorepo (1 file, 2 additional flaws)

| File | Lines | Resources | Flaws | Description |
|------|-------|-----------|-------|-------------|
| `enterprise_monorepo_stress.tf` | 1,153 | ~100 | GT-012, GT-013 | Full enterprise stack (VPC, ALB, ECS Fargate, RDS, ElastiCache, DynamoDB, Lambda, CloudWatch). Vulnerability: unencrypted PII S3 bucket (GT-012) + 5-resource ALB → ECS → IAM → S3 privilege chain buried across 600+ lines of boilerplate (GT-013). |

### 2.3 Multi-File Enterprise Structure (10 modular files)

Created to test whether the LLM can trace cross-file dependencies when resources are split across separate Terraform modules:

| File | Lines | Purpose |
|------|-------|---------|
| `00-variables.tf` | 46 | Variables, locals, common tags |
| `01-vpc.tf` | 180 | VPC, subnets (public/private/database), NAT gateways, VPC endpoints |
| `02-security-groups.tf` | 79 | 9 security groups (ALB, ECS API, ECS worker, data-exporter, RDS, ElastiCache, bastion, VPC endpoints, Lambda) |
| `03-iam.tf` | 119 | IAM roles: ECS execution, API task, worker task, **data-exporter task (overprivileged)**, Lambda authorizer, backup |
| `04-rds.tf` | 39 | Encrypted RDS primary + read replica |
| `05-s3.tf` | 64 | 7 S3 buckets — 6 properly encrypted, **1 unencrypted PII exports bucket** |
| `06-ecs.tf` | 96 | ECS cluster, 3 task definitions (API, worker, **data-exporter**), 3 services |
| `07-alb.tf` | 42 | **Public ALB** with listener rules routing `/api/v1/exports/*` to data-exporter |
| `08-monitoring.tf` | 78 | CloudWatch alarms, SNS topics, SQS queues |
| `09-extras.tf` | 100 | SSM parameters, Lambda authorizer, bastion, ElastiCache, DynamoDB tables, autoscaling |

**Multi-file vulnerability chain:** `07-alb.tf` (public ALB) → `06-ecs.tf` (data-exporter service) → `03-iam.tf` (overprivileged IAM role with `dynamodb:*` and S3 write) → `05-s3.tf` (unencrypted customer PII bucket).

---

## 3. Policy Library

### 3.1 Core Enforcement Policies (12 policies with Rego rules)

| Policy ID | Title |
|-----------|-------|
| POL-S3-001 | S3 bucket ACL must not be public-read or public-read-write |
| POL-S3-002 | S3 buckets must have server-side encryption configured |
| POL-SG-001 | Security groups must not allow SSH from 0.0.0.0/0 |
| POL-IAM-002 | Internet-facing compute must not hold IAM roles with data store access |
| POL-IAM-003 | IAM policies must not use wildcard resource |
| POL-DDB-001 | DynamoDB tables must have server-side encryption |
| POL-IAM-004 | Unauthenticated endpoints must not have write access to data stores |
| POL-RDS-001 | RDS instances must have storage encryption enabled |
| POL-RDS-002 | RDS instances must not be publicly accessible with open security groups |
| POL-IAM-005 | IAM trust policies must not specify wildcard principal |
| POL-EC2-002 | EC2 instances must enforce IMDSv2 |
| POL-EC2-003 | Public instances with IMDSv1 must not access secrets stores |

### 3.2 Decoy / Noise Policies (88 additional, no Rego enforcement)

For stress testing, the policy library was expanded from 12 → **100 policies** with 88 decoy policies covering: VPC flow logs, CloudTrail, CloudWatch, ECS hardening, Lambda, CloudFront, WAF, API Gateway, SQS/SNS, ECR, ElastiCache, Kinesis, Redshift, Glue, Route53, SageMaker, ELB, and more.

**Purpose:** Test whether the LLM incorrectly attributes findings to irrelevant policies when the library is noisy.

---

## 4. Ablation Study: Isolating the Citation Gate

Three operational modes compared across all 6 core scenarios:

| Mode | Prompt | Gate | Hallucination Rate | Complex Recall |
|------|--------|------|-------------------|----------------|
| **Mode 1: Baseline B** | No policy catalog | None | **100%** (no citations possible) | 100% (5/5) |
| **Mode 2: Grounded, No Gate** | Policy catalog in prompt | None | **0.0%** (at T=0.2) | 100% (5/5) |
| **Mode 3: GateIaC (Full)** | Policy catalog in prompt | Citation Gate verifies ID + verbatim quote | **0.0%** (formally guaranteed) | 100% (5/5) |

**Key insight:** At low temperature, grounded prompting alone produces well-formed citations. The Citation Gate's value is as a **deterministic safety guarantee** — it ensures zero hallucination regardless of model behavior or temperature, acting as a formal verification layer rather than an empirical filter.

---

## 5. Scalability Stress Tests

### 5.1 Policy Scaling (12 → 42 → 100 policies)

All tests on `enterprise_monorepo_stress.tf` (1,153 lines, ~100 resources) with Gemini 3.5 Flash-Lite:

| Policies | Prompt Tokens | Trials | GT-012 (S3) | GT-013 (Chain) | False Positives | Avg Latency |
|----------|--------------|--------|-------------|----------------|-----------------|-------------|
| 12 | ~9,600 | 5/5 ✅ | 100% | 100% | 0 | 2.8s |
| 42 | ~13,000 | 5/5 ✅ | 100% | 100% | 0 | 2.6s |
| 100 | ~19,200 | 2/2 ✅ | 100% | 100% | 0 | 4.5s |

At 100 policies, Flash-Lite also discovered `POL-ELB-002` (HTTP listener lacking HTTPS redirect) — a real finding enabled by the expanded policy library.

### 5.2 Multi-File Enterprise Test (10 modular `.tf` files + 100 policies)

Concatenated all 10 files (843 lines, ~9,138 tokens) with 100 policies (~10,587 tokens) = **~20,022 total prompt tokens**.

| Trial | Raw Findings | Accepted | Dropped | GT: S3 Encryption | GT: Multi-File Chain | Latency |
|-------|-------------|----------|---------|-------------------|---------------------|---------|
| 1 | 2 | 2 | 0 | ✅ `POL-S3-002` | ✅ `POL-IAM-002` | 3.15s |
| 2 | 3 | 3 | 0 | ✅ `POL-S3-002` | ✅ `POL-IAM-002` | 11.47s |

**Flash-Lite successfully traced the vulnerability chain spanning 4 separate Terraform files** (ALB → ECS → IAM → S3) with zero hallucinations.

### 5.3 Cross-Provider Benchmark: Groq API Failure

The same 20,022-token prompt was sent to Groq (free tier) using `qwen/qwen3.8-27b`:

```
Error code: 413 — Request too large for model `qwen/qwen3.8-27b`:
Limit 7,000 tokens, Requested 20,053
```

All Groq models hit hard TPM limits: `qwen/qwen3.8-27b` (7,000 ITPM), `openai/gpt-oss-120b` (8,000 TPM), `openai/gpt-oss-20b` (8,000 TPM). The raw whole-file prompt cannot fit.

**This failure directly motivates the AST graph traverser.**

---

## 6. AST-Based Dependency Graph Traverser

### 6.1 Problem Statement

Sending entire Terraform codebases as raw text to LLMs fails when:
- Prompts exceed API token limits (Groq: 7K–8K TPM on free tier).
- Attention is diluted across hundreds of noise resources (VPC subnets, route tables, CloudWatch alarms).
- Vulnerability chains span 600+ lines of boilerplate between the relevant resources.

### 6.2 Architecture

```
plan.json ──► build_resource_graph() ──► find_candidate_subgraphs() ──► export_subgraph_context()
  (124 nodes       networkx.DiGraph         Entrypoint → Sink            Compact pseudo-HCL
   146 edges)     with risk_tags            paths extracted              (<1000 tokens)
                                            noise pruned
```

**Implementation:** `pipeline/ast_graph_traverser.py` (619 lines, uses `networkx`).

**Three-stage pipeline:**
1. **`build_resource_graph(plan.json)`** — Parses `resource_changes` and `configuration.root_module.resources.expressions.references` to construct a directed dependency graph. Each node carries type, config, and risk_tags.
2. **`find_candidate_subgraphs(graph)`** — Identifies entrypoints (public ALBs, wildcard SGs, unauthenticated Lambda URLs) and sinks (S3, IAM policies, RDS, DynamoDB). Traverses undirected paths with infrastructure hub nodes pruned (VPCs, subnets, route tables, CloudWatch alarms). Deduplicates overlapping candidates.
3. **`export_subgraph_context_from_graph(subgraph, graph)`** — Serializes only security-relevant attributes per resource type into a compact pseudo-HCL snippet with explicit dependency chain comments.

### 6.3 Token Reduction Results

| Metric | Raw Whole-File | AST-Extracted Subgraph |
|--------|---------------|----------------------|
| Resources sent to LLM | 124 (all noise included) | **8** (targeted attack path only) |
| Source snippet size | ~8,750 tokens | **~544 tokens** |
| Total prompt (+ 12 core policies) | ~20,050 tokens | **~1,976 tokens** |
| Fits Groq free tier (7K limit)? | ❌ **HTTP 413 crash** | ✅ **Fits comfortably** |

**Reduction: 90% fewer tokens in the prompt.**

### 6.4 AST + Groq End-to-End Result

With the AST-extracted subgraph feeding Groq's `qwen/qwen3.8-27b`:

```
Groq Response Time: 0.84s
Findings: 1 raw -> 1 accepted, 0 dropped

[1] ACCEPTED | POL-IAM-002
    Resource: aws_lb.public, aws_security_group.alb_public, aws_ecs_service.data_exporter...
    Issue: The ECS service is reachable from the internet via a public ALB
           and is attached to an overprivileged IAM role with S3 write access.
```

**The AST traverser enabled Groq to detect the exact same cross-resource chain that raw prompting could not even attempt.**

---

## 7. Comparative Benchmark Summary

| Metric | Checkov 3.3.16 | tfsec v1.28.14 | Baseline B (Raw LLM) | GateIaC (Full) | GateIaC + AST |
|--------|:-----------:|:-----------:|:-----------:|:-----------:|:-----------:|
| **Paradigm** | Static AST | Static AST | Ungrounded LLM | Gated Hybrid | Gated Hybrid + Graph |
| **Simple Flaw Recall** | 100% | 100% | N/A | 100% (OPA) | 100% (OPA) |
| **Complex Cross-Resource Recall** | **0%** | **0%** | 100% | 100% | 100% |
| **False Positives on Clean Code** | 22 alerts | 14 alerts | 1 speculation | **0** | **0** |
| **Hallucination Rate** | 0% | 0% | 100% | **0% (Gated)** | **0% (Gated)** |
| **Max Prompt Size** | N/A | N/A | ~20K tokens | ~20K tokens | **~2K tokens** |
| **Groq Compatibility** | N/A | N/A | ❌ 413 | ❌ 413 | ✅ **0.84s** |
| **Latency (per scenario)** | 4.09s | 0.44s | 4.67s | 7.37s | **0.84s** (Groq) |

---

## 8. How to Execute

### Core Pipeline
```bash
cd /home/avirup/Desktop/mlshet/p16-hybrid-iac
source /home/avirup/Desktop/mlshet/.venv/bin/activate

# Run OPA deterministic engine
conftest test --policy policies/ --all-namespaces corpus/plan.json

# Run full GateIaC hybrid pipeline
python pipeline/hybrid_pipeline.py corpus/complex_misconfig.tf corpus/plan.json

# Run 3-mode ablation study
python scripts/run_ablation_study.py

# Generate publication plots
python scripts/generate_review2_plots.py
```

### AST Traverser + Groq Demo
```bash
# Demonstrates 90% token reduction enabling Groq API compatibility
python scripts/demo_ast_groq.py
```

### Generated Artifacts
- `results/ablation_study_summary.json` — Per-scenario findings for all 3 ablation modes
- `results/plots/*.png` — Publication-grade figures at 300 DPI
- `corpus/plan.json` — Compiled Terraform plan (124 resources)
