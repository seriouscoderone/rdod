# RDOD Codebase Crawling Methodology

Use this when analyzing an existing codebase to detect domains and fill RDOD templates. Work depth-first: fully map one domain before expanding to the next.

---

## Step 1 — Orient at the top level

1. List all top-level packages/modules/folders (`tree -L 2` or equivalent).
2. Run the dependency graph tool for the language:
   - JS/TS: `npm ls --all` or `madge src/`
   - Python: `pipdeptree` or scan `import` statements
   - Rust: `cargo tree`
3. Identify the artifact with the most dependents — this is likely a core domain or subdomain kernel. Identify the artifact with no dependents — this is likely a domain client (top-level app or service).
4. Write down a provisional list of candidate domain names. These are guesses; they will be refined.

---

## Step 2 — Pick one domain and enter it

Start with a mid-level domain (not the very top, not the very bottom). This gives you both upstream clients and downstream subdomains to trace immediately.

Create `domains/<name>/domain.yaml` from the blank template. Fill `id`, `name`, `description` now. Leave everything else blank.

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
5. Fill `ubiquitous-language.yaml`.

---

## Step 4 — Identify clients (upstream)

Who imports or depends on this domain?

```
grep -rn "from <domain>\|import <domain>\|use <domain>::\|require('<domain>')" ../
```

For each caller:
- Is it a higher-level domain orchestrating this one? → Domain client. Add to `domain_clients`.
- Is it a sibling at roughly the same level using this as a utility? → Likely adjacent (come back to this in Step 6).

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

---

## Step 8 — Fill code locations and recurse

Fill `code_locations` with actual file paths.

Now pick the first stub created in Step 5 and repeat Steps 3–8 for it. That stub is now "the domain." Recurse depth-first until all stubs are filled.

---

## Step 9 — Coverage check

After all domains are filled:

1. **Orphan check:** Any domain with no clients and no subdomains? Either it's a legitimate top-level entry point, or you missed a connection. Investigate.
2. **Mirror check:** For every entry in domain A's `domain_clients`, domain B should list domain A in its `subdomains` or `adjacents`. Verify both sides match.
3. **Gap check:** Any required field still empty? Fill or explicitly mark `null` with a note.

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

## Working notes

- Mark unfilled stubs `version: "0.0.0-stub"` so they're distinguishable from completed domains.
- If a dependency's role is ambiguous after applying the decision rule, note the ambiguity in `description` and move on — ambiguity is data, not failure.
- Re-enter any domain whenever new clients or subdomains are discovered; templates are living documents.
