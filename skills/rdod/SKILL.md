---
name: rdod
description: "Recursive Domain-Oriented Design (RDOD) — a DDD-inspired methodology for structuring and navigating software at any abstraction level. Use when: (1) designing a new library, service, application, or system using domain-driven principles, (2) analyzing an existing codebase to map its domains and relationships, (3) deciding where code belongs within a domain structure, (4) the user mentions RDOD, recursive domain, domain navigation, or domain mapping, or asks how to structure domains/subdomains/libraries. Applies to any artifact: kernel, library, middleware, service, or application."
---

# Recursive Domain-Oriented Design (RDOD)

## Core Principle

**Everything is a domain.** Whether a crypto primitive library, a video editing SDK, or a social media platform — all are domains at their own level. The terms "subdomain" and "domain client" are **relative viewpoints**, not fixed types:

- **Subdomain** = a domain *this* domain depends on (downstream)
- **Domain Client** = a domain that depends on *this* domain (upstream)
- Entering any subdomain makes it "the domain" with its own subdomains and clients

This enables recursive navigation: orient identically at every depth of the hierarchy.

## When RDOD Is Not Appropriate

RDOD assumes the thing being analyzed has **domain concepts** — terms, invariants, and relationships that form a model. It is not useful for:

- **Pure utility libraries** with no domain semantics (string manipulation, math helpers, left-pad). If there's no ubiquitous language to extract, RDOD adds overhead without insight.
- **Build tooling and CI/CD configuration** — these are infrastructure, not domains.
- **Generated code** — the generator is the domain, not its output.

If a codebase module has no recognizable domain concepts after a brief inspection, mark it `out-of-scope` on the master checklist and move on. RDOD is for code that models a problem space, not code that merely executes mechanics.

## Orientation Questions (enter any domain, ask these)

1. **Language** — What are the core terms, rules, and invariants here?
2. **Clients** — Who depends on / uses me? (upstream)
3. **Subdomains** — What do I depend on / use? (downstream)
4. **Kernels** — Which external libs am I adopting as native primitives?
5. **Adjacents** — Which peer domains do I collaborate with laterally?
6. **Externals** — What infra/IO concerns do I encapsulate behind interfaces?
7. **Tier** — Is this a kernel (adopted primitive), domain (core logic), external (infrastructure/storage behind an interface), service (independently deployed), or application (end-user entry point)?

Answer these questions in language a technical adopter would use — not implementation jargon. See `references/linguistic-discovery.md` for naming tests and the red flags checklist.

## The 5 Neighbor Types

| Type | Relation | Nature | Example |
|------|----------|--------|---------|
| **Client** | Upstream | Depends on this domain | `SocialMediaPlatform` using `VideoEditing` |
| **Subdomain** | Downstream (owned) | Child domain this domain drives and composes | `VideoFormatHandling` inside `VideoEditing` |
| **Kernel** | Adopted | External lib whose types become this domain's types — no ownership, no wrapping | `ColorLibrary` types used directly in `Effect` fields |
| **Adjacent** | Lateral (peer) | Collaborator at the same level — neither domain controls the other | `AudioProcessing` alongside `VideoEditing` |
| **External** | Encapsulated | Infra/IO concern hidden behind a domain-owned interface | `VideoRepository` for persistence |

### Decision Rule — where does it belong?

```
Does it contribute to this domain's core model/language?
  ├─ Yes + built/composed internally →
  │     Does this domain control/drive it? → Subdomain
  │     Do they collaborate as equals? → Adjacent
  ├─ Yes + external lib → Kernel or Subdomain (see below)
  └─ No →
       Does it collaborate laterally with this domain? → Adjacent
       Is it infra, IO, or external service? → External (encapsulate via interface)
```

**Subdomain vs. Adjacent — the control test:** Can this domain tell the dependency what to do? If yes — this domain drives it, owns its evolution, and composes its output — it's a **subdomain**. If the relationship is a negotiation between equals, neither side controls the other's model, and changes require coordination — it's an **adjacent**. When uncertain, look at who would break if the relationship changed: if only this domain breaks → subdomain. If both break → adjacent.

**Kernel vs. Subdomain for external libs** — the key question is: *do its types appear unchanged in your domain's public surface?*

- **Kernel:** You use the lib's own types directly in your domain objects and public API. Its vocabulary becomes your vocabulary. No translation layer. Example: a `Color` type from a color lib appears in your `Effect` aggregate's fields — you've adopted it as native.
- **Subdomain:** You depend on the lib but translate or wrap it at your boundary. Your domain has its own type (e.g., `Clip`) that internally uses the lib but never exposes it. The lib's language does not bleed into your model.

If you find yourself writing `MyDomainThing(externalLib.TheirType)` → Kernel. If you write `MyDomainType { inner: externalLib.TheirType }` hidden behind your own type → Subdomain wrapper.

## Ports (Interfaces at Domain Boundaries)

- **Inbound port** — interface domain clients use to drive this domain (Application Service, Facade, Command handler)
- **Outbound port** — interface this domain uses for subdomains or externals (Repository, Adapter)
- **Adapters** — concrete implementations of outbound ports (live outside the domain core)

Each port defines a structured contract with typed `input`, `output`, and `errors` references (using `types://`, `errors://`, or `kernel://id#Type` URIs), plus `semantics` (command/query/event) and `idempotent` flag. Protocol (REST, gRPC, etc.) is not part of the port — it is derivable from the `tier` boundary between domains.

Adjacent domains connect via agreed-upon contracts. Choose the context-map pattern that best describes the relationship:

| Pattern | When to use |
|---------|-------------|
| **Partnership** | Two domains cooperate closely with joint planning — mutual dependency, both teams align on changes |
| **Shared Kernel** | Two domains share a small, carefully managed subset of the model (e.g., a common types library) — tight coupling, but controlled and explicit |
| **Customer-Supplier** | Downstream domain depends on upstream; upstream plans features to serve downstream's needs — clear power direction |
| **Conformist** | Downstream adopts upstream's model as-is with no negotiation — avoids translation overhead, accepts coupling |
| **ACL (Anti-Corruption Layer)** | Downstream protects its own model by translating incoming data through a dedicated boundary layer — prevents model pollution |
| **OHS + Published Language** | Upstream exposes a standardized service/API with a published schema so multiple downstreams can consume it independently |
| **Separate Ways** | Domains ignore each other completely — no integration, by deliberate choice |

If no pattern fits, the boundary may be unclear — investigate whether the relationship is actually subdomain (one side controls the other) rather than adjacent.

## Cross-Cutting Concerns vs. Accidental Coupling

RDOD uses "cross-cutting" in one specific sense. These two situations look similar but are fundamentally different:

- **Cross-cutting adjacent** (`is_cross_cutting: true`): A domain that legitimately spans many other domains by design — auth, logging, observability, error reporting. These are intentional, healthy, and classified as adjacents with the cross-cutting flag. They have their own ubiquitous language and clear boundaries.

- **Accidental coupling** (an issue, not a classification): Code from one domain appearing inside another domain's internals when it shouldn't — e.g., a `User` type from the identity domain leaking into the billing domain with no ACL. This is unintentional, a smell, and caught by issue categories like `inverted-dependency`, `kernel-pollution`, or `language-inconsistency`.

The test: did someone *decide* this concern should span domains (→ cross-cutting adjacent), or did it *drift* there through convenience (→ accidental coupling, log an issue)?

## Output Directory

RDOD writes all domain files to **`rdod/analysis/domains/`** by default. This keeps RDOD's analysis of existing code separate from any ddd-spec design work, which writes to `rdod/spec/domains/`.

```
rdod/
  analysis/          ← RDOD output (what the code IS)
    domains/
      <domain-id>/
        domain.yaml
        ubiquitous-language.yaml
        ports.yaml
  spec/              ← ddd-spec output (what it SHOULD be)
    domains/
      ...
```

Both directories use the same domain.yaml format. Running both skills on the same project and comparing the two directories gives you the delta between current architecture and ideal architecture — the refactoring roadmap.

## Templates

See `references/templates.md` for all YAML template schemas. See `references/uri-schemes.md` for the formal grammar and resolution rules of all 8 URI reference schemes. Blank templates in `assets/`.

**Per domain (required):**
- `domain.yaml` — identity, published language, neighbors, issues, code locations
- `ubiquitous-language.yaml` — terms (sole source of truth), imports, specializations, events, rules
- `ports.yaml` — inbound and outbound interfaces with contracts

**Per domain (optional, for AI-implementability):**
- `errors.yaml` — error taxonomy with cause, recovery, severity, context
- `types.yaml` — formal data structures with variants, fields, constraints, encoding
- `protocols.yaml` — cross-domain orchestration sequences with failure paths
- `verification.yaml` — formalized invariants, port contracts, state machines

**Spec root (cross-domain):**
- `integration-scenarios.yaml` — cross-domain end-state assertions for each protocol

## Codebase Analysis Methodology

See `references/crawling.md` for the step-by-step process to detect domains in existing code, fill templates comprehensively, and verify links and cross-references.

## Domain-Driven Verification (optional)

See `references/verification.md` for how to formalize domain invariants, port contracts, and state machines into machine-executable expressions that external harnesses can verify. Maps RDOD concepts to property-based testing, SMT solvers (Z3), and symbolic execution.

## Quick Usage Guide

**Designing new software:**
Use orientation questions + decision rule to place each concern. Start with the core domain, define its ubiquitous language, then identify clients/subdomains/kernels/adjacents/externals outward.

**Analyzing existing code:**
Follow `references/crawling.md`. Start top-down, detect cohesive modules by naming/dependency patterns, assign provisional domain IDs, recurse depth-first into each.

**Deciding where code goes:**
Apply the decision rule. The hardest call is subdomain vs. adjacent — use the control test: does this domain drive it (subdomain), or do they negotiate as peers (adjacent)? If it's infrastructure with no domain concepts → external with an interface.

## Validate Spec (optional)

After completing an RDOD analysis, validate structural integrity:

```bash
python skills/rdod/scripts/validate_spec.py rdod/analysis/domains
```

Checks reference resolution, mirror consistency, cycle detection, published language rules, folder hierarchy, term uniqueness, and completeness. Use `--strict` to treat warnings as errors. Use `--json` for machine-readable output.

## Generate Context Map (optional)

After completing an RDOD analysis with filled `domain.yaml` files:

```bash
python skills/rdod/scripts/generate_context_map.py rdod/analysis/domains
```

Opens as `context-map.html` in any browser — no server needed. Shows each domain's
neighborhood: clients above, subdomains below, kernels left, adjacents right.
Click any neighbor to navigate to it. Use the sidebar to jump to any domain directly.
