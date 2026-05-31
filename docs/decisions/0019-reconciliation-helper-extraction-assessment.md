# 19. Reconciliation helper extraction assessment

Date: 2026-05-31

## Status

Accepted (assessment only — no extraction in this milestone)

## Context

Several capital packages implement small numeric reconciliation helpers and
result-validation routines. Duplication is currently tolerable because each
package documents its own tolerance policy next to regulatory formulae. As more
partial-runtime packages mature, inconsistent tolerance semantics could emerge.

## Inventory

| Package | Helper / pattern | Tolerance policy | Package-specific? |
| --- | --- | --- | --- |
| `frtb-sbm` | `numeric.is_reconciled`, `validate_sbm_result_reconciliation` | `rel_tol=1e-12`, `abs_tol=1e-9` | Yes — risk-class scenario selection branches |
| `frtb-rrao` | `numeric.is_reconciled`, `validate_rrao_result_reconciliation` | `rel_tol=1e-12`, `abs_tol=1e-9` | Yes — classification/allocation subtotals |
| `frtb-cva` | `numeric.is_reconciled`, `validate_cva_result_reconciliation` | same as RRAO | Yes — BA-CVA portfolio formula and SA-CVA buckets |
| `frtb-drc` | `validate_reconciliation` inline `abs` checks | default `1e-12` absolute | Yes — HBR ratio/denominator semantics |
| `frtb-ima` | domain-specific reconciliation (NMRF valuation, capital assembly) | varies by stage | Yes — not a simple total compare |

Observed duplication: the `math.isclose` pair (`rel_tol=1e-12`, `abs_tol=1e-9`)
is copy-pasted in SBM, RRAO, and CVA `numeric.py` modules.

## Decision

**Do not extract to `frtb-common` yet.**

Rationale:

1. Regulatory audit messages and field names differ materially across packages.
2. DRC uses absolute tolerance on heterogeneous structures (HBR, category totals)
   rather than the shared `isclose` helper pattern.
3. Premature shared abstraction would obscure formula-specific reconciliation
   stages called out in audit follow-up [#234](https://github.com/tomanizer/frtb-capital/issues/234).

### Future extraction candidates (when stable)

If a third package adds identical `isclose` tolerances **and** shared tests
prove no package needs a different abs/rel pair, consider:

- `frtb_common.numeric.reconcile_totals(actual, expected, *, rel_tol, abs_tol)`
  returning a boolean only;
- keeping `validate_*_result_reconciliation` functions package-local with named
  audit stages.

Any extraction requires:

- package-local tests unchanged;
- shared tests in `frtb-common` for the boolean helper only;
- ADR update if tolerances diverge by component.

## Consequences

- Copy-paste `numeric.is_reconciled` in SBM/RRAO/CVA remains acceptable for
  now.
- Refactors should split long validation functions into named stages before
  considering shared helpers.
- Package boundary discipline unchanged.

## References

- Issue [#231](https://github.com/tomanizer/frtb-capital/issues/231)
- [`docs/decisions/0012-capital-impact-attribution.md`](0012-capital-impact-attribution.md)
