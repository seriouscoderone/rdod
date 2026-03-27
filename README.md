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
| **`verification.yaml`** | Formalized invariants, port contracts, state machines, validation constraint graphs |

**Spec root (cross-domain):**

| File | Purpose |
|------|---------|
| **`integration-scenarios.yaml`** | Cross-domain end-state assertions for each protocol |

All refs use URI-style strings: `domain://video-editing`, `port://video-editing/inbound/editing-api`, `kernel://color-lib`.

All refs use consistent URI schemes: `domain://`, `port://`, `types://`, `errors://`, `verification://`, `protocols://`.

Per-file JSON schemas in `assets/schemas/` enforce `additionalProperties: false` — extra fields are flagged by the linter. Requires `jsonschema` pip package (graceful fallback without it).

## Context Map Viewer

After producing domain files, generate a standalone HTML browser:

```bash
python skills/rdod/scripts/generate_context_map.py rdod/analysis/domains
# or
python skills/ddd-spec/scripts/generate_context_map.py rdod/spec/domains
```

Requires Python + PyYAML. Opens in any browser — no server needed.

Features:
- **Layered sidebar** grouped by architecture layer (Kernels, Domains, Services, Applications)
- **Full-text sidebar search** across all domain JSON fields
- **Info panel search** with match highlighting, prev/next navigation, and auto-expand of collapsed sections
- **Term count badges** showing vocabulary richness per domain
- **Interactive graph** with color-coded neighbor types and pattern labels (click to navigate)
- **Complete info panel** — every field from every spec file rendered: published language, imports, language with formal invariants, neighbors with patterns, ports with repository invariants, events, rules, errors with context, types with constraints/encoding, protocols with trigger/dependencies/failure paths/compensation, verification properties/contracts/state machines/constraint graphs, integration scenarios, issues, code locations, implementation guidance, source material
- **Hierarchy breadcrumb** (reflects sidebar tree, not navigation history) with separate back-button history
- **AJV schema validation** on page load (results in browser console)

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
| `terms` | Published language: single owner, import resolution (checks source UL + parent chain), no unauthorized redefinition |
| `ports` | No duplicate ports across parent-child hierarchy |
| `verification` | Flags vague invariants, attribute-testing expressions, validation constraint graph cycles |
| `files` | Missing companion files, empty templates |
| `vocabulary` | Implementation-specific terms leaking into domain definitions (supports `.vocabulary-whitelist`) |
| `schema` | JSON Schema validation with `additionalProperties: false` (8 per-file schemas) |
| `completeness` | Required fields, stub detection (respects domain intent) |
| `hierarchy` | Folder nesting matches subdomain declarations |
| `cross-refs` | Type references, TypeRef→types:// syntax, duplicate sibling errors, escrow queues, integration scenario refs, verification port_ref |
| `yaml-structure` | Orphaned items, duplicate keys, section ordering, term count cross-check |
| `depth-audit` | Flags domains with rich source material but thin UL (info severity) |

```bash
# Run specific categories
python validate_spec.py rdod/spec/domains --rules verification,terms

# Strict mode (warnings = errors)
python validate_spec.py rdod/spec/domains --strict

# Auto-fix orphaned YAML items, section ordering, and TypeRef→types:// migration
python validate_spec.py rdod/spec/domains --fix

# Vocabulary whitelist (skip known spec-level identifiers like .code, .raw)
python validate_spec.py rdod/spec/domains --vocabulary-whitelist .vocabulary-whitelist

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
| Validation pipelines | Constraint graphs (topological sort of depends_on DAGs) |

Add `verification.yaml` to formalize invariants as machine-executable expressions. Use `validation_constraints:` to express validation pipelines as declarative constraint DAGs — AIs can derive evaluation order, identify parallelizable branches, and compose constraints across domains.

An AI implementing from the spec gets both the blueprint AND the verification criteria.

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
