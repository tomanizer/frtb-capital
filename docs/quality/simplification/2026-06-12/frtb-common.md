# frtb-common simplification audit

Date: 2026-06-12  
Audit-only - no runtime code changes in this report.

## Scope

`frtb-common` owns package-neutral mechanics used by the capital packages: hashing, serialization, Arrow table helpers, batch-array coercion, contribution records, status errors, and regulatory citation helpers. It must not absorb component-specific risk weights, buckets, profiles, formulas, or unsupported-feature semantics.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `frtb_common/crif.py` | 1306 | Remaining suite-level monolith; CRIF normalization has multiple parsing and Arrow handoff responsibilities. |
| `frtb_common/arrow_table.py` | 598 | Arrow handoff hashing/diagnostics surface; acceptable but close to future split threshold. |
| `frtb_common/arrow_conversion.py` | 564 | Shared Arrow-to-NumPy conversion mechanics; should stay common. |
| `frtb_common/batch_arrays.py` | 456 | Shared coercion mechanics now used by package adapters. |

## Duplicated code

- `package-local`, P1: exact `as_dict`/enum-coercion shapes remain duplicated between common records and some package result records. Use `dataclass_as_dict` style helpers where no component semantics are involved.
- `audit-only`, P2: `crif.py` contains enough internal stages that future CRIF changes will be hard to review if it keeps growing.

## Dead or storage-only code

- No high-confidence dead-code finding in the changed-code dead-code guard.

## `frtb-common` candidates

| Finding | Scope | Priority |
| --- | --- | --- |
| Shared hash wrappers still duplicated in CVA/DRC/RRAO | `frtb-common` | P1 |
| Shared optional/required text array coercion still duplicated in CVA/DRC/RRAO | `frtb-common` | P1 |
| Simple enum coercion / dataclass `as_dict` mechanics | `frtb-common` | P2 |

## Package-local factoring candidates

- Split `crif.py` by normalization stages only if the split improves reviewability without changing the public CRIF table contract.

## Over-complexity

- `normalize_crif_arrow_table` and its static-mapping helper remain large functions in the code-drift report.

## Wrappers and readability

- Keep compatibility exports small and explicit when moving common CRIF internals; avoid a new forwarding matrix.

## What must not move

- Component-specific CRIF interpretations, regulatory classifications, risk weights, and package rejection semantics must remain in owning packages.

## Recommended sequence

1. Burn down package-neutral shared mechanics under #899.
2. If needed, split `frtb_common.crif` into package-neutral parser, normalization, and Arrow-output helpers under a separate common-only PR.
3. Re-run source duplicate scan and import-lint before moving any consumer code.

## Validation required

- `uv run pytest packages/frtb-common/tests`
- `make drift-check`
- `make changed-code-check`
- `make quality-control`

## Tracking

GitHub issue: [#899](https://github.com/tomanizer/frtb-capital/issues/899)
