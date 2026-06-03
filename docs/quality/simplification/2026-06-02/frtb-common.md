# frtb-common simplification audit

## Scope

`frtb-common` owns shared primitives, package-neutral Arrow handoff mechanics,
CRIF normalization, status objects, serialization, and regulatory citation test
helpers. It must not carry capital-component regulatory semantics.

## Hotspot map

| Module | Lines | Notes |
| --- | ---: | --- |
| `frtb_common.crif` | 1211 | Largest shared module; owns CRIF normalization mechanics. |
| `frtb_common.handoff` | 438 | Arrow-backed handoff primitives and hashing. |
| `frtb_common.regulatory.policy_citations` | 239 | Test utility for citation coverage. |
| `frtb_common.component_handoff` | 118 | Standardised component handoff contract. |

## Duplicated code

- `frtb_common.handoff.normalized_arrow_table_hash` already implements stable JSON
  payload hashing, while component packages reimplement `_hash_payload` and
  input-hash helpers.
- CRIF normalization mechanics exist here, but component CRIF adapters still
  carry package-local alias resolution and primitive coercion in places. Some of
  that may be intentional where the source is not yet normalized through common.

## Dead or storage-only code

No clear dead code was identified. `frtb-common` is the right place for
package-neutral CRIF and handoff mechanics that are already referenced by tests.

## `frtb-common` candidates

These are candidates to add to `frtb-common`, not problems in the existing
package:

- `stable_json_hash(payload: object) -> str`, using `jsonable`, sorted keys,
  compact separators, and UTF-8 bytes.
- `validate_sha256_hex(value: str, *, field: str, error_factory: ...)`, or a
  boolean validator that packages wrap in their own error types.
- Arrow-to-NumPy primitive conversion helpers for handoff modules, including
  object, float64, integer, boolean, dictionary, chunk, and null policies.
- Batch array coercion primitives if they stay package-neutral and do not encode
  regulatory schema semantics.

## Package-local factoring candidates

- Consider splitting `crif.py` into schema/alias definitions, record-to-Arrow
  construction, vectorized coercion, and diagnostics if further CRIF behavior is
  added. Current size is manageable but already above 1200 lines.
- Avoid adding many more exports to `frtb_common.__init__`; prefer submodule
  imports for specialized helpers.

## Over-complexity

The main complexity risk is making `frtb-common` too broad. Shared mechanics are
useful, but commonizing regulatory concepts would weaken package boundaries.

## What must not move

Do not add component risk weights, bucket definitions, classification rules,
jurisdiction profile support decisions, capital-line semantics, or result
subtotals here.

## Recommended sequence

1. Add stable hash and SHA256 validation helpers with tests.
2. Add Arrow conversion helpers only after checking the existing handoff modules
   for null/chunk/dictionary differences.
3. Consider batch array helpers after one package migration proves the API is
   not schema-specific.

## Validation required

- `packages/frtb-common/tests` for every new helper.
- Existing component hash tests must continue to pass after each package
  migration.
- `make quality-control` because this touches shared governance boundaries.

