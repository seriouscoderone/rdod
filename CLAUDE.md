# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repository Is

A dual-skill Claude Code plugin for domain-oriented design. Two skills, one shared domain.yaml format:

- **RDOD** (`skills/rdod/`) — Analyzes existing codebases to map domains, relationships, and architectural issues. Bottom-up, code-first.
- **ddd-spec** (`skills/ddd-spec/`) — Generates domain specifications from scratch through iterative LLM-driven expansion. Top-down, design-first.

Both produce compatible output. Running both on the same project gives you the delta between current architecture and ideal architecture.

## Architecture

```
.claude-plugin/
  plugin.json              # "domain-design-toolkit" — registers both skills
  marketplace.json         # Lists rdod and ddd-spec as separate marketplace entries

skills/
  rdod/                    # Analysis skill
    SKILL.md               # Core theory (neighbor types, decision rules, context-map patterns)
    references/
      crawling.md          # 11-step codebase analysis methodology
      templates.md         # YAML schema + reference integrity rules
      verification.md      # Domain-driven verification methodology
    assets/                # Blank YAML templates
      domain.yaml, ubiquitous-language.yaml, ports.yaml, verification.yaml
      issues.yaml, checklist.yaml
      context-map-template.html
      rdod-data.schema.json      # JSON schema for generated context map data
    scripts/
      generate_context_map.py    # Reads domain.yaml files → standalone HTML browser

  ddd-spec/                # Generation skill
    SKILL.md               # Same core theory + generative methodology overview
    references/
      expansion.md         # 10-step expansion loop (seed → expand → verify)
      templates.md         # Adapted YAML schema (implementation_guidance, rationale, source_material)
      verification.md      # Same verification methodology
    assets/                # Adapted blank templates (same set as rdod)
    scripts/
      generate_context_map.py    # Same generator, copied for independence

rdod.skill                 # Packaged zip of skills/rdod/
ddd-spec.skill             # Packaged zip of skills/ddd-spec/
```

## Key Concepts (shared by both skills)

- **Everything is a domain.** Subdomain/client are relative viewpoints, not fixed types.
- **5 Neighbor Types:** Client (upstream), Subdomain (downstream/owned), Kernel (adopted external), Adjacent (lateral peer), External (encapsulated infra).
- **The control test:** "Does this domain drive it?" → subdomain. "Do they negotiate as peers?" → adjacent.
- **Template format:** domain.yaml + ubiquitous-language.yaml + ports.yaml + verification.yaml (optional) per domain, with URI-style refs (`domain://`, `port://`, `kernel://`).
- **Verification bridge:** Domain invariants can be formalized as machine-executable expressions for property-based testing, SMT solvers, or symbolic execution.

## Default Output Directories

- RDOD writes to `rdod/analysis/domains/` (what the code IS)
- ddd-spec writes to `rdod/spec/domains/` (what it SHOULD be)

## Building Skill Packages

The `.skill` files are zip archives built from the `skills/` directory. Rebuild after any content changes:

```bash
cd skills
rm -f ../rdod.skill ../ddd-spec.skill
zip -r ../rdod.skill rdod/
zip -r ../ddd-spec.skill ddd-spec/
```

## Context Map Generator

Both skills include `generate_context_map.py` (requires PyYAML). It reads `domain.yaml` files and produces a standalone HTML browser with Cytoscape.js:

```bash
python skills/rdod/scripts/generate_context_map.py rdod/analysis/domains
python skills/ddd-spec/scripts/generate_context_map.py rdod/spec/domains
```

The script resolves its HTML template and JSON schema relative to its own location (`../assets/`). Each skill's copy is independent. The generator also loads companion files (`ubiquitous-language.yaml`, `ports.yaml`, `verification.yaml`) from each domain's directory and merges them into the JSON payload. AJV validates the data against the schema on page load in the browser.

## Template Differences Between Skills

| Field | RDOD | ddd-spec |
|-------|------|----------|
| Code traceability | `code_locations` (repo paths) | `implementation_guidance` (suggested type, language affinity) |
| Issue evidence | `evidence` (file paths, snippets) | `rationale` (reasoning, no code) |
| Provenance | N/A | `source_material` (user-input, document, llm-inferred) |
| Default version | `"0.0.1"` | `"0.0.0-stub"` |

Both use `template_version: "2.0"` (structured port contracts, required tier field).

## Editing Guidelines

- Both skills share core theory (neighbor types, decision rules, context-map patterns). Changes to these concepts must be applied to **both** `SKILL.md` files.
- Template format changes must be applied to **both** `references/templates.md` files and their corresponding `assets/domain.yaml` blank templates.
- After any content change, rebuild both `.skill` packages and commit them.
- The skills are self-contained — no cross-references between `skills/rdod/` and `skills/ddd-spec/`. Either can be installed independently.
