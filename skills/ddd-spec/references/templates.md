# DDD Spec YAML Templates

Three templates per domain. Store as files in `rdod/spec/domains/<domain-name>/`.

All refs use URI-style strings for linkability: `domain://<id>`, `port://<domain-id>/<direction>/<name>`.

---

## domain.yaml — Main entry point

```yaml
# domain.yaml
template_version: "1.0"    # DDD-spec template format version — do not change
id: "<unique-id>"          # e.g., "video-editing" — globally unique, URI-friendly
name: "<human-readable>"   # e.g., "Video Editing"
description: "<what problem space this covers, scope, purpose>"
version: "<semver>"        # e.g., "0.1.0" — use "0.0.0-stub" for unfilled stubs

# Where this domain's specification came from
source_material:
  - type: "<user-input | document | domain-expert | llm-inferred>"
    reference: "<description or document name>"

# Core language — brief here; expand in ubiquitous-language.yaml
ubiquitous_language:
  - term: "<term>"
    definition: "<precise meaning in this domain>"
    invariants: ["<rule>"]  # e.g., "Timeline must contain at least one clip"

# Upstream: who uses me?
domain_clients:
  - ref: "domain://<client-id>"
    relationship: "<brief desc>"
    via_port: "port://<this-domain>/inbound/<port-name>"

# Downstream: what do I depend on / compose?
subdomains:
  - ref: "domain://<subdomain-id>"
    relationship: "<brief desc>"
    via_port: "port://<subdomain-id>/inbound/<port-name>"

kernels:                    # Off-the-shelf, adopted natively (no wrapping)
  - ref: "kernel://<id>"
    source: "<npm:pkg@ver | cargo:crate | pip:pkg>"
    relationship: "<why adopted natively>"

# Lateral: peer collaborators or cross-cutting concerns
adjacents:
  - ref: "domain://<adjacent-id>"
    relationship: "<context-map pattern, e.g. Partnership, ACL, Conformist>"
    via_port: "port://<adjacent-id>/inbound/<port-name>"
    is_cross_cutting: false  # true for logging, auth, observability, etc.

# Infra/IO: encapsulated external concerns
externals:
  - name: "<concern name>"           # e.g., "File Persistence"
    abstraction: "<Repository | Service | Adapter>"
    ref: "port://<this-domain>/outbound/<port-name>"
    implementation_notes: "<how adapters should implement this>"

# Implementation guidance — hints for future implementors (optional)
implementation_guidance:
  suggested_type: ""        # module | package | service | app | middleware
  language_affinity: ""     # "any" | "typescript" | "rust" | etc.
  notes: ""                 # free-form guidance for implementors

# Design issues: architectural concerns identified during specification
issues:
  - ref: "<affected-ref>"            # e.g., "kernel://color-library"
    category: "<see categories below>"
    severity: "<low|medium|high|critical>"
    description: "<what's wrong and how it compromises this domain's structure>"
    rationale: "<why this is a concern — reasoning, not code evidence>"
    recommendation: "<see recommendations below>"

tags: []
```

---

## Issue Categories

Same categories as RDOD — these describe architectural violations, not code smells. They apply equally to designed and implemented systems.

| Category | What it flags | Default recommendation |
|---|---|---|
| `kernel-pollution` | Kernel internals leaking into domain model beyond intended use | `wrap-with-acl` or `refactor-port` |
| `missing-port` | External dep used directly with no interface abstraction | `add-port` or `refactor-port` |
| `language-inconsistency` | Same term used differently across domains with no ACL | `wrap-with-acl` or `introduce-concept:<name>` |
| `wrong-classification` | Neighbor mislabeled (e.g., peer called a subdomain) | `reclassify` |
| `inverted-dependency` | Lower-level domain depends on a higher-level one | `refactor-port` or `split-subdomain` |
| `hierarchy-imbalance` | Over-nesting or under-nesting | `split-subdomain` or `merge-hierarchy` |
| `modeling-gap` | Missing concept, aggregate, or invariant the domain needs | `introduce-concept:<proposed-name>` |
| `other:<subtype>` | Non-architectural issue (e.g., `other:security`) | Varies |

### Issue prioritization

Severity alone does not determine fix order. Prioritize by **severity weighted by domain centrality**:

1. **Critical/high in core domains** — fix first. These compromise the load-bearing parts of the system.
2. **Critical/high in subdomains of core** — fix next. Damage propagates upward.
3. **Medium in core domains** — before high issues in peripheral domains.
4. **Any severity in peripheral/leaf domains** — fix last. Blast radius is small.

When the expansion loop surfaces many issues, use this ordering to sequence which domains to revisit first.

### Recommendation values

| Value | Meaning |
|---|---|
| `replace` | Swap out the offending dependency entirely |
| `wrap-with-acl` | Add an Anti-Corruption Layer to translate at the boundary |
| `add-port` | Define a new interface so the domain depends on an abstraction |
| `refactor-port` | Restructure an existing interface to fix the violation |
| `reclassify` | Move the neighbor to the correct category in domain.yaml |
| `split-subdomain` | Break an oversized domain or dependency into smaller parts |
| `merge-hierarchy` | Collapse unnecessary nesting |
| `introduce-concept:<name>` | Name and define a missing domain concept |

---

## issues.yaml — Overflow for large issue lists

When a domain's `issues` list exceeds ~10 entries, move them to a separate `issues.yaml` file and add `issues_ref: "issues://<domain-id>"` to `domain.yaml`. This keeps the main template readable.

```yaml
# issues.yaml
domain_ref: "<domain-id>"

issues:
  - ref: "<affected-ref>"
    category: "<see categories above>"
    severity: "<low|medium|high|critical>"
    description: "<what's wrong>"
    rationale: "<why this is a concern — reasoning, not code evidence>"
    recommendation: "<see recommendations above>"
```

The format is identical to the `issues` array in `domain.yaml` — just extracted into its own file. Note: uses `rationale` (not `evidence`) since ddd-spec operates on designs, not code.

---

## ubiquitous-language.yaml — Deep language detail

This file expands the brief `ubiquitous_language` entries in `domain.yaml`. Both files should stay in sync — every term here should appear in `domain.yaml` and vice versa. The `domain.yaml` carries the summary (term + definition + invariants); this file adds synonyms, examples, related terms, events, and rules.

```yaml
# ubiquitous-language.yaml
domain_ref: "<domain-id>"

terms:
  - term: "<term>"
    synonyms: []
    definition: "<precise definition>"
    invariants: ["<rule that must always hold for this term>"]
    examples: ["<code snippet or scenario>"]
    related_terms: ["<other term in this domain>"]

events:                     # Domain events emitted by this domain
  - name: "<EventName>"
    payload: "<field: type descriptions>"
    triggers: "<what causes this event>"

# Business rules and invariants that span multiple terms
rules:
  - "<cross-term business rule or invariant>"
```

---

## ports.yaml — Inbound and outbound interfaces

```yaml
# ports.yaml
domain_ref: "<domain-id>"

ports:
  - id: "port://<domain-id>/inbound/<name>"
    type: inbound             # Driving port — what clients call
    name: "<name>"
    contract: "<method/event signature>"
    protocol: "<method-call | REST | GraphQL | events | message-queue>"
    refs: ["domain://<client-id>"]   # who uses this port

  - id: "port://<domain-id>/outbound/<name>"
    type: outbound            # Driven port — what this domain calls out to
    name: "<name>"
    contract: "<interface signature>"
    protocol: "<method-call | events>"
    refs: ["domain://<subdomain-or-external-id>"]
```

---

## Reference Integrity Rules (for tooling)

- Every `domain://` ref must resolve to an `id:` in another `domain.yaml`
- Every `port://` ref must resolve to a port `id:` in the referenced domain's `ports.yaml`
- `kernel://` refs do not require a `domain.yaml`. In a pre-code spec, validate that the kernel is a real library (check package registries or note as "planned")
- Every `via_port:` must resolve to a port `id:` in the referenced domain's `ports.yaml`. For adjacents that communicate via events (no direct port call), omit `via_port` and document the event contract in the `relationship` field instead
- No cycles in subdomain graph (adjacents may be mutual)
- Each domain's `domain_clients` must be the mirror of some other domain's `subdomains` or `adjacents`

## Folder Convention

```
rdod/spec/domains/
  README.md                     # Overview, domain map, status table
  video-editing/
    domain.yaml
    ubiquitous-language.yaml
    ports.yaml
  video-editing/format-handling/
    domain.yaml
    ubiquitous-language.yaml
    ports.yaml
  social-media-platform/
    domain.yaml
    ...
```

Nesting folder structure mirrors the subdomain hierarchy. Adjacent domains are siblings, not nested.

**Folder-hierarchy consistency rule:** If domain B is listed in domain A's `subdomains`, then B's folder should be nested under A's folder (e.g., `domains/A/B/domain.yaml`). If B's folder is a sibling of A instead, either: (a) the folder is misplaced — move it, or (b) the relationship is actually adjacent, not subdomain — reclassify. Tooling can validate this by checking that every subdomain ref's `id` starts with the parent domain's `id` as a prefix (e.g., subdomain `video-editing/format-handling` under parent `video-editing`).

## Compatibility with RDOD

The template format is intentionally compatible with RDOD (Recursive Domain-Oriented Design). A project can:

1. Use **ddd-spec** to design the intended domain architecture (this skill)
2. Implement code based on the spec
3. Use **RDOD** to analyze the implementation and verify it matches the spec

The main differences from RDOD's templates:
- `implementation_guidance` replaces `code_locations` (no code paths yet)
- `rationale` replaces `evidence` in issues (no code to point at)
- `source_material` added for provenance tracking
