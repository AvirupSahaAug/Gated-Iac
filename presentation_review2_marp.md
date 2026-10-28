---
marp: true
theme: gaia
size: 16:9
paginate: true
backgroundColor: #ffffff
color: #1e293b
footer: 'P16: GateIaC — Policy-Gated Hybrid IaC Misconfiguration Detection | Review 2'
style: |
  section {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    padding: 24px 40px;
    font-size: 16.5px;
    line-height: 1.36;
  }
  h1 {
    color: #0f172a;
    font-size: 1.8rem;
    margin-bottom: 6px;
    margin-top: 0;
  }
  h2 {
    color: #1e40af;
    font-size: 1.3rem;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 4px;
    margin-top: 0;
    margin-bottom: 8px;
  }
  h3 {
    color: #0369a1;
    font-size: 1.05rem;
    margin-top: 0;
    margin-bottom: 4px;
  }
  p, ul, ol {
    margin-top: 3px;
    margin-bottom: 3px;
  }
  li {
    margin-bottom: 3px;
    font-size: 15px;
    line-height: 1.34;
  }
  table {
    font-size: 13px;
    width: 100%;
    border-collapse: collapse;
    margin-top: 6px;
    margin-bottom: 6px;
  }
  th {
    background-color: #1e40af;
    color: white;
    padding: 6px 9px;
    text-align: left;
    font-size: 13.5px;
  }
  td {
    padding: 5px 9px;
    border-bottom: 1px solid #e2e8f0;
    font-size: 13px;
  }
  tr:nth-child(even) {
    background-color: #f8fafc;
  }
  code {
    background-color: #f1f5f9;
    color: #0f172a;
    font-size: 14px;
    padding: 1px 4px;
    border-radius: 4px;
    border: 1px solid #cbd5e1;
  }
  pre {
    background-color: #f8fafc;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    font-size: 14.5px;
    border-radius: 6px;
    padding: 10px 14px;
    line-height: 1.34;
    margin: 5px 0;
  }
  .card {
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 6px;
    font-size: 15px;
  }
  .card ul {
    margin: 3px 0 3px 18px;
    padding: 0;
  }
  .card li {
    font-size: 14.5px;
    line-height: 1.32;
    margin-bottom: 2px;
  }
  .highlight-box {
    background: #f0f9ff;
    border-left: 5px solid #0284c7;
    padding: 6px 12px;
    border-radius: 4px;
    margin: 6px 0;
    font-size: 14.5px;
    line-height: 1.35;
  }
  .alert-box {
    background: #fef2f2;
    border-left: 5px solid #ef4444;
    padding: 6px 12px;
    border-radius: 4px;
    margin: 6px 0;
    font-size: 14.5px;
    line-height: 1.35;
  }
  .success-box {
    background: #f0fdf4;
    border-left: 5px solid #22c55e;
    padding: 6px 12px;
    border-radius: 4px;
    margin: 6px 0;
    font-size: 14.5px;
    line-height: 1.35;
  }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 12.5px;
    font-weight: 600;
  }
  .badge-green { background: #dcfce7; color: #166534; }
  .badge-blue { background: #dbeafe; color: #1e40af; }
  .badge-amber { background: #fef3c7; color: #92400e; }
  .badge-red { background: #fee2e2; color: #991b1b; }
  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-top: 6px;
  }
  .grid-3 {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
    margin-top: 6px;
  }
  .viz-container {
    text-align: center;
    margin: 4px 0;
  }
  .viz-img {
    max-width: 88%;
    max-height: 370px;
    width: auto;
    height: auto;
    object-fit: contain;
    border-radius: 6px;
    border: 1px solid #e2e8f0;
  }
---

<!-- _class: lead -->
# GateIaC: Grounded Hybrid IaC Security Pipeline
### Full Prototype, Scalability Stress Testing, Multi-Model Evaluation and AST Traversal

<br>

**Project Review 2 — Comprehensive Technical Defense and Empirical Results**  
*Team P16 | Academic Year 2026*

---

## 1. Review 2 Objectives and Deliverables Matrix

| Objective | Expected Rubric Deliverable | Implementation and Evidence Delivered | Verification |
| :--- | :--- | :--- | :--- |
| **Corpus Expansion** | Multi-service enterprise test suite covering topological privilege paths. | 7 core scenarios (32 res) + 1,153-line Monorepo + 10-file modular suite. | `corpus/` and `ground_truth.json` |
| **Policy Scaling** | Formal rule catalog expanded beyond toy rule sets. | Scaled from 12 core rules to **100 policies** (88 decoy rules across 18 services). | `policies/policy_library.yaml` |
| **Ablation Study** | Isolate mathematical value of the Citation Gate. | 3-mode ablation across all scenarios verifying 0.0% post-gate hallucination. | `results/ablation_study_summary.json` |
| **Multi-Model Scaling** | Evaluate across model regimes and identify failure boundaries. | Evaluated Gemini 3.5 Flash-Lite vs Groq LPUs (`qwen/qwen3.8-27b`). | `scripts/test_tf_stress.py` |
| **AST Optimization** | Solve context-window and TPM bottlenecks on enterprise repos. | Built **AST Dependency Graph Traverser** reducing tokens by **90%** (20k to ~2k). | `pipeline/ast_graph_traverser.py` |

---

## 2. Core Benchmark Corpus: Topological Attack Paths

<table style="font-size:12.5px;">
  <tr><th>Scenario File</th><th>Cloud Services</th><th>Flaws</th><th>Threat Model Description</th></tr>
  <tr><td><b>complex_misconfig.tf</b></td><td>EC2, SG, IAM, S3</td><td>GT-001..3</td><td>Public EC2 bound to IAM role with private S3 secrets access (Capital One SSRF).</td></tr>
  <tr><td><b>serverless_dynamo_privilege.tf</b></td><td>Lambda URL, DynamoDB, IAM</td><td>GT-004..5</td><td>Public unauthenticated Lambda URL granting full write access to customer PII table.</td></tr>
  <tr><td><b>rds_public_subnet_leak.tf</b></td><td>RDS PostgreSQL, SG</td><td>GT-006..7</td><td>Production PostgreSQL DB marked <code>publicly_accessible=true</code> with 0.0.0.0/0 ingress.</td></tr>
  <tr><td><b>cross_account_iam_assume.tf</b></td><td>IAM Trust Policy, S3</td><td>GT-008..9</td><td>Backup S3 bucket with cross-account IAM trust role specifying wildcard <code>AWS: *</code>.</td></tr>
  <tr><td><b>ssrf_imds_v1_vulnerable.tf</b></td><td>EC2, IMDSv1, IAM SSM</td><td>GT-010..11</td><td>Public EC2 with legacy IMDSv1 allowing SSRF theft of Parameter Store credentials.</td></tr>
  <tr><td><b>secure_hardened_reference.tf</b></td><td>Private EC2, Bastion, S3</td><td><i>None</i></td><td><b>Negative Control:</b> Fully hardened CIS-compliant reference (0 false alarms target).</td></tr>
</table>

<div class="highlight-box">
<b>Topological Flaw Reality:</b> None of the complex flaws (GT-003, 005, 007, 009, 011) can be detected by examining any single resource attribute in isolation.
</div>

---

## 3. Negative Control: Overcoming Alert Fatigue

Standard static AST linters generate substantial alert fatigue on compliant infrastructure:

<div class="grid-2">
<div class="card">
<h3>Hardened Reference (<code>secure_hardened_reference.tf</code>)</h3>
<ul>
  <li><b>Network:</b> Private compute behind dedicated VPN bastion host.</li>
  <li><b>Storage:</b> S3 buckets enforce default <code>AES256</code> server-side encryption.</li>
  <li><b>IAM:</b> Least-privilege scoped to read-only <code>s3:GetObject</code>.</li>
  <li><b>Metadata:</b> IMDSv2 strictly enforced (<code>http_tokens = "required"</code>).</li>
</ul>
</div>

<div class="card">
<h3>Empirical Tool Behavior on Clean Code</h3>
<ul>
  <li><b>Checkov 3.3.16:</b> <b>22 noisy alerts</b> (missing flow logs, default KMS keys).</li>
  <li><b>tfsec v1.28.14:</b> <b>14 static alerts</b> (missing descriptions, unversioned buckets).</li>
  <li><b>Baseline B (Raw LLM):</b> 1 speculative ungrounded assertion.</li>
  <li><span class="badge badge-green">GateIaC (Proposed)</span>: <b>0 Alerts (100% Specificity, 0.0% FPR)</b>.</li>
</ul>
</div>
</div>

<div class="success-box">
<b>Finding:</b> GateIaC eliminates alert fatigue by filtering noise through deterministic OPA rules and verified policy constraints.
</div>

---

## 4. Policy Library Expansion: From 12 to 100 Policies

To stress-test model selection and citation precision under noisy conditions, we scaled the policy catalog:

<div class="grid-2">
<div class="card">
<h3>1. Core Enforced Policies (12 Rules)</h3>
<ul>
  <li>Backed by deterministic Rego verification modules.</li>
  <li>Covers S3 public ACLs/encryption (<code>POL-S3-001/002</code>).</li>
  <li>Covers open SSH ingress (<code>POL-SG-001</code>).</li>
  <li>Covers public compute IAM data paths (<code>POL-IAM-002</code>).</li>
  <li>Covers public RDS and unauthenticated Lambda access.</li>
</ul>
</div>

<div class="card">
<h3>2. Decoy / Noise Library (88 Policies)</h3>
<ul>
  <li>Expanded across 18 AWS cloud service domains.</li>
  <li>Includes CloudTrail, CloudWatch, VPC flow logs, ECS, Lambda, WAF, API Gateway, SQS/SNS, ECR, ElastiCache, Kinesis, Redshift, Route53, and SageMaker.</li>
  <li><b>Goal:</b> Test if the LLM falsely cites irrelevant decoy rules.</li>
</ul>
</div>
</div>

<div class="highlight-box">
<b>Result:</b> When tested against 100 policies (~10,500 tokens of rules alone), the Citation Gate dropped 0 legitimate claims and rejected zero valid citations.
</div>

---

## 5. Enterprise Monorepo Stress Benchmark (1,153 Lines)

We evaluated single-file scalability using `corpus/enterprise_monorepo_stress.tf`:
- **1,153 lines of Terraform**, ~100 cloud resources, 124 compiled plan nodes.
- **Topological Chain Buried Across 600+ Lines:**
  `aws_lb.public` -> `aws_ecs_service.data_exporter` -> `aws_ecs_task_definition` -> `aws_iam_role_policy` (wildcard DynamoDB + S3 write) -> `aws_s3_bucket.customer_data_exports` (unencrypted PII).

<div class="card">
<h3>Policy Scaling Stress Test Results (Gemini 3.5 Flash-Lite)</h3>
<table>
  <tr><th>Policy Catalog Size</th><th>Total Prompt Tokens</th><th>Trials</th><th>GT-012 (Unencrypted S3)</th><th>GT-013 (Complex Chain)</th><th>False Positives</th></tr>
  <tr><td><b>12 Policies (Core)</b></td><td>~9,600 tokens</td><td>5/5</td><td>100.0% Detected</td><td>100.0% Detected</td><td>0.0</td></tr>
  <tr><td><b>42 Policies (Intermediate)</b></td><td>~13,000 tokens</td><td>5/5</td><td>100.0% Detected</td><td>100.0% Detected</td><td>0.0</td></tr>
  <tr><td><b>100 Policies (Massive Noise)</b></td><td>~19,200 tokens</td><td>2/2</td><td>100.0% Detected</td><td>100.0% Detected</td><td>0.0</td></tr>
</table>
</div>

---

## 6. Multi-File Enterprise Suite: Architecture

In real enterprise repositories, infrastructure is divided across separate modular files:

<div class="grid-2">
<div class="card">
<h3>10-File Modular Infrastructure Layout</h3>
<ul>
  <li><code>00-variables.tf</code>: Environment, tags, and cluster config.</li>
  <li><code>01-vpc.tf</code>: VPC, subnets, NAT gateways, VPC endpoints.</li>
  <li><code>02-security-groups.tf</code>: 9 security groups for tier isolation.</li>
  <li><code>03-iam.tf</code>: Execution, worker, and data-exporter roles.</li>
  <li><code>04-rds.tf</code>: Encrypted PostgreSQL primary and replica.</li>
  <li><code>05-s3.tf</code>: 7 S3 buckets (6 encrypted, 1 unencrypted PII).</li>
  <li><code>06-ecs.tf</code>: Task definitions and ECS services.</li>
  <li><code>07-alb.tf</code>: Public load balancer and listener rules.</li>
  <li><code>08-monitoring.tf</code>: CloudWatch alarms, SNS, SQS queues.</li>
  <li><code>09-extras.tf</code>: Bastion, Redis cluster, DynamoDB tables.</li>
</ul>
</div>

<div class="card">
<h3>Design Rationale</h3>
<ul>
  <li>Reflects real production setups where networking, identity, storage, and compute live in separate modules.</li>
  <li>Forces the analyzer to resolve references across files rather than relying on local line proximity.</li>
  <li>Concatenating all 10 files produces 843 lines and ~9,138 source tokens.</li>
</ul>
</div>
</div>

---

## 7. Multi-File Enterprise Suite: Vulnerability Chain

<div class="card">
<h3>Cross-File Vulnerability Path</h3>
<p>The privilege path deliberately traverses 4 distinct modular files:</p>
<ol>
  <li><b><code>07-alb.tf</code></b>: Public ALB listener routes <code>/api/v1/exports/*</code> directly to target group.</li>
  <li><b><code>06-ecs.tf</code></b>: Target group forwards traffic to <code>data-exporter</code> Fargate ECS service.</li>
  <li><b><code>03-iam.tf</code></b>: Task role possesses broad S3 write and wildcard <code>dynamodb:*</code> permissions.</li>
  <li><b><code>05-s3.tf</code></b>: Destination <code>customer_exports</code> bucket stores sensitive PII without encryption.</li>
</ol>
</div>

<div class="success-box">
<b>Gemini Flash-Lite Multi-File Result:</b> Evaluated across all 10 concatenated files (~20,022 tokens total with 100 policies). Successfully identified both <code>POL-S3-002</code> and <code>POL-IAM-002</code> across files with 0 dropped citations.
</div>

---

## 8. The Hardware and API Wall: Groq LPU Failure

To evaluate portability and inference speed, we executed the identical multi-file benchmark on **Groq LPUs** (`qwen/qwen3.8-27b` and `openai/gpt-oss-120b`):

<div class="alert-box">
<b>API Execution Failure:</b> Groq returned HTTP 413 (Rate Limit Exceeded):<br>
<code>Request too large on tokens per minute (TPM): Limit 7,000, Requested 20,053.</code>
</div>

<div class="grid-2">
<div class="card">
<h3>Why Raw Multi-File Prompting Fails</h3>
<ul>
  <li>Fast inference engines (Groq, Cerebras) enforce strict per-minute token caps (7k to 8k TPM).</li>
  <li>Sending raw <code>.tf</code> files dumps hundreds of irrelevant lines (VPC subnets, route tables, alarms).</li>
  <li>Attention window dilution increases latency and inference cost on production repositories.</li>
</ul>
</div>

<div class="card">
<h3>The Architectural Bottleneck</h3>
<ul>
  <li>Concatenating whole repositories does not scale to real-world codebases (50k to 100k+ tokens).</li>
  <li>The LLM was forced to act as both a graph parser and a security auditor simultaneously.</li>
  <li><b>Required Solution:</b> Pre-filter code using graph-based AST path traversal.</li>
</ul>
</div>
</div>

---

## 9. AST Dependency Graph Traverser: Architecture

We implemented `pipeline/ast_graph_traverser.py` using `networkx` to build an inter-resource dependency graph:

```
  Terraform plan.json (124 Resources, 146 Edges)
                          |
                          v
         build_resource_graph(plan_json_path)
    [Nodes: Resources | Edges: Consumer -> Dependency]
                          |
                          v
        Hub Node Pruning (VPCs, Subnets, Alarms)
                          |
                          v
             find_candidate_subgraphs()
   [Identifies Paths from Entrypoints -> Sensitive Sinks]
                          |
                          v
       export_subgraph_context_from_graph()
   [Compact Pseudo-HCL Snippet: Target < 1,000 Tokens]
```

---

## 10. AST Graph Traverser: Token Pruning and Results

The traverser identifies entrypoints (`aws_lb`, public SGs, Lambda URLs) and traces directed paths to sinks (`aws_s3_bucket`, IAM policies, databases):

<div class="grid-2">
<div class="card">
<h3>Isolated Attack Path Extracted</h3>
<pre>
aws_lb.public 
  --> aws_security_group.alb_public 
  --> aws_security_group.ecs_data_exporter 
  --> aws_ecs_service.data_exporter 
  --> aws_ecs_task_definition.data_exporter 
  --> aws_s3_bucket.customer_data_exports
</pre>
<p>Extracted <b>8 security-relevant resources</b> from 124 total plan nodes.</p>
</div>

<div class="card">
<h3>Quantitative Token Reduction</h3>
<table>
  <tr><th>Metric</th><th>Raw Code</th><th>AST Subgraph</th></tr>
  <tr><td><b>Resources Sent</b></td><td>124 nodes</td><td><b>8 nodes</b></td></tr>
  <tr><td><b>Snippet Size</b></td><td>~8,750 tokens</td><td><b>~544 tokens</b></td></tr>
  <tr><td><b>Total Prompt</b></td><td>~20,050 tokens</td><td><b>~1,976 tokens</b></td></tr>
  <tr><td><b>Token Reduction</b></td><td>Baseline</td><td><span class="badge badge-green"><b>90.1% Reduction</b></span></td></tr>
  <tr><td><b>Groq Free Tier</b></td><td>Crushed (HTTP 413)</td><td><b>Fits Safely</b></td></tr>
</table>
</div>
</div>

---

## 11. End-to-End AST and Groq Evaluation Success

By passing only the AST-extracted candidate subgraph (~1,976 tokens total), Groq executed successfully:

```
[1] Building AST Graph from corpus/plan.json... (124 nodes, 146 edges)
[2] AST Subgraph Isolated: 8 resources along privilege path (544 tokens)
[3] Calling Groq API (qwen/qwen3.8-27b) with AST Context...

Groq Response Time: 0.84 seconds
Findings: 1 raw -> 1 accepted, 0 dropped

[1] ACCEPTED | POL-IAM-002 | aws_lb.public, aws_ecs_service.data_exporter...
    Issue: Internet-facing ECS service routed via public ALB possesses task role with S3 write access.
    Citation: "A compute resource reachable from 0.0.0.0/0 must not be attached to an IAM role..."
```

<div class="success-box">
<b>Outcome:</b> The AST traverser solved the token-limit problem, reducing latency from 7.37s (Gemini full file) to <b>0.84s (Groq LPU on subgraph)</b> with 0% hallucination.
</div>

---

## 12. The 3-Mode Ablation Study: Isolating the Citation Gate

<div class="grid-3">
<div class="card">
<h3>Mode 1: Baseline B</h3>
<b>Ungrounded Prompt:</b>
<ul>
  <li>No policy catalog provided.</li>
  <li>Generative free-form audit.</li>
  <li>No citation requirement.</li>
  <li><b>Result:</b> 100% ungrounded claims (no policy backing).</li>
</ul>
</div>

<div class="card">
<h3>Mode 2: Grounded (No Gate)</h3>
<b>Catalog Only:</b>
<ul>
  <li>Policy catalog included in prompt.</li>
  <li>Model asked to cite policy quotes.</li>
  <li>Outputs accepted as-is.</li>
  <li><b>Result:</b> 0.0% hallucination at low temperature (T=0.2).</li>
</ul>
</div>

<div class="card">
<h3>Mode 3: GateIaC (Full)</h3>
<b>Catalog + Citation Gate:</b>
<ul>
  <li>Policy catalog in prompt.</li>
  <li>Deterministic verification gate active.</li>
  <li>Exact substring matching.</li>
  <li><b>Result:</b> <b>0.0% Formally Guaranteed</b>.</li>
</ul>
</div>
</div>

<div class="highlight-box">
<b>Key Insight:</b> Prompt engineering (Mode 2) produces well-formed citations at low temperatures, but the Citation Gate (Mode 3) provides a <b>deterministic safety guarantee</b> regardless of temperature drift or prompt attacks.
</div>

---

## 13. Empirical Ablation Visualizations: Hallucination Rate

<div class="viz-container">
  <img src="results/plots/hallucination_ablation.png" class="viz-img" alt="Hallucination Ablation Chart" />
</div>

<div class="highlight-box">
<b>Empirical Proof:</b> Mode 1 (ungrounded) yields 100% unverified claims. Mode 2 constrains model output via prompt catalog. Mode 3 (GateIaC) formally eliminates ungrounded findings (0.0% post-gate rate).
</div>

---

## 14. Empirical Visualizations: Detection Recall Comparison

<div class="viz-container">
  <img src="results/plots/recall_comparison.png" class="viz-img" alt="Recall Comparison Chart" />
</div>

<div class="highlight-box">
<b>The Critical Recall Gap:</b> Checkov (3.3.16) and tfsec (v1.28.14) achieve 100% recall on isolated syntax flaws but fail completely (0.0%) on multi-resource contextual attack paths. GateIaC achieves 100% recall across both flaw classes.
</div>

---

## 15. Comprehensive Benchmark Evaluation Table

All metrics computed dynamically from disk execution artifacts across all evaluation dimensions:

<table style="font-size:13px;">
  <tr><th>Dimension</th><th>Checkov 3.3.16</th><th>tfsec v1.28.14</th><th>Baseline B (Raw LLM)</th><th>GateIaC (Full)</th><th>GateIaC + AST Traverser</th></tr>
  <tr><td><b>Analysis Engine</b></td><td>Static AST Rules</td><td>Static AST Rules</td><td>Ungrounded Generative</td><td>Gated Hybrid</td><td><b>Graph Traverser + Gated Hybrid</b></td></tr>
  <tr><td><b>Simple Flaw Recall</b></td><td>100.0% (5/5)</td><td>100.0% (5/5)</td><td>N/A</td><td>100.0% (OPA)</td><td><b>100.0% (OPA)</b></td></tr>
  <tr><td><b>Complex Flaw Recall</b></td><td><b style="color:#dc2626;">0.0% (0/5)</b></td><td><b style="color:#dc2626;">0.0% (0/5)</b></td><td>100.0% (5/5)</td><td>100.0% (5/5)</td><td><b>100.0% (5/5)</b></td></tr>
  <tr><td><b>False Positive Rate</b></td><td>22 alerts</td><td>14 alerts</td><td>1 speculation</td><td><b>0 alerts (100% Spec)</b></td><td><b>0 alerts (100% Spec)</b></td></tr>
  <tr><td><b>Post-Gate Hallucination</b></td><td>0.0%</td><td>0.0%</td><td>100.0%</td><td><b>0.0% (Verified)</b></td><td><b>0.0% (Verified)</b></td></tr>
  <tr><td><b>Prompt Token Size</b></td><td>N/A</td><td>N/A</td><td>~20,000 tokens</td><td>~20,000 tokens</td><td><span class="badge badge-green"><b>~1,976 tokens (-90.1%)</b></span></td></tr>
  <tr><td><b>Groq LPU Support</b></td><td>N/A</td><td>N/A</td><td>Crushed (HTTP 413)</td><td>Crushed (HTTP 413)</td><td><span class="badge badge-green"><b>Supported (0.84s)</b></span></td></tr>
  <tr><td><b>End-to-End Latency</b></td><td>4.09s</td><td>0.44s</td><td>4.67s</td><td>7.37s</td><td><b>0.84s (Groq LPU)</b></td></tr>
</table>

---

## 16. Architecture Evolution: Review 1 to Review 2

```
Review 1 Architecture:
  Single TF File --> Rego / OPA --> Raw Gemini Pass --> Final Report
  (Toy micro-benchmark, 1 scenario, manual inspection)

Review 2 Architecture (Now Fully Delivered):
  Modular / Monorepo IaC (10 Files / 1,153 Lines)
         |
         +--> OPA / Conftest Pass (Catches Syntactic Flaws, 0% FPR)
         |
         +--> AST Graph Traverser (networkx)
                     |
                     v Prunes 90% Noise (VPCs, Subnets, Alarms)
              Candidate Subgraph (< 1,000 Tokens)
                     |
                     v Multi-Model Inference (Gemini Flash-Lite / Groq Qwen)
              Candidate Findings JSON
                     |
                     v Citation Verification Gate (Exact Policy Substring Check)
              Authoritative Security Audit Report (0.0% Hallucinations)
```

---

## 17. Summary and Roadmap for Review 3 (Final Defense)

<div class="grid-2">
<div class="card">
<h3>Review 2 Deliverables Completed</h3>
<ul>
  <li>7 Core Benchmark Scenarios (32 resources) + Negative Control.</li>
  <li>Enterprise Monorepo (1,153 lines) and 10-File Modular Suite.</li>
  <li>100-Policy Scaled Catalog with 88 Decoy Rules.</li>
  <li>3-Mode Empirical Ablation Study.</li>
  <li>AST Graph Traverser with 90% token reduction.</li>
  <li>Cross-Provider Validation (Gemini 3.5 Flash-Lite and Groq).</li>
</ul>
</div>

<div class="card">
<h3>Roadmap to Review 3 (Final Defense)</h3>
<ul>
  <li><b>Statistical Sweeps:</b> At least 5 runs across temperatures (T = 0.0 to 1.0) with 95% confidence intervals.</li>
  <li><b>Automated Remediation:</b> Generate validated HCL patch diffs for detected contextual flaws.</li>
  <li><b>K8s / Multi-IaC Ingestion:</b> Expand AST traverser to Helm and Kubernetes manifests.</li>
  <li><b>Publication Manuscript:</b> Prepare research paper for IEEE/ACM DevSecOps submission.</li>
</ul>
</div>
</div>

---

<!-- _class: lead -->
# Thank You!
### Questions and Technical Discussion

<br>

**Project P16:** Grounded Hybrid IaC Misconfiguration Detection (GateIaC)  
**Demonstration Scripts:** `scripts/run_review2_demo.py` and `scripts/demo_ast_groq.py`  
**Official Dossier:** `REVIEW2_SUBMISSION_DOSSIER.md`
