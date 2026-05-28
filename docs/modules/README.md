# FRTB Module Planning Documents

This directory holds documentation-only module plans for capital components that
are not yet implemented on `main`. The files are deliberately outside
`packages/` so the `uv` workspace glob `packages/*` is not changed until a real
package manifest is added.

For market risk Standardised Approach, SA is the composed total `SBM + DRC +
RRAO` under Basel MAR20.4. The implementation taxonomy therefore uses three
planned component packages: `frtb-sbm`, `frtb-drc`, and `frtb-rrao`.

| Module | Regulatory requirements | PRD | Workable requirements |
| --- | --- | --- | --- |
| SBM | [frtb-sbm/REGULATORY_REQUIREMENTS.md](frtb-sbm/REGULATORY_REQUIREMENTS.md) | [frtb-sbm/PRD.md](frtb-sbm/PRD.md) | [frtb-sbm/requirements/BASEL_FRTB_SBM.yml](frtb-sbm/requirements/BASEL_FRTB_SBM.yml) |
| DRC | [frtb-drc/REGULATORY_REQUIREMENTS.md](frtb-drc/REGULATORY_REQUIREMENTS.md) | [frtb-drc/PRD.md](frtb-drc/PRD.md) | [frtb-drc/requirements/BASEL_FRTB_DRC.yml](frtb-drc/requirements/BASEL_FRTB_DRC.yml) |
| RRAO | [frtb-rrao/REGULATORY_REQUIREMENTS.md](frtb-rrao/REGULATORY_REQUIREMENTS.md) | [frtb-rrao/PRD.md](frtb-rrao/PRD.md) | [frtb-rrao/requirements/BASEL_FRTB_RRAO.yml](frtb-rrao/requirements/BASEL_FRTB_RRAO.yml) |
| CVA | [frtb-cva/REGULATORY_REQUIREMENTS.md](frtb-cva/REGULATORY_REQUIREMENTS.md) | [frtb-cva/PRD.md](frtb-cva/PRD.md) | [frtb-cva/requirements/BASEL_FRTB_CVA.yml](frtb-cva/requirements/BASEL_FRTB_CVA.yml) |

## Research Sources

The documents use these primary references:

- Basel MAR20, standardised approach structure:
  https://www.bis.org/basel_framework/chapter/MAR/20.htm
- Basel MAR21, sensitivities-based method:
  https://www.bis.org/basel_framework/chapter/MAR/21.htm
- Basel MAR22, default risk capital:
  https://www.bis.org/basel_framework/chapter/MAR/22.htm
- Basel MAR23, residual risk add-on:
  https://www.bis.org/basel_framework/chapter/MAR/23.htm
- Basel MAR50, CVA framework:
  https://www.bis.org/basel_framework/chapter/MAR/50.htm
- U.S. NPR 2.0 / Federal Register 91 FR 14952:
  https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959
- CRR3 Regulation (EU) 2024/1623:
  https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng
- EBA residual risk add-on RTS:
  https://www.eba.europa.eu/legacy/regulation-and-policy/regulatory-activities/market-counterparty-and-cva-risk/regulatory-2?version=2021
- Commission Delegated Regulation (EU) 2022/2328:
  https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32022R2328

The local reference implementation used for design inspiration is the external
`extract_cva` capital navigator implementation. It is not part of this
repository.

That implementation is treated as an implementation reference only. Regulatory
requirements in these documents are sourced from Basel, U.S. NPR, CRR3, and EBA
references.
