"""
ast_graph_traverser.py
=======================

GateIaC (Project P16) — AST-based Dependency Graph Traverser.

Purpose
-------
Terraform `plan.json` files (produced by `terraform show -json plan.bin`)
describe entire enterprise workspaces as flat lists of hundreds of resources.
Feeding that whole blob to an LLM blows past prompt budgets (20,000+ tokens)
and buries genuine privilege-escalation chains under boilerplate (subnets,
route tables, CloudWatch alarms, etc).

This module parses the plan's resource graph, extracts only the connected
subgraphs that run from a public entrypoint (load balancer, public EC2
instance, unauthenticated Lambda URL, ...) to a sensitive sink (S3 bucket,
IAM policy, RDS/DynamoDB table, ...), and serializes each surviving path as a
compact HCL-like snippet suitable for direct LLM inspection.

Pipeline stage:
    plan.json --> build_resource_graph --> find_candidate_subgraphs
               --> export_subgraph_context --> [LLM policy engine]

Dependencies
------------
- networkx (pure-Python graph library, no native deps)
- stdlib only otherwise (json, re, os, dataclasses)

Author: GateIaC Engineering
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    import networkx as nx
except ImportError as exc:  # pragma: no cover - hard dependency, fail loudly
    raise ImportError(
        "GateIaC's ast_graph_traverser requires networkx. "
        "Install it with `pip install networkx`."
    ) from exc


# --------------------------------------------------------------------------- #
# Configuration: risk heuristics
# --------------------------------------------------------------------------- #

# Resource types treated as potential public/attacker-reachable entrypoints.
ENTRYPOINT_TYPES: Set[str] = {
    "aws_lb",
    "aws_alb",
    "aws_instance",
    "aws_lambda_function_url",
    "aws_api_gateway_rest_api",
    "aws_apigatewayv2_api",
    "aws_cloudfront_distribution",
    "aws_security_group",
    "aws_security_group_rule",
    "aws_ecs_service",
}

# Resource types treated as sensitive sinks (data stores / privilege objects).
SINK_TYPES: Set[str] = {
    "aws_s3_bucket",
    "aws_s3_bucket_policy",
    "aws_iam_role_policy",
    "aws_iam_policy",
    "aws_iam_role_policy_attachment",
    "aws_iam_role",
    "aws_db_instance",
    "aws_rds_cluster",
    "aws_dynamodb_table",
    "aws_secretsmanager_secret",
    "aws_kms_key",
    "aws_sqs_queue",
}

# High-degree infrastructure container / monitoring nodes that act as connectivity hubs.
# Pruning these during path finding prevents transitive explosion through VPC/Subnet backbones.
CONTAINER_NOISE_TYPES: Set[str] = {
    "aws_vpc",
    "aws_subnet",
    "aws_route_table",
    "aws_route_table_association",
    "aws_internet_gateway",
    "aws_nat_gateway",
    "aws_eip",
    "aws_cloudwatch_metric_alarm",
    "aws_flow_log",
    "aws_db_subnet_group",
    "aws_elasticache_subnet_group",
}

# Attribute keys that, when present with a "risky" value, mark a node as a
# *confirmed* (not merely candidate-typed) entrypoint or sink. Used to compute
# a risk_score and risk_tags on each node.
WILDCARD_CIDRS = {"0.0.0.0/0", "::/0"}

# When exporting subgraph context, only these attributes per resource type are
# kept (keeps token count low while preserving security-relevant signal).
# "*" is a fallback set applied to any type not explicitly listed.
EXPORT_ATTRS: Dict[str, List[str]] = {
    "aws_lb": ["internal", "load_balancer_type", "security_groups"],
    "aws_lb_listener": ["port", "protocol", "default_action"],
    "aws_lb_target_group": ["port", "protocol", "target_type"],
    "aws_instance": ["associate_public_ip_address", "iam_instance_profile", "vpc_security_group_ids"],
    "aws_security_group": ["ingress", "egress"],
    "aws_security_group_rule": ["type", "cidr_blocks", "from_port", "to_port"],
    "aws_ecs_service": ["task_definition", "desired_count", "network_configuration"],
    "aws_ecs_task_definition": ["execution_role_arn", "task_role_arn", "container_definitions"],
    "aws_iam_role": ["assume_role_policy"],
    "aws_iam_role_policy": ["policy"],
    "aws_iam_policy": ["policy"],
    "aws_iam_role_policy_attachment": ["policy_arn"],
    "aws_lambda_function": ["role", "environment"],
    "aws_lambda_function_url": ["authorization_type", "function_name"],
    "aws_s3_bucket": ["bucket", "acl"],
    "aws_s3_bucket_policy": ["policy"],
    "aws_dynamodb_table": ["name", "hash_key"],
    "aws_db_instance": ["publicly_accessible", "storage_encrypted"],
    "*": [],
}

DEFAULT_MAX_PATH_LENGTH = 8  # cutoff for all_simple_paths (nodes, not edges)
DEFAULT_MAX_ATTR_STR_LEN = 160  # truncate long attribute values on export


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #

@dataclass
class CandidateSubgraph:
    """A pruned, connected slice of the resource graph worth showing an LLM."""

    entrypoint: str
    sinks: List[str] = field(default_factory=list)
    nodes: Set[str] = field(default_factory=set)
    edges: List[Tuple[str, str]] = field(default_factory=list)
    paths: List[List[str]] = field(default_factory=list)
    risk_score: float = 0.0
    risk_tags: Set[str] = field(default_factory=set)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "entrypoint": self.entrypoint,
            "sinks": self.sinks,
            "nodes": sorted(self.nodes),
            "edges": sorted(self.edges),
            "paths": self.paths,
            "risk_score": round(self.risk_score, 2),
            "risk_tags": sorted(self.risk_tags),
        }


# --------------------------------------------------------------------------- #
# Step 1: Graph construction
# --------------------------------------------------------------------------- #

def _load_plan(plan_json_path: str) -> Dict[str, Any]:
    """Load and lightly validate a `terraform show -json` plan file."""
    if not os.path.isfile(plan_json_path):
        raise FileNotFoundError(f"Terraform plan JSON not found at: {plan_json_path}")

    with open(plan_json_path, "r", encoding="utf-8") as fh:
        try:
            plan_data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Could not parse '{plan_json_path}' as JSON. Was it produced with "
                f"`terraform show -json plan.bin > plan.json`?"
            ) from exc

    if "resource_changes" not in plan_data and "configuration" not in plan_data:
        raise ValueError(
            "Input does not look like a Terraform plan JSON: missing both "
            "'resource_changes' and 'configuration' top-level keys."
        )
    return plan_data


def _strip_module_prefix(address: str) -> str:
    """
    Normalize a reference expression into a bare resource address of the
    form 'type.name', stripping any trailing attribute path and leading
    'module.x.' / 'data.' qualifiers we don't model as graph nodes here.
    """
    parts = address.split(".")
    if parts[0] == "module" and len(parts) >= 4:
        base = ".".join(parts[:4])
        return base
    if parts[0] == "data" and len(parts) >= 3:
        return ".".join(parts[:3])
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return address


def _walk_module_resources(module: Dict[str, Any], prefix: str = "") -> Iterable[Tuple[str, Dict[str, Any]]]:
    """
    Recursively yield (address, resource_config) pairs from a
    `configuration.root_module`-shaped subtree, correctly namespacing
    resources that live inside child modules.
    """
    for res in module.get("resources", []) or []:
        addr = res.get("address", "")
        full_addr = f"{prefix}{addr}" if prefix else addr
        yield full_addr, res

    for call_name, call in (module.get("module_calls", {}) or {}).items():
        child = call.get("module", {})
        child_prefix = f"{prefix}module.{call_name}."
        yield from _walk_module_resources(child, prefix=child_prefix)


def _collect_references(expressions: Any) -> Set[str]:
    """
    Recursively descend a Terraform plan `expressions` block (which mixes
    dicts, lists, and leaf {"references": [...]} objects) and collect every
    resource address referenced anywhere within it.
    """
    refs: Set[str] = set()
    if isinstance(expressions, dict):
        if "references" in expressions and isinstance(expressions["references"], list):
            for r in expressions["references"]:
                if isinstance(r, str):
                    refs.add(_strip_module_prefix(r))
        for value in expressions.values():
            refs |= _collect_references(value)
    elif isinstance(expressions, list):
        for item in expressions:
            refs |= _collect_references(item)
    return refs


_ARN_OR_ID_ATTR_RE = re.compile(
    r"^(role|iam_instance_profile|security_groups?|vpc_security_group_ids|"
    r"target_group_arn|subnet_ids?|policy_arn|execution_role_arn|task_role_arn|"
    r"function_name|bucket|kms_key_id)$",
    re.IGNORECASE,
)


def _guess_references_from_after(
    after: Dict[str, Any], address_by_hint: Dict[str, str]
) -> Set[str]:
    found: Set[str] = set()
    if not isinstance(after, dict):
        return found

    for key, value in after.items():
        if not _ARN_OR_ID_ATTR_RE.match(key):
            continue
        candidates: List[Any] = value if isinstance(value, list) else [value]
        for cand in candidates:
            if not isinstance(cand, str) or not cand:
                continue
            tail = cand.rstrip("/").split("/")[-1]
            for hint in (cand, tail):
                if hint in address_by_hint:
                    found.add(address_by_hint[hint])
    return found


def build_resource_graph(plan_json_path: str) -> "nx.DiGraph":
    """
    Parse a Terraform `plan.json` and construct a directed dependency graph
    of its resources.
    """
    plan_data = _load_plan(plan_json_path)
    graph = nx.DiGraph()

    # 1. Seed nodes from resource_changes
    resource_changes = plan_data.get("resource_changes", []) or []
    after_by_address: Dict[str, Dict[str, Any]] = {}
    for rc in resource_changes:
        addr = rc.get("address")
        if not addr:
            continue
        change = rc.get("change", {}) or {}
        after = change.get("after") or {}
        actions = change.get("actions", []) or []
        if actions == ["delete"]:
            continue
        after_by_address[addr] = after
        graph.add_node(
            addr,
            type=rc.get("type", "unknown"),
            name=rc.get("name", addr),
            config=after,
            risk_tags=set(),
        )

    # 2. Merge in any resources present only in configuration
    root_module = (plan_data.get("configuration") or {}).get("root_module") or {}
    config_by_address: Dict[str, Dict[str, Any]] = {}
    for addr, res_cfg in _walk_module_resources(root_module):
        config_by_address[addr] = res_cfg
        if addr not in graph:
            graph.add_node(
                addr,
                type=res_cfg.get("type", "unknown"),
                name=res_cfg.get("name", addr),
                config=after_by_address.get(addr, {}),
                risk_tags=set(),
            )

    if graph.number_of_nodes() == 0:
        raise ValueError(
            "Parsed plan JSON successfully but found zero resources in "
            "'resource_changes' or 'configuration.root_module'."
        )

    # Build cheap lookup hints
    address_by_hint: Dict[str, str] = {}
    for addr in graph.nodes:
        short_name = addr.split(".")[-1]
        address_by_hint.setdefault(short_name, addr)
        cfg = graph.nodes[addr].get("config", {}) or {}
        for id_key in ("id", "arn", "name", "bucket"):
            v = cfg.get(id_key)
            if isinstance(v, str) and v:
                address_by_hint.setdefault(v, addr)
                address_by_hint.setdefault(v.rstrip("/").split("/")[-1], addr)

    # 3. Wire edges from expression references or heuristics
    for addr in list(graph.nodes):
        res_cfg = config_by_address.get(addr, {})
        expressions = res_cfg.get("expressions", {})
        refs = _collect_references(expressions) if expressions else set()

        if not refs:
            refs = _guess_references_from_after(graph.nodes[addr].get("config", {}), address_by_hint)

        for ref in refs:
            if ref == addr:
                continue
            if ref not in graph:
                continue
            graph.add_edge(addr, ref, relation="references")

    _annotate_risk_tags(graph)
    return graph


# --------------------------------------------------------------------------- #
# Step 1b: Risk heuristics (node tagging)
# --------------------------------------------------------------------------- #

def _has_wildcard_ingress(cfg: Dict[str, Any]) -> bool:
    def _cidrs_from_rule(rule: Dict[str, Any]) -> Set[str]:
        cidrs = set()
        for key in ("cidr_blocks", "ipv6_cidr_blocks"):
            v = rule.get(key)
            if isinstance(v, list):
                cidrs |= {c for c in v if isinstance(c, str)}
        return cidrs

    ingress = cfg.get("ingress")
    if isinstance(ingress, list):
        for rule in ingress:
            if isinstance(rule, dict) and _cidrs_from_rule(rule) & WILDCARD_CIDRS:
                return True
    if cfg.get("type") == "ingress" and _cidrs_from_rule(cfg):
        return True
    return False


def _annotate_risk_tags(graph: "nx.DiGraph") -> None:
    for addr, data in graph.nodes(data=True):
        rtype = data.get("type", "")
        cfg = data.get("config", {}) or {}
        tags: Set[str] = data.setdefault("risk_tags", set())

        if rtype in ("aws_lb", "aws_alb") and cfg.get("internal") is False:
            tags.add("public_load_balancer")

        if rtype == "aws_instance" and cfg.get("associate_public_ip_address") is True:
            tags.add("public_ec2_instance")

        if rtype in ("aws_security_group", "aws_security_group_rule") and _has_wildcard_ingress(cfg):
            tags.add("wildcard_ingress")

        if rtype == "aws_lambda_function_url" and str(cfg.get("authorization_type", "")).upper() == "NONE":
            tags.add("unauthenticated_invoke")

        if rtype == "aws_s3_bucket" and str(cfg.get("acl", "")).lower() in ("public-read", "public-read-write"):
            tags.add("public_bucket_acl")

        if rtype == "aws_db_instance" and cfg.get("publicly_accessible") is True:
            tags.add("publicly_accessible_db")

        if rtype in ("aws_iam_role_policy", "aws_iam_policy"):
            policy_doc = cfg.get("policy")
            if isinstance(policy_doc, str) and ('"Resource": "*"' in policy_doc or "'*'" in policy_doc):
                tags.add("wildcard_iam_resource")
            if isinstance(policy_doc, str) and '"Action": "*"' in policy_doc:
                tags.add("wildcard_iam_action")


# --------------------------------------------------------------------------- #
# Step 2: Candidate subgraph extraction
# --------------------------------------------------------------------------- #

def _is_entrypoint(graph: "nx.DiGraph", node: str) -> bool:
    data = graph.nodes[node]
    if data.get("type") in ENTRYPOINT_TYPES:
        return True
    return bool(data.get("risk_tags", set()) & {
        "public_load_balancer", "public_ec2_instance", "wildcard_ingress", "unauthenticated_invoke",
    })


def _is_sink(graph: "nx.DiGraph", node: str) -> bool:
    return graph.nodes[node].get("type") in SINK_TYPES


def _score_path(graph: "nx.DiGraph", path: List[str]) -> Tuple[float, Set[str]]:
    score = 0.0
    tags: Set[str] = set()
    tag_weight = {
        "public_load_balancer": 1.0,
        "public_ec2_instance": 1.5,
        "wildcard_ingress": 2.0,
        "unauthenticated_invoke": 2.5,
        "public_bucket_acl": 2.0,
        "publicly_accessible_db": 2.0,
        "wildcard_iam_resource": 2.5,
        "wildcard_iam_action": 2.5,
    }
    for node in path:
        node_tags = graph.nodes[node].get("risk_tags", set())
        tags |= node_tags
        for t in node_tags:
            score += tag_weight.get(t, 0.5)
    score += max(0.0, (DEFAULT_MAX_PATH_LENGTH - len(path)) * 0.1)
    return score, tags


def find_candidate_subgraphs(
    graph: "nx.DiGraph",
    max_path_length: int = DEFAULT_MAX_PATH_LENGTH,
    min_risk_score: float = 0.0,
) -> List[Dict[str, Any]]:
    if graph.number_of_nodes() == 0:
        return []

    entrypoints = [n for n in graph.nodes if _is_entrypoint(graph, n)]
    sinks = [n for n in graph.nodes if _is_sink(graph, n)]

    undirected = graph.to_undirected(as_view=False)
    # Remove high-degree container/monitoring hub nodes so paths follow direct security/privilege associations
    noise_nodes = [n for n in undirected.nodes if graph.nodes[n].get("type") in CONTAINER_NOISE_TYPES]
    undirected.remove_nodes_from(noise_nodes)

    max_paths_per_pair = 4

    candidates: List[CandidateSubgraph] = []

    for entry in entrypoints:
        merged = CandidateSubgraph(entrypoint=entry)
        reached_any_sink = False
        entry_component: Optional[Set[str]] = None

        for sink in sinks:
            if entry == sink:
                continue
            if entry not in undirected or sink not in undirected:
                continue

            if entry_component is None:
                entry_component = nx.node_connected_component(undirected, entry)
            if sink not in entry_component:
                continue

            try:
                path_iter = nx.all_simple_paths(
                    undirected, source=entry, target=sink, cutoff=max_path_length
                )
                paths = []
                for idx, path in enumerate(path_iter):
                    if idx >= max_paths_per_pair:
                        break
                    paths.append(path)
            except nx.NodeNotFound:
                continue

            for path in paths:
                reached_any_sink = True
                if sink not in merged.sinks:
                    merged.sinks.append(sink)
                merged.nodes.update(path)
                merged.paths.append(path)

                for a, b in zip(path[:-1], path[1:]):
                    if graph.has_edge(a, b):
                        merged.edges.append((a, b))
                    elif graph.has_edge(b, a):
                        merged.edges.append((b, a))

                path_score, path_tags = _score_path(graph, path)
                merged.risk_score += path_score
                merged.risk_tags |= path_tags

        if reached_any_sink and merged.risk_score >= min_risk_score:
            merged.edges = list(dict.fromkeys(merged.edges))
            candidates.append(merged)

    candidates.sort(key=lambda c: c.risk_score, reverse=True)

    maximal: List[CandidateSubgraph] = []
    for cand in candidates:
        if any(cand.nodes <= kept.nodes for kept in maximal):
            continue
        maximal.append(cand)

    return [c.as_dict() for c in maximal]


# --------------------------------------------------------------------------- #
# Step 3: Compact export for LLM prompting
# --------------------------------------------------------------------------- #

def _truncate(value: Any, max_len: int = DEFAULT_MAX_ATTR_STR_LEN) -> Any:
    if isinstance(value, str):
        return value if len(value) <= max_len else value[: max_len - 3] + "..."
    if isinstance(value, list):
        shortened = value[:6]
        rendered = [_truncate(v, max_len // 2) for v in shortened]
        if len(value) > 6:
            rendered.append(f"...(+{len(value) - 6} more)")
        return rendered
    if isinstance(value, dict):
        return {k: _truncate(v, max_len // 2) for k, v in list(value.items())[:8]}
    return value


def _pseudo_hcl_block(address: str, node_data: Dict[str, Any]) -> str:
    rtype = node_data.get("type", "unknown")
    name = node_data.get("name", address.split(".")[-1])
    cfg = node_data.get("config", {}) or {}
    keep_keys = EXPORT_ATTRS.get(rtype, EXPORT_ATTRS["*"])

    if keep_keys:
        shown = {k: cfg[k] for k in keep_keys if k in cfg}
    else:
        shown = {k: cfg[k] for k in list(cfg.keys())[:5]}

    lines = [f'resource "{rtype}" "{name}" {{']
    tags = node_data.get("risk_tags")
    if tags:
        lines.append(f"  # risk_tags: {', '.join(sorted(tags))}")
    if not shown:
        lines.append("  # (no security-relevant attributes captured)")
    for key, value in shown.items():
        rendered = _truncate(value)
        lines.append(f"  {key} = {json.dumps(rendered)}")
    lines.append("}")
    return "\n".join(lines)


def export_subgraph_context_from_graph(subgraph: Dict[str, Any], graph: "nx.DiGraph") -> str:
    nodes: List[str] = subgraph.get("nodes", [])
    edges: List[Tuple[str, str]] = [tuple(e) for e in subgraph.get("edges", [])]
    entrypoint = subgraph.get("entrypoint", "")
    sinks = subgraph.get("sinks", [])

    ordered: List[str] = []
    seen: Set[str] = set()
    for path in subgraph.get("paths", []) or [nodes]:
        for n in path:
            if n not in seen and n in graph:
                ordered.append(n)
                seen.add(n)
    for n in nodes:
        if n not in seen and n in graph:
            ordered.append(n)
            seen.add(n)

    lines: List[str] = []
    lines.append("# --- GateIaC candidate privilege-path subgraph ---")
    lines.append(f"# entrypoint: {entrypoint}")
    lines.append(f"# sink(s):    {', '.join(sinks) if sinks else '(none)'}")
    if subgraph.get("risk_tags"):
        lines.append(f"# risk_tags:  {', '.join(sorted(subgraph['risk_tags']))}")
    lines.append("#")
    lines.append("# dependency chain(s):")
    for path in subgraph.get("paths", []):
        lines.append("#   " + " -> ".join(path))
    lines.append("")

    for addr in ordered:
        node_data = graph.nodes[addr]
        lines.append(_pseudo_hcl_block(addr, node_data))
        lines.append("")

    lines.append("# --- edges (dependency direction: source references target) ---")
    for src, dst in edges:
        lines.append(f"# {src} --> {dst}")

    return "\n".join(lines).strip() + "\n"


def export_subgraph_context(subgraph: Dict[str, Any], graph_or_plan: Any = None) -> str:
    """Polymorphic helper supporting both graph and plan dicts."""
    if isinstance(graph_or_plan, nx.DiGraph):
        return export_subgraph_context_from_graph(subgraph, graph_or_plan)
    raise TypeError("export_subgraph_context requires an nx.DiGraph instance as second argument.")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
