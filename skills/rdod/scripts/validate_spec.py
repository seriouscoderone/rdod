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
    """If A lists B as a client, B should list A in subdomains or adjacents. Adjacents respect patterns."""
    # Build set of domain IDs that are consumed as kernels (one-way, no back-ref needed)
    kernel_domains = set()
    for sid, spec in specs.items():
        for ref in spec.kernels:
            # kernel refs may be kernel:// or domain://
            clean = strip_prefix(ref)
            kernel_domains.add(clean)

    for sid, spec in specs.items():
        # domain_clients: one-way by nature — upstream serves clients, doesn't enumerate them
        # Only check subdomains (parent→child requires child→parent back-ref)

        for ref in spec.subdomains:
            clean = strip_prefix(ref)
            if clean in specs:
                other = specs[clean]
                other_clients = [strip_prefix(r) for r in other.clients]
                if sid not in other_clients:
                    result.warn("relationships", sid,
                        f"lists '{clean}' as subdomain, but '{clean}' does not list '{sid}' as client")

        # Adjacents — respect pattern field for one-way relationships
        # Normalize: "Customer-Supplier" → "customer-supplier", "Published Language" → "published language"
        ONE_WAY_KEYWORDS = {"conformist", "customer", "supplier", "published", "anticorruption", "acl", "ohs"}
        for adj_item in spec.data.get("adjacents", []):
            if isinstance(adj_item, str):
                adj_ref = adj_item
                pattern = ""
            else:
                adj_ref = adj_item.get("ref", "")
                # Read pattern: field first, fall back to relationship: field
                pattern = (adj_item.get("pattern", "") or adj_item.get("relationship", ""))
                pattern = pattern.lower().replace("-", " ").replace("_", " ")

            clean = strip_prefix(adj_ref)
            if clean not in specs:
                continue

            # Skip bidirectional check for one-way patterns
            pattern_words = set(pattern.split())
            if pattern_words & ONE_WAY_KEYWORDS:
                continue

            # Skip if the other domain is consumed as a kernel by anyone
            if clean in kernel_domains:
                continue

            other = specs[clean]
            other_adjs = [strip_prefix(r) for r in other.adjacents]
            other_clients = [strip_prefix(r) for r in other.clients]
            if sid not in other_adjs and sid not in other_clients:
                result.warn("relationships", sid,
                    f"lists '{clean}' as adjacent, but '{clean}' does not list '{sid}' in adjacents or domain_clients")


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
        # Also check detailed UL terms from ubiquitous-language.yaml
        for t in spec.lang_data.get("terms", []):
            if isinstance(t, dict) and t.get("term") and t.get("specializes"):
                specialized_terms.add(t["term"])

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

        # Empty language — skip for intentionally thin domains
        intent = spec.data.get("intent", "")
        if not spec.terms and intent not in ("adapter", "facade", "thin"):
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


def check_duplicate_ports(specs, result):
    """No two ports in a parent-child hierarchy should have the same name and contract."""
    for sid, spec in specs.items():
        for ref in spec.subdomains:
            child_id = strip_prefix(ref)
            if child_id in specs:
                child = specs[child_id]
                parent_ports = {(p.get("name"), p.get("contract")) for p in spec.ports}
                for cp in child.ports:
                    key = (cp.get("name"), cp.get("contract"))
                    if key in parent_ports and key[0]:
                        result.warn("ports", sid,
                            f"port '{key[0]}' duplicated in child '{child_id}' with same contract — child should define, parent should reference via via_port")


def check_verification_quality(specs, result):
    """Flag vague verification properties and attribute-testing expressions."""
    import re
    # Only flag genuinely vague qualifiers — not strong prescriptive assertions
    # "properly handled" = vague. "MUST be rejected" = strong.
    VAGUE_PATTERNS = re.compile(
        r'\bproperly\b'
        r'|\bcorrectly\b'
        r'|\bhandled\b(?!\s+(by|via|through|as|in))'
        r'|\bprocessed\b(?!\s+(by|into|through|via|using|in|as))',
        re.IGNORECASE
    )

    def is_attribute_test(expression):
        """Check if a formal expression tests attributes instead of behavior."""
        # @given tests are behavioral (Hypothesis property-based testing) — skip entirely
        if '@given' in expression:
            return False
        # These patterns test attributes, not behavior
        return bool(re.search(r'\bhasattr\s*\(|\bisinstance\s*\(|(?<!\w)type\s*\(|__class__', expression))

    for sid, spec in specs.items():
        for term in spec.terms:
            for inv in term.get("invariants", []):
                text = inv if isinstance(inv, str) else (inv.get("text", "") if isinstance(inv, dict) else "")
                if text and VAGUE_PATTERNS.search(text):
                    match = VAGUE_PATTERNS.search(text)
                    result.warn("verification", sid,
                        f"term '{term['term']}' has vague invariant: '{text[:80]}'")

                # Check formal expressions
                if isinstance(inv, dict) and inv.get("formal"):
                    expr = inv["formal"].get("expression", "")
                    lang = inv["formal"].get("language", "")
                    if expr and lang != "pseudocode" and is_attribute_test(expr):
                        result.warn("verification", sid,
                            f"term '{term['term']}' formal expression tests attributes instead of behavior: '{expr[:80]}'")

        # Check verification.yaml properties too
        verify_path = Path(spec.dir) / "verification.yaml"
        if verify_path.exists():
            vdata = load_yaml(str(verify_path))
            if vdata:
                for prop in vdata.get("properties", []):
                    if isinstance(prop, dict):
                        inv_text = prop.get("invariant", "")
                        if inv_text and VAGUE_PATTERNS.search(inv_text):
                            result.warn("verification", sid,
                                f"verification property has vague language: '{inv_text[:80]}'")
                        formal = prop.get("formal", {})
                        if isinstance(formal, dict):
                            expr = formal.get("expression", "")
                            lang = formal.get("language", "")
                            if expr and lang != "pseudocode" and is_attribute_test(expr):
                                result.warn("verification", sid,
                                    f"verification expression tests attributes: '{expr[:80]}'")


def check_missing_files(specs, result):
    """Check for missing companion files and empty templates."""
    for sid, spec in specs.items():
        domain_dir = Path(spec.dir)

        # Required companion files
        if not (domain_dir / "ubiquitous-language.yaml").exists():
            result.warn("files", sid, "missing ubiquitous-language.yaml")
        if not (domain_dir / "ports.yaml").exists():
            result.warn("files", sid, "missing ports.yaml")

        # Check if optional files exist but are empty (just template headers)
        for fname in ["errors.yaml", "types.yaml", "protocols.yaml", "verification.yaml"]:
            fpath = domain_dir / fname
            if fpath.exists():
                fdata = load_yaml(str(fpath))
                if fdata:
                    # Check if all list fields are empty
                    list_fields = [v for v in fdata.values() if isinstance(v, list)]
                    if list_fields and all(len(lf) == 0 for lf in list_fields):
                        result.warn("files", sid,
                            f"{fname} exists but all sections are empty — remove or fill")

        # Check subdomains reference existing directories
        for ref in spec.subdomains:
            child_id = strip_prefix(ref)
            if child_id and child_id not in specs:
                # Check if directory exists but domain.yaml is missing
                possible_dir = domain_dir / child_id.split("/")[-1]
                if possible_dir.exists() and not (possible_dir / "domain.yaml").exists():
                    result.error("files", sid,
                        f"subdomain '{child_id}' directory exists but has no domain.yaml")


def check_implementation_vocabulary(specs, result):
    """Flag implementation-specific vocabulary leaking into domain definitions."""
    import re
    # Short dotted identifiers (likely LMDB subdatabase names)
    DOTTED_ID = re.compile(r'\.[a-z]{2,5}[es]?\b')
    # Test framework terms
    TEST_TERMS = re.compile(r'\b(pytest|unittest|assert\s+not\s+hasattr|#\[test\]|cargo\s+test)\b')
    # Exclusions for dotted identifiers
    METHOD_NAMES = {'.get', '.set', '.put', '.delete', '.post', '.list', '.find',
                    '.groups', '.items', '.keys', '.values', '.append', '.pop',
                    '.sort', '.split', '.join', '.strip', '.lower', '.upper'}
    RFC_PATHS = {'.well', '.well-known'}

    def is_impl_vocab(text, match):
        """Check if a dotted identifier is actually implementation vocabulary."""
        if match in METHOD_NAMES or match in RFC_PATHS:
            return False
        # Skip matches inside [.xxx in impl] bracket convention
        escaped = re.escape(match)
        if re.search(r'\[' + escaped + r'\s+in\s+\w+', text):
            return False
        return True

    for sid, spec in specs.items():
        # Check description
        desc = spec.data.get("description", "")
        if desc:
            matches = [m for m in DOTTED_ID.findall(desc) if is_impl_vocab(desc, m)]
            if matches:
                result.warn("vocabulary", sid,
                    f"description contains implementation identifiers: {', '.join(matches)}")

        # Check terms
        for term in spec.terms:
            definition = term.get("definition", "")
            if definition:
                matches = [m for m in DOTTED_ID.findall(definition) if is_impl_vocab(definition, m)]
                if matches:
                    result.warn("vocabulary", sid,
                        f"term '{term['term']}' definition contains implementation identifiers: {', '.join(matches)}")

            for inv in term.get("invariants", []):
                text = inv if isinstance(inv, str) else (inv.get("text", "") if isinstance(inv, dict) else "")
                if text:
                    matches = [m for m in DOTTED_ID.findall(text) if is_impl_vocab(text, m)]
                    if matches:
                        result.warn("vocabulary", sid,
                        f"term '{term['term']}' invariant contains implementation identifiers: {', '.join(matches)}")

                # Check formal expressions for test framework terms
                if isinstance(inv, dict) and inv.get("formal"):
                    expr = inv["formal"].get("expression", "")
                    if expr and TEST_TERMS.search(expr):
                        result.warn("vocabulary", sid,
                            f"term '{term['term']}' formal expression contains test framework terms")


def check_schema_conformance(specs, result):
    """Validate required fields per file type."""
    for sid, spec in specs.items():
        domain_dir = Path(spec.dir)

        # Validate ports.yaml entries
        for port in spec.ports:
            if not port.get("id"):
                result.error("schema", sid, f"port missing required field: id")
            if not port.get("type"):
                result.error("schema", sid, f"port '{port.get('name', '?')}' missing required field: type")
            if not port.get("name"):
                result.error("schema", sid, f"port '{port.get('id', '?')}' missing required field: name")

        # Validate UL terms
        for term in spec.terms:
            if not term.get("definition"):
                result.warn("schema", sid, f"term '{term['term']}' missing definition")

        # Validate errors.yaml
        errors_path = domain_dir / "errors.yaml"
        if errors_path.exists():
            edata = load_yaml(str(errors_path))
            if edata:
                for err in edata.get("errors", []):
                    if isinstance(err, dict):
                        for req in ["name", "description", "cause", "recovery", "severity"]:
                            if not err.get(req):
                                result.warn("schema", sid,
                                    f"errors.yaml: error '{err.get('name', '?')}' missing field: {req}")

        # Validate types.yaml
        types_path = domain_dir / "types.yaml"
        if types_path.exists():
            tdata = load_yaml(str(types_path))
            if tdata:
                for t in tdata.get("types", []):
                    if isinstance(t, dict):
                        if not t.get("name"):
                            result.error("schema", sid, "types.yaml: type missing required field: name")
                        if not t.get("variants") and not t.get("fields"):
                            result.warn("schema", sid,
                                f"types.yaml: type '{t.get('name', '?')}' has no variants or fields")

        # Validate protocols.yaml
        proto_path = domain_dir / "protocols.yaml"
        if proto_path.exists():
            pdata = load_yaml(str(proto_path))
            if pdata:
                for p in pdata.get("protocols", []):
                    if isinstance(p, dict):
                        if not p.get("name"):
                            result.error("schema", sid, "protocols.yaml: protocol missing required field: name")
                        if not p.get("steps"):
                            result.warn("schema", sid,
                                f"protocols.yaml: protocol '{p.get('name', '?')}' has no steps")
                        if not p.get("participants"):
                            result.warn("schema", sid,
                                f"protocols.yaml: protocol '{p.get('name', '?')}' has no participants")


# ── Rule Registry ─────────────────────────────────────────────────────────────

RULE_CATEGORIES = {
    "references": [check_ref_resolution],
    "relationships": [check_mirror_consistency],
    "cycles": [check_cycles],
    "terms": [check_published_language, check_term_uniqueness],
    "ports": [check_duplicate_ports],
    "verification": [check_verification_quality],
    "files": [check_missing_files],
    "vocabulary": [check_implementation_vocabulary],
    "schema": [check_schema_conformance],
    "completeness": [check_completeness, check_orphans],
    "hierarchy": [check_folder_hierarchy],
}

ALL_CATEGORIES = list(RULE_CATEGORIES.keys())


# ── Runner ────────────────────────────────────────────────────────────────────

def validate(domains_dir, strict=False, rules=None):
    """Run validation checks. Returns (specs, ValidationResult).
    If rules is None, run all. Otherwise run only the specified categories."""
    specs = load_spec(domains_dir)

    if not specs:
        r = ValidationResult()
        r.error("loading", "(none)", f"No domain.yaml files found in {domains_dir}")
        return specs, r

    result = ValidationResult()
    categories = rules if rules else ALL_CATEGORIES

    for cat in categories:
        if cat in RULE_CATEGORIES:
            for check_fn in RULE_CATEGORIES[cat]:
                if check_fn in (check_folder_hierarchy,):
                    check_fn(specs, domains_dir, result)
                else:
                    check_fn(specs, result)

    return specs, result


def main():
    parser = argparse.ArgumentParser(
        description="Validate RDOD/ddd-spec domain specification files")
    parser.add_argument("domains_dir",
        help="Path to directory containing domain.yaml files")
    parser.add_argument("--strict", action="store_true",
        help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true",
        help="Output results as JSON")
    parser.add_argument("--rules",
        help=f"Comma-separated rule categories to run (default: all). Available: {', '.join(ALL_CATEGORIES)}")
    args = parser.parse_args()

    domains_dir = args.domains_dir
    rules = args.rules.split(",") if args.rules else None

    if rules:
        unknown = [r for r in rules if r not in RULE_CATEGORIES]
        if unknown:
            print(f"Unknown rule categories: {', '.join(unknown)}", file=sys.stderr)
            print(f"Available: {', '.join(ALL_CATEGORIES)}", file=sys.stderr)
            sys.exit(2)

    specs, result = validate(domains_dir, strict=args.strict, rules=rules)
    print(f"Validating: {domains_dir} ({len(specs)} domains, {len(rules) if rules else len(ALL_CATEGORIES)} rule categories)", file=sys.stderr)

    if args.json:
        output = {
            "domains": len(specs),
            "rules": rules or ALL_CATEGORIES,
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
