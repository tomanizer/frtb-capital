# FRTB-DRC

**Prototype FRTB Default Risk Charge (DRC) capital calculator.**

> ⚠️ Prototype only. Not for regulatory reporting. U.S. NPR 2.0, Basel MAR22,
> CRR3, and PRA references are proposed-rule or comparison material.
> Outputs are not final regulatory capital.

## What this is

A Python prototype demonstrating the FRTB Default Risk Charge (DRC) calculation path:

- Issuer-level JTD (jump-to-default) exposure inputs
- Regulatory risk weights (BCBS, CRR2, FRB/NPR 2.0, PRA) including FRB-specific buckets
  (NON_US_SOVEREIGNS, PSE_GSE_DEBT) and IG/SG/SSG credit quality
- Seniority-based netting (no cross-seniority offset within issuer)
- Bucket-level aggregation with hedging benefit
- Full audit decomposition (per-issuer, per-seniority, per-bucket marginals)
- CRIF column mapping compatibility (from reference reconstruction)

The package follows the exact style and engineering standards of `frtb-ima`:
frozen dataclasses + enums, pure functional helpers, numpy only, deterministic
tests, explicit regulatory citations, and SR 11-7-ready audit records.

**Current status (Issue #25 complete baseline):** Core data models, reference
risk-weight tables + `get_risk_weight()`, Position dataclass, basic validation.
JTD netting, bucket aggregation, full capital, CRIF loader, and securitisation
paths are under active implementation in the chained issues #26–#32.

## Install

From the monorepo root:

```bash
uv sync
```

Then:

```bash
uv run python -c "import frtb_drc; print(frtb_drc.__version__)"
uv run python -c "
from frtb_drc import get_risk_weight
from frtb_drc.data_models import RulesVersion
print(get_risk_weight('NON_US_SOVEREIGNS', 'IG', RulesVersion.FRB))
"
```

## Run tests

```bash
uv run pytest packages/frtb-drc
```

From inside the package dir after `make install`:

```bash
make check
```

## Package layout (target)

```
packages/frtb-drc/src/frtb_drc/
    data_models.py          Enums + frozen Position / Netted* dataclasses
    reference_data.py       RW tables, LGD, get_risk_weight, load_reference_data
    jtd.py                  Gross JTD + seniority netting (#26)
    aggregation.py          Bucket DRC + hedging benefit (#27)
    crif.py                 CRIF rename + position construction (#28)
    capital.py              Full DRCResult assembly (#29)
    audit.py                Audit records + NDJSON (#29)
    logging.py              Structured logging
    demo_data.py            Synthetic credit book generator
```

## Regulatory citations (key)

- Basel Committee: *Minimum capital requirements for market risk* (Jan 2019),
  MAR22 (Default risk capital requirement) — all paragraphs.
- U.S. NPR 2.0 (91 FR 14952, 27 Mar 2026), section __.212 and FRB appendix.
- EU CRR3 Articles 325ba–325bk.
- See `docs/REGULATORY_TRACEABILITY.md` for full mapping.

## Reference implementation

Logic and tables cross-checked against the video-derived reconstruction in
`drc.zip` (non-production). Exact numerical parity is asserted in tests for
all supported regimes and FRB (NON_US_SOVEREIGNS / PSE_GSE_DEBT / IG-SG-SSG)
combinations.

## Next steps

See GitHub issues #25 (done) through #32 for the remaining implementation
slices. All work is performed via draft PRs that are merged only after
review against the CLAUDE.md / AGENTS.md checklist.

## License

MIT (same as frtb-ima).
