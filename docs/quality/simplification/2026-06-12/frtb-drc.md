# frtb-drc simplification audit

Date: 2026-06-12  
Audit-only - no runtime code changes in this report.

## Scope

`frtb-drc` owns DRC non-securitisation, securitisation non-CTP, and CTP behavior. The #718 wave is now materially complete: adapters, validation, kernel, assembly, registry, and citation table splits exist, and every runtime source file is below 800 LOC.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `frtb_drc/reference_data.py` | 798 | Under the stage target but at the ceiling. |
| `frtb_drc/kernel/ctp.py` | 792 | Under the stage target; avoid adding new responsibilities. |
| `frtb_drc/attribution.py` | 791 | Under the stage target; attribution projection remains dense. |
| `frtb_drc/kernel/securitisation.py` | 753 | Under the stage target. |
| `frtb_drc/batch.py` | 713 | Public batch orchestration remains; not a monolith by old baseline. |

## Duplicated code

- `package-local`, P1: `_sorted_indices` is duplicated across `assembly/fair_value_cap.py`, `assembly/hashes.py`, `batch.py`, and `kernel/net_jtd.py`.
- `package-local`, P1: `_zero_nonsec_category` exists in both batch and row-kernel paths. This is the remaining row/batch bridge seam after the audit-preserving #718 decision.
- `frtb-common`, P1: `_text_array_with_default`, `_optional_text_array`, `hash_payload`, enum coercion, and `as_dict` shapes overlap with other packages.

## Dead or storage-only code

- `ctp.py`, `securitisation.py`, and `arrow_batch.py` are tiny compatibility import paths. Keep until a deliberate public surface trim.

## `frtb-common` candidates

| Finding | Scope | Priority |
| --- | --- | --- |
| Hash wrapper mechanics | `frtb-common` | P1 |
| Batch text-array coercion mechanics | `frtb-common` | P1 |
| Enum coercion mechanics | `frtb-common` | P2 |

## Package-local factoring candidates

- A local sorted-index helper can remove four exact DRC duplicates without changing formulas.
- Keep the row public API as an audit-preserving adapter over extracted kernels unless a future ADR changes row audit payloads.

## Over-complexity

- Large functions remain in `adapters/positions.py`, `batch.py`, `capital.py`, `kernel/net_jtd.py`, and `scaffold.py`, but the remaining code is stage-separated enough for review.

## Wrappers and readability

- Compatibility shims are short and acceptable. Do not add new per-path wrapper matrices.

## What must not move

- HBR, seniority, securitisation evidence gates, risk-weight evidence, fair-value-cap behavior, and rejected-offset semantics remain DRC-local.

## Recommended sequence

1. Use #899 for shared mechanics and the local sorted-index helper.
2. Use #897 only if DRC files grow past the 800-line ceiling again.
3. Keep #718 closed unless a future issue proposes an audit-preserving shared internal row/batch execution object.

## Validation required

- `uv run pytest packages/frtb-drc/tests`
- `make drift-check`
- `make changed-code-check`
- `make quality-control`

## Tracking

GitHub issue: [#899](https://github.com/tomanizer/frtb-capital/issues/899)
