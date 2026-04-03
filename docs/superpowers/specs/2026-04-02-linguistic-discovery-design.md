# Design: Linguistic Discovery Methodology

## Context

RDOD's expansion and crawling methodologies tell you *what* to name (domains, ports, terms) but never *how* to name them well. The natural tendency when building a DDD spec — whether from code or from a design document — is to adopt implementation terminology verbatim. This produces relabeled implementation docs, not true domain-driven designs.

This design adds a **linguistic discovery** methodology: a concise reference document defining universal naming patterns and tests, plus lightweight quality gates embedded at each naming decision point in the existing methodology steps.

Addresses seriouscoderone/rdod#1.

## Approach: Hybrid — Reference + Inline Gates

- **`references/linguistic-discovery.md`** (new, both skills): Defines the naming tests, pattern catalog, verb translation technique, and red flags checklist. Single source of truth.
- **Inline quality gates** (3-5 lines each): Embedded at naming decision points in `expansion.md`, `crawling.md`, `templates.md`, and both `SKILL.md` files. These are triggers that invoke the reference by name — they force the pause without duplicating theory.

## Reference Document: `linguistic-discovery.md`

### Section 1: The Problem

When building a DDD spec, the first name that comes to mind is usually an implementation term (a class name, a database table, a wire format field). These names describe mechanisms, not jobs. The spec should use language that a technical adopter — someone building *with* this domain, not someone who wrote its internals — would recognize and find natural.

### Section 2: Three Naming Tests

Apply to every domain name, port name, and UL term before committing.

**Production test:** Does the name match what the thing produces or does? A `ClipValidator` should validate clips. If a `ClipRepository` validates, coordinates, and enforces invariants instead of just storing and retrieving, the name is wrong — it's a Service wearing a Repository's name. Conversely, if a `MessageProcessor` mainly stores messages on a shelf for later retrieval, it's a Repository wearing a Service's name.

**Readability test:** Can someone who has never seen the implementation understand this name? If a name requires reading source code to parse (acronyms, internal codenames, concatenated class names), it fails.

**Verb test:** What verb does the adopter use when they interact with this? "I need to *serialize* the payload" is a mechanism verb. "I need to *send* the message" is an adopter verb. Port names and domain event names should use adopter verbs.

### Section 3: Multiple Framings

Never accept the first name. For every domain or significant term, explore at least 2-3:

| Framing | Question | Example |
|---------|----------|---------|
| Action-derived | What does it DO? | `EventValidator` |
| Output-derived | What does it PRODUCE? | `ValidatedEvent` |
| Job-derived | What job does the adopter hire it for? | `IdentityService` |
| Stakeholder | What would a non-technical person call it? | `Identity Manager` |

The job-derived framing usually wins for domain names and port names. The action-derived framing works for internal operations. The output-derived framing works for event names.

### Section 4: Pattern Recognition

Universal patterns that reveal naming problems:

| You see... | It's actually... | The pattern |
|------------|-----------------|-------------|
| A "Repository" with rich validation, coordination, or multi-step logic | A **Service** wrapping a Repository | **Service-over-Repository** — the adopter interacts with the Service (behavior: validate, coordinate, approve). The Repository underneath just stores and retrieves (a shelf). Repositories are nouns (storage); Services are verbs (behavior). |
| Multiple tightly-coupled components that can't be explained independently | A single domain artificially split | **Premature Decomposition** — merge until the domain has one coherent name that passes the readability test. |
| A component that produces something different from what its name implies | A misnamed domain | **Production Mismatch** — rename after what it actually produces or does. If a `DelegationEscrowRepo` produces approvals, call it `ApprovalService`. |
| Cross-domain operations described with internal mechanism verbs | Missing adopter-facing contract language | **Verb Translation** — find the adopter verb that reveals the actual relationship: approval, authorization, commitment, verification, notification, subscription. The mechanism verb tells you *how*; the adopter verb tells you *what*. |
| A domain named after an implementation artifact (a database, a wire format, a framework class) | A domain that needs a business-concept name | **Implementation Leak** — name after the business concept the artifact serves, not the artifact itself. |
| A "Service" that only stores and retrieves with no validation or coordination | A Repository wearing a Service name | **Over-promotion** — demote to Repository. If it's just a shelf, call it a shelf. |

### Section 5: Adopter Verb Translation

When defining ports and cross-domain relationships, mechanism verbs describe the *how*. Adopter verbs describe the *what* — and often reveal the underlying business pattern:

| Mechanism verb | Adopter verb | Reveals |
|----------------|-------------|---------|
| "serializes," "encodes," "marshals" | "sends," "publishes," "delivers" | It's a communication boundary |
| "anchors," "seals," "checkpoints" | "approves," "authorizes," "commits" | It's an approval or commitment workflow |
| "escrows," "queues," "buffers" | "holds pending," "awaits," "defers" | It's a deferral pattern (awaiting a condition) |
| "indexes," "caches," "denormalizes" | "looks up," "queries," "resolves" | It's a query optimization |
| "wraps," "adapts," "bridges" | "translates," "mediates," "integrates" | It's a translation boundary (ACL pattern) |
| "polls," "watches," "subscribes" | "monitors," "tracks," "observes" | It's an observation pattern |

Port names and domain event names should use the adopter column, not the mechanism column.

### Section 6: Red Flags Checklist

Check before finalizing any domain name, port name, or UL term:

- [ ] Name is an implementation term used verbatim (class name, database name, wire format field)
- [ ] Name describes a mechanism, not a job
- [ ] Can't explain the name to someone unfamiliar with the implementation
- [ ] Accepted the first name without exploring alternatives
- [ ] A Repository has rich validation/coordination logic (should be a Service)
- [ ] A Service only stores and retrieves (should be a Repository)
- [ ] Cross-domain ports use mechanism verbs instead of adopter verbs
- [ ] The production test fails (the thing doesn't produce/do what its name implies)
- [ ] An acronym or abbreviation is used without expansion in the term definition
- [ ] The domain name mirrors a source code module path rather than a business concept

## Inline Quality Gates

Lightweight triggers at naming decision points. Each is 3-5 lines max.

### expansion.md — Step 5a (after drafting terms, ~line 108)

```markdown
**Naming quality gate:** Before finalizing terms, run each through the three naming tests (production, readability, verb) from `references/linguistic-discovery.md`. Explore at least 2 alternative names for each domain-level term. Code terms and protocol jargon are starting points, not final names — translate to adopter language.
```

### expansion.md — Step 5b (after classifying neighbors, ~line 176)

```markdown
**Verb translation gate:** For each cross-domain relationship, check the verb. Are port names using mechanism verbs ("anchors," "serializes," "escrows") or adopter verbs ("approves," "sends," "defers")? See the adopter verb translation table in `references/linguistic-discovery.md`.
```

### expansion.md — Step 5c (after filling ports, ~line 200)

```markdown
**Port naming gate:** Port names and operation names should use adopter verbs, not mechanism verbs. Apply the verb test: "What verb does the adopter use when they call this port?" If the answer is a mechanism verb, translate it.
```

### crawling.md — Step 3 (after extracting UL from code, ~line 79)

```markdown
**Naming quality gate:** Code names are implementation terms — they are inputs to linguistic discovery, not the output. For each extracted term, apply the three naming tests from `references/linguistic-discovery.md`. Check the pattern recognition table: is this a Service wearing a Repository name? A domain named after an implementation artifact? Translate to adopter language before writing to `ubiquitous-language.yaml`.
```

### crawling.md — Step 7 (after filling ports, ~line 202)

```markdown
**Port naming gate:** Check each port name against the verb test. Code-extracted port names often reflect implementation function signatures — translate to adopter verbs. See `references/linguistic-discovery.md` for the verb translation table.
```

### templates.md — After domain.yaml code block (~line 88)

Add to the existing "Tier vs. Intent" section or as a sibling section:

```markdown
### Naming Quality

Domain `id` and `name` should pass the readability test: a technical adopter who has never seen the implementation should understand what this domain is about from its name alone. Avoid implementation artifacts (class names, database names, framework terms) as domain names. See `references/linguistic-discovery.md` for naming tests and the pattern recognition table.
```

### templates.md — After ports.yaml section (~line 241)

Append to the "Port fields" table section:

```markdown
Port `name` and operation descriptions should use adopter verbs, not mechanism verbs. "approve-delegation" is better than "anchor-seal." "send-notification" is better than "serialize-and-queue." See `references/linguistic-discovery.md` for the verb translation table.
```

### Both SKILL.md — After orientation questions (~line 36 rdod, ~line 32 ddd-spec)

```markdown
Answer these questions in language a technical adopter would use — not implementation jargon. See `references/linguistic-discovery.md` for naming tests and the red flags checklist.
```

## Files Modified

| File | Change |
|------|--------|
| `skills/rdod/references/linguistic-discovery.md` | **New** — full reference document |
| `skills/ddd-spec/references/linguistic-discovery.md` | **New** — identical copy |
| `skills/rdod/references/expansion.md` | N/A (rdod doesn't have this) |
| `skills/ddd-spec/references/expansion.md` | 3 inline gates (Steps 5a, 5b, 5c) |
| `skills/rdod/references/crawling.md` | 2 inline gates (Steps 3, 7) |
| `skills/rdod/references/templates.md` | 2 brief sections (domain naming, port naming) |
| `skills/ddd-spec/references/templates.md` | 2 brief sections (same) |
| `skills/rdod/SKILL.md` | 1 line after orientation questions |
| `skills/ddd-spec/SKILL.md` | 1 line after orientation questions |
| `rdod.skill` | Rebuild |
| `ddd-spec.skill` | Rebuild |

## Verification

1. Read the new `linguistic-discovery.md` — confirm no KERI-specific terms, all examples are generic
2. Read each inline gate in context — confirm it flows naturally within the existing step
3. Run `validate_spec.py` against any existing spec — confirm no regressions (no linter changes in this PR)
4. Rebuild both `.skill` packages and verify contents
