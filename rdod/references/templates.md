# RDOD YAML Templates

Three templates per domain. Store as files in `domains/<domain-name>/`.

All refs use URI-style strings for linkability: `domain://<id>`, `port://<domain-id>/<direction>/<name>`.

---

## domain.yaml — Main entry point

```yaml
# domain.yaml
id: "<unique-id>"          # e.g., "video-editing" — globally unique, URI-friendly
name: "<human-readable>"   # e.g., "Video Editing"
description: "<what problem space this covers, scope, purpose>"
version: "<semver>"        # e.g., "1.0.0"

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
    implementation_notes: "<how adapters implement this>"

# Issues (optional): architectural violations in this domain or its references
# Move to issues.yaml + add issues_ref: "issues://<id>" if list exceeds ~10 entries
issues:
  - ref: "<affected-ref>"            # e.g., "kernel://color-library"
    category: "<see categories below>"
    severity: "<low|medium|high|critical>"
    description: "<what's wrong and how it compromises this domain's structure>"
    evidence: "<concrete proof: file path, method name, snippet, or test failure>"
    recommendation: "<see recommendations below>"

# Code traceability
code_locations:
  - path: "<repo-path>"              # e.g., "src/video-editing/core"
    type: "<pure-domain-lib | service | middleware | app>"

tags: []
```

---

## Issue Categories (RDOD-native)

Use these to diagnose how a violation compromises domain structure, hierarchy, or navigation. Always prefer a specific category over `other`.

| Category | What it flags | Default recommendation |
|---|---|---|
| `kernel-pollution` | Kernel internals leaking into domain model beyond intended use | `wrap-with-acl` or `refactor-port` |
| `missing-port` | Infrastructure or external dep used directly in domain code with no interface | `add-port` or `refactor-port` |
| `language-inconsistency` | Same term used differently across domains with no ACL translating between them | `wrap-with-acl` or `introduce-concept:<name>` |
| `wrong-classification` | Neighbor mislabeled (e.g., wrapped lib called a kernel; peer called a subdomain) | `reclassify` |
| `inverted-dependency` | Lower-level domain imports from a higher-level one — creates a cycle | `refactor-port` or `split-subdomain` |
| `hierarchy-imbalance` | Over-nesting (unnecessary depth) or under-nesting (monolith needing splits) | `split-subdomain` or `merge-hierarchy` |
| `modeling-gap` | Missing concept, aggregate, or invariant that the domain needs but hasn't defined | `introduce-concept:<proposed-name>` |
| `other:<subtype>` | Non-architectural issue (e.g., `other:security`, `other:performance`) | Varies — tie back to RDOD impact where possible |

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
| `introduce-concept:<name>` | Name and define a missing domain concept, e.g. `introduce-concept:RenderPipeline` |

---

## ubiquitous-language.yaml — Deep language detail

```yaml
# ubiquitous-language.yaml
domain_ref: "<domain-id>"

terms:
  - term: "<term>"
    synonyms: []
    definition: "<precise definition>"
    examples: ["<code snippet or scenario>"]
    related_terms: ["<other term in this domain>"]

events:                     # Domain events emitted by this domain
  - name: "<EventName>"
    payload: "<field: type descriptions>"
    triggers: "<what causes this event>"

rules:
  - "<business rule or invariant>"
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

- Every `ref:` must resolve to an `id:` in another `domain.yaml`
- Every `via_port:` must resolve to a port `id:` in the referenced domain's `ports.yaml`
- No cycles in subdomain graph (adjacents may be mutual)
- Each domain's `domain_clients` must be the mirror of some other domain's `subdomains` or `adjacents`

## Folder Convention

```
domains/
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
