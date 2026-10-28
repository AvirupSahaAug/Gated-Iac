# P16 — GateIaC: Grounded Hybrid Detection of IaC Misconfigurations

Hybrid pipeline: deterministic policy rules (OPA/Rego) + a contextual LLM pass
(Gemini Flash-Lite) gated behind a citation-verification step that drops any finding
that can't quote real policy text.

## 0. Prerequisites
- Terraform, Checkov, tfsec, OPA + Conftest installed
- A Gemini API key: https://aistudio.google.com/apikey
- Python 3.10+

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Then edit .env with your API key
```

## 1. Project Layout
```
corpus/            6 Terraform test scenarios + ground_truth.json (11 labeled flaws)
policies/          policy_library.yaml (12 policies) + .rego rules for OPA
pipeline/          GateIaC hybrid pipeline (OPA + LLM + Citation Gate)
baseline/          Ungrounded LLM baseline runner
scripts/           Ablation study, plot generation, demo harness
results/           JSON outputs + publication plots
```

## 2. Corpus Scenarios
| Scenario | File | Flaws |
|----------|------|-------|
| S3 ACL + SSH ingress | `simple_misconfig.tf` | GT-001, GT-002 |
| SSRF via IAM to secrets | `complex_misconfig.tf` | GT-003 |
| Lambda + DynamoDB PII | `serverless_dynamo_privilege.tf` | GT-004, GT-005 |
| Public RDS PostgreSQL | `rds_public_subnet_leak.tf` | GT-006, GT-007 |
| Wildcard cross-account IAM | `cross_account_iam_assume.tf` | GT-008, GT-009 |
| IMDSv1 SSRF credential theft | `ssrf_imds_v1_vulnerable.tf` | GT-010, GT-011 |
| Negative control (hardened) | `secure_hardened_reference.tf` | None |

## 3. Run the Deterministic Engine (OPA)
```bash
cd corpus
terraform init
terraform plan -out=plan.bin
terraform show -json plan.bin > plan.json
cd ..

conftest test --policy policies/ corpus/plan.json
```

## 4. Run the GateIaC Hybrid Pipeline
```bash
python pipeline/hybrid_pipeline.py corpus/complex_misconfig.tf corpus/plan.json
```

## 5. Run the Full Ablation Study (Review 2)
```bash
python scripts/run_ablation_study.py
```
Compares 3 modes across all 6 scenarios:
- Mode 1: Baseline B (Ungrounded Prompt)
- Mode 2: Grounded Prompt without Gate
- Mode 3: GateIaC (Full Gated Hybrid)

Results saved to `results/ablation_study_summary.json`.

## 6. Generate Publication Plots
```bash
python scripts/generate_review2_plots.py
```
Reads from `results/ablation_study_summary.json` and generates:
- `results/plots/recall_comparison.png`
- `results/plots/hallucination_ablation.png`
- `results/plots/latency_vs_coverage.png`

## 7. One-Shot Demo (Review 2)
```bash
python scripts/run_review2_demo.py
```
Runs environment check, baseline scanners, ablation study, plot generation,
and dynamic summary table in one command.

## 8. Model Configuration
`pipeline/gemini_client.py` uses `gemini-3.5-flash-lite` by default.
Set `GEMINI_API_KEY` in `.env` or as an environment variable.
