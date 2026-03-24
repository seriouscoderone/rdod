# RDOD Codebase Crawling Methodology

Use this when analyzing an existing codebase to detect domains and fill RDOD templates. Work depth-first: fully map one domain before expanding to the next.

---

## Step 1 — Build the complete module inventory

Before touching any domain, enumerate **everything** in the repo. This becomes the master checklist that guarantees completeness — the crawl is not done until every item on it is accounted for.

1. List all packages/modules at every level:
   ```
   tree -L 3 src/         # or the repo root
   ```
   For monorepos, also list workspace members:
   - JS/TS: `cat package.json | grep workspaces` or `ls packages/`
   - Python: `cat pyproject.toml` or `ls src/`
   - Rust: `cat Cargo.toml | grep members` or `ls crates/`

2. Produce the full dependency graph:
   - JS/TS: `npm ls --all` or `madge src/`
   - Python: `pipdeptree`
   - Rust: `cargo tree`

3. **Write the master checklist.** List every distinct internal module/package with its provisional classification from the dependency graph. This is the authoritative list. Use `assets/checklist.yaml` as the template, or a markdown checklist — either works. Example:
   ```
   MASTER CHECKLIST
   [ ] social-media-platform    (client — no dependents)
   [ ] video-editing            (core — most dependents)
   [ ] format-handling          (subdomain candidate)
   [ ] rendering-engine         (subdomain candidate)
   [ ] color-library            (kernel candidate — external)
   [ ] shared-types             (subdomain candidate)
   [ ] legacy-importer          (isolated — not in dep graph)
   ```
   Include modules that appear isolated (not yet connected in the dep graph) — these are the ones a pure traversal would miss. The classification column is a guess at this stage; update it as the crawl refines your understanding.

   Two additional classifications beyond the standard domain types:

   - **`out-of-scope: <reason>`** — For items that are clearly not domain concerns: dead code (no imports in either direction AND no recognizable domain concepts), build tooling, test utilities, generated code. Do not create `domain.yaml` files for these — just note them on the checklist with a reason so they're accounted for.
   - **`decomposition-target`** — For modules named `utils`, `common`, `shared`, `helpers`, or similar grab-bag packages. These are treated like any other module during the crawl, but they almost always lack cohesion. When you enter one in Steps 3-8, expect to find mixed concerns that should be distributed across multiple domains. Log `hierarchy-imbalance` with `recommendation: split-subdomain` and note *what* each piece should become (subdomain, kernel, adjacent, external, or dead code). A single split can produce multiple outputs of different types.

4. From the dependency graph, classify each item provisionally:
   - **No dependents** → likely a domain client (top-level app or service)
   - **Most dependents** → likely a core domain or kernel candidate
   - **Middle** → subdomain or adjacent candidate

---

## Step 2 — Pick one domain and enter it

Apply this priority order to select the first domain:

1. **User intent first.** If the user named a specific domain, concern, or area when invoking the skill, start there.
2. **Most-depended-upon internal module.** The internal module imported by the most other internal modules is the most load-bearing — understanding it early orients everything else. **Skip modules with utility-flavored names** (`utils`, `common`, `shared`, `helpers`, `types`) — high import count does not make a grab-bag a good entry point. These are decomposition targets, not domain entry points.
3. **Clearest domain naming.** When dependency counts are close, prefer the module whose name and type names read as business/problem concepts (e.g., `order`, `credential`, `timeline`).
4. **Ask if still unclear.** If no candidate stands out after applying the above, ask the user which domain to enter first rather than guess.

Aim for a mid-level domain when possible — not the very top (client) and not the very bottom (leaf library). This gives you both upstream clients and downstream subdomains to trace immediately.

Create `rdod/analysis/domains/<name>/domain.yaml` from the blank template. Fill `id`, `name`, `description` now. Leave everything else blank. Check this domain off the master checklist.

---

## Step 3 — Extract ubiquitous language

Inside the domain's source folder:

1. Collect all type/class/struct/enum names. These are your candidate terms.
   ```
   grep -rn "class \|struct \|type \|interface \|enum " src/<domain>/
   ```
2. Collect the most-used nouns in method names and field names. High-frequency nouns that appear across multiple files are core language.
3. Scan comments and doc strings for definitions or rules.
4. For each term: write `term`, `definition`, and any `invariants` you can find (look for validation logic, assertions, `if`/`guard` checks that enforce a rule).
5. Fill `ubiquitous-language.yaml` (the sole source of truth for all term content).
6. **Published language:** If any terms are foundational concepts that other domains depend on (used across multiple modules), add them to `published_language` in `domain.yaml`. Other domains should import these rather than redefining them.
7. **Imports and specializations:** If this domain uses terms defined in a parent or sibling domain's `published_language`, add an `imports` entry in `ubiquitous-language.yaml`. If it narrows a parent's term, add `specializes: "domain://<parent>"` on the term.

**Issue cue:** If invariants are enforced ad-hoc across multiple places (repeated validation logic, no single owner) rather than inside a named aggregate or value object → log `modeling-gap` (`recommendation: introduce-concept:<proposed-name>`).

**Pattern detection:** After extracting 3+ terms, check for shared structural patterns. If multiple types have the same set of fields/invariant categories but differ only in specific values (e.g., 7 escrow types each with a trigger, storage location, timeout, and reprocess condition), extract a pattern term that defines the common structure. Add a `pattern` field to each instance term in `ubiquitous-language.yaml`. This signals that a parameterized implementation is appropriate and that the domain should NOT be further decomposed — splitting instances of the same pattern into separate subdomains is over-nesting.

---

## Step 3b — Spec-depth audit (per domain)

The initial crawl captures code structure (classes, functions, modules). This step probes the domain's source material for concepts that hide behind simple code — protocol-level richness, design principles, variant taxonomies, and philosophical constraints that AST extraction misses.

**When to run:** After extracting UL terms (Step 3) and before mapping relationships (Step 4). Prioritize domains with rich source material (`source_material:` in domain.yaml) but few UL terms.

**For each domain, probe the source material with these 5 questions:**

1. **Variant taxonomy**: "What are ALL the variants/forms/modes of [concept]? Not just the main one — edge cases, special forms, alternative patterns?"

2. **Architectural principles**: "What design principles or constraints govern [concept]? Why was it designed this way? What alternatives were rejected?"

3. **Independence/coupling**: "Can [concept] operate independently of [assumed dependency]? What is the minimum infrastructure required?"

4. **Consumer patterns**: "Who uses [concept] and HOW? Are there different usage patterns for different consumers?"

5. **Lifecycle/evolution**: "How does [concept] change over time? Immutable? Append-only? Replaceable? What update semantics apply?"

**Gap identification:** For each concept found in source material but NOT in the UL:
- New term → add to `ubiquitous-language.yaml`
- Variant of existing term → expand the type definition in `types.yaml`
- Architectural property → add as a principle term with invariants
- Implementation detail → skip (not domain-level)

**Cross-domain check:** For each new concept, ask "does this affect other domains?" If yes, check those domains for corresponding terms or relationships.

---

## Step 4 — Identify clients (upstream)

Who imports or depends on this domain?

```
grep -rn "from <domain>\|import <domain>\|use <domain>::\|require('<domain>')" ../
```

For each caller:
- Is it a higher-level domain orchestrating this one? → Domain client. Add to `domain_clients`.
- Is it a sibling at roughly the same level using this as a utility? → Likely adjacent (come back to this in Step 6).

**Issue cue:** If a caller imports internal implementation types rather than going through a port/interface, log `inverted-dependency` or `missing-port` against this domain.

**Circular dependency detected (A imports B, B imports A):** Do not ignore this or defer it to Step 11. Resolve it now — the rest of the crawl builds on these classifications. Three possible resolutions:

1. **Missing abstraction (most common).** Both domains depend on a concept that should be extracted as a shared port or interface. This is a Dependency Inversion Principle violation. Log `inverted-dependency` against both, with `recommendation: add-port` or `refactor-port`. Identify what the shared abstraction should be.
2. **Actually one domain.** If both modules share significant ubiquitous language and neither can be understood without the other, they may be a single domain that was artificially split. Log `hierarchy-imbalance` with `recommendation: merge-hierarchy`.
3. **Adjacent with event/callback pattern.** One direction is a direct call, the other is a callback, listener, or event subscription. Classify as adjacents, not client/subdomain. The event direction is not a true dependency — it's a notification.

---

## Step 5 — Identify subdomains and kernels (downstream)

List every import/dependency this domain pulls in.

For each dependency, ask two questions in order:

**Q1: Is this internal (built as part of this system) or external (third-party lib)?**
- Internal → **Subdomain candidate.** Create a stub `domain.yaml` for it. You will recurse into it after finishing this domain.

**Q2 (external libs only): Do this lib's types appear unchanged in my domain's public surface?**
- Yes — its types are in my aggregates, value objects, or public method signatures → **Kernel.** List it under `kernels`. No wrapping layer exists or is needed.
- No — I wrap or translate its types before exposing them → **Subdomain wrapper.** List it under `subdomains` with a note that it wraps the external lib.
- No domain model involvement at all (purely runtime plumbing) → **External concern** (handle in Step 7).

Fill `subdomains` and `kernels` in `domain.yaml`.

**Issue cues:**
- A lib is classified as a kernel but its types are actually being wrapped → log `wrong-classification` (`recommendation: reclassify`).
- A kernel's exception types, internal structs, or implementation details appear in domain aggregates beyond what the model needs → log `kernel-pollution`.
- A subdomain has no clear interface — the domain calls into it directly by concrete type → log `missing-port`.
- A subdomain appears to have more responsibility than its name implies, or covers multiple unrelated concerns → log `hierarchy-imbalance` (`recommendation: split-subdomain`).

---

## Step 6 — Identify adjacents

Look for dependencies that don't fit cleanly as parent or child:

- Event emitters/listeners that cross domain boundaries
- Shared service interfaces consumed by multiple domains at the same level
- Anything you felt uncertain about in Steps 4 or 5 ("kinda a subdomain but not really")

For each adjacent, choose the context-map pattern that describes the relationship:
- **Partnership** — mutual collaboration, both teams align
- **ACL (Anti-Corruption Layer)** — you protect your model by translating their types at entry
- **Conformist** — you simply adopt their model without translation
- **Shared Kernel** — a small shared subset of model both domains use directly
- **OHS + Published Language** — they expose a stable API/schema you consume

Flag `is_cross_cutting: true` for concerns that touch many domains (auth, logging, observability).

Fill `adjacents` in `domain.yaml`.

**Issue cue:** If two adjacent domains share concepts (e.g., both have a `User` type) with no ACL or Shared Kernel between them → log `language-inconsistency` against both domains.

---

## Step 7 — Identify externals and ports

Scan for infrastructure boundaries:
- Database access (repositories, ORMs, query builders)
- HTTP clients, message queue producers/consumers
- File system, blob storage
- External service SDKs that are not adopted as kernels

For each:
- The domain must own an **interface** (outbound port) — infrastructure implements it, domain depends only on the interface.
- If you find raw DB/HTTP calls directly in domain logic → flag as purity violation.

Fill `externals` in `domain.yaml`. For each port (inbound and outbound), fill `ports.yaml`.

**Domain logic vs. implementation:** The domain owns the *interface* (e.g., "a repository for storing clips"). The concrete implementation (e.g., "PostgreSQL with table `clips`") lives outside the domain and is noted in `implementation_notes` on the external entry. When filling externals, name the abstraction the domain needs, not the technology behind it. The technology is evidence for the implementation notes, not the domain model.

**Issue cues:**
- Raw infrastructure calls (DB queries, HTTP requests, file I/O) found directly in domain logic with no interface → log `missing-port`.
- No inbound port exists — clients call internal domain types directly → log `missing-port` (inbound).
- An external concern's interface is defined outside the domain (e.g., in an infra layer) rather than owned by the domain → log `inverted-dependency`.

---

## Step 7b — Extract errors, types, and protocols (optional)

For domains with significant complexity, fill the optional companion files:

**errors.yaml** — Scan for error types, exception classes, and error handling patterns. For each error the domain can produce, record: name, cause, recovery strategy (retry/escrow/escalate/abort), severity (fatal/recoverable/transient), and context fields. Link each error to the port operation that produces it.

**types.yaml** — For domains with key data structures (not just simple value objects), extract formal type definitions: variants, fields with types and constraints, construction defaults, and encoding rules. Focus on types that cross domain boundaries or that an implementor would need to reproduce exactly.

**protocols.yaml** — For domains that orchestrate multi-domain flows, document the end-to-end sequences: participants, step ordering with dependencies, failure paths with compensation, timeouts, and terminal states. This is most valuable for parent/orchestrator domains.

**When to skip:** Leaf domains with simple language and few types can skip these files. Prioritize them for core domains, protocol domains, and domains with complex error handling.

---

## Step 7c — Set domain intent (optional)

If this domain is an adapter layer, API facade, or thin delegation point with no domain logic of its own, set `intent:` in `domain.yaml`:

- **core** — full domain logic, rich UL, types, errors expected
- **adapter** — thin HTTP/API layer forwarding to parent domain logic
- **orchestrator** — coordinates subdomains, protocols expected
- **facade** — simplified interface over complex subdomains

This tells the linter to adjust expectations (e.g., no UL terms warning for adapters).

---

## Step 8 — Fill code locations, tick checklist, and recurse

Fill `code_locations` with actual file paths.

Check this domain off the master checklist from Step 1.

Now pick the next stub to recurse into. Priority order:
1. **Most-connected subdomain** — the stub referenced by the most other candidates or completed domains. Understanding it early informs later classifications.
2. **User's choice** — if the user has a preference, follow it.
3. **Dependency order** — a stub that other stubs depend on should be filled before its dependents.
4. **Alphabetical** — as a tiebreaker.

Repeat Steps 3–8 for the chosen stub. That stub is now "the domain." Recurse depth-first until all stubs are filled.

After each domain is completed, scan the master checklist for any unchecked item that has not yet appeared as a stub. If one exists, it was not reachable by traversal from the current entry point — create a stub for it now and recurse into it as a new branch.

**Correcting the model mid-crawl:** If you realize a domain boundary is wrong (e.g., you classified something as a subdomain but it's really an adjacent, or two domains should be one), correct the `domain.yaml` files immediately. Don't build more analysis on a known-wrong foundation. This corrects the *analyst's model*, not the code. If the *code's structure* is wrong (e.g., a monolith that should be split), that's an issue to log (`hierarchy-imbalance`), not a model correction — the model should reflect what the code IS, with issues noting what it SHOULD BE.

---

## Step 9 — Coverage check

After all stubs are filled:

1. **Checklist completion:** Compare the master checklist from Step 1 against all completed `domain.yaml` files. Every item on the checklist must be either (a) a completed domain, (b) a kernel entry in some domain's `kernels`, (c) explicitly marked `out-of-scope: <reason>` (dead code, build tooling, test utilities, generated code), or (d) distributed across multiple domains via a `split-subdomain` decomposition. Any unchecked item with no accounting → create a stub and recurse.
2. **Orphan check:** Any domain with no clients and no subdomains? Either it's a legitimate top-level entry point (note it as such), or a relationship was missed. A domain reachable only by `out-of-scope` items is suspicious — investigate whether those items were correctly excluded.
3. **Mirror check:** For every entry in domain A's `domain_clients`, domain B should list domain A in its `subdomains` or `adjacents`. Verify both sides match.
4. **Gap check:** Any required field still empty? Fill or explicitly mark `null` with a note.

---

## Step 10 — Cross-check for verification

**Language consistency:** Compare terms across linked domains. If the same word (e.g., "User") appears in two domains with different definitions and there is no ACL between them → flag as model pollution risk.

**Code vs. declaration:** Re-run the dependency tool from Step 1. Compare actual imports against declared `subdomains`/`adjacents`. Any import not in templates → missing relationship. Any template relationship with no import → stale or forward-declared (note which).

**Invariant coverage:** For each invariant in `ubiquitous-language.yaml`, find an existing test that exercises it. If none exists → flag as untested invariant.

---

## Step 11 — Link verification

For every `ref:` value across all templates:

1. Does `domain://<id>` resolve to a `domain.yaml` whose `id` field matches exactly? If not → broken ref.
2. Does `port://<domain-id>/<dir>/<name>` resolve to a port entry in that domain's `ports.yaml`? If not → broken port ref.
3. Trace the full subdomain graph. Any cycle (A depends on B depends on A) → architectural problem, flag immediately.

Produce a Mermaid diagram of the full domain graph as a deliverable:

```
graph TD
  social-media-platform --> video-editing
  video-editing --> format-handling
  video-editing --> color-library:::kernel
  video-editing -. adjacent .-> audio-processing
  classDef kernel fill:#f9f,stroke:#333
```

---

## Termination Criteria

The crawl is complete when ALL of the following are true:

1. **Every item on the master checklist is accounted for** — either a completed `domain.yaml`, a kernel entry in some domain's `kernels`, or explicitly marked `out-of-scope: <reason>`.
2. **No unfilled stubs remain** — every `domain.yaml` has version ≥ 0.1.0 (not `0.0.0-stub`).
3. **The frontier is all leaves** — every domain's subdomains are either completed domains, kernels, or externals. No unvisited internal domains remain to recurse into.
4. **A full pass of Steps 9–11 produces no new work** — no new stubs to create, no broken refs, no missing mirrors. The verification steps are clean.

If Step 9 or 10 surfaces new stubs or relationships, those must be filled before re-running verification. The crawl converges when expansion reaches the leaves of the domain tree (kernels and externals) and verification passes clean.

---

## Focused Library Audit

Use this when you want to deliberately evaluate a specific dependency — a known-bad library, a suspect kernel, or any reference that warrants more than incidental detection during crawling. Run this instead of (or after) the main crawl for the target library.

**Trigger:** User names a specific library, or a crawl pass surfaces enough incidental issues on one dependency to warrant deeper investigation.

---

### Audit Step 1 — Identify the blast radius

Before auditing the library itself, map who is exposed:

1. Find every domain that lists this library as a `kernel`, `subdomain`, or `external`.
2. For each of those domains, find their `domain_clients` — these are the upstream domains that inherit any damage.
3. Write a short impact list: `<library> → affects: [domain-A, domain-B] → upstream: [domain-C, domain-D]`

This tells you how bad "bad" actually is before you start digging.

---

### Audit Step 2 — Check classification correctness

Is this library classified correctly in every domain that uses it?

- Listed as a kernel but its types are being wrapped → `wrong-classification` + `kernel-pollution`
- Listed as a subdomain but its types leak into the domain's public surface → `wrong-classification`
- Listed as an external but it contributes to domain logic → `wrong-classification`

Log one issue per domain that has it misclassified.

---

### Audit Step 3 — Check interface integrity

Does the domain interact with this library through a clean interface?

- Domain calls the library's concrete types directly with no port/interface → `missing-port`
- The library's exceptions, error types, or internal structs appear in the domain's aggregates or events → `kernel-pollution`
- The domain's public API exposes the library's types to its clients → `kernel-pollution` (severity: high — the blast radius now includes clients)

For each finding: record the specific file, method, or type as `evidence`.

---

### Audit Step 4 — Check language integrity

Does this library's vocabulary pollute or conflict with the domain's ubiquitous language?

- Compare the library's type/method names against `ubiquitous-language.yaml` terms.
- If the library uses the same word with a different meaning (e.g., library calls it `Frame`, domain calls it `Frame` but means something different) → `language-inconsistency`
- If the domain has adopted the library's terminology wholesale without defining it in its own language → `modeling-gap` (the domain's language is hollow)

---

### Audit Step 5 — Check structural fit

Does this library's shape fit its role in the hierarchy?

- Does it do too much for a kernel (broad scope, many unrelated concerns)? → `hierarchy-imbalance` (`recommendation: split-subdomain` or `reclassify` to subdomain)
- Does it have its own significant dependencies that the parent domain is now indirectly inheriting? → document those transitive deps; flag any that reach into infrastructure as `missing-port` against the parent domain
- Is it actively maintained? If abandoned/unmaintained: log `other:maintainability` with evidence (last commit date, open critical issues)

---

### Audit Step 6 — Trace impact upward

For each issue found in Steps 2–5:

1. Note which domains in the blast radius (from Audit Step 1) are directly affected.
2. For high/critical issues: add a corresponding issue entry in each affected domain's `domain.yaml` — not just the domain where the library lives. The `ref` points to the library; the `description` explains how the impact manifests in that specific domain.
3. Produce a short impact summary:
   ```
   kernel://color-library
     kernel-pollution (high) → video-editing: kernel exception types in RenderPass aggregate
       → upstream impact: social-media-platform receives corrupted render events
   ```

---

### Audit Step 7 — Deliver the verdict

Summarize the audit as a structured finding:

```
LIBRARY AUDIT: <library-name>
Classification: <current> → <correct if different>
Issues found: <count by severity>
  critical: N  high: N  medium: N  low: N
Blast radius: <list of affected domains>
Recommended action: <single primary recommendation>
Rationale: <one sentence>
```

If `recommended action` is `replace`: note whether a suitable alternative exists and what the migration boundary would be (which port or ACL would contain the swap).

If `recommended action` is `wrap-with-acl`: identify exactly which types/methods need wrapping and where the ACL boundary sits in the domain hierarchy.

---

- Mark unfilled stubs `version: "0.0.0-stub"` so they're distinguishable from completed domains.
- If a dependency's role is ambiguous after applying the decision rule, note the ambiguity in `description` and move on — ambiguity is data, not failure.
- Re-enter any domain whenever new clients or subdomains are discovered; templates are living documents.
