# Arrow Conversion Migration Notes

Issue: #379

## Shared Helper Boundary

`frtb-common` now owns package-neutral Arrow-to-NumPy mechanics used by handoff
adapters:

- object-array decoding, including dictionary arrays and Arrow nulls
- float64 casting from numeric Arrow columns
- optional float null filling
- boolean null filling

Capital packages still own package-specific schemas, required/optional column
rules, regulatory batch construction, and package-local exception types. Kernels
must continue to receive NumPy arrays and must not import Arrow.

## First Migration

`frtb-drc` now delegates duplicated object and float conversion internals to the
shared helpers. Its DRC wrappers still raise `DrcInputError`, enforce required
columns, freeze returned arrays, and keep DRC's local boolean behavior.

## Remaining Differences

- DRC, RRAO, and CVA boolean adapters differ for non-boolean input. The common
  helpers expose both strict boolean conversion and bool-or-object fallback, but
  package migration should verify existing behavior before replacing local code.
- RRAO and CVA already preserve integer nulls as `None`; the common object
  helper follows that behavior.
- IMA has date/string conversion requirements that are not covered by this
  helper set.
- SBM has broader handoff-specific aggregation mechanics. Only pure conversion
  steps should move to `frtb-common`.

## Repeatable Follow-Up

For each future package migration:

1. Replace only pure conversion functions with `frtb_common` helpers.
2. Keep package-level schema and regulatory construction local.
3. Preserve package exception messages at wrapper boundaries.
4. Run the affected package handoff tests plus `make quality-control`.
