# Linguistic Discovery

DDD is fundamentally a language game. The spec designer's job is to discover what the adopter — the person building *with* this system — actually does and would naturally call it. The first name that comes to mind is usually an implementation term (a class name, a database table, a wire format field). These names describe mechanisms, not jobs. This reference defines the tests, patterns, and techniques for translating implementation language into adopter language.

---

## Three Naming Tests

Apply to every domain name, port name, and UL term before committing.

**Production test:** Does the name match what the thing produces or does? A `ClipValidator` should validate clips. If a `ClipRepository` validates, coordinates, and enforces invariants instead of just storing and retrieving, the name is wrong — it's a Service wearing a Repository's name. Conversely, if a `MessageProcessor` mainly stores messages on a shelf for later retrieval, it's a Repository wearing a Service's name.

**Readability test:** Can someone who has never seen the implementation understand this name? If a name requires reading source code to parse (acronyms, internal codenames, concatenated class names), it fails.

**Verb test:** What verb does the adopter use when they interact with this? "I need to *serialize* the payload" is a mechanism verb. "I need to *send* the message" is an adopter verb. Port names and domain event names should use adopter verbs.

---

## Multiple Framings

Never accept the first name. For every domain or significant term, explore at least 2-3:

| Framing | Question | Example |
|---------|----------|---------|
| Action-derived | What does it DO? | `EventValidator` |
| Output-derived | What does it PRODUCE? | `ValidatedEvent` |
| Job-derived | What job does the adopter hire it for? | `IdentityService` |
| Stakeholder | What would a non-technical person call it? | `Identity Manager` |

The job-derived framing usually wins for domain names and port names. The action-derived framing works for internal operations. The output-derived framing works for event names.

---

## Pattern Recognition

Universal patterns that reveal naming problems:

| You see... | It's actually... | The pattern |
|------------|-----------------|-------------|
| A "Repository" with rich validation, coordination, or multi-step logic | A **Service** wrapping a Repository | **Service-over-Repository** — the adopter interacts with the Service (behavior: validate, coordinate, approve). The Repository underneath just stores and retrieves (a shelf). Repositories are nouns (storage); Services are verbs (behavior). |
| Multiple tightly-coupled components that can't be explained independently | A single domain artificially split | **Premature Decomposition** — merge until the domain has one coherent name that passes the readability test. |
| A component that produces something different from what its name implies | A misnamed domain | **Production Mismatch** — rename after what it actually produces or does. |
| Cross-domain operations described with internal mechanism verbs | Missing adopter-facing contract language | **Verb Translation** — find the adopter verb that reveals the actual relationship: approval, authorization, commitment, verification, notification, subscription. The mechanism verb tells you *how*; the adopter verb tells you *what*. |
| A domain named after an implementation artifact (a database, a wire format, a framework class) | A domain that needs a business-concept name | **Implementation Leak** — name after the business concept the artifact serves, not the artifact itself. |
| A "Service" that only stores and retrieves with no validation or coordination | A Repository wearing a Service name | **Over-promotion** — demote to Repository. If it's just a shelf, call it a shelf. |

---

## Adopter Verb Translation

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

---

## Red Flags Checklist

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

If any box is checked, the name needs work. Apply the multiple framings technique and the three naming tests until no flags remain.
