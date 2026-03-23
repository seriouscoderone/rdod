#!/usr/bin/env python3
"""
validate_spec.py — RDOD/ddd-spec Domain Specification Validator

Deterministically validates structural integrity of domain spec files.
Checks reference resolution, mirror consistency, cycle detection,
published language rules, folder hierarchy, and completeness.

Usage:
    python validate_spec.py <domains-dir> [--strict] [--json]

Exit codes:
    0 — all checks passed
    1 — errors found
    2 — warnings only (with --strict, warnings become errors)
"""
import sys
import json
import glob
import argparse
import yaml
from pathlib import Path
from collections import defaultdict


# ── Loading ───────────────────────────────────────────────────────────────────

def load_yaml(path):
    """Load a YAML file, return dict or None on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else None
    except Exception as e:
        return None


def strip_prefix(ref):
    """Remove URI scheme prefix (e.g., 'domain://video-editing' → 'video-editing')."""
    if not ref:
        return ref
    ref = str(ref)
    if "://" in ref:
        return ref.split("://", 1)[1]
    return ref


def get_refs(items, key="ref"):
    """Extract ref strings from a list of items (strings or dicts)."""
    if not items or not isinstance(items, list):
        return []
    refs = []
    for item in items:
        if isinstance(item, str):
            refs.append(item)
        elif isinstance(item, dict):
            r = item.get(key, item.get("ref", ""))
            if r:
                refs.append(r)
    return refs


# ── Spec Loader ───────────────────────────────────────────────────────────────

class DomainSpec:
    """Loaded domain spec with all companion files."""
    def __init__(self, domain_data, domain_path, lang_data=None, ports_data=None):
        self.data = domain_data
        self.path = domain_path
        self.dir = str(Path(domain_path).parent)
        self.id = strip_prefix(domain_data.get("id", ""))
        self.name = domain_data.get("name", self.id)
        self.version = domain_data.get("version", "")
        self.lang_data = lang_data or {}
        self.ports_data = ports_data or {}

    @property
    def clients(self):
        return get_refs(self.data.get("domain_clients", []))

    @property
    def subdomains(self):
        return get_refs(self.data.get("subdomains", []))

    @property
    def kernels(self):
        return get_refs(self.data.get("kernels", []))

    @property
    def adjacents(self):
        return get_refs(self.data.get("adjacents", []))

    @property
    def externals(self):
        return get_refs(self.data.get("externals", []), key="name")

    @property
    def terms(self):
        return [t for t in self.data.get("ubiquitous_language", [])
                if isinstance(t, dict) and t.get("term")]

    @property
    def term_names(self):
        return [t["term"] for t in self.terms]

    @property
    def published_language(self):
        return [p for p in self.data.get("published_language", [])
                if isinstance(p, dict) and p.get("term")]

    @property
    def published_terms(self):
        return [p["term"] for p in self.published_language]

    @property
    def imports(self):
        return [i for i in self.lang_data.get("imports", [])
                if isinstance(i, dict) and i.get("term")]

    @property
    def ports(self):
        return [p for p in self.ports_data.get("ports", [])
                if isinstance(p, dict) and p.get("id")]

    @property
    def port_ids(self):
        return [p["id"] for p in self.ports]


def load_spec(domains_dir):
    """Load all domain specs from a directory. Returns dict of id → DomainSpec."""
    pattern = str(Path(domains_dir) / "**" / "*.yaml")
    files = glob.glob(pattern, recursive=True)
    specs = {}

    for path in sorted(files):
        data = load_yaml(path)
        if not data or "id" not in data or "domain_clients" not in data:
            continue

        domain_dir = str(Path(path).parent)

        # Load companions
        lang_path = Path(domain_dir) / "ubiquitous-language.yaml"
        lang_data = load_yaml(str(lang_path)) if lang_path.exists() else {}

        ports_path = Path(domain_dir) / "ports.yaml"
        ports_data = load_yaml(str(ports_path)) if ports_path.exists() else {}

        spec = DomainSpec(data, path, lang_data or {}, ports_data or {})
        specs[spec.id] = spec

    return specs


# ── Validation Rules ──────────────────────────────────────────────────────────

class ValidationResult:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, rule, domain_id, message):
        self.errors.append({"rule": rule, "domain": domain_id, "message": message})

    def warn(self, rule, domain_id, message):
        self.warnings.append({"rule": rule, "domain": domain_id, "message": message})

    @property
    def ok(self):
        return len(self.errors) == 0


def check_ref_resolution(specs, result):
    """Every domain:// ref must resolve to a known domain id."""
    for sid, spec in specs.items():
        for ref in spec.clients + spec.subdomains + spec.adjacents:
            clean = strip_prefix(ref)
            if clean and clean not in specs:
                result.error("ref-resolution", sid,
                    f"domain ref '{ref}' does not resolve to any domain.yaml")

        # Check via_port refs
        for section in ["domain_clients", "subdomains", "adjacents"]:
            for item in spec.data.get(section, []):
                if isinstance(item, dict) and item.get("via_port"):
                    port_ref = item["via_port"]
                    port_domain_id = strip_prefix(port_ref.split("/inbound/")[0].split("/outbound/")[0])
                    if port_domain_id in specs:
                        target_ports = specs[port_domain_id].port_ids
                        if target_ports and port_ref not in target_ports:
                            result.warn("port-resolution", sid,
                                f"via_port '{port_ref}' not found in {port_domain_id}/ports.yaml")


def check_mirror_consistency(specs, result):
    """If A lists B as a client, B should list A in subdomains or adjacents."""
    for sid, spec in specs.items():
        for ref in spec.clients:
            clean = strip_prefix(ref)
            if clean in specs:
                other = specs[clean]
                other_subs = [strip_prefix(r) for r in other.subdomains]
                other_adjs = [strip_prefix(r) for r in other.adjacents]
                if sid not in other_subs and sid not in other_adjs:
                    result.warn("mirror-check", sid,
                        f"lists '{clean}' as client, but '{clean}' does not list '{sid}' in subdomains or adjacents")

        for ref in spec.subdomains:
            clean = strip_prefix(ref)
            if clean in specs:
                other = specs[clean]
                other_clients = [strip_prefix(r) for r in other.clients]
                if sid not in other_clients:
                    result.warn("mirror-check", sid,
                        f"lists '{clean}' as subdomain, but '{clean}' does not list '{sid}' as client")


def check_cycles(specs, result):
    """No cycles in the subdomain graph."""
    # Build adjacency list (parent → children via subdomains)
    graph = {}
    for sid, spec in specs.items():
        graph[sid] = [strip_prefix(r) for r in spec.subdomains if strip_prefix(r) in specs]

    # DFS cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {sid: WHITE for sid in specs}
    path = []

    def dfs(node):
        color[node] = GRAY
        path.append(node)
        for child in graph.get(node, []):
            if color.get(child) == GRAY:
                cycle_start = path.index(child)
                cycle = path[cycle_start:] + [child]
                result.error("cycle-detection", node,
                    f"subdomain cycle detected: {' → '.join(cycle)}")
                return
            if color.get(child) == WHITE:
                dfs(child)
        path.pop()
        color[node] = BLACK

    for sid in specs:
        if color[sid] == WHITE:
            dfs(sid)


def check_published_language(specs, result):
    """Published language rules: single owner, import required, no unauthorized redefinition."""
    # Build term → publisher mapping
    publishers = {}  # term → [domain_ids]
    for sid, spec in specs.items():
        for term in spec.published_terms:
            if term not in publishers:
                publishers[term] = []
            publishers[term].append(sid)

    # Rule: single owner
    for term, owners in publishers.items():
        if len(owners) > 1:
            result.error("published-single-owner", owners[0],
                f"term '{term}' published by multiple domains: {', '.join(owners)}")

    # Rule: import required + no unauthorized redefinition
    for sid, spec in specs.items():
        imported_terms = {i["term"] for i in spec.imports}
        specialized_terms = {t["term"] for t in spec.terms if t.get("specializes")}

        for term_name in spec.term_names:
            # Check if this term is published by another domain
            if term_name in publishers:
                owner_ids = publishers[term_name]
                if sid not in owner_ids:
                    # This domain defines a term published elsewhere
                    if term_name not in imported_terms and term_name not in specialized_terms:
                        result.error("published-no-redefinition", sid,
                            f"term '{term_name}' is published by {owner_ids[0]} but redefined locally without import or specializes")

    # Rule: import source exists
    for sid, spec in specs.items():
        for imp in spec.imports:
            from_domain = strip_prefix(imp.get("from", ""))
            term = imp.get("term", "")
            if from_domain and from_domain in specs:
                source = specs[from_domain]
                if term and term not in source.published_terms and term not in source.term_names:
                    result.warn("import-source-exists", sid,
                        f"imports '{term}' from '{from_domain}', but '{from_domain}' does not define or publish it")
            elif from_domain and from_domain not in specs:
                result.error("import-source-exists", sid,
                    f"imports '{term}' from '{from_domain}', but that domain does not exist")


def check_folder_hierarchy(specs, domains_dir, result):
    """Folder nesting should match subdomain declarations."""
    domains_dir = str(Path(domains_dir).resolve())
    for sid, spec in specs.items():
        for ref in spec.subdomains:
            child_id = strip_prefix(ref)
            if child_id in specs:
                # Check if child's ID starts with parent's ID
                if not child_id.startswith(sid + "/"):
                    result.warn("folder-hierarchy", sid,
                        f"subdomain '{child_id}' ID does not start with parent prefix '{sid}/' — folder nesting may not match hierarchy")


def check_completeness(specs, result):
    """Required fields present, stub detection."""
    for sid, spec in specs.items():
        if not spec.data.get("id"):
            result.error("completeness", sid, "missing required field: id")
        if not spec.data.get("name"):
            result.warn("completeness", sid, "missing field: name")
        if not spec.data.get("description"):
            result.warn("completeness", sid, "missing field: description")

        # Stub detection
        if spec.version == "0.0.0-stub":
            result.warn("stub-detection", sid, "domain is still a stub (version: 0.0.0-stub)")

        # Empty language
        if not spec.terms:
            result.warn("completeness", sid, "no ubiquitous language terms defined")


def check_term_uniqueness(specs, result):
    """No duplicate term names within a single domain."""
    for sid, spec in specs.items():
        seen = {}
        for t in spec.terms:
            name = t["term"]
            if name in seen:
                result.error("term-uniqueness", sid,
                    f"duplicate term '{name}' defined in ubiquitous_language")
            seen[name] = True


def check_orphans(specs, result):
    """Domains with no clients, no parent subdomain, and not a root should be investigated."""
    # Find all domains that are someone's subdomain
    has_parent = set()
    for sid, spec in specs.items():
        for ref in spec.subdomains:
            has_parent.add(strip_prefix(ref))

    for sid, spec in specs.items():
        if sid not in has_parent and not spec.clients:
            # This is a root domain — only warn if it also has no subdomains (isolated)
            if not spec.subdomains and not spec.adjacents:
                result.warn("orphan-check", sid,
                    "domain has no clients, no parent, no subdomains, and no adjacents — isolated")


# ── Runner ────────────────────────────────────────────────────────────────────

def validate(domains_dir, strict=False):
    """Run all validation checks. Returns ValidationResult."""
    specs = load_spec(domains_dir)

    if not specs:
        r = ValidationResult()
        r.error("loading", "(none)", f"No domain.yaml files found in {domains_dir}")
        return r

    result = ValidationResult()

    check_ref_resolution(specs, result)
    check_mirror_consistency(specs, result)
    check_cycles(specs, result)
    check_published_language(specs, result)
    check_folder_hierarchy(specs, domains_dir, result)
    check_completeness(specs, result)
    check_term_uniqueness(specs, result)
    check_orphans(specs, result)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Validate RDOD/ddd-spec domain specification files")
    parser.add_argument("domains_dir",
        help="Path to directory containing domain.yaml files")
    parser.add_argument("--strict", action="store_true",
        help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true",
        help="Output results as JSON")
    args = parser.parse_args()

    domains_dir = args.domains_dir
    specs = load_spec(domains_dir)
    print(f"Validating: {domains_dir} ({len(specs)} domains)", file=sys.stderr)

    result = validate(domains_dir, strict=args.strict)

    if args.json:
        output = {
            "domains": len(specs),
            "errors": result.errors,
            "warnings": result.warnings,
            "passed": result.ok if not args.strict else (result.ok and len(result.warnings) == 0),
        }
        print(json.dumps(output, indent=2))
    else:
        if result.errors:
            print(f"\nERRORS ({len(result.errors)}):")
            for e in result.errors:
                print(f"  [{e['rule']}] {e['domain']}: {e['message']}")

        if result.warnings:
            print(f"\nWARNINGS ({len(result.warnings)}):")
            for w in result.warnings:
                print(f"  [{w['rule']}] {w['domain']}: {w['message']}")

        total_issues = len(result.errors) + len(result.warnings)
        if total_issues == 0:
            print(f"\n✓ All checks passed ({len(specs)} domains)")
        else:
            print(f"\n{'✗' if result.errors else '⚠'} {len(result.errors)} error(s), {len(result.warnings)} warning(s)")

    # Exit code
    if result.errors:
        sys.exit(1)
    elif args.strict and result.warnings:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
