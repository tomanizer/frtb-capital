# Public API integration section template

Use this fragment when adding or refreshing a package `PUBLIC_API.md`.

## Client integration

### Integration tiers

| Tier | Client input | Package path | Notes |
| --- | --- | --- | --- |
| 1 - Arrow/Parquet input table | Tables matching `*_ARROW_COLUMN_SPECS` | `normalize_*_arrow_table` -> `build_*_batch_from_arrow` -> `calculate_*_from_batch` | Recommended production path. |
| 2 - CRIF/vendor rows | Iterable mapping rows | `adapt_crif_records` / `adapt_*_records` -> Tier 1 or Tier 3 | Use when upstream already emits vendor or CRIF-shaped rows. |
| 3 - Canonical dataclasses | Package row dataclasses | `calculate_*_capital` | Notebooks, tests, fixtures, and small books only. |

### Required sections

- Package identity and `PACKAGE_METADATA`.
- Tier 3 row entrypoints and canonical dataclasses.
- Tier 1 batch entrypoints.
- Input table column spec symbols.
- Normalize functions.
- Optional CRIF or vendor adapters.
- Supported regulatory profiles and explicit fail-closed paths.
- Errors, diagnostics, rejected-row records, and no-silent-drop policy.
- Audit, hashing, attribution, and replay entrypoints.
- Submodule-only symbols clients must not treat as stable contracts.

### Input Table Column Summary

Include a compact table for every public input table spec:

| Column | Required | Logical type | Null policy | Notes |
| --- | --- | --- | --- | --- |

The Python `ColumnSpec` tuple remains the source of truth. The table is a
client-facing summary, not a replacement for generated machine-readable schemas.

### Cross-links

- Suite guide: [`docs/CLIENT_INTEGRATION.md`](../../CLIENT_INTEGRATION.md)
- Reference data matrix:
  [#422](https://github.com/tomanizer/frtb-capital/issues/422)
- Schema exports: [`docs/schemas/input_table/`](../../schemas/input_table/)
- Validation harness: `scripts/validate_client_input_table.py`
