# Batch Array Coercion Assessment

Issue: #380

Follow-up implementation issue: #391

## Decision

Approve a limited `frtb_common.batch_arrays` extraction for package-neutral
NumPy array mechanics only.

The repeated helper blocks in DRC, RRAO, and CVA are similar enough to justify a
small shared module, but the full blocks should not move. Text coercion,
enum-specific errors, citation defaults, source-column-map treatment, and
package validation context still carry component-specific behavior or public
error contracts.

No new ADR is needed for a helper-only module that imports NumPy and stays below
capital package semantics. ADR coverage would be needed if the extraction starts
to define package schemas, regulatory meanings, public batch contracts, or
cross-package validation behavior.

## Evidence

The repeated mechanical helpers are concentrated in:

- `packages/frtb-drc/src/frtb_drc/batch.py` lines 2153-2365
- `packages/frtb-rrao/src/frtb_rrao/batch.py` lines 1340-1665
- `packages/frtb-cva/src/frtb_cva/batch.py` lines 2351-2615

Common patterns:

- length checks over `row_count` and named columns
- object-array construction via `np.asarray(..., dtype=object)` and read-only
  wrapping
- float-array construction with a NumPy fast path and fallback scalar coercion
- optional float arrays defaulting missing values to `np.nan`
- boolean arrays accepting common string spellings and defaulting missing
  columns
- read-only NumPy view/copy mechanics through `setflags(write=False)`

Important differences:

- DRC and RRAO text helpers coerce non-null values with `str(value).strip()`;
  CVA requires actual non-empty strings for required text.
- DRC and RRAO required floats accept `float(value)` broadly; CVA rejects bools
  and non-numeric types before conversion.
- CVA validates one-dimensional NumPy numeric inputs and finite values in its
  fast path; DRC and RRAO currently use a narrower mechanical fast path.
- DRC sorts `source_column_map` pairs after string coercion; RRAO and CVA
  preserve order and require non-empty text.
- DRC has citation-id defaults and validation that do not exist in the same form
  in RRAO or CVA.
- CVA contains EAD sign-convention normalization and duplicate-id checks that
  are not package-neutral array coercion.

## Safe Common Extraction

The follow-up implementation should start with these helpers:

- `readonly_array(array, *, copy)`
- `object_array(values, *, copy)`
- `immutable_object_array(values)`
- `immutable_float_array(values)`
- `float_array_from_numpy(values, *, field, copy, allow_nan, require_1d=True, require_finite=True)`
- `coerce_bool_value(value)`
- `bool_array(values, row_count, *, default, copy)`

Use a common exception such as `BatchArrayCoercionError`. Package modules should
wrap that exception in `DrcInputError`, `RraoInputError`, or `CvaInputError` so
public messages and metadata remain package-local.

## Keep Package-Local

Do not extract these in the first pass:

- `_required_text`, `_optional_text`, and text-array helpers
- enum conversion helpers
- `_freeze_source_column_maps`
- citation/default-citation helpers
- duplicate-id and position/record-id validation helpers
- CVA EAD sign-convention normalization
- RRAO underlying-count optional integer coercion

These helpers either encode package-specific public errors, preserve audit
lineage behavior, or depend on component-specific data contracts.

## Migration Order

1. Add `frtb_common.batch_arrays` with common tests only.
2. Migrate DRC read-only/object/numeric-fast-path/bool mechanics while keeping
   text, enum, citation, and source-column-map helpers local.
3. Migrate RRAO read-only/object/numeric-fast-path/bool mechanics; evaluate its
   nullable bool-object helper after the shared boolean coercer lands.
4. Migrate CVA read-only/object/bool mechanics and numeric fast paths using
   stricter options for one-dimensional finite arrays.

## Validation

For the assessment PR:

- `make quality-control`
- `make docs-check`

For #391 and later migration PRs:

- `packages/frtb-common/tests` for each shared helper
- affected package batch tests for each migrated package
- `make quality-control`
- `make check` for any PR that migrates more than one component
