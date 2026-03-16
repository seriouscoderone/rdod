---
name: ddd-spec
description: "DDD Specification Generator — produces domain.yaml files from scratch through iterative LLM-driven expansion. Use when: (1) designing a new system, library, or service and you need comprehensive domain specifications before writing code, (2) turning domain documents, whitepapers, or requirements into structured domain specs, (3) the user mentions ddd-spec, domain spec, spec generation, domain modeling from scratch, or asks to design domains from requirements. Produces specs compatible with RDOD analysis and the context map generator."
---

# DDD Specification Generator

## Purpose

Generate comprehensive DDD domain specifications from scratch — before any code exists. Start with a seed (a description, domain documents, or a blank slate), iteratively discover domain concepts, and produce structured `domain.yaml` files that AI systems can implement in any language.

This is the design-first counterpart to RDOD (which analyzes existing code). Both produce the same output format.

## Core Principle

**Everything is a domain.** Whether a crypto primitive library, a video editing SDK, or a social media platform — all are domains at their own level. The terms "subdomain" and "domain client" are **relative viewpoints**, not fixed types:

- **Subdomain** = a domain *this* domain depends on (downstream)
- **Domain Client** = a domain that depends on *this* domain (upstream)
- Entering any subdomain makes it "the domain" with its own subdomains and clients

This enables recursive navigation: orient identically at every depth of the hierarchy. Aggregates are simply domains that compose sub-concepts. No rigid bounded contexts or enforced deep hierarchies — just relative, compositional descriptions.

## Orientation Questions (enter any domain, ask these)

1. **Language** — What are the core terms, rules, and invariants here?
2. **Clients** — Who depends on / uses me? (upstream)
3. **Subdomains** — What do I depend on / use? (downstream)
4. **Kernels** — Which external libs am I adopting as native primitives?
5. **Adjacents** — Which peer domains do I collaborate with laterally?
6. **Externals** — What infra/IO concerns do I encapsulate behind interfaces?

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

- **Kernel:** You use the lib's own types directly in your domain objects and public API. Its vocabulary becomes your vocabulary. No translation layer.
- **Subdomain:** You depend on the lib but translate or wrap it at your boundary. Your domain has its own type that internally uses the lib but never exposes it.

## Ports (Interfaces at Domain Boundaries)

- **Inbound port** — interface domain clients use to drive this domain (Application Service, Facade, Command handler)
- **Outbound port** — interface this domain uses for subdomains or externals (Repository, Adapter)
- **Adapters** — concrete implementations of outbound ports (live outside the domain core)

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

- **Accidental coupling** (an issue, not a classification): Concepts from one domain appearing inside another domain's model when they shouldn't. This is unintentional, a smell, and caught by issue categories like `inverted-dependency`, `kernel-pollution`, or `language-inconsistency`.

The test: did someone *decide* this concern should span domains (→ cross-cutting adjacent), or did it *drift* there through convenience (→ accidental coupling, log an issue)?

## Templates

See `references/templates.md` for fillable YAML templates (`domain.yaml`, `ubiquitous-language.yaml`, `ports.yaml`) with full field descriptions.

Blank template files ready to copy into a project are in `assets/`.

## Specification Generation Methodology

See `references/expansion.md` for the step-by-step expansion loop to discover domains from requirements, user input, or domain documents, fill templates iteratively, and verify completeness.

## Quick Usage Guide

**From a seed description:**
User provides a paragraph or a few sentences describing the system. Start the expansion loop from Step 1, Mode A of `references/expansion.md`.

**From domain documents:**
User provides or references documents (whitepapers, RFCs, API specs, requirements docs). Read them, then start expansion.md at Step 1, Mode B (the documents serve as the seed's first expansion).

**Continue an existing spec:**
User has an existing `domains/` directory with `domain.yaml` files. Start expansion.md at Step 1, Mode D (reconstruct candidate list from existing files, then expand).

**Deciding where a concept goes:**
Apply the decision rule. The hardest call is subdomain vs. adjacent — use the control test: does this domain drive it (subdomain), or do they negotiate as peers (adjacent)? If it's infrastructure with no domain concepts → external with an interface.

## Generate Context Map (optional)

After any expansion session with filled `domain.yaml` files:

```bash
python skills/ddd-spec/scripts/generate_context_map.py ./domains
```

Opens as `context-map.html` in any browser — no server needed. Shows each domain's neighborhood: clients above, subdomains below, kernels left, adjacents right. Click any neighbor to navigate to it. Use the sidebar to jump to any domain directly.

## Compatibility

The output format is intentionally compatible with RDOD (Recursive Domain-Oriented Design). A project can:

1. Use **ddd-spec** to design the intended domain architecture
2. Implement code based on the spec
3. Use **RDOD** to analyze the implementation and compare against the spec

The domain.yaml files produced by this skill can also be placed into a Spec Kit project structure to fill the DDD gap in spec-driven development workflows.
