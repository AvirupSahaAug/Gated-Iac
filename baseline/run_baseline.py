"""
Baseline B from the hypothesis: same model, same task, NO citation
requirement. Compare this output's hallucination rate against the gated
hybrid pipeline's to compute your headline metric.

Usage:
    export GEMINI_API_KEY=...
    python baseline/run_baseline.py corpus/complex_misconfig.tf

You still need to run Checkov and tfsec separately for the static-scanner
half of the baseline:
    checkov -d corpus/ --output json > results/checkov_baseline.json
    tfsec corpus/ --format json > results/tfsec_baseline.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from gemini_client import call_gemini_json
from prompts import UNGROUNDED_PROMPT


def run_ungrounded_pass(tf_path: str) -> list:
    with open(tf_path) as f:
        source = f.read()

    prompt = UNGROUNDED_PROMPT.format(
        filename=os.path.basename(tf_path),
        terraform_source=source,
    )
    return call_gemini_json(prompt)


def main(tf_path: str):
    os.makedirs("results", exist_ok=True)
    findings = run_ungrounded_pass(tf_path)

    out_name = os.path.basename(tf_path).replace(".tf", "_baseline_findings.json")
    out_path = os.path.join("results", out_name)
    with open(out_path, "w") as f:
        json.dump(findings, f, indent=2)

    print(f"Ungrounded findings: {len(findings)}")
    print(f"Written to {out_path}")
    print(
        "\nNext: manually label each finding against corpus/ground_truth.json "
        "as true-positive or hallucinated, then compute:\n"
        "  hallucination_rate = hallucinated / total_findings"
    )


if __name__ == "__main__":
    main(sys.argv[1])
