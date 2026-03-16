# RDOD YAML Templates

Three templates per domain. Store as files in `domains/<domain-name>/`.

All refs use URI-style strings for linkability: `domain://<id>`, `port://<domain-id>/<direction>/<name>`.

---

## domain.yaml — Main entry point

```yaml
# domain.yaml
template_version: "1.0"    # RDOD template format version — do not change
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
    type: "<module | package | service | app | middleware>"
    # module    — directory/namespace within a larger codebase
    # package   — standalone publishable library (crate, npm package, pip package)
    # service   — runs as its own process/deployment
    # app       — end-user application or CLI
    # middleware — intermediary layer (HTTP middleware, message handler)

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

### Issue prioritization

Severity alone does not determine fix order. Prioritize by **severity weighted by domain centrality**:

1. **Critical/high in core domains** — fix first. These compromise the load-bearing parts of the system.
2. **Critical/high in subdomains of core** — fix next. Damage propagates upward.
3. **Medium in core domains** — before high issues in peripheral domains.
4. **Any severity in peripheral/leaf domains** — fix last. Blast radius is small.

When a crawl surfaces many issues, use this ordering to sequence remediation. An issue's `ref` field identifies which domain it affects; check that domain's position in the hierarchy to determine centrality.

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

## issues.yaml — Overflow for large issue lists

When a domain's `issues` list exceeds ~10 entries, move them to a separate `issues.yaml` file and add `issues_ref: "issues://<domain-id>"` to `domain.yaml`. This keeps the main template readable.

```yaml
# issues.yaml
domain_ref: "<domain-id>"

issues:
  - ref: "<affected-ref>"
    category: "<see categories below>"
    severity: "<low|medium|high|critical>"
    description: "<what's wrong>"
    evidence: "<file path, method name, snippet>"
    recommendation: "<see recommendations below>"
```

The format is identical to the `issues` array in `domain.yaml` — just extracted into its own file.

---

## ubiquitous-language.yaml — Deep language detail

This file expands the brief `ubiquitous_language` entries in `domain.yaml`. Both files should stay in sync — every term here should appear in `domain.yaml` and vice versa. The `domain.yaml` carries the summary (term + definition + invariants); this file adds synonyms, examples, related terms, events, and cross-term rules.

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

## Multi-Repo Support

When a system spans multiple repositories (e.g., microservices), the domain graph crosses repo boundaries. Handle this as follows:

- **One `domains/` directory spans all repos.** Maintain a single top-level `domains/` directory (in its own repo or a designated repo) that contains domain.yaml files for the entire system. Each domain's `code_locations` points to paths in specific repos (prefix with the repo name: `<repo>/src/path`).
- **Cross-repo refs work unchanged.** `domain://` and `port://` refs are globally unique by `id`, not by file path. A domain in repo A can reference a domain in repo B as long as both have entries in the shared `domains/` directory.
- **Master checklist spans all repos.** During crawling, build one checklist covering all repos. Note which repo each module comes from.
- **Validate cross-repo refs explicitly.** Since imports can't be traced across repo boundaries with a single `grep`, document cross-repo dependencies in the `relationship` field and verify them manually or via API contracts.

For single-repo systems, ignore this section — everything lives under one `domains/` directory by default.

## Reference Integrity Rules (for tooling)

- Every `domain://` ref must resolve to an `id:` in another `domain.yaml`
- Every `port://` ref must resolve to a port `id:` in the referenced domain's `ports.yaml`
- `kernel://` refs are **not** required to resolve to a `domain.yaml` (kernels are external libs). Validate kernels by checking that `source:` matches an installed dependency (e.g., `npm ls <pkg>`, `cargo tree -p <crate>`, `pip show <pkg>`)
- Every `via_port:` must resolve to a port `id:` in the referenced domain's `ports.yaml`. For adjacents that communicate via events (no direct port call), omit `via_port` and document the event contract in the `relationship` field instead
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

**Folder-hierarchy consistency rule:** If domain B is listed in domain A's `subdomains`, then B's folder should be nested under A's folder (e.g., `domains/A/B/domain.yaml`). If B's folder is a sibling of A instead, either: (a) the folder is misplaced — move it, or (b) the relationship is actually adjacent, not subdomain — reclassify. Tooling can validate this by checking that every subdomain ref's `id` starts with the parent domain's `id` as a prefix (e.g., subdomain `video-editing/format-handling` under parent `video-editing`).
