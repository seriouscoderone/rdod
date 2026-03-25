# Domain Design Toolkit

A Claude Code plugin with two skills for domain-oriented software design:

| Skill | Purpose | Approach |
|-------|---------|----------|
| **RDOD** | Analyze existing codebases | Bottom-up: crawl code, extract domains, map relationships, surface issues |
| **ddd-spec** | Generate domain specifications from scratch | Top-down: start from a seed, iteratively discover and specify domains |

Both skills produce the same `domain.yaml` format. Run both on a project to compare what the code IS versus what it SHOULD be.

## Install

```bash
claude install seriouscoderone/rdod
```

## What It Does

### RDOD (Recursive Domain-Oriented Design)

Analyzes an existing codebase and produces structured domain maps:

1. Inventories all modules and their dependencies
2. Classifies each as a domain with typed relationships (client, subdomain, kernel, adjacent, external)
3. Extracts ubiquitous language, invariants, and ports
4. Detects cross-term structural patterns (e.g., 7 escrow types sharing the same trigger/storage/timeout structure)
5. Surfaces architectural issues (inverted dependencies, kernel pollution, language inconsistencies)
6. Produces an interactive HTML context map

Output goes to `rdod/analysis/domains/`.

### ddd-spec (DDD Specification Generator)

Generates domain specifications through an iterative expansion loop:

1. Start from a seed: a description, domain documents, reference libraries, or requirements
2. Discover domain concepts, relationships, and boundaries
3. Fill domain.yaml files with language, invariants, ports, and neighbor relationships
4. Detect structural patterns across terms and extract them as reusable pattern definitions
5. Optionally formalize invariants for verification harnesses
6. Verify completeness and cross-references
7. Produces the same interactive HTML context map

Output goes to `rdod/spec/domains/`.

## Core Concepts

**Everything is a domain.** The terms "subdomain" and "domain client" are relative viewpoints — entering any subdomain makes it "the domain" with its own subdomains and clients. Aggregates are simply domains that compose sub-concepts.

**5 Neighbor Types:**

| Type | Relation | Nature |
|------|----------|--------|
| Client | Upstream | Depends on this domain |
| Subdomain | Downstream (owned) | This domain drives and composes it |
| Kernel | Adopted | External lib whose types become this domain's types |
| Adjacent | Lateral (peer) | Collaborator — neither side controls the other |
| External | Encapsulated | Infra/IO hidden behind a domain-owned interface |

**The control test:** "Can this domain tell the dependency what to do?" If yes → subdomain. If it's a negotiation between equals → adjacent.

**Context Map Patterns** for adjacent relationships: Partnership, Shared Kernel, Customer-Supplier, Conformist, ACL, OHS + Published Language, Separate Ways.

## Output Format

Up to 7 YAML files per domain (last 4 are optional):

| File | Purpose |
|------|---------|
| **`domain.yaml`** | Identity, published language, neighbor relationships, intent, issues |
| **`ubiquitous-language.yaml`** | All term definitions (sole source of truth), imports, specializations, events, rules |
| **`ports.yaml`** | Inbound and outbound interfaces with contracts |
| **`errors.yaml`** | Error taxonomy — every error with cause, recovery, severity, context |
| **`types.yaml`** | Formal data structures — variants, fields, constraints, encoding rules |
| **`protocols.yaml`** | Cross-domain orchestration — step sequences, failure paths, compensation |
| **`verification.yaml`** | Formalized invariants, port contracts, state machines |

All refs use URI-style strings: `domain://video-editing`, `port://video-editing/inbound/editing-api`, `kernel://color-lib`.

A JSON schema (`assets/rdod-data.schema.json`) defines the full structure of the generated data, validated via AJV in the browser.

## Context Map Viewer

After producing domain files, generate a standalone HTML browser:

```bash
python skills/rdod/scripts/generate_context_map.py rdod/analysis/domains
# or
python skills/ddd-spec/scripts/generate_context_map.py rdod/spec/domains
```

Requires Python + PyYAML. Opens in any browser — no server needed.

Features:
- **Hierarchical tree sidebar** built from subdomain ownership (collapsed by default, auto-expands on navigation)
- **Full-text search** across all domain fields (terms, invariants, descriptions, ports, issues)
- **Term count badges** showing vocabulary richness per domain
- **Interactive graph** with color-coded neighbor types (click to navigate)
- **Complete info panel** showing all template data: published language, imports, language with invariants, neighbors with relationships, ports, events, rules, errors, types, protocols, issues, code locations, implementation guidance, and source material
- **AJV schema validation** on page load (results in browser console)
- **Breadcrumb navigation** with back button

## Spec Validator

Deterministic linter for domain specs — catches structural issues without LLM involvement:

```bash
python skills/rdod/scripts/validate_spec.py rdod/analysis/domains
python skills/ddd-spec/scripts/validate_spec.py rdod/spec/domains
```

15 rule categories:

| Category | What it checks |
|---|---|
| `references` | Every domain://, port:// ref resolves |
| `relationships` | Mirror consistency, adjacents symmetry (respects conformist/kernel patterns) |
| `cycles` | No cycles in subdomain graph |
| `terms` | Published language: single owner, import required, no unauthorized redefinition |
| `ports` | No duplicate ports across parent-child hierarchy |
| `verification` | Flags vague invariants, attribute-testing expressions |
| `files` | Missing companion files, empty templates |
| `vocabulary` | Implementation-specific terms leaking into domain definitions |
| `schema` | Required fields per file type |
| `completeness` | Required fields, stub detection (respects domain intent) |
| `hierarchy` | Folder nesting matches subdomain declarations |
| `cross-refs` | Type references, TypeRef syntax, duplicate errors, escrow queue terms |
| `yaml-structure` | Orphaned items, duplicate keys, section ordering, term count cross-check |
| `depth-audit` | Flags domains with rich source material but thin UL (info severity) |

```bash
# Run specific categories
python validate_spec.py rdod/spec/domains --rules verification,terms

# Strict mode (warnings = errors)
python validate_spec.py rdod/spec/domains --strict

# Auto-fix orphaned YAML items and section ordering
python validate_spec.py rdod/spec/domains --fix

# CI-friendly JSON output
python validate_spec.py rdod/spec/domains --json
```

## Build Order Generator

Generate a topologically sorted implementation roadmap from domain dependencies:

```bash
python skills/rdod/scripts/build_order.py rdod/spec/domains
python skills/rdod/scripts/build_order.py rdod/spec/domains --mermaid   # mermaid diagram
python skills/rdod/scripts/build_order.py rdod/spec/domains --json      # structured JSON
```

Computes layers from kernels, subdomains, conformist/customer-supplier adjacents, and partnership groupings. Child subdomains inherit parent dependencies so leaf domains don't appear as false "no dependencies" starting points.

## Published Language Boundaries

Formal term ownership across domain boundaries:

- **`published_language`** in `domain.yaml` — declares terms this domain authoritatively owns
- **`imports`** in `ubiquitous-language.yaml` — declares terms imported from other domains
- **`specializes`** on terms — narrows a parent domain's term with additive invariants

The validator enforces single ownership, import requirements, and redefinition rules.

## Domain-Driven Verification (optional)

Domain invariants are the natural inputs to formal verification. The toolkit bridges domain specs to three verification techniques:

| Domain concept | Verification technique |
|---|---|
| Term invariants | Property-Based Testing (Hypothesis, fast-check) |
| Port contracts (pre/postconditions) | SMT Solvers (Z3, CrossHair) |
| Ordered behavior / state machines | Symbolic Execution (Dafny, KLEE) |

Add `verification.yaml` to formalize invariants as machine-executable expressions. An AI implementing from the spec gets both the blueprint AND the verification criteria.

See `references/verification.md` in either skill for the full methodology.

## Comparing Analysis vs Design

Run both skills on the same project:

```
rdod/
  analysis/domains/    ← RDOD output (what the code IS)
  spec/domains/        ← ddd-spec output (what it SHOULD be)
```

The delta between the two directories is your refactoring roadmap.

## License

MIT
