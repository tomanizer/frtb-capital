# Regulatory corpus

This directory is the suite-level source register and crosswalk for regulatory
materials used to design, implement, and validate `frtb-capital`.

It is not a legal opinion and does not assert regulatory compliance.

## Scope

The corpus covers:

- Basel / BCBS FRTB source material.
- UK PRA Basel 3.1 / FRTB material.
- EU CRR3 / EBA / ECB material.
- US Fed/OCC/FDIC proposed market-risk material.
- Component-level traceability for IMA, SBM, DRC, RRAO, CVA, and orchestration.

## Design

- `sources.yml` is the canonical source register.
- `crosswalk/*.yml` maps regulatory sources to packages, requirements, code, and tests.
- `regimes/*.yml` captures jurisdiction-specific rule profiles.
- Package-local manifests under `packages/<component>/docs/` may reference this corpus.

## Text policy

Do not vendor full regulatory texts into this repository by default. Store
official source URLs, section hints, status, effective dates, and review notes.
Downloaded PDFs, HTML snapshots, or OCR artifacts belong in `.cache/regulatory/`
or in a separately permissioned evidence store.

## Review workflow

1. Add or update `sources.yml` for regulatory source metadata.
2. Map the source to package requirements in `crosswalk/*.yml`.
3. Capture jurisdiction-specific profile changes in `regimes/*.yml`.
4. Add `@pytest.mark.regulatory_ref(...)` to tests once implementation begins.
5. Run `make regulatory-corpus` before opening a PR.
