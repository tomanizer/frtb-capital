# DRC Regulatory Support Evidence

This page applies the suite-wide
[`REGULATORY_SUPPORT_EVIDENCE.md`](../../REGULATORY_SUPPORT_EVIDENCE.md)
standard to `frtb-drc`. It explains, in plain language, how DRC decides whether
a regulatory path is supported, what evidence backs that claim, and what
happens when evidence is missing.

Outputs are engineering and validation evidence for the implemented package.
They are not final regulatory capital, legal advice, or supervisory approval.

## What A DRC Support Box Means

The DRC package has several rule profiles, such as `US_NPR_2_0`,
`BASEL_MAR22`, `EU_CRR3`, and `PRA_UK_CRR`. Each profile can be combined with
one DRC risk class:

- non-securitisation
- securitisation non-CTP
- correlation trading portfolio, or CTP

The support matrix is a table of these combinations. A single table entry is a
support box. Code types such as `DrcProfileSupportCell` call the same thing a
support cell, but the meaning is simply one profile plus one DRC risk class.

For example, `EU_CRR3` plus securitisation non-CTP is one support box.
`PRA_UK_CRR` plus CTP is another support box.

## What Supported Means

Supported means the package has enough documented, implemented, and tested
evidence to calculate that path without guessing.

For a DRC support box to be treated as supported, the package must have:

- a known rule profile and DRC risk class
- runtime code that routes that profile and risk class to the right calculation
- explicit regulatory anchors, such as CRR3 Article 325z and Article 325aa for
  securitisation non-CTP, or Article 325ab, Article 325ac, and Article 325ad for
  CTP
- required reference-data or evidence inputs, such as typed risk-weight evidence
  where securitisation or CTP rules need it
- deterministic synthetic tests or fixtures that exercise the path
- traceability from docs to code to tests

The current profile support table is
[`PROFILE_SUPPORT_MATRIX.md`](PROFILE_SUPPORT_MATRIX.md). The regulatory
crosswalk is
[`docs/regulatory/crosswalk/frtb-drc.yml`](../../regulatory/crosswalk/frtb-drc.yml).

## What Fail Closed Means

Fail closed means the package refuses to calculate when required support or
evidence is missing.

It does not:

- silently return zero capital
- silently fall back to another profile
- use a placeholder risk weight
- treat an unsupported path as if it were supported

Instead, the runtime raises a typed error, such as
`UnsupportedRegulatoryFeatureError`, or a validation error for missing required
inputs. This is intentional. A missing support claim should be visible to the
caller and to review, not hidden inside a capital number.

The fail-closed behavior is part of the supported design, not a temporary
defect. It protects the package from producing numbers that appear more
complete than the evidence allows.

## What Counts As Evidence

The support claim is backed by several kinds of evidence.

1. The support matrix states which profile and risk-class combinations are
   supported.

2. The regulatory traceability page maps major mechanics to regulatory anchors,
   code modules, and tests.

3. The runtime gate in
   [`packages/frtb-drc/src/frtb_drc/regimes.py`](../../../packages/frtb-drc/src/frtb_drc/regimes.py)
   checks whether the selected profile and risk class are supported before
   calculation continues.

4. Synthetic fixtures and tests exercise the supported paths. These include
   non-securitisation, securitisation non-CTP, CTP, EU CRR3, PRA UK CRR, public
   API, Arrow batch, and fail-closed cases.

5. The quality registry records the package maturity evidence and required test
   coverage for the DRC package.

The main evidence entrypoints are:

- [`PROFILE_SUPPORT_MATRIX.md`](PROFILE_SUPPORT_MATRIX.md)
- [`REGULATORY_TRACEABILITY.md`](REGULATORY_TRACEABILITY.md)
- [`REGULATORY_ASSUMPTIONS.md`](REGULATORY_ASSUMPTIONS.md)
- [`packages/frtb-drc/tests/test_drc_regimes.py`](../../../packages/frtb-drc/tests/test_drc_regimes.py)
- [`packages/frtb-drc/tests/test_drc_public_api.py`](../../../packages/frtb-drc/tests/test_drc_public_api.py)
- [`docs/quality/package_maturity.toml`](../../quality/package_maturity.toml)

## Example: EU CRR3 Securitisation Non-CTP

For `EU_CRR3` securitisation non-CTP, support means the package has a specific
row and batch path for that profile and class, cites Article 325z and Article
325aa, requires typed risk-weight evidence where needed, and has tests covering
the path.

If the caller supplies the required profile, class, positions, and evidence, the
calculation can proceed. If required risk-weight evidence is missing, stale, or
invalid, the package fails closed instead of using a substitute value.

## Example: PRA UK CRR CTP

For `PRA_UK_CRR` CTP, support means the package has a specific row and batch
path for that profile and class, cites Article 325ab, Article 325ac, and Article
325ad, requires typed CTP risk-weight and decomposition evidence where needed,
and has tests covering the path.

If the required evidence is incomplete, the calculation does not proceed as a
supported PRA UK CRR CTP calculation.

## How To Audit A Support Claim

To check whether a support claim is real, use this review path:

1. Find the profile and risk class in
   [`PROFILE_SUPPORT_MATRIX.md`](PROFILE_SUPPORT_MATRIX.md).
2. Check that the matrix entry has the expected support status and citations.
3. Check [`REGULATORY_TRACEABILITY.md`](REGULATORY_TRACEABILITY.md) and the
   [`crosswalk`](../../regulatory/crosswalk/frtb-drc.yml) for mapped code and
   tests.
4. Check that the cited tests cover the path and expected fail-closed behavior.
5. Check the [`maturity registry`](../../quality/package_maturity.toml) if the
   support claim is used as package maturity evidence.

Rule of thumb: if the package cannot point to docs, code, tests, and citations,
the path is not supported.

## What This Does Not Prove

This evidence does not prove supervisory approval, legal interpretation,
production market-data quality, or firm-specific implementation readiness. It
only proves that the package has an explicit, cited, deterministic engineering
basis for the supported DRC paths it claims.
