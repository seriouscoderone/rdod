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


KNOWN_URI_SCHEMES = {"domain", "kernel", "port", "types", "errors", "verification", "protocols", "external"}


def parse_typed_ref(ref):
    """Parse RDOD URIs per the formal grammar in uri-schemes.md.

    Returns (scheme, domain_path, fragment) where:
      - scheme: one of KNOWN_URI_SCHEMES, or None if not a recognized URI
      - domain_path: the domain identifier (or full path for port://)
      - fragment: the #fragment (type name, error name, etc.), or None

    Special case for port://: domain_path is extracted by stripping the
    last two segments (direction/port_name) from the path.
    """
    if not ref or "://" not in str(ref):
        return None, None, None
    ref = str(ref)
    scheme, rest = ref.split("://", 1)
    if scheme not in KNOWN_URI_SCHEMES:
        return None, None, None

    if "#" in rest:
        domain_path, fragment = rest.split("#", 1)
        # Strip variant suffix: "InceptionEvent/non-delegated" → "InceptionEvent"
        if "/" in fragment:
            fragment = fragment.split("/")[0]
    else:
        domain_path, fragment = rest, None

    # For port://, extract domain_path by stripping /direction/name
    if scheme == "port":
        parts = domain_path.split("/")
        if len(parts) >= 3:
            # port://domain/path/inbound/port-name → domain_path = domain/path
            for i, part in enumerate(parts):
                if part in ("inbound", "outbound") and i > 0:
                    domain_path = "/".join(parts[:i])
                    break

    return scheme, domain_path, fragment


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
        """Read terms from ubiquitous-language.yaml (sole source of truth)."""
        return [t for t in self.lang_data.get("terms", [])
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
        self.infos = []

    def error(self, rule, domain_id, message):
        self.errors.append({"rule": rule, "domain": domain_id, "message": message})

    def warn(self, rule, domain_id, message):
        self.warnings.append({"rule": rule, "domain": domain_id, "message": message})

    def info(self, rule, domain_id, message):
        self.infos.append({"rule": rule, "domain": domain_id, "message": message})

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

        # Check verification.yaml contract port_ref fields
        verif_path = Path(spec.dir) / "verification.yaml"
        if verif_path.exists():
            vdata = load_yaml(str(verif_path))
            if vdata:
                for contract in vdata.get("contracts", []):
                    if not isinstance(contract, dict):
                        continue
                    port_ref = contract.get("port_ref", "") or contract.get("port", "")
                    if not port_ref:
                        continue
                    port_domain_id = strip_prefix(port_ref.split("/inbound/")[0].split("/outbound/")[0])
                    if port_domain_id in specs:
                        target_ports = specs[port_domain_id].port_ids
                        if target_ports and port_ref not in target_ports:
                            result.warn("port-resolution", sid,
                                f"verification contract port_ref '{port_ref}' not found in {port_domain_id}/ports.yaml")

        # Check externals port:// refs
        for ext in spec.data.get("externals", []):
            if not isinstance(ext, dict):
                continue
            ext_ref = ext.get("ref", "")
            if not ext_ref or not str(ext_ref).startswith("port://"):
                continue
            port_ref = str(ext_ref)
            port_domain_id = strip_prefix(port_ref.split("/inbound/")[0].split("/outbound/")[0])
            if port_domain_id in specs:
                target_ports = specs[port_domain_id].port_ids
                if target_ports and port_ref not in target_ports:
                    ext_name = ext.get("name", ext.get("id", "?"))
                    result.warn("port-resolution", sid,
                        f"external '{ext_name}' ref '{port_ref}' not found in {port_domain_id}/ports.yaml")


def check_protocol_refs(specs, result):
    """Validate typed references in protocols.yaml steps (types://, errors://, verification://)."""
    for sid, spec in specs.items():
        proto_path = Path(spec.dir) / "protocols.yaml"
        if not proto_path.exists():
            continue
        pdata = load_yaml(str(proto_path))
        if not pdata:
            continue

        for proto in pdata.get("protocols", []):
            if not isinstance(proto, dict):
                continue
            pname = proto.get("name", "?")
            for step in proto.get("steps", []):
                if not isinstance(step, dict):
                    continue

                # Collect all typed refs from this step
                typed_refs = []

                # input.types[].ref
                inp = step.get("input")
                if isinstance(inp, dict):
                    for t in inp.get("types", []):
                        if isinstance(t, dict) and t.get("ref"):
                            typed_refs.append(t["ref"])

                # output.type
                out = step.get("output")
                if isinstance(out, dict) and out.get("type"):
                    typed_refs.append(out["type"])

                # on_failure[].ref
                for fail in step.get("on_failure", []):
                    if isinstance(fail, dict) and fail.get("ref"):
                        typed_refs.append(fail["ref"])

                # preconditions[].ref
                for pre in step.get("preconditions", []):
                    if isinstance(pre, dict) and pre.get("ref"):
                        typed_refs.append(pre["ref"])

                # Validate each typed ref
                for ref in typed_refs:
                    scheme, domain_path, item_name = parse_typed_ref(ref)
                    if not scheme or not domain_path:
                        continue

                    # Check domain exists
                    if domain_path not in specs:
                        result.warn("protocol-refs", sid,
                            f"protocol '{pname}' step {step.get('seq', '?')}: "
                            f"ref '{ref}' targets unknown domain '{domain_path}'")
                        continue

                    target = specs[domain_path]
                    target_dir = Path(target.dir)

                    # Validate by scheme
                    if scheme == "types" and item_name:
                        tpath = target_dir / "types.yaml"
                        if tpath.exists():
                            tdata = load_yaml(str(tpath))
                            if tdata:
                                type_names = {t.get("name", "") for t in tdata.get("types", []) if isinstance(t, dict)}
                                if item_name not in type_names:
                                    result.warn("protocol-refs", sid,
                                        f"protocol '{pname}': types ref '{ref}' — "
                                        f"'{item_name}' not found in {domain_path}/types.yaml")

                    elif scheme == "errors" and item_name:
                        epath = target_dir / "errors.yaml"
                        if epath.exists():
                            edata = load_yaml(str(epath))
                            if edata:
                                err_names = {e.get("name", "") for e in edata.get("errors", []) if isinstance(e, dict)}
                                if item_name not in err_names:
                                    result.warn("protocol-refs", sid,
                                        f"protocol '{pname}': errors ref '{ref}' — "
                                        f"'{item_name}' not found in {domain_path}/errors.yaml")

                    elif scheme == "verification" and item_name:
                        vpath = target_dir / "verification.yaml"
                        if vpath.exists():
                            vdata = load_yaml(str(vpath))
                            if vdata:
                                prop_names = set()
                                for p in vdata.get("properties", []):
                                    if isinstance(p, dict):
                                        prop_names.add(p.get("name", ""))
                                        prop_names.add(p.get("term", ""))
                                if item_name not in prop_names:
                                    result.warn("protocol-refs", sid,
                                        f"protocol '{pname}': verification ref '{ref}' — "
                                        f"'{item_name}' not found in {domain_path}/verification.yaml")


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

    # Rule: imported terms must exist in source domain's UL
    for sid, spec in specs.items():
        for imp in spec.imports:
            from_domain = strip_prefix(imp.get("from", ""))
            term = imp.get("term", "")
            if not from_domain or not term:
                continue

            if from_domain not in specs:
                result.error("import-resolution", sid,
                    f"imports '{term}' from '{from_domain}', but that domain does not exist")
                continue

            # Search the target domain and its parent chain for the term
            found_in = None
            search_chain = [from_domain]
            parent = from_domain
            while "/" in parent:
                parent = parent.rsplit("/", 1)[0]
                if parent in specs:
                    search_chain.append(parent)

            for candidate in search_chain:
                source = specs[candidate]
                if term in source.term_names:
                    found_in = candidate
                    break
                # Check if any term specializes to this name
                for t in source.terms:
                    if t.get("specializes") and t.get("term") == term:
                        found_in = candidate
                        break
                if found_in:
                    break

            if not found_in:
                result.error("import-resolution", sid,
                    f"imported term '{term}' not found in {from_domain} "
                    f"ubiquitous-language.yaml terms (checked: {', '.join(search_chain)})")
            elif found_in == from_domain:
                # Term found — check if it's published
                source = specs[from_domain]
                if source.published_terms and term not in source.published_terms:
                    result.warn("import-resolution", sid,
                        f"imports '{term}' from '{from_domain}', but it is not in published_language "
                        f"(importing a private concept)")


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

    # Find all domains referenced as kernels
    referenced_as_kernel = set()
    for sid, spec in specs.items():
        for ref in spec.kernels:
            referenced_as_kernel.add(strip_prefix(ref))

    for sid, spec in specs.items():
        if sid not in has_parent and not spec.clients:
            # This is a root domain — only warn if truly isolated
            if not spec.subdomains and not spec.adjacents and sid not in referenced_as_kernel:
                result.warn("orphan-check", sid,
                    "domain has no clients, no parent, no subdomains, no adjacents, and not referenced as kernel — isolated")


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


def check_validation_constraints(specs, result):
    """Validate constraint graph: depends_on refs resolve, no cycles."""
    for sid, spec in specs.items():
        vpath = Path(spec.dir) / "verification.yaml"
        if not vpath.exists():
            continue
        vdata = load_yaml(str(vpath))
        if not vdata:
            continue
        constraints = vdata.get("validation_constraints", [])
        if not constraints:
            continue

        # Build ID set
        ids = set()
        for c in constraints:
            if isinstance(c, dict) and c.get("id"):
                if c["id"] in ids:
                    result.warn("constraints", sid,
                        f"duplicate constraint id '{c['id']}'")
                ids.add(c["id"])

        # Validate depends_on refs
        graph = {}
        for c in constraints:
            if not isinstance(c, dict) or not c.get("id"):
                continue
            cid = c["id"]
            deps = c.get("depends_on", []) or []
            graph[cid] = []
            for dep in deps:
                if dep not in ids:
                    result.warn("constraints", sid,
                        f"constraint '{cid}' depends_on '{dep}' which does not exist")
                else:
                    graph[cid].append(dep)

        # Cycle detection via DFS
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {cid: WHITE for cid in graph}

        def has_cycle(node, path):
            color[node] = GRAY
            for dep in graph.get(node, []):
                if dep not in color:
                    continue
                if color[dep] == GRAY:
                    cycle_path = path + [node, dep]
                    result.error("constraints", sid,
                        f"cycle in validation_constraints: {' → '.join(cycle_path)}")
                    return True
                if color[dep] == WHITE and has_cycle(dep, path + [node]):
                    return True
            color[node] = BLACK
            return False

        for cid in graph:
            if color.get(cid) == WHITE:
                has_cycle(cid, [])


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


def _load_vocabulary_whitelist(domains_dir, cli_path=None):
    """Load vocabulary whitelist from spec root or CLI-specified path."""
    if cli_path:
        wl_path = Path(cli_path)
    else:
        wl_path = Path(domains_dir).parent / ".vocabulary-whitelist"
        if not wl_path.exists():
            wl_path = Path(domains_dir) / ".vocabulary-whitelist"
    if not wl_path.exists():
        return set()
    whitelist = set()
    try:
        for line in wl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                whitelist.add(line)
    except (IOError, OSError):
        pass
    return whitelist


# Module-level whitelist, set by validate() before rules run
_vocabulary_whitelist = set()


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
        if match in _vocabulary_whitelist:
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


def _load_json_schemas():
    """Load per-file JSON schemas from assets/schemas/. Returns {filename: schema_dict}."""
    schemas_dir = Path(__file__).parent / ".." / "assets" / "schemas"
    schemas = {}
    if not schemas_dir.exists():
        return schemas
    for schema_file in schemas_dir.glob("*.schema.json"):
        yaml_filename = schema_file.name.replace(".schema.json", "")
        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                schemas[yaml_filename] = json.load(f)
        except Exception:
            pass
    return schemas


def _validate_against_schema(data, schema, filename, sid, result):
    """Validate a YAML data dict against a JSON schema. Reports errors/warnings."""
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema)
        for error in validator.iter_errors(data):
            path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
            msg = error.message
            # additionalProperties violations are warnings (extra fields)
            if "Additional properties" in msg or "additionalProperties" in msg:
                result.warn("schema", sid, f"{filename} [{path}]: {msg}")
            else:
                result.error("schema", sid, f"{filename} [{path}]: {msg}")
    except ImportError:
        # jsonschema not installed — fall back to basic field checks
        _check_schema_basic(data, filename, sid, result)


def _check_schema_basic(data, filename, sid, result):
    """Basic field validation when jsonschema is not installed."""
    if filename == "domain.yaml":
        for field in ("id", "name", "description"):
            if not data.get(field):
                result.error("schema", sid, f"{filename}: missing required field '{field}'")


def check_schema_conformance(specs, result):
    """Validate YAML files against JSON schemas (additionalProperties: false)."""
    schemas = _load_json_schemas()

    for sid, spec in specs.items():
        domain_dir = Path(spec.dir)

        # Validate domain.yaml
        if "domain.yaml" in schemas:
            _validate_against_schema(spec.data, schemas["domain.yaml"], "domain.yaml", sid, result)

        # Validate ubiquitous-language.yaml
        if "ubiquitous-language.yaml" in schemas and spec.lang_data:
            _validate_against_schema(spec.lang_data, schemas["ubiquitous-language.yaml"],
                                     "ubiquitous-language.yaml", sid, result)

        # Validate ports.yaml
        if "ports.yaml" in schemas and spec.ports_data:
            _validate_against_schema(spec.ports_data, schemas["ports.yaml"],
                                     "ports.yaml", sid, result)

        # Validate optional companion files
        for fname in ["errors.yaml", "types.yaml", "protocols.yaml", "verification.yaml"]:
            fpath = domain_dir / fname
            if fpath.exists() and fname in schemas:
                fdata = load_yaml(str(fpath))
                if fdata:
                    _validate_against_schema(fdata, schemas[fname], fname, sid, result)


# ── Cross-Reference Rules ─────────────────────────────────────────────────────

PRIMITIVE_TYPES = {"string", "integer", "boolean", "bytes", "map", "float", "null", "any", "array", "list", "datetime"}


def _load_types_registry(specs):
    """Build {type_name: [domain_ids]} and {domain_id: {local_type_names}}."""
    global_types = {}
    local_types = {}
    for sid, spec in specs.items():
        tdata = load_yaml(str(Path(spec.dir) / "types.yaml"))
        if not tdata:
            local_types[sid] = set()
            continue
        names = set()
        for t in tdata.get("types", []):
            if isinstance(t, dict) and t.get("name"):
                names.add(t["name"])
                global_types.setdefault(t["name"], []).append(sid)
        local_types[sid] = names
    return global_types, local_types


def check_type_references(specs, result):
    """Cross-reference type names in types.yaml fields and ports.yaml contracts."""
    global_types, local_types = _load_types_registry(specs)

    for sid, spec in specs.items():
        tdata = load_yaml(str(Path(spec.dir) / "types.yaml"))
        if not tdata:
            continue
        for t in tdata.get("types", []):
            if not isinstance(t, dict):
                continue
            tname = t.get("name", "?")
            for variant in t.get("variants", []):
                if not isinstance(variant, dict):
                    continue
                for field in variant.get("fields", []):
                    if not isinstance(field, dict):
                        continue
                    ftype = field.get("type", "")
                    fname = field.get("name", "?")
                    if not ftype or ftype.lower() in PRIMITIVE_TYPES:
                        continue
                    if ftype.startswith("array[") or ftype.startswith("map["):
                        continue
                    if ftype.startswith("types://"):
                        # Standard URI syntax — validate target
                        ref_part = ftype[len("types://"):]
                        if "#" in ref_part:
                            domain, type_name = ref_part.split("#", 1)
                            if "/" in type_name:
                                type_name = type_name.split("/")[0]
                            if domain not in specs:
                                result.warn("type-ref", sid,
                                    f"types ref '{ftype}' in {tname}.{fname} — domain '{domain}' not found")
                            elif type_name and type_name not in local_types.get(domain, set()):
                                result.warn("type-ref", sid,
                                    f"types ref '{ftype}' in {tname}.{fname} — type '{type_name}' not in {domain}/types.yaml")
                    elif ftype.startswith("TypeRef:"):
                        # Non-standard syntax — validate target but also flag syntax
                        ref_part = ftype[len("TypeRef:"):]
                        if "#" in ref_part:
                            domain, type_name = ref_part.split("#", 1)
                            if domain not in specs:
                                result.warn("type-ref", sid,
                                    f"TypeRef '{ftype}' in {tname}.{fname} — domain '{domain}' not found")
                            elif type_name and type_name not in local_types.get(domain, set()):
                                result.warn("type-ref", sid,
                                    f"TypeRef '{ftype}' in {tname}.{fname} — type '{type_name}' not in {domain}/types.yaml")
                    else:
                        # Bare type name — must be local or globally defined
                        if ftype not in local_types.get(sid, set()) and ftype not in global_types:
                            result.warn("type-ref", sid,
                                f"type '{ftype}' used in {tname}.{fname} but not defined in any types.yaml")


def check_typeref_syntax(specs, result):
    """Flag non-standard TypeRef: syntax and bare cross-domain type refs."""
    _, local_types = _load_types_registry(specs)

    for sid, spec in specs.items():
        tdata = load_yaml(str(Path(spec.dir) / "types.yaml"))
        if not tdata:
            continue
        local = local_types.get(sid, set())
        for t in tdata.get("types", []):
            if not isinstance(t, dict):
                continue
            tname = t.get("name", "?")
            for variant in t.get("variants", []):
                if not isinstance(variant, dict):
                    continue
                for field in variant.get("fields", []):
                    if not isinstance(field, dict):
                        continue
                    ftype = field.get("type", "")
                    fname = field.get("name", "?")
                    if not ftype or ftype.lower() in PRIMITIVE_TYPES:
                        continue
                    if ftype.startswith("array[") or ftype.startswith("map[") or ftype.startswith("types://"):
                        continue
                    # Non-standard TypeRef: syntax → recommend types://
                    if ftype.startswith("TypeRef:"):
                        fixed = ftype.replace("TypeRef:", "types://")
                        result.warn("typeref-syntax", sid,
                            f"'{ftype}' in {tname}.{fname} uses non-standard 'TypeRef:' — use 'types://' instead: {fixed}")
                        continue
                    # Bare type name that's not local → needs types:// prefix
                    if ftype not in local:
                        result.warn("typeref-syntax", sid,
                            f"bare type '{ftype}' in {tname}.{fname} — use types://domain#Type for cross-domain refs")


def check_duplicate_errors(specs, result):
    """Flag same-name errors in parent/child domains."""
    error_registry = {}  # {error_name: [domain_ids]}
    for sid, spec in specs.items():
        edata = load_yaml(str(Path(spec.dir) / "errors.yaml"))
        if not edata:
            continue
        for err in edata.get("errors", []):
            if isinstance(err, dict) and err.get("name"):
                error_registry.setdefault(err["name"], []).append(sid)

    for name, domains in error_registry.items():
        if len(domains) < 2:
            continue
        for i, d1 in enumerate(domains):
            for d2 in domains[i+1:]:
                is_parent_child = d1.startswith(d2 + "/") or d2.startswith(d1 + "/")
                parent1 = d1.rsplit("/", 1)[0] if "/" in d1 else ""
                parent2 = d2.rsplit("/", 1)[0] if "/" in d2 else ""
                is_sibling = parent1 and parent1 == parent2
                if is_parent_child or is_sibling:
                    result.warn("duplicate-error", d1,
                        f"error '{name}' defined in both '{d1}' and '{d2}' — "
                        f"differentiate names or document scope distinction")


def check_integration_scenarios(specs, domains_dir, result):
    """Validate integration-scenarios.yaml at the spec root."""
    ipath = Path(domains_dir) / "integration-scenarios.yaml"
    if not ipath.exists():
        return
    idata = load_yaml(str(ipath))
    if not idata:
        return

    # Build protocol registry: {domain_id: {protocol_name}}
    proto_registry = {}
    for sid, spec in specs.items():
        ppath = Path(spec.dir) / "protocols.yaml"
        if not ppath.exists():
            continue
        pdata = load_yaml(str(ppath))
        if not pdata:
            continue
        names = set()
        for p in pdata.get("protocols", []):
            if isinstance(p, dict) and p.get("name"):
                names.add(p["name"])
        if names:
            proto_registry[sid] = names

    for scenario in idata.get("scenarios", []):
        if not isinstance(scenario, dict):
            continue
        sname = scenario.get("name", "?")

        # Validate protocol ref
        pref = scenario.get("protocol", "")
        if pref:
            scheme, domain_path, proto_name = parse_typed_ref(pref)
            if scheme == "protocols" and domain_path:
                if domain_path not in specs:
                    result.warn("integration-scenarios", sname,
                        f"protocol ref '{pref}' targets unknown domain '{domain_path}'")
                elif proto_name and domain_path in proto_registry:
                    if proto_name not in proto_registry[domain_path]:
                        result.warn("integration-scenarios", sname,
                            f"protocol ref '{pref}' — '{proto_name}' not found in {domain_path}/protocols.yaml")

        # Validate domain refs in assertions
        for assertion in scenario.get("end_state_assertions", []):
            if isinstance(assertion, dict) and assertion.get("domain"):
                dref = strip_prefix(assertion["domain"])
                if dref and dref not in specs:
                    result.warn("integration-scenarios", sname,
                        f"end_state assertion references unknown domain '{dref}'")

        # Validate domain refs in preconditions
        setup = scenario.get("setup", {})
        if isinstance(setup, dict):
            for pre in setup.get("preconditions", []):
                if isinstance(pre, dict) and pre.get("domain"):
                    dref = strip_prefix(pre["domain"])
                    if dref and dref not in specs:
                        result.warn("integration-scenarios", sname,
                            f"precondition references unknown domain '{dref}'")

        # Validate failure scenario domain refs
        for fail in scenario.get("failure_scenarios", []):
            if not isinstance(fail, dict):
                continue
            for state in fail.get("expected_state", []):
                if isinstance(state, dict) and state.get("domain"):
                    dref = strip_prefix(state["domain"])
                    if dref and dref not in specs:
                        result.warn("integration-scenarios", f"{sname}/{fail.get('name', '?')}",
                            f"failure state references unknown domain '{dref}'")


def check_recovery_target_refs(specs, result):
    """Cross-reference recovery_target fields against UL terms."""
    all_terms = set()
    for sid, spec in specs.items():
        for t in spec.terms:
            all_terms.add(t.get("term", ""))
            for syn in t.get("synonyms", []):
                if isinstance(syn, str):
                    all_terms.add(syn)

    for sid, spec in specs.items():
        edata = load_yaml(str(Path(spec.dir) / "errors.yaml"))
        if not edata:
            continue
        for err in edata.get("errors", []):
            if not isinstance(err, dict):
                continue
            target = err.get("recovery_target", "") or err.get("escrow_queue", "")
            if target and target not in all_terms:
                result.warn("recovery-target-ref", sid,
                    f"error '{err.get('name', '?')}' recovery_target '{target}' "
                    f"not defined as a UL term or synonym in any domain")


def check_contract_type_refs(specs, result):
    """Parse PascalCase type names from port contracts and verify against types.yaml + UL terms."""
    import re
    # PascalCase compound words (at least one lowercase→uppercase transition)
    PASCAL_ID = re.compile(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b')
    BUILTINS = {"Result", "Iterator", "NotFound", "NotApplicable", "AlreadyExists",
                "NotSupported", "InvalidInput"}

    # Load contract-types whitelist
    whitelist = set()
    for sid, spec in specs.items():
        wl_path = Path(spec.dir).parent / ".contract-types-whitelist"
        if wl_path.exists():
            try:
                for line in wl_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        whitelist.add(line)
            except (IOError, OSError):
                pass
            break  # one whitelist per spec root

    # Build global type, term, and error name registries
    all_type_names = set()
    all_term_names = set()
    all_error_names = set()
    for sid, spec in specs.items():
        tdata = load_yaml(str(Path(spec.dir) / "types.yaml"))
        if tdata:
            for t in tdata.get("types", []):
                if isinstance(t, dict) and t.get("name"):
                    all_type_names.add(t["name"])
        edata = load_yaml(str(Path(spec.dir) / "errors.yaml"))
        if edata:
            for e in edata.get("errors", []):
                if isinstance(e, dict) and e.get("name"):
                    all_error_names.add(e["name"])
        for t in spec.terms:
            all_term_names.add(t.get("term", ""))

    # Collect port-local type names across all ports
    all_port_local_types = set()
    port_local_by_domain = defaultdict(set)
    for sid, spec in specs.items():
        for port in spec.ports:
            local_types = port.get("types", {})
            if isinstance(local_types, dict):
                for tname in local_types:
                    all_port_local_types.add(tname)
                    port_local_by_domain[sid].add(tname)

    known = all_type_names | all_term_names | all_error_names | all_port_local_types | BUILTINS | whitelist

    for sid, spec in specs.items():
        for port in spec.ports:
            contract = port.get("contract", "")
            if not contract:
                continue
            identifiers = set(PASCAL_ID.findall(contract))
            for ident in identifiers:
                if ident not in known:
                    result.warn("contract-type-ref", sid,
                        f"port '{port.get('name', port.get('id', '?'))}' contract references "
                        f"type '{ident}' — not found in any types.yaml, errors.yaml, or UL terms")

    # Info: suggest moving port-local types to types.yaml
    for sid, local_names in port_local_by_domain.items():
        if local_names:
            result.info("port-local-types", sid,
                f"port(s) define types locally — consider moving {', '.join(sorted(local_names))} "
                f"to {sid}/types.yaml for discoverability")


# ── URI Resolution Rules ──────────────────────────────────────────────────────

def _collect_all_uris(data, path=""):
    """Recursively walk YAML data and collect all URI strings with their location."""
    uris = []
    if isinstance(data, str) and "://" in data:
        scheme = data.split("://")[0]
        if scheme in KNOWN_URI_SCHEMES:
            uris.append((data, path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            uris.extend(_collect_all_uris(item, f"{path}[{i}]"))
    elif isinstance(data, dict):
        for key, value in data.items():
            uris.extend(_collect_all_uris(value, f"{path}.{key}" if path else key))
    return uris


def _collect_domain_uris(spec):
    """Collect all URIs from every YAML file in a domain."""
    uris = _collect_all_uris(spec.data)
    if spec.lang_data:
        uris.extend(_collect_all_uris(spec.lang_data))
    if spec.ports_data:
        uris.extend(_collect_all_uris(spec.ports_data))
    for fname in ["errors.yaml", "types.yaml", "protocols.yaml", "verification.yaml"]:
        fdata = load_yaml(str(Path(spec.dir) / fname))
        if fdata:
            uris.extend(_collect_all_uris(fdata))
    return uris


def check_uri_resolution(specs, result):
    """Validate all URI scheme targets per the formal resolution table in uri-schemes.md."""
    # Build resolution registries
    type_registry = {}     # {domain_id: {type_names}}
    error_registry = {}    # {domain_id: {error_names}}
    protocol_registry = {} # {domain_id: {protocol_names}}
    verif_registry = {}    # {domain_id: {term/constraint names}}

    for sid, spec in specs.items():
        d = Path(spec.dir)
        tdata = load_yaml(str(d / "types.yaml"))
        type_registry[sid] = {t.get("name", "") for t in (tdata or {}).get("types", [])
                              if isinstance(t, dict) and t.get("name")}
        edata = load_yaml(str(d / "errors.yaml"))
        error_registry[sid] = {e.get("name", "") for e in (edata or {}).get("errors", [])
                               if isinstance(e, dict) and e.get("name")}
        pdata = load_yaml(str(d / "protocols.yaml"))
        protocol_registry[sid] = {p.get("name", "") for p in (pdata or {}).get("protocols", [])
                                  if isinstance(p, dict) and p.get("name")}
        vdata = load_yaml(str(d / "verification.yaml"))
        vnames = set()
        if vdata:
            for p in vdata.get("properties", []):
                if isinstance(p, dict):
                    vnames.add(p.get("term", ""))
                    vnames.add(p.get("name", ""))
            for c in vdata.get("validation_constraints", []):
                if isinstance(c, dict):
                    vnames.add(c.get("id", ""))
        vnames.discard("")
        verif_registry[sid] = vnames

    for sid, spec in specs.items():
        for uri, location in _collect_domain_uris(spec):
            scheme, domain_path, fragment = parse_typed_ref(uri)
            if not scheme or not domain_path:
                continue

            # external:// — abstract, no resolution
            if scheme == "external":
                continue

            # Step 1: domain directory must exist (all schemes except external)
            if domain_path not in specs:
                result.error("uri-resolution", sid,
                    f"{scheme}://{domain_path} at {location} — domain not found")
                continue

            target_dir = Path(specs[domain_path].dir)

            # Step 2+3: file and element resolution per scheme
            if scheme in ("domain", "kernel"):
                pass  # directory check above is sufficient

            elif scheme == "port":
                if not (target_dir / "ports.yaml").exists():
                    result.error("uri-resolution", sid,
                        f"{uri} at {location} — ports.yaml not found in {domain_path}/")
                else:
                    target_ports = specs[domain_path].port_ids
                    if target_ports and uri not in target_ports:
                        result.warn("uri-resolution", sid,
                            f"{uri} at {location} — port not found in {domain_path}/ports.yaml")

            elif scheme == "types":
                if not (target_dir / "types.yaml").exists():
                    result.warn("uri-resolution", sid,
                        f"{uri} at {location} — types.yaml not found in {domain_path}/")
                elif fragment and fragment not in type_registry.get(domain_path, set()):
                    result.warn("uri-resolution", sid,
                        f"{uri} at {location} — type '{fragment}' not in {domain_path}/types.yaml")

            elif scheme == "errors":
                if not (target_dir / "errors.yaml").exists():
                    result.warn("uri-resolution", sid,
                        f"{uri} at {location} — errors.yaml not found in {domain_path}/")
                elif fragment and fragment not in error_registry.get(domain_path, set()):
                    result.warn("uri-resolution", sid,
                        f"{uri} at {location} — error '{fragment}' not in {domain_path}/errors.yaml")

            elif scheme == "verification":
                if not (target_dir / "verification.yaml").exists():
                    result.warn("uri-resolution", sid,
                        f"{uri} at {location} — verification.yaml not found in {domain_path}/")
                elif fragment and fragment not in verif_registry.get(domain_path, set()):
                    result.warn("uri-resolution", sid,
                        f"{uri} at {location} — '{fragment}' not in {domain_path}/verification.yaml")

            elif scheme == "protocols":
                if not (target_dir / "protocols.yaml").exists():
                    result.warn("uri-resolution", sid,
                        f"{uri} at {location} — protocols.yaml not found in {domain_path}/")
                elif fragment and fragment not in protocol_registry.get(domain_path, set()):
                    result.warn("uri-resolution", sid,
                        f"{uri} at {location} — protocol '{fragment}' not in {domain_path}/protocols.yaml")


def check_scheme_consistency(specs, result):
    """Validate kernel:// only appears in kernels: sections. domain:// is valid everywhere."""
    # kernel:// is valid in: kernels[].ref, kernels[].source
    # kernel:// is invalid in: adjacents, from, specializes, domain_clients, subdomains
    KERNEL_VALID_CONTEXTS = {"kernels"}

    for sid, spec in specs.items():
        # Check domain.yaml sections for misplaced kernel:// refs
        for section in ["domain_clients", "subdomains", "adjacents"]:
            for item in spec.data.get(section, []):
                ref = ""
                if isinstance(item, str):
                    ref = item
                elif isinstance(item, dict):
                    ref = item.get("ref", "")
                if str(ref).startswith("kernel://"):
                    result.warn("scheme-consistency", sid,
                        f"kernel:// used in {section}: '{ref}' — "
                        f"kernel:// belongs in kernels: section, use domain:// here")

        # Check UL imports for misplaced kernel:// in from:
        for imp in spec.imports:
            from_ref = imp.get("from", "")
            if str(from_ref).startswith("kernel://"):
                result.warn("scheme-consistency", sid,
                    f"kernel:// used in imports from: '{from_ref}' — use domain:// for imports")

        # Check UL terms for misplaced kernel:// in specializes:
        for term in spec.terms:
            spec_ref = term.get("specializes", "")
            if str(spec_ref).startswith("kernel://"):
                result.warn("scheme-consistency", sid,
                    f"kernel:// used in specializes: '{spec_ref}' — use domain:// for specializations")


# ── YAML Structure Rules ──────────────────────────────────────────────────────

UL_SECTION_RULES = {
    "terms": lambda item: isinstance(item, dict) and "term" in item,
    "events": lambda item: isinstance(item, dict) and "name" in item,
    "rules": lambda item: isinstance(item, str),
    "imports": lambda item: isinstance(item, dict) and "term" in item and "from" in item,
}

CANONICAL_ORDER = {
    "ubiquitous-language.yaml": ["domain_ref", "imports", "terms", "events", "rules"],
    "domain.yaml": ["template_version", "id", "name", "description", "version", "intent",
                     "source_material", "published_language",
                     "domain_clients", "subdomains", "kernels", "adjacents",
                     "externals", "implementation_guidance", "issues", "tags"],
}

ALL_YAML_FILES = ["domain.yaml", "ubiquitous-language.yaml", "ports.yaml",
                  "verification.yaml", "errors.yaml", "types.yaml", "protocols.yaml"]


def check_section_item_types(specs, result):
    """Validate that items are in the correct YAML section."""
    for sid, spec in specs.items():
        if not spec.lang_data:
            continue
        for section, validator in UL_SECTION_RULES.items():
            items = spec.lang_data.get(section, [])
            if not items or not isinstance(items, list):
                continue
            for i, item in enumerate(items):
                if not validator(item):
                    if isinstance(item, dict) and "term" in item:
                        actual = "term"
                    elif isinstance(item, dict) and "name" in item:
                        actual = "event"
                    else:
                        actual = "unknown"
                    result.error("yaml-structure", sid,
                        f"item {i} in '{section}:' section appears to be a {actual}, "
                        f"not a valid {section} entry — likely appended after wrong section header")


def check_duplicate_yaml_keys(specs, result):
    """Detect duplicate top-level keys in YAML files."""
    for sid, spec in specs.items():
        for filename in ALL_YAML_FILES:
            filepath = Path(spec.dir) / filename
            if not filepath.exists():
                continue
            seen_keys = {}
            try:
                with open(filepath) as f:
                    for lineno, line in enumerate(f, 1):
                        stripped = line.rstrip()
                        if stripped and not stripped[0].isspace() and not stripped.startswith("#"):
                            key = stripped.split(":")[0].strip()
                            if key in seen_keys:
                                result.error("yaml-duplicate-key", sid,
                                    f"{filename} has duplicate top-level key '{key}' "
                                    f"at lines {seen_keys[key]} and {lineno} — "
                                    f"YAML silently uses the last occurrence")
                            seen_keys[key] = lineno
            except (IOError, OSError):
                pass


def check_section_ordering(specs, result):
    """Warn when YAML sections appear out of canonical order."""
    for sid, spec in specs.items():
        for filename, expected_order in CANONICAL_ORDER.items():
            filepath = Path(spec.dir) / filename
            if not filepath.exists():
                continue
            found_order = []
            try:
                with open(filepath) as f:
                    for line in f:
                        stripped = line.rstrip()
                        if stripped and not stripped[0].isspace() and not stripped.startswith("#") and ":" in stripped:
                            key = stripped.split(":")[0].strip()
                            if key in expected_order and key not in found_order:
                                found_order.append(key)
            except (IOError, OSError):
                continue

            expected_indices = [expected_order.index(k) for k in found_order if k in expected_order]
            if expected_indices != sorted(expected_indices):
                result.warn("yaml-ordering", sid,
                    f"{filename} sections out of canonical order: "
                    f"found {found_order}")


def check_term_count(specs, result):
    """Cross-check raw term count vs parsed term count in UL files."""
    for sid, spec in specs.items():
        filepath = Path(spec.dir) / "ubiquitous-language.yaml"
        if not filepath.exists():
            continue
        try:
            in_terms = False
            raw_count = 0
            with open(filepath) as f:
                for line in f:
                    stripped = line.rstrip()
                    # Detect top-level section headers (no leading whitespace)
                    if stripped and not stripped[0].isspace() and not stripped.startswith("#") and ":" in stripped:
                        key = stripped.split(":")[0].strip()
                        in_terms = (key == "terms")
                    if in_terms and line.strip().startswith("- term:"):
                        raw_count += 1
        except (IOError, OSError):
            continue

        parsed_count = len(spec.lang_data.get("terms", []))
        if raw_count > parsed_count:
            result.error("yaml-orphaned-terms", sid,
                f"ubiquitous-language.yaml has {raw_count} '- term:' lines "
                f"but YAML parsed only {parsed_count} terms — "
                f"{raw_count - parsed_count} terms are orphaned "
                f"(likely placed after events: or rules: section)")


def fix_yaml_structure(specs):
    """Auto-fix orphaned items and section ordering. Returns list of fixed files."""
    import yaml
    fixed = []
    for sid, spec in specs.items():
        filepath = Path(spec.dir) / "ubiquitous-language.yaml"
        if not filepath.exists():
            continue
        data = spec.lang_data
        if not data:
            continue
        changed = False

        # Move orphaned terms from events/rules to terms
        terms = list(data.get("terms", []))
        for section in ("events", "rules"):
            items = data.get(section, [])
            if not items or not isinstance(items, list):
                continue
            orphaned = [item for item in items if isinstance(item, dict) and "term" in item]
            if orphaned:
                terms.extend(orphaned)
                data[section] = [item for item in items if not (isinstance(item, dict) and "term" in item)]
                changed = True

        if changed:
            data["terms"] = terms

        # Rewrite in canonical order
        if changed:
            ordered = {}
            for key in CANONICAL_ORDER.get("ubiquitous-language.yaml", []):
                if key in data:
                    ordered[key] = data[key]
            # Preserve any extra keys not in canonical order
            for key in data:
                if key not in ordered:
                    ordered[key] = data[key]
            with open(filepath, "w") as f:
                yaml.dump(ordered, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            fixed.append(f"{sid}/ubiquitous-language.yaml")

    # Fix TypeRef: → types:// in types.yaml files
    for sid, spec in specs.items():
        tpath = Path(spec.dir) / "types.yaml"
        if not tpath.exists():
            continue
        try:
            content = tpath.read_text(encoding="utf-8")
        except (IOError, OSError):
            continue
        if "TypeRef:" in content:
            content = content.replace("TypeRef:", "types://")
            tpath.write_text(content, encoding="utf-8")
            fixed.append(f"{sid}/types.yaml")

    return fixed


# ── Depth Audit Rules ─────────────────────────────────────────────────────────

def check_source_material_coverage(specs, result):
    """Flag domains with rich source material but few UL terms — may have unexplored depth."""
    for sid, spec in specs.items():
        source_count = len([s for s in spec.data.get("source_material", [])
                           if isinstance(s, dict)])
        term_count = len(spec.terms)
        if source_count >= 2 and term_count < 5:
            result.info("depth-audit", sid,
                f"has {source_count} source materials but only {term_count} UL terms "
                f"— consider a spec-depth audit for hidden concepts")


def check_type_variant_completeness(specs, result):
    """Flag types with small enums on classifier fields — may have undiscovered variants."""
    for sid, spec in specs.items():
        tdata = load_yaml(str(Path(spec.dir) / "types.yaml"))
        if not tdata:
            continue
        for t in tdata.get("types", []):
            if not isinstance(t, dict):
                continue
            for variant in t.get("variants", []):
                if not isinstance(variant, dict):
                    continue
                for field in variant.get("fields", []):
                    if not isinstance(field, dict):
                        continue
                    constraints = field.get("constraints", {})
                    if not isinstance(constraints, dict):
                        continue
                    enum_values = constraints.get("enum", [])
                    if 1 <= len(enum_values) <= 2 and field.get("name", "") in (
                        "type", "role", "kind", "variant", "mode", "category", "form"
                    ):
                        result.info("depth-audit", sid,
                            f"type '{t.get('name', '?')}' field '{field['name']}' has only "
                            f"{len(enum_values)} enum values — verify against source material for completeness")


# ── Rule Registry ─────────────────────────────────────────────────────────────

RULE_CATEGORIES = {
    "references": [check_ref_resolution, check_protocol_refs],
    "relationships": [check_mirror_consistency],
    "cycles": [check_cycles],
    "terms": [check_published_language, check_term_uniqueness],
    "ports": [check_duplicate_ports],
    "verification": [check_verification_quality, check_validation_constraints],
    "files": [check_missing_files],
    "vocabulary": [check_implementation_vocabulary],
    "schema": [check_schema_conformance],
    "completeness": [check_completeness, check_orphans],
    "hierarchy": [check_folder_hierarchy],
    "cross-refs": [check_type_references, check_typeref_syntax, check_duplicate_errors, check_recovery_target_refs, check_integration_scenarios, check_contract_type_refs],
    "yaml-structure": [check_section_item_types, check_duplicate_yaml_keys, check_section_ordering, check_term_count],
    "depth-audit": [check_source_material_coverage, check_type_variant_completeness],
    "uri-resolution": [check_uri_resolution, check_scheme_consistency],
}

ALL_CATEGORIES = list(RULE_CATEGORIES.keys())


# ── Runner ────────────────────────────────────────────────────────────────────

def validate(domains_dir, strict=False, rules=None, vocabulary_whitelist_path=None):
    """Run validation checks. Returns (specs, ValidationResult).
    If rules is None, run all. Otherwise run only the specified categories."""
    global _vocabulary_whitelist
    _vocabulary_whitelist = _load_vocabulary_whitelist(domains_dir, vocabulary_whitelist_path)
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
                if check_fn in (check_folder_hierarchy, check_integration_scenarios):
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
    parser.add_argument("--fix", action="store_true",
        help="Auto-fix structural YAML issues (orphaned items, section ordering)")
    parser.add_argument("--vocabulary-whitelist",
        help="Path to vocabulary whitelist file (default: {spec_root}/.vocabulary-whitelist)")
    args = parser.parse_args()

    domains_dir = args.domains_dir
    rules = args.rules.split(",") if args.rules else None

    if rules:
        unknown = [r for r in rules if r not in RULE_CATEGORIES]
        if unknown:
            print(f"Unknown rule categories: {', '.join(unknown)}", file=sys.stderr)
            print(f"Available: {', '.join(ALL_CATEGORIES)}", file=sys.stderr)
            sys.exit(2)

    specs, result = validate(domains_dir, strict=args.strict, rules=rules,
                             vocabulary_whitelist_path=args.vocabulary_whitelist)

    if args.fix and specs:
        fixed = fix_yaml_structure(specs)
        if fixed:
            print(f"\nFixed {len(fixed)} file(s):", file=sys.stderr)
            for f in fixed:
                print(f"  {f}", file=sys.stderr)
            # Re-validate after fix
            specs, result = validate(domains_dir, strict=args.strict, rules=rules,
                             vocabulary_whitelist_path=args.vocabulary_whitelist)
    print(f"Validating: {domains_dir} ({len(specs)} domains, {len(rules) if rules else len(ALL_CATEGORIES)} rule categories)", file=sys.stderr)

    if args.json:
        output = {
            "domains": len(specs),
            "rules": rules or ALL_CATEGORIES,
            "errors": result.errors,
            "warnings": result.warnings,
            "infos": result.infos,
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

        if result.infos:
            print(f"\nINFO ({len(result.infos)}):")
            for i in result.infos:
                print(f"  [{i['rule']}] {i['domain']}: {i['message']}")

        total_issues = len(result.errors) + len(result.warnings)
        if total_issues == 0 and not result.infos:
            print(f"\n✓ All checks passed ({len(specs)} domains)")
        elif total_issues == 0:
            print(f"\n✓ {len(result.errors)} error(s), {len(result.warnings)} warning(s), {len(result.infos)} info(s)")
        else:
            print(f"\n{'✗' if result.errors else '⚠'} {len(result.errors)} error(s), {len(result.warnings)} warning(s), {len(result.infos)} info(s)")

    # Exit code
    if result.errors:
        sys.exit(1)
    elif args.strict and result.warnings:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
