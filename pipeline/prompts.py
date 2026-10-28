"""
Prompt templates for Project P16.

GROUNDED_PROMPT is the hybrid-pipeline version: the model is given the policy
library text and MUST cite a policy_id + exact quoted fragment for every
finding, or the citation gate will drop it.

UNGROUNDED_PROMPT is the baseline: same task, same model, no citation
requirement. This is what you compare against to measure hallucination
reduction.

STANDARD_RAG_PROMPT is the ungated grounding mode (Mode 2): the model is given
the policy library and asked to cite rules naturally without forced verbatim quotes.
Used in the temperature drift benchmark to measure paraphrasing and hallucination
before gating.
"""

GROUNDED_PROMPT = """You are a cloud security reviewer looking for CONTEXTUAL,
multi-resource misconfigurations in Terraform code — the kind that static
scanners miss because no single resource looks wrong in isolation.

You are given:
1. The Terraform source file.
2. A policy library (JSON) of controls you may cite.

Rules:
- Only report a finding if you can cite a policy_id from the library below.
- For each finding, quote a short fragment (5-20 words) taken VERBATIM from
  that policy's "text" field. This fragment must actually appear in the
  policy text — do not paraphrase it.
- Do not repeat single-resource issues a pattern scanner would already catch
  (e.g. a bare public ACL, a bare open port) unless the violation depends on
  a relationship between multiple resources.
- Respond with ONLY a JSON array, no prose, no markdown fences. Each item:
  {{
    "resource": "<resource address(es) involved>",
    "issue": "<one sentence description>",
    "policy_id": "<id from the library>",
    "cited_fragment": "<verbatim fragment from that policy's text>"
  }}
- If you find nothing, respond with [].

POLICY LIBRARY:
{policy_library_json}

TERRAFORM FILE ({filename}):
{terraform_source}
"""

UNGROUNDED_PROMPT = """You are a cloud infrastructure compliance auditor reviewing Terraform code for architectural and cross-resource configuration issues.

Identify cross-resource misconfigurations where relationships between resources violate best practices (e.g. public access combined with excessive privilege). Do not repeat single-resource issues a static scanner would catch unless the issue depends on an interaction between resources.

Respond with ONLY a valid JSON array, no prose, no markdown fences. Each item format:
{{
  "resource": "<resource address(es) involved>",
  "issue": "<one sentence description>"
}}
If you find nothing, respond with [].

TERRAFORM FILE ({filename}):
{terraform_source}
"""

STANDARD_RAG_PROMPT = """You are a cloud infrastructure compliance auditor reviewing Terraform code.
You are given:
1. The Terraform source code.
2. A policy library (JSON) of security controls.

Identify cross-resource misconfigurations that violate any of the provided policies.
For each finding, cite the policy_id from the library and explain the issue.

Respond with ONLY a valid JSON array, no prose, no markdown fences:
[
  {{
    "resource": "<resource address(es) involved>",
    "issue": "<one sentence description of violation>",
    "policy_id": "<id from library>",
    "cited_fragment": "<text or explanation of the violated policy>"
  }}
]
If you find nothing, respond with [].

POLICY LIBRARY:
{policy_library_json}

TERRAFORM FILE ({filename}):
{terraform_source}
"""
