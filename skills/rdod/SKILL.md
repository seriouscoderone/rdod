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

## Orientation Questions (enter any domain, ask these)

1. **Language** — What are the core terms, rules, and invariants here?
2. **Clients** — Who depends on / uses me? (upstream)
3. **Subdomains** — What do I depend on / use? (downstream)
4. **Kernels** — Which external libs am I adopting as native primitives?
5. **Adjacents** — Which peer domains do I collaborate with laterally?
6. **Externals** — What infra/IO concerns do I encapsulate behind interfaces?

## The 5 Neighbor Types

| Type | Direction | Nature | Example |
|------|-----------|--------|---------|
| **Client** | Upstream | Depends on this domain | `SocialMediaPlatform` using `VideoEditing` |
| **Subdomain** | Downstream | Custom/composed child domain | `VideoFormatHandling` inside `VideoEditing` |
| **Kernel** | Downstream | Adopted off-the-shelf lib, used natively | `ColorLibrary` types used directly, no wrapping |
| **Adjacent** | Lateral | Peer collaborator or cross-cutting concern | `AudioProcessing` alongside `VideoEditing` |
| **External** | Plugged in | Infra/IO, encapsulated behind an interface | `VideoRepository` for persistence |

### Decision Rule — where does it belong?

```
Does it contribute to this domain's core model/language?
  ├─ Yes + built/composed internally → Subdomain
  ├─ Yes + external lib → Kernel or Subdomain (see below)
  └─ No →
       Is it a peer / cross-cutting collaborator? → Adjacent
       Is it infra, IO, or external service? → External (encapsulate via interface)
```

**Kernel vs. Subdomain for external libs** — the key question is: *do its types appear unchanged in your domain's public surface?*

- **Kernel:** You use the lib's own types directly in your domain objects and public API. Its vocabulary becomes your vocabulary. No translation layer. Example: a `Color` type from a color lib appears in your `Effect` aggregate's fields — you've adopted it as native.
- **Subdomain:** You depend on the lib but translate or wrap it at your boundary. Your domain has its own type (e.g., `Clip`) that internally uses the lib but never exposes it. The lib's language does not bleed into your model.

If you find yourself writing `MyDomainThing(externalLib.TheirType)` → Kernel. If you write `MyDomainType { inner: externalLib.TheirType }` hidden behind your own type → Subdomain wrapper.

## Ports (Interfaces at Domain Boundaries)

- **Inbound port** — interface domain clients use to drive this domain (Application Service, Facade, Command handler)
- **Outbound port** — interface this domain uses for subdomains or externals (Repository, Adapter)
- **Adapters** — concrete implementations of outbound ports (live outside the domain core)

Adjacent domains connect via agreed-upon contracts: method interfaces, event schemas, or published language. Apply DDD context-map patterns as needed: ACL (protect your model), Conformist, Shared Kernel, Open Host Service + Published Language, Partnership.

## Templates

See `references/templates.md` for fillable YAML templates (`domain.yaml`, `ubiquitous-language.yaml`, `ports.yaml`) with full field descriptions.

Blank template files ready to copy into a project are in `assets/`.

## Codebase Analysis Methodology

See `references/crawling.md` for the step-by-step process to detect domains in existing code, fill templates comprehensively, and verify links and cross-references.

## Quick Usage Guide

**Designing new software:**
Use orientation questions + decision rule to place each concern. Start with the core domain, define its ubiquitous language, then identify clients/subdomains/kernels/adjacents/externals outward.

**Analyzing existing code:**
Follow `references/crawling.md`. Start top-down, detect cohesive modules by naming/dependency patterns, assign provisional domain IDs, recurse depth-first into each.

**Deciding where code goes:**
Apply the decision rule. If something "feels like a subdomain but not really" → likely adjacent. If it's infrastructure → external with an interface.

## Generate Context Map (optional)

After completing an RDOD analysis with filled `domain.yaml` files:

```bash
python skills/rdod/scripts/generate_context_map.py ./domains
```

Opens as `context-map.html` in any browser — no server needed. Shows each domain's
neighborhood: clients above, subdomains below, kernels left, adjacents right.
Click any neighbor to navigate to it. Use the sidebar to jump to any domain directly.
