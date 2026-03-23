#!/usr/bin/env python3
"""
generate_context_map.py — RDOD Context Map Generator

Reads a completed domains/ directory of domain.yaml files and produces
a standalone context-map.html browser.

Usage:
    python generate_context_map.py <domains-dir> [--output context-map.html] [--template path]
"""
import sys
import json
import glob
import argparse
import yaml
from pathlib import Path


def find_domain_files(domains_dir):
    """Glob domains_dir recursively for all .yaml files."""
    pattern = str(Path(domains_dir) / "**" / "*.yaml")
    return glob.glob(pattern, recursive=True)


def load_domain(path):
    """Load a YAML file and return the parsed dict, or None on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"  warning: could not parse {path}: {e}", file=sys.stderr)
        return None


def is_domain_file(data):
    """Return True if this YAML looks like a domain.yaml (has 'id' and 'domain_clients')."""
    if not isinstance(data, dict):
        return False
    return "id" in data and "domain_clients" in data


def enrich_domain(data, domain_dir):
    """Load companion files (ubiquitous-language.yaml, ports.yaml) and merge into domain data."""
    # Load ubiquitous-language.yaml for events, rules, and expanded term details
    lang_path = Path(domain_dir) / "ubiquitous-language.yaml"
    if lang_path.exists():
        lang_data = load_domain(str(lang_path))
        if lang_data and isinstance(lang_data, dict):
            data["_events"] = lang_data.get("events", [])
            data["_rules"] = lang_data.get("rules", [])
            data["_imports"] = lang_data.get("imports", [])

            # UL file is the authoritative source for terms.
            # If the UL file has terms, use them as primary (replacing domain.yaml inline terms).
            # Fall back to domain.yaml inline terms only if UL file has none.
            ul_terms = [t for t in lang_data.get("terms", [])
                        if isinstance(t, dict) and t.get("term")]
            if ul_terms:
                # UL file is authoritative — use its terms, merge any extra from domain.yaml
                inline_terms = {t["term"]: t for t in data.get("ubiquitous_language", [])
                                if isinstance(t, dict) and t.get("term")}
                for term in ul_terms:
                    # If domain.yaml has a brief entry, merge any fields it has that UL file lacks
                    if term["term"] in inline_terms:
                        brief = inline_terms[term["term"]]
                        for key in ("definition", "invariants"):
                            if key in brief and brief[key] and not term.get(key):
                                term[key] = brief[key]
                data["ubiquitous_language"] = ul_terms
            else:
                # No UL file terms — keep domain.yaml inline terms as-is
                pass

    # Load ports.yaml
    ports_path = Path(domain_dir) / "ports.yaml"
    if ports_path.exists():
        ports_data = load_domain(str(ports_path))
        if ports_data and isinstance(ports_data, dict):
            data["_ports"] = ports_data.get("ports", [])

    # Load verification.yaml
    verify_path = Path(domain_dir) / "verification.yaml"
    if verify_path.exists():
        verify_data = load_domain(str(verify_path))
        if verify_data and isinstance(verify_data, dict):
            data["_verification"] = {
                "properties": verify_data.get("properties", []),
                "contracts": verify_data.get("contracts", []),
                "state_machines": verify_data.get("state_machines", []),
            }

    # Load errors.yaml
    errors_path = Path(domain_dir) / "errors.yaml"
    if errors_path.exists():
        errors_data = load_domain(str(errors_path))
        if errors_data and isinstance(errors_data, dict):
            data["_errors"] = errors_data.get("errors", [])

    # Load types.yaml
    types_path = Path(domain_dir) / "types.yaml"
    if types_path.exists():
        types_data = load_domain(str(types_path))
        if types_data and isinstance(types_data, dict):
            data["_types"] = types_data.get("types", [])

    # Load protocols.yaml
    protocols_path = Path(domain_dir) / "protocols.yaml"
    if protocols_path.exists():
        protocols_data = load_domain(str(protocols_path))
        if protocols_data and isinstance(protocols_data, dict):
            data["_protocols"] = protocols_data.get("protocols", [])

    return data


def strip_prefix(ref):
    """Remove URI scheme prefix (e.g., 'domain://video-editing' → 'video-editing')."""
    if "://" in ref:
        return ref.split("://", 1)[1]
    return ref


def build_data(domains_dir):
    """Collect all valid domain dicts from domains_dir, enriched with companion files.
    Returns a dict keyed by stripped domain ID."""
    files = find_domain_files(domains_dir)
    domains = {}
    for path in sorted(files):
        data = load_domain(path)
        if data is None:
            continue
        if not is_domain_file(data):
            continue
        # Attach source path for debugging
        data["_source"] = str(path)
        # Enrich with companion files from the same directory
        domain_dir = str(Path(path).parent)
        enrich_domain(data, domain_dir)
        key = strip_prefix(data.get("id", ""))
        domains[key] = data
    return domains


def load_schema(schema_path):
    """Load the JSON schema file. Returns the schema dict or None."""
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"  note: schema not found at {schema_path}", file=sys.stderr)
        return None


def generate(domains_dir, output, template_path):
    """Build the context map HTML and write to output."""
    print(f"Scanning: {domains_dir}")
    domains = build_data(domains_dir)
    if not domains:
        print("No domain.yaml files found — nothing to generate.", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(domains)} domain(s): {list(domains.keys())}")

    # Load schema for embedding
    script_dir = Path(__file__).parent
    schema_path = str(script_dir / ".." / "assets" / "rdod-data.schema.json")
    schema = load_schema(schema_path)

    # Read template
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        print(f"Template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    # Inject data and schema
    payload = json.dumps(domains, indent=2, ensure_ascii=False)
    schema_payload = json.dumps(schema, ensure_ascii=False) if schema else "null"
    html = template.replace("__RDOD_DATA_PLACEHOLDER__", payload)
    html = html.replace("__RDOD_SCHEMA_PLACEHOLDER__", schema_payload)

    # Write output
    out_path = Path(output)
    out_path.write_text(html, encoding="utf-8")
    print(f"Written: {out_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="Generate RDOD context map HTML")
    parser.add_argument("domains_dir", help="Path to directory containing domain.yaml files")
    parser.add_argument("--output", default="context-map.html", help="Output HTML file (default: context-map.html)")
    parser.add_argument("--template", default=None, help="Path to template HTML (default: context-map-template.html next to this script)")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    template_path = args.template if args.template else str(script_dir / ".." / "assets" / "context-map-template.html")

    generate(args.domains_dir, args.output, template_path)


if __name__ == "__main__":
    main()
