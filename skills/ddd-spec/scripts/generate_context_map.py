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


def build_data(domains_dir):
    """Collect all valid domain dicts from domains_dir."""
    files = find_domain_files(domains_dir)
    domains = []
    for path in sorted(files):
        data = load_domain(path)
        if data is None:
            continue
        if not is_domain_file(data):
            continue
        # Attach source path for debugging (stripped from JSON output if undesired)
        data["_source"] = str(path)
        domains.append(data)
    return domains


def generate(domains_dir, output, template_path):
    """Build the context map HTML and write to output."""
    print(f"Scanning: {domains_dir}")
    domains = build_data(domains_dir)
    if not domains:
        print("No domain.yaml files found — nothing to generate.", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(domains)} domain(s): {[d.get('id','?') for d in domains]}")

    # Read template
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        print(f"Template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    # Inject data
    payload = json.dumps(domains, indent=2, ensure_ascii=False)
    html = template.replace("__RDOD_DATA_PLACEHOLDER__", payload)

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
