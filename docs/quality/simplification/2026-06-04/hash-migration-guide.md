# Stable hash migration guide

Issue: #537

This guide records the shared `frtb-common` contract for replacing package-local
`_hash_payload` helpers with `frtb_common.stable_json_hash`. Migrations should
remain package-scoped: use the package tracking issues for `frtb-cva` (#538),
`frtb-drc` (#539), and `frtb-sbm` (#544), and avoid bundling multiple capital
packages in one PR unless an ADR explicitly covers the cross-cutting change.

## Shared contract

Use:

```python
from frtb_common import stable_json_hash
```

or, when keeping submodule imports local to a package style:

```python
from frtb_common.hashing import stable_json_hash
```

`stable_json_hash(payload)` is the SHA-256 digest of:

- `frtb_common.serialization.jsonable(payload)`;
- JSON encoded with sorted keys;
- compact separators `(",", ":")`;
- UTF-8 bytes.

This matches both legacy helper shapes currently used by consumers:

```python
hashlib.sha256(
    bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")), "utf-8")
).hexdigest()
```

and:

```python
hashlib.sha256(
    json.dumps(jsonable(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
```

The compatibility tests live in
`packages/frtb-common/tests/test_hashing.py::test_stable_json_hash_matches_plain_legacy_payload_helper`
and
`packages/frtb-common/tests/test_hashing.py::test_stable_json_hash_matches_jsonable_legacy_payload_helper`.

## Migration checklist

1. Add package-local regression tests that compare representative existing
   `_hash_payload` outputs against `stable_json_hash` before changing imports.
2. Replace the local helper body or helper import with `stable_json_hash`.
3. Keep package-specific payload builders, validation errors, audit record
   fields, and regulatory semantics inside the capital package.
4. Remove now-unused `hashlib`, `json`, and `jsonable` imports only where they
   are no longer used by that module.
5. Run the affected package tests plus `packages/frtb-common/tests/test_hashing.py`
   and `make quality-control` before opening the PR.

Do not migrate IMA binary or NumPy-array hashing through this helper. Those
input envelopes deliberately remain package-local until a separate design covers
binary and array canonicalization.

## Current package order

| Package | Tracking issue | First target |
| --- | --- | --- |
| `frtb-sbm` | #544 | profile and audit helpers after fixture hash checks |
| `frtb-drc` | #539 | helpers that already coerce with `jsonable` |
| `frtb-cva` | #538 | `_payloads.hash_payload` after row/batch alignment checks |

`frtb-rrao` and `frtb-result-store` already use `stable_json_hash` through their
package-local payload or storage helpers.
