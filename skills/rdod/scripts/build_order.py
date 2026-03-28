#!/usr/bin/env python3
"""
build_order.py — Generate topologically sorted build-order from domain specs.

Reads domain.yaml files and produces a layered build order showing which
domains to implement first based on their dependency relationships.

Usage:
    python build_order.py <domains-dir>
    python build_order.py <domains-dir> --mermaid
    python build_order.py <domains-dir> --json

Dependencies: Python 3.10+ and PyYAML only.
"""
import sys
import json
import glob
import argparse
import yaml
from pathlib import Path
from collections import defaultdict


def load_yaml(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def strip_prefix(ref):
    if not ref:
        return ""
    ref = str(ref)
    if "://" in ref:
        return ref.split("://", 1)[1]
    return ref


def get_refs(items, key="ref"):
    if not items or not isinstance(items, list):
        return []
    refs = []
    for item in items:
        if isinstance(item, str):
            refs.append(strip_prefix(item))
        elif isinstance(item, dict):
            refs.append(strip_prefix(item.get(key, "")))
    return [r for r in refs if r]


ONE_WAY_PATTERNS = {"conformist", "customer", "supplier", "published", "anticorruption", "acl"}


def load_domains(domains_dir):
    """Load all domain.yaml files. Returns {id: data}."""
    pattern = str(Path(domains_dir) / "**" / "*.yaml")
    files = glob.glob(pattern, recursive=True)
    domains = {}
    for path in sorted(files):
        data = load_yaml(path)
        if not data or "id" not in data or "domain_clients" not in data:
            continue
        did = strip_prefix(data.get("id", ""))
        domains[did] = data
    return domains


def build_dependency_graph(domains):
    """Build directed dependency graph: {domain_id: set(dependency_ids)}.
    An edge A→B means A depends on B (B must be built before A)."""
    all_ids = set(domains.keys())
    deps = {did: set() for did in all_ids}

    # Build kernel set
    kernel_ids = set()
    for did, data in domains.items():
        for ref in get_refs(data.get("kernels", [])):
            kernel_ids.add(ref)

    # Partnerships (mutual deps → same layer, handled during layering)
    partnerships = set()  # frozenset pairs

    for did, data in domains.items():
        # Kernels: this domain depends on them
        for ref in get_refs(data.get("kernels", [])):
            if ref in all_ids:
                deps[did].add(ref)

        # Subdomains: parent depends on children (children build first)
        for ref in get_refs(data.get("subdomains", [])):
            if ref in all_ids:
                deps[did].add(ref)

        # Adjacents: depends on direction from pattern
        for adj in data.get("adjacents", []):
            if isinstance(adj, str):
                ref = strip_prefix(adj)
                pattern = ""
            else:
                ref = strip_prefix(adj.get("ref", ""))
                pattern = (adj.get("pattern", "") or adj.get("relationship", ""))
                pattern = pattern.lower().replace("-", " ").replace("_", " ")

            if ref not in all_ids:
                continue

            pattern_words = set(pattern.split())

            if "partnership" in pattern_words:
                partnerships.add(frozenset([did, ref]))
            elif pattern_words & ONE_WAY_PATTERNS:
                # Conformist/Customer-Supplier/Published Language: this domain depends on the other
                deps[did].add(ref)
            elif ref in kernel_ids:
                # Kernel consumption
                deps[did].add(ref)
            else:
                # Unspecified pattern — assume dependency
                deps[did].add(ref)

    # No propagation: children are layered from their OWN declared dependencies only.
    # Parent layer = max(child layers) + 1 — handled by the subdomain edge above.

    return deps, partnerships, kernel_ids


def compute_layers(deps, partnerships, kernel_ids):
    """Topological sort with layer assignment. Returns [(layer_num, [domain_ids])]."""
    all_ids = set(deps.keys())

    # Merge partnership pairs into equivalence groups (same layer)
    parent = {did: did for did in all_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for pair in partnerships:
        pair = list(pair)
        if len(pair) == 2 and pair[0] in all_ids and pair[1] in all_ids:
            union(pair[0], pair[1])

    # Group by equivalence class
    groups = defaultdict(set)
    for did in all_ids:
        groups[find(did)].add(did)

    # Build group-level dependency graph
    group_of = {did: find(did) for did in all_ids}
    group_deps = defaultdict(set)
    for did in all_ids:
        g = group_of[did]
        for dep in deps[did]:
            if dep in group_of:
                dg = group_of[dep]
                if dg != g:
                    group_deps[g].add(dg)

    # Longest-path layer assignment (ensures parent always > child layer)
    all_groups = set(groups.keys())
    layers = {}

    def get_layer(g, visited=None):
        if g in layers:
            return layers[g]
        if visited is None:
            visited = set()
        if g in visited:
            return 0  # cycle — break it
        visited.add(g)
        dep_layers = [get_layer(d, visited) for d in group_deps[g] if d in all_groups]
        layers[g] = (max(dep_layers) + 1) if dep_layers else 0
        return layers[g]

    for g in all_groups:
        get_layer(g)

    # Expand groups back to domains
    domain_layers = {}
    for g, members in groups.items():
        for did in members:
            domain_layers[did] = layers.get(g, 0)

    # Force leaf kernels (no deps) to layer 0
    for kid in kernel_ids:
        if kid in domain_layers and kid in deps and not deps[kid]:
            domain_layers[kid] = 0

    # Collect by layer
    by_layer = defaultdict(list)
    for did, layer in domain_layers.items():
        by_layer[layer].append(did)

    result = []
    for layer_num in sorted(by_layer.keys()):
        result.append((layer_num, sorted(by_layer[layer_num])))

    return result


def label_layer(layer_num, total_layers, kernel_ids, domains_in_layer):
    """Generate a descriptive label for a build layer."""
    if all(d in kernel_ids for d in domains_in_layer):
        return "kernels — no dependencies"
    if layer_num == 0:
        return "foundation — no dependencies"
    if layer_num == total_layers - 1:
        # Check if all are services/applications
        return "services + applications"
    return f"depends on layers 0–{layer_num - 1}"


def render_text(layers, kernel_ids):
    total_domains = sum(len(ids) for _, ids in layers)
    total_layers = len(layers)
    lines = [f"Build Order ({total_domains} domains, {total_layers} layers):", ""]

    for layer_num, domain_ids in layers:
        label = label_layer(layer_num, total_layers, kernel_ids, domain_ids)
        lines.append(f"Layer {layer_num} ({label}):")
        for did in domain_ids:
            lines.append(f"  {did}")
        lines.append("")

    return "\n".join(lines)


def render_mermaid(layers, deps):
    lines = ["graph TD"]

    # Define subgraphs per layer
    for layer_num, domain_ids in layers:
        lines.append(f"  subgraph Layer{layer_num}[\"Layer {layer_num}\"]")
        for did in domain_ids:
            safe = did.replace("/", "_").replace("-", "_")
            lines.append(f"    {safe}[\"{did}\"]")
        lines.append("  end")

    # Add dependency edges (only cross-layer to keep it readable)
    for did, dep_set in deps.items():
        safe_from = did.replace("/", "_").replace("-", "_")
        for dep in dep_set:
            if dep in deps:  # dep exists as a domain
                safe_to = dep.replace("/", "_").replace("-", "_")
                lines.append(f"  {safe_from} --> {safe_to}")

    return "\n".join(lines)


def render_json(layers, kernel_ids, deps):
    return json.dumps({
        "total_domains": sum(len(ids) for _, ids in layers),
        "total_layers": len(layers),
        "layers": [
            {
                "layer": layer_num,
                "label": label_layer(layer_num, len(layers), kernel_ids, domain_ids),
                "domains": domain_ids,
            }
            for layer_num, domain_ids in layers
        ],
    }, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Generate topologically sorted build-order from domain specs")
    parser.add_argument("domains_dir",
        help="Path to directory containing domain.yaml files")
    parser.add_argument("--mermaid", action="store_true",
        help="Output as mermaid diagram")
    parser.add_argument("--json", action="store_true",
        help="Output as JSON")
    args = parser.parse_args()

    domains = load_domains(args.domains_dir)
    if not domains:
        print(f"No domain.yaml files found in {args.domains_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(domains)} domains", file=sys.stderr)

    deps, partnerships, kernel_ids = build_dependency_graph(domains)
    layers = compute_layers(deps, partnerships, kernel_ids)

    if args.mermaid:
        print(render_mermaid(layers, deps))
    elif args.json:
        print(render_json(layers, kernel_ids, deps))
    else:
        print(render_text(layers, kernel_ids))


if __name__ == "__main__":
    main()
