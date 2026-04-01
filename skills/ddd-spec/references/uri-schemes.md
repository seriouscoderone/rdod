# RDOD URI Reference Schemes

8 URI schemes for cross-referencing between domain spec files. These are toolkit-level conventions — every RDOD spec uses the same grammar.

## Scheme Definitions

| Scheme | Grammar | Resolves to |
|--------|---------|-------------|
| `domain://` | `domain://{domain_id}` | `{domain_id}/domain.yaml` |
| `kernel://` | `kernel://{domain_id}[#{type_name}]` | `{domain_id}/domain.yaml` (kernel adoption); with fragment: specific type from the kernel |
| `port://` | `port://{domain_id}/{direction}/{port_name}` | `{domain_id}/ports.yaml → ports[id == full_uri]` |
| `types://` | `types://{domain_id}#{type_name}` | `{domain_id}/types.yaml → types[name == {type_name}]` |
| `errors://` | `errors://{domain_id}#{error_name}` | `{domain_id}/errors.yaml → errors[name == {error_name}]` |
| `verification://` | `verification://{domain_id}#{term_or_constraint}` | `{domain_id}/verification.yaml` |
| `protocols://` | `protocols://{domain_id}#{protocol_name}` | `{domain_id}/protocols.yaml → protocols[name == {protocol_name}]` |
| `external://` | `external://{external_name}` | Abstract — no file resolution |

## Parsing Algorithm

For any string matching `{scheme}://{rest}`:

1. Split on `://` → `(scheme, rest)`
2. If `#` present in rest → split on first `#` → `(domain_id, fragment)`; else `(domain_id, None)`
3. For `port://` → split domain_id on the last two `/` segments → `(domain_path, direction, port_name)`, reconstruct full URI as the port id to match

## Resolution Algorithm

| Scheme | Step 1: Directory | Step 2: File | Step 3: Element |
|--------|------------------|-------------|-----------------|
| `domain://X` | `X/` exists | `X/domain.yaml` exists | — |
| `kernel://X` | `X/` exists | `X/domain.yaml` exists | Referenced in another domain's `kernels:` |
| `kernel://X#Y` | `X/` exists | `X/domain.yaml` exists | Type `Y` from kernel `X` — resolved by convention, not file lookup |
| `port://X/dir/name` | `X/` exists | `X/ports.yaml` exists | `ports[].id` matches full URI |
| `types://X#Y` | `X/` exists | `X/types.yaml` exists | `types[].name == Y` |
| `errors://X#Y` | `X/` exists | `X/errors.yaml` exists | `errors[].name == Y` |
| `verification://X#Y` | `X/` exists | `X/verification.yaml` exists | `properties[].term == Y` or `validation_constraints[].id == Y` |
| `protocols://X#Y` | `X/` exists | `X/protocols.yaml` exists | `protocols[].name == Y` |
| `external://X` | — | — | Documented in spec conventions |

## Error Levels

| Check | Level | Meaning |
|-------|-------|---------|
| Directory not found | error | Domain doesn't exist |
| File not found | error | Required companion file missing |
| Element not found | warning | Named item missing from the file |
| Fragment missing when required | warning | `types://X` without `#TypeName` |

## Valid Contexts

| Scheme | Valid in |
|--------|---------|
| `domain://` | Anywhere — structural references |
| `kernel://` | `kernels[].ref`, `kernels[].source`, port `contract.input`/`contract.output` (with `#fragment` only) |
| `port://` | `via_port`, `port_ref`, `delegates_to`, `externals[].ref` |
| `types://` | `types.yaml` field types, `protocols.yaml` typed I/O, port `contract.input`/`contract.output` |
| `errors://` | `protocols.yaml` on_failure[].ref, port `contract.errors` |
| `verification://` | `protocols.yaml` preconditions[].ref |
| `protocols://` | `integration-scenarios.yaml` scenario protocol refs |
| `external://` | `externals[].ref` in domain.yaml |

## Extending with Spec-Specific Schemes

Per-spec `conventions.yaml` can define additional schemes (e.g., `rfc://` for standards references). The linter skips schemes it doesn't recognize — no false positives for custom extensions.
