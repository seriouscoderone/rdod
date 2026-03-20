# Domain-Driven Verification

Map domain invariants, port contracts, and behavioral rules to formal verification techniques. The domain spec defines *what* must be true; verification proves it *is* true.

This is optional infrastructure — the domain spec is complete without it. Verification adds formalized, machine-executable expressions that external harnesses can consume.

---

## The Bridge: Domain Concepts → Verification Inputs

| Domain concept | Where it lives | Verification technique | What the harness does |
|---|---|---|---|
| Term invariants | `ubiquitous_language[].invariants` | **Property-Based Testing** | Fuzz with random inputs, check invariant holds for all |
| Pattern invariants | Pattern term's invariants | **Property-Based Testing** | Verify all instances satisfy the pattern structure |
| Port contracts (pre/post) | `ports.yaml` `contract` + `verification.yaml` | **SMT Contracts (Z3)** | Prove pre→post holds mathematically, or find counter-model |
| Cross-term rules | `ubiquitous-language.yaml` `rules` | **SMT / Property-Based** | Multi-concept constraints verified across compositions |
| Ordered behavior | Terms with temporal/sequence invariants | **Symbolic Execution** | Exhaustively verify all state transition paths |
| Event triggers | `ubiquitous-language.yaml` `events[].triggers` | **Symbolic Execution** | Verify trigger conditions produce correct events on all paths |

---

## Formalizing Invariants

Natural-language invariants in the domain spec become machine-executable when given a `formal` expression. Add these in `verification.yaml` (one per domain, optional).

### From natural language to formal expression

| Natural language | Formal (Python/Hypothesis) | Technique |
|---|---|---|
| "Timeline must contain at least one clip" | `lambda t: len(t.clips) >= 1` | Property-Based |
| "Clip duration must be positive" | `lambda c: c.duration > 0` | Property-Based |
| "Escrow timeout must be > 0 and ≤ 86400" | `And(timeout > 0, timeout <= 86400)` | SMT (Z3) |
| "Event sequence numbers are strictly monotonic" | `ForAll(i, Implies(i < len-1, sn[i] < sn[i+1]))` | SMT (Z3) |
| "After rotation, old keys cannot sign" | State machine spec | Symbolic Execution |

### Formalization guidelines

1. **Start with property-based.** Most invariants are properties — universal statements about all valid inputs. These are the easiest to formalize and give the fastest feedback loop.

2. **Escalate to SMT for boundary conditions.** When an invariant involves numeric boundaries, overflow, or exact conditions (off-by-one, empty collections, zero values), SMT catches what fuzzing might miss.

3. **Use symbolic execution for state machines.** When a domain has ordered behavior (lifecycle transitions, event sequences, protocol state), symbolic execution verifies all paths through the state machine.

### Classification rule

```
Is the invariant about a single value/input?
  ├─ Yes + range/boundary → SMT contract
  ├─ Yes + universal property → Property-Based Testing
  └─ No →
       Does it involve state transitions or ordering? → Symbolic Execution
       Does it span multiple terms? → SMT or Property-Based (depending on complexity)
```

---

## verification.yaml Template

One per domain. Maps invariants and contracts to formal verification.

```yaml
# verification.yaml
domain_ref: "<domain-id>"

# Formalized invariants from ubiquitous_language terms
properties:
  - invariant: "<natural language invariant from domain.yaml>"
    term: "<which term this belongs to>"
    technique: "<property-based | smt | symbolic>"
    formal:
      language: "<python | typescript | rust | z3 | dafny>"
      expression: "<machine-executable expression>"
    strategy: "<hypothesis strategy or input generator, if property-based>"
    notes: ""

# Formalized port contracts
contracts:
  - port_ref: "port://<domain-id>/<direction>/<name>"
    preconditions:
      - formal:
          language: "<python | z3>"
          expression: "<precondition expression>"
        description: "<natural language>"
    postconditions:
      - formal:
          language: "<python | z3>"
          expression: "<postcondition expression>"
        description: "<natural language>"

# State machine specifications (for ordered/stateful domains)
state_machines:
  - name: "<state machine name>"
    term: "<which term this models>"
    states: ["<state1>", "<state2>"]
    transitions:
      - from: "<state>"
        to: "<state>"
        trigger: "<event or condition>"
        guard: "<condition that must hold>"
    invariants:
      - "<invariant that holds across all states>"
    initial_state: "<state>"
    terminal_states: ["<state>"]
```

---

## The Verification Loop

The domain spec feeds the verification harness. The harness feeds failures back to whoever is refining the spec or implementation.

```
┌─────────────────────────────────────────────────┐
│  Domain Spec (domain.yaml + verification.yaml)  │
│  Invariants, contracts, state machines          │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │   Property-Based Testing │ ← Fuzz invariants with random inputs
          │   (Hypothesis / fast-check)│   Catches class-level bugs fast
          └────────────┬────────────┘
                       │ all properties hold
          ┌────────────▼────────────┐
          │   SMT Verification (Z3)  │ ← Prove contracts mathematically
          │   (CrossHair / CBMC)     │   Kills boundary/overflow bugs
          └────────────┬────────────┘
                       │ all contracts proven
          ┌────────────▼────────────┐
          │   Symbolic Execution     │ ← Verify all state machine paths
          │   (Dafny / KLEE / Rosette)│  Nothing ships unproven
          └────────────┬────────────┘
                       │
              ┌────────▼────────┐
              │   VERIFIED CODE  │
              └─────────────────┘
```

Each gate catches what the previous can't. Each failure produces a **precise, minimal counterexample** that feeds back to the LLM or developer. The loop iterates until correctness is proven, not assumed.

---

## Mapping Domain Behavioral Weight to Verification Depth

The behavioral weight of a term (from the domain spec) determines the minimum verification depth:

| Behavioral weight | Minimum verification | Why |
|---|---|---|
| **Stateless** | Property-Based Testing | Pure functions — fuzz inputs, check outputs |
| **Stateful** | Property-Based + SMT | Lifecycle transitions need boundary proofs |
| **Invariant-bound** | SMT Contracts | Mathematical proof that invariants always hold |
| **Ordered** | Symbolic Execution | Temporal constraints require exhaustive path verification |

This isn't a rigid rule — escalate when lower techniques don't catch the class of bug. But it gives a starting point for deciding how much verification each term warrants.

---

## Integration with RDOD/ddd-spec Workflow

### During ddd-spec expansion (Step 5a):

After writing invariants for each term, ask: "Can this invariant be formalized as a testable property?" If yes, note it. If the domain has enough formalized invariants, create `verification.yaml` for it.

### During RDOD crawling (Step 3):

After extracting invariants from code, check: "Is this invariant already tested? What technique?" If tested via property-based testing, note the test location. If untested, flag as `modeling-gap` with `recommendation: add-verification`.

### When generating implementation from spec:

An AI implementing from the ddd-spec output can use `verification.yaml` directly:
1. Read `properties` → generate property-based tests (Hypothesis/fast-check)
2. Read `contracts` → generate Z3 assertions or contract annotations
3. Read `state_machines` → generate state machine tests or Dafny specs

The spec becomes both the blueprint and the verification criteria.

---

## Tools Reference

### Property-Based Testing

| Language | Library | Notes |
|---|---|---|
| Python | Hypothesis | Mature, excellent shrinking |
| TypeScript/JS | fast-check | Good integration with Jest/Vitest |
| Rust | proptest | Cargo-native |
| Haskell | QuickCheck | The original |
| Java | jqwik | JUnit 5 integration |
| Erlang | PropEr | Built for concurrent systems |

### SMT Solvers

| Tool | Use Case |
|---|---|
| Z3 (Python bindings) | General-purpose SMT solving |
| CrossHair | Python contract verification via Z3 |
| CBMC | C/C++ bounded model checking |
| Creusot | Rust verification via Why3/Z3 |

### Symbolic Execution

| Tool | Use Case |
|---|---|
| Dafny | Spec-first language with built-in verification |
| KLEE | Symbolic execution for C/LLVM |
| angr | Binary-level symbolic execution (Python) |
| Rosette | Solver-aided programming in Racket |
| KeY | Symbolic execution + verification for Java |
