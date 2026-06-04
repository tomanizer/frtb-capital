# Stable hash migration plan

Issue: #378

This note records the migration plan enabled by `frtb_common.hashing`. The #378
implementation adds shared helpers only; component input hashes and profile
hashes are not migrated in the same PR.

For the current migration contract and package-scoped follow-up checklist, see
[`../2026-06-04/hash-migration-guide.md`](../2026-06-04/hash-migration-guide.md).

## Shared helpers

- `frtb_common.stable_json_dumps(payload)`
- `frtb_common.stable_json_hash(payload)`
- `frtb_common.is_sha256_hex(value)`
- `frtb_common.require_sha256_hex(value, field=...)`

`stable_json_hash` uses `frtb_common.serialization.jsonable`, sorted JSON keys,
compact JSON separators, UTF-8 encoding, and SHA-256.

## First migration candidates

These helpers already match the compact sorted JSON hash pattern and can be
replaced one package at a time after package-local hash compatibility tests are
in place:

| Package | Helper | Notes |
| --- | --- | --- |
| `frtb-rrao` | `audit._hash_payload` | Plain dict payloads; migrate after unifying audit/batch position payloads. |
| `frtb-rrao` | `batch._hash_payload` | Already calls `jsonable`; should be a direct wrapper candidate. |
| `frtb-rrao` | `regimes._hash_payload` | Profile hash candidate; verify profile hash fixtures/tests. |
| `frtb-cva` | `audit._hash_payload` | Plain dict payloads; migrate after shared audit/batch payload builders. |
| `frtb-cva` | `batch._hash_payload` | Plain dict payloads; verify batch and row input hashes stay aligned. |
| `frtb-cva` | `regimes._hash_payload` | Profile hash candidate. |
| `frtb-drc` | `audit._hash_payload` | Already calls `jsonable`; verify fixture hash gates before migration. |
| `frtb-drc` | `batch._hash_payload` | Already calls `jsonable`; verify row/batch hash equivalence. |
| `frtb-drc` | `regimes.profile_content_hash` | Already uses `jsonable`; profile hash candidate. |
| `frtb-sbm` | `audit._hash_payload` | Plain dict payloads; verify fixture expected input hashes. |
| `frtb-sbm` | `regimes._hash_payload` | Profile hash candidate. |

## Deferred candidates

- `frtb-ima.audit_inputs.compute_inputs_hash` handles bytes and NumPy arrays
  specially and appends a newline before hashing. Keep it local unless a later
  common helper explicitly supports binary/array digest envelopes.
- File-content helpers such as fixture `_sha256(path)` functions should remain
  local unless enough packages need a shared file hashing API.
- Package `_validate_hash` helpers should wrap `is_sha256_hex` or
  `require_sha256_hex` so each package can keep its own input error type and
  field names.

## Migration order

1. Migrate profile hash helpers where tests assert deterministic SHA-256 output
   but do not pin a hard-coded digest.
2. Migrate batch helpers that already call `jsonable`.
3. Migrate audit helpers only after package-local payload builders are unified.
4. Keep IMA binary/NumPy hashing local until a separate design covers those
   envelopes.

Every migration PR should run the affected package tests plus
`make quality-control`.
