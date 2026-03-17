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
4. Surfaces architectural issues (inverted dependencies, kernel pollution, language inconsistencies)
5. Produces an interactive HTML context map

Output goes to `rdod/analysis/domains/`.

### ddd-spec (DDD Specification Generator)

Generates domain specifications through an iterative expansion loop:

1. Start from a seed: a description, domain documents, or requirements
2. Discover domain concepts, relationships, and boundaries
3. Fill domain.yaml files with language, invariants, ports, and neighbor relationships
4. Verify completeness and cross-references
5. Produces the same interactive HTML context map

Output goes to `rdod/spec/domains/`.

## Core Concepts

**Everything is a domain.** The terms "subdomain" and "domain client" are relative viewpoints — entering any subdomain makes it "the domain" with its own subdomains and clients.

**5 Neighbor Types:**

| Type | Relation | Nature |
|------|----------|--------|
| Client | Upstream | Depends on this domain |
| Subdomain | Downstream (owned) | This domain drives and composes it |
| Kernel | Adopted | External lib whose types become this domain's types |
| Adjacent | Lateral (peer) | Collaborator — neither side controls the other |
| External | Encapsulated | Infra/IO hidden behind a domain-owned interface |

**Context Map Patterns** for adjacent relationships: Partnership, Shared Kernel, Customer-Supplier, Conformist, ACL, OHS + Published Language, Separate Ways.

## Output Format

Three YAML files per domain:

- **`domain.yaml`** — Identity, ubiquitous language, neighbor relationships, issues
- **`ubiquitous-language.yaml`** — Expanded terms, events, cross-term rules
- **`ports.yaml`** — Inbound and outbound interfaces with contracts

All refs use URI-style strings: `domain://video-editing`, `port://video-editing/inbound/editing-api`, `kernel://color-lib`.

## Context Map Generator

After producing domain files, generate a standalone HTML browser:

```bash
python skills/rdod/scripts/generate_context_map.py rdod/analysis/domains
# or
python skills/ddd-spec/scripts/generate_context_map.py rdod/spec/domains
```

Requires Python + PyYAML. Opens in any browser — no server needed.

## License

MIT
