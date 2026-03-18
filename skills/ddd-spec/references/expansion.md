# DDD Spec Expansion Loop

Use this to generate domain specifications from scratch (or a seed) through iterative LLM-driven discovery. Work depth-first: fully specify one domain before expanding to the next.

The loop has three phases: **Seed** (establish scope), **Expand** (fill domains iteratively), and **Verify** (check completeness and integrity).

---

## Phase A: Seed

### Step 1 — Establish the seed

Determine the starting point. Exactly one mode applies:

**Mode A — User provides a description.** A paragraph to a few pages describing the system, problem space, or library. This is the seed.

**Mode B — User provides domain documents.** Whitepapers, RFCs, API specs, requirements docs, or other reference material. Read them. Extract a summary paragraph that becomes the seed. Retain the full documents as source material for Step 2.

**Mode C — Blank slate.** Ask the user: "What system or problem space should we model? Describe it in a few sentences." Their answer is the seed.

**Mode D — Continue existing spec.** User has a `rdod/spec/domains/` directory with existing `domain.yaml` files. Read all files, reconstruct the candidate list (see "Handling Continue Mode" below), and skip to Step 6.

Write the seed down verbatim. Every later step refers back to it.

---

### Step 2 — Extract the candidate domain list

From the seed text (and any source documents), perform these extractions:

1. **Noun extraction.** Identify every significant noun or noun phrase. Group synonyms. These are candidate domain concepts.

2. **Verb extraction.** Identify every significant verb or action phrase. These hint at domain operations, events, and commands.

3. **Boundary detection.** Look for phrases that imply separation of concerns: "managed by," "responsible for," "communicates with," "independent of," "depends on." Each boundary phrase suggests two domains and a relationship between them.

4. **Stakeholder detection.** Identify distinct roles, actors, or systems mentioned. Each is either a domain client (it uses the system) or an adjacent (it collaborates laterally).

Produce a **candidate domain list** — the equivalent of RDOD's master checklist, but derived from text rather than code:

```
CANDIDATE DOMAIN LIST
[ ] timeline            (core — central to seed)              source: seed text
[ ] clip                (subdomain candidate)                  source: seed text
[ ] rendering           (subdomain candidate)                  source: inferred
[ ] format-handling     (subdomain candidate)                  source: whitepaper §3.2
[ ] audio-processing    (adjacent candidate)                   source: seed text
[ ] video-storage       (external candidate)                   source: inferred
```

Mark each entry with:
- Its **provisional role** (core, subdomain candidate, client candidate, adjacent candidate, external candidate, kernel candidate)
- Its **source** (seed text, document section, domain-expert input, llm-inferred)

The source field matters for provenance — LLM-inferred candidates should be scrutinized more carefully by the user.

---

### Step 3 — Present and negotiate the candidate list

Show the candidate domain list to the user. For each candidate, state:
- Why it was identified as a separate domain
- Its provisional role
- What source material led to it

Ask: "Does this look right? Should any be merged, split, renamed, or removed? Are there domains I missed?"

The user's feedback refines the list. **The loop cannot proceed until the user acknowledges the candidate list.** This is the first negotiation point — getting the scope right before deep-filling prevents wasted work.

If source documents are available, also ask: "Are there other documents I should review?"

---

## Phase B: Expand

### Step 4 — Pick one domain and enter it

Apply this priority order:

1. **User intent first.** If the user named a domain to start with, start there.
2. **Core domain.** The domain that most other candidates reference or depend on.
3. **Most constrained.** The domain with the most invariants or business rules mentioned in the seed.
4. **Ask if unclear.** If no candidate stands out, ask the user.

Aim for the core domain first — not a leaf and not a top-level client. This gives you both upstream clients and downstream subdomains to trace immediately.

Create `rdod/spec/domains/<name>/domain.yaml` from the blank template. Fill `id`, `name`, `description`. Set `version: "0.1.0"`. Record `source_material` entries with where this domain's information came from.

---

### Step 5 — Deep-fill the domain

This is the heart of the expansion loop. For the current domain, work through these sub-steps. Each sub-step either uses LLM domain knowledge or asks the user.

#### 5a — Ubiquitous language

Using the nouns and verbs extracted in Step 2 that belong to this domain, draft the `ubiquitous_language` entries:

1. For each term: write a precise `definition` scoped to this domain
2. Propose `invariants` — rules that must always hold for this term
3. If uncertain about a definition or invariant, ask the user

Fill both:
- The `ubiquitous_language` section in `domain.yaml` (brief: term + definition + invariants)
- The full `ubiquitous-language.yaml` (expanded: synonyms, examples, related terms)

Present the language to the user: "Here are the core terms for [domain]. Are these definitions accurate? Terms missing? Invariants wrong?"

**Issue cue:** If a term seems to mean different things in different contexts within this domain → the domain may need splitting (`hierarchy-imbalance`).

#### 5a-bis — Pattern detection

After drafting 3+ terms for a domain, check for shared structural patterns:

1. **Shape comparison.** Do multiple terms have the same set of invariant categories (e.g., all have a "trigger," "storage," "timeout," and "resolution" invariant)?

2. **Value-only variation.** If the terms differ only in the specific values within those categories (not in what categories exist), they are instances of a pattern.

3. **Extract the pattern.** Create a new term that defines the common structure. Name it "&lt;Thing&gt; Pattern" or "&lt;Thing&gt; Structure." List the structural elements as invariants. Note any exceptions (instances that deviate from the pattern).

4. **Link instances.** Add a `pattern` field to each instance term in `ubiquitous-language.yaml`, referencing the pattern term. This signals to implementors that a parameterized/generic implementation is appropriate.

**Issue cue:** If a domain has 3+ terms that are instances of the same pattern, the domain is likely at the right depth — decomposing further would split instances of the same concept into separate domains, which is over-splitting.

#### 5b — Neighbor discovery

For each remaining candidate on the domain list, determine its relationship to the current domain by applying the decision rule:

```
Does this candidate contribute to the current domain's core model?
  ├─ Yes + this domain controls/drives it             → Subdomain
  │     (this domain owns its evolution and composes its output)
  ├─ Yes + they collaborate as equals                  → Adjacent
  │     (neither side controls the other; changes require coordination)
  ├─ Yes + it's an external standard/lib               →
  │     Do its types appear unchanged in this domain?  → Kernel
  │     Are its types wrapped/translated?              → Subdomain
  ├─ No + it collaborates laterally                    → Adjacent
  ├─ No + it's infra/IO                               → External
  ├─ No + it depends on this domain                    → Client
  └─ No relationship                                   → Skip
```

For each neighbor identified:
- Fill the appropriate section (`domain_clients`, `subdomains`, `kernels`, `adjacents`, `externals`)
- For adjacents: choose the context-map pattern (Partnership, ACL, Conformist, Shared Kernel, Customer-Supplier, OHS+PL, Separate Ways)
- For adjacents with `is_cross_cutting: true`: ensure they have their own language and clear boundaries
- For externals: name the abstraction type (Repository, Service, Adapter)

Present the neighborhood to the user: "Here's how [domain] relates to its neighbors. Does the classification feel right?"

**Issue cues:**
- A candidate that's hard to classify → may need splitting or the relationship is actually bidirectional (adjacent, not subdomain)
- A kernel with many concepts leaking into this domain → `kernel-pollution`

#### 5c — Ports

Based on the neighbors:

1. For each **client**: define an **inbound port** — how the client drives this domain. What operations does it expose?
2. For each **subdomain**: define an **outbound port** — how this domain drives the subdomain. What does it ask for?
3. For each **external**: define an **outbound port** — the interface this domain owns for infrastructure access
4. For **adjacents**: document the contract type (shared events, partnership API, published language, etc.)

Fill `ports.yaml`.

**Issue cue:** If a port's contract is hard to define → the domain boundary may be in the wrong place (`hierarchy-imbalance`) or the adjacent pattern needs revisiting.

#### 5d — Events and rules

Based on the language and ports:

1. **Domain events:** What state changes in this domain might other domains care about? Each event has a name, payload, and trigger.
2. **Cross-term rules:** Business rules that span multiple terms in the ubiquitous language — invariants that aren't owned by a single term.

Fill the `events` and `rules` sections of `ubiquitous-language.yaml`.

#### 5e — Design issues (optional)

Flag any architectural concerns discovered during this domain's expansion:

- Terms appearing in multiple domains with conflicting meanings → `language-inconsistency`
- A candidate that was hard to classify → `wrong-classification` (provisional)
- A domain that seems too broad (too many unrelated terms) → `hierarchy-imbalance`
- Missing concepts the domain needs but hasn't defined → `modeling-gap`
- A dependency that seems inverted → `inverted-dependency`

Use `rationale` instead of `evidence` — explain why it's a concern, since there's no code to point at.

---

### Step 6 — Tick and recurse

Mark the domain as complete on the candidate list (`[ ]` → `[x]`).

Pick the next unfilled domain. Priority:
1. Any **subdomain** of the domain just completed (depth-first recursion)
2. Any domain the user explicitly asks about
3. Next candidate on the list by importance (most referenced, most constrained)

Repeat Steps 5a–5e for the new domain.

**Important:** Each time a new domain is entered, check whether it introduces new candidates not on the original list — new subdomains, infrastructure concerns, kernel dependencies. If so, add them to the candidate list.

**Pattern-instance domains should NOT be further decomposed.** If a domain's terms are primarily instances of a single pattern (e.g., 7 escrow types all following the same trigger/storage/timeout/reprocess structure), the domain is at the right depth. Splitting individual instances into separate sub-subdomains would be over-nesting — they share vocabulary, invariants, and implementation. Instead, ensure the pattern term is defined and all instances reference it.

---

### Step 7 — Consolidation checkpoint

After every 3–5 domains are filled, pause and perform:

1. **Mirror check.** For every entry in domain A's `domain_clients`, domain B should list A in its `subdomains` or `adjacents`. Fix any mismatches by updating both sides.

2. **Language collision check.** Compare terms across all filled domains. If the same term (e.g., "Event") appears in two domains with different definitions:
   - They need an ACL between them, OR
   - One should rename its term, OR
   - The term should move to a shared kernel

3. **Pattern check.** For each domain with 4+ terms, scan for structural similarity. If 3+ terms share the same invariant categories with different values, flag as a potential unextracted pattern. Ask the user: "These terms look like instances of the same pattern. Should we extract the common structure?"

4. **User checkpoint.** Summarize progress:
   - "We've filled N of M domains."
   - Show the current domain graph (text or Mermaid).
   - "Where should we focus next? Any domains that need revisiting?"

---

### Step 8 — Fill remaining candidates

Continue Steps 5–7 until every candidate is either:
- A completed `domain.yaml` (version ≥ 0.1.0, has language + neighbors)
- A kernel entry in some domain's `kernels`
- Explicitly removed from the list with a reason

---

## Phase C: Verify

### Step 9 — Coverage and integrity check

After all candidates are filled:

1. **Candidate list completion.** Every item accounted for.
2. **Orphan check.** Any domain with no clients and no parent domain? Either it's a legitimate top-level entry point, or a relationship was missed. Investigate.
3. **Mirror check (full).** All bidirectional refs verified across every domain.
4. **Gap check.** Any required field still empty? Fill or explicitly mark null with a note.
5. **Cycle check.** No cycles in the subdomain graph. Adjacents may be mutual.
6. **Link verification.** Every `domain://` ref resolves to an `id:` in another `domain.yaml`. Every `port://` ref resolves to a port entry.

---

### Step 10 — Final review and deliverables

Present the complete spec to the user:

1. **Summary table.** One row per domain: id, name, role (core / subdomain / client / adjacent), neighbor count, term count, issue count.

2. **Mermaid diagram** of the full domain graph:
   ```
   graph TD
     platform --> video-editing
     video-editing --> format-handling
     video-editing --> color-library:::kernel
     video-editing -. partnership .-> audio-processing
     classDef kernel fill:#f9f,stroke:#333
   ```

3. **Generate `rdod/spec/domains/README.md`** as the entry point:
   ```markdown
   # Domain Specification

   ## System Description
   <the seed text, verbatim or refined>

   ## Domain Map
   <Mermaid diagram>

   ## Domains
   | ID | Name | Status | Description |
   |---|---|---|---|
   | ... | ... | complete / stub | ... |

   ## Source Material
   | Type | Reference |
   |---|---|
   | ... | ... |

   ## Open Questions
   - ...
   ```

4. **Open questions.** Any unresolved ambiguities, design issues, or areas where the LLM was uncertain.

5. **Context map.** Offer to generate the interactive HTML visualization:
   ```bash
   python skills/ddd-spec/scripts/generate_context_map.py rdod/spec/domains
   ```

Ask: "Is this spec complete enough to implement against? What should we refine?"

---

## Handling Continue Mode

When a `rdod/spec/domains/` directory already exists with `domain.yaml` files:

1. Read all `domain.yaml` files
2. Classify each as:
   - **Complete:** version ≥ 0.1.0 AND has at least 2 of: ubiquitous_language entries, neighbor entries (clients/subdomains/adjacents), ports
   - **Stub:** version is "0.0.0-stub" or all sections are empty
   - **Work-in-progress:** has some content but doesn't meet "complete" criteria
3. Reconstruct the candidate list from files, marking complete ones `[x]`
4. Find `domain://` refs that point to nonexistent files — these are implicit stubs to create
5. Present the reconstructed list to the user with status per domain
6. Enter Step 6 directly — pick the first unfilled stub or ask the user what to expand next

---

## Notes

- Mark unfilled stubs `version: "0.0.0-stub"` so they're distinguishable from completed domains.
- If a candidate's role is ambiguous after applying the decision rule, note the ambiguity in `description` and move on — ambiguity is data, not failure. It often resolves when neighboring domains are specified.
- Re-enter any domain whenever new clients, subdomains, or adjacents are discovered. Domain specs are living documents.
- The expansion loop is designed for multi-session use. Each conversation session may cover one or more iterations. The `domain.yaml` files on disk are the persistent state — the candidate list can always be reconstructed from them (Mode D).
