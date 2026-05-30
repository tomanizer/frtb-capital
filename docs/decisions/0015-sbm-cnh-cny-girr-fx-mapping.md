# 15. SBM CNH/CNY GIRR and FX currency mapping

Date: 2026-05-30

## Status

Accepted

## Context

Claude audit FINDING-4 flagged an ambiguity in `frtb-sbm` reference data: GIRR
bucket 8 was labeled `CNH` while the Basel MAR21 FX specified-currency list
(MAR21.88) uses `CNY`. A firm booking onshore renminbi (`CNY`) GIRR sensitivities
could not map cleanly to the current registry, and the split between onshore and
offshore renminbi was undocumented.

Regulatory anchors:

- **MAR21.41** — each currency is a separate delta GIRR bucket; all risk factors
  on risk-free yield curves for the same currency denomination group into that
  bucket.
- **MAR21.8(c)** — onshore and offshore currency curves (for example onshore
  Indian rupee versus offshore Indian rupee) are **different curves** when
  constructing GIRR risk-free yield curves.
- **MAR21.14(4)** — no distinction is required between onshore and offshore
  variants of a currency for FX delta, vega, and curvature risk factors; Basel
  FAQ confirms this extends to deliverable/non-deliverable variants.
- **MAR21.88** — Basel specified FX currency pairs use **USD/CNY**, not CNH.

The prototype's phase-1 GIRR registry is a finite supported-currency list, not
the full set of all possible ISO codes. Unsupported currencies must continue to
fail closed at lookup.

## Decision

1. **GIRR (delta and vega)** — treat **CNY** and **CNH** as **separate GIRR
   buckets** in the BASEL_MAR21 profile registry:
   - bucket `8` → `CNY` (onshore renminbi curve denomination);
   - bucket `17` → `CNH` (offshore renminbi curve denomination).

   Upstream systems must supply the curve denomination that matches MAR21.8(c).
   Intra-bucket aggregation uses separate onshore/offshore curves within the
   same currency bucket only when both curves share one bucket code; here CNY and
   CNH are distinct buckets because they are distinct market currency codes.

2. **FX delta** — map **CNH to CNY** at the FX bucket lookup boundary via
   `normalise_fx_delta_currency_code`, reflecting MAR21.14(4) and the MAR21.88
   specified-pair list. FX `bucket` and `risk_factor` must both normalise to the
   same canonical code after normalisation.

3. **Citations** — retain `basel_mar21_38` on the GIRR bucket registry row as
   the package's historical registry key, but treat **MAR21.41** as the
   regulatory basis for one-currency-one-bucket assignment. Document MAR21.8(c),
   MAR21.14(4), and MAR21.88 in traceability notes for cross-class behaviour.

4. **No silent merge** — do not aggregate CNY and CNH GIRR buckets. Inter-bucket
   GIRR correlation remains the uniform MAR21.50 parameter (50%) between all
   currency buckets, including CNY versus CNH.

## Consequences

- BASEL_MAR21 `profile_hash` changes when the GIRR bucket registry updates.
- Existing synthetic fixtures that omit CNH/CNY are unchanged numerically.
- Callers with offshore RMB GIRR must use bucket `17` / currency `CNH`; onshore
  RMB uses bucket `8` / currency `CNY`.
- FX adapters may pass `CNH`; the kernel normalises to the `CNY` FX bucket.
- Future CRIF adapters must document CNH/CNY mapping in lineage metadata.
- If national implementation text prescribes a different onshore/offshore split,
  update this ADR and the profile registry in the same PR.

## References

- Basel Framework MAR21.8(c), MAR21.14(4), MAR21.41, MAR21.45, MAR21.50,
  MAR21.88 — https://www.bis.org/basel_framework/chapter/MAR/21.htm
- OSFI CAR 2026 Chapter 9 (Basel MAR21 transposition), FX/GIRR cross-refs.
- `packages/frtb-sbm/src/frtb_sbm/reference_data.py`
- `packages/frtb-sbm/docs/REGULATORY_ASSUMPTIONS.md`
- Claude audit FINDING-4 (CNH/CNY bucket ambiguity).
