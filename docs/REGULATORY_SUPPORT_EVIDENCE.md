# Regulatory Support Evidence

This page explains the suite-wide meaning of a support claim in
`frtb-capital`. It applies to all capital packages and to orchestration where
orchestration claims support for combining component outputs.

Outputs from this suite are engineering and validation evidence. They are not
final regulatory capital, legal advice, regulatory submissions, or supervisory
approval.

## The Core Rule

A package may call a regulatory path supported only when the repository can
point to all of the following:

- the documented scope being claimed
- the regulatory anchors for the rule mechanics
- runtime code for that exact scope
- required reference data, policy data, or client-supplied evidence
- deterministic tests or fixtures
- traceability from documentation to code to tests
- fail-closed behavior for unsupported or under-evidenced paths

If any of those pieces is missing, the path is not supported. It may be planned,
partial, out of scope, or explicitly unsupported, but it should not produce a
capital number that looks like a supported result.

## What A Support Box Means

Many package docs use support matrices. A single table entry is a support box.
Some code and review comments call the same thing a support cell. It means one
specific combination of scope dimensions for a package.

The dimensions differ by package:

- IMA: rule profile, desk/model eligibility state, and calculation component
  such as ES, IMCC, RFET, PLA, backtesting, SES, or capital assembly
- SBM: rule profile, risk class, and risk measure
- DRC: rule profile and DRC risk class
- RRAO: rule profile and residual-risk classification path
- CVA: rule profile, method, and where relevant SA-CVA risk class and measure
- Orchestration: jurisdiction-family routing, component handoff, SA
  composition, IMA fallback, CVA inclusion, and top-of-house aggregation

The word "box" does not change the control standard. It is just a plain-English
name for one support claim that can be checked.

## What Supported Means

Supported means the package has enough documented, implemented, and tested
evidence to calculate that path without guessing or silently substituting a
different rule.

A supported path must have:

- a public or package-owned entrypoint that reaches the intended calculation
- cited policy or regulatory mechanics at the point where they enter the code
  or docs
- explicit input requirements and rejection rules
- deterministic output ordering and audit metadata where the result contributes
  to capital, attribution, reconciliation, or storage
- tests for the supported path
- tests for at least the material ways the same path can become unsupported or
  invalid

Support is scoped. A package can be implemented overall while still having
unsupported boxes inside a wider matrix. A package can also be partial while
having some boxes that are supported.

## What Fail Closed Means

Fail closed means the suite refuses to calculate when required support or
evidence is missing.

It does not:

- silently return zero capital
- silently fall back to Basel, U.S., EU, or PRA treatment from another profile
- use placeholder regulatory parameters
- ignore missing reference data
- treat an unsupported sub-feature as if it were supported

Instead, the runtime raises a typed unsupported-feature or input-validation
error, or records an explicit unsupported/residual state for non-capital
attribution and impact analysis where a number can still reconcile without
claiming exact regulatory decomposition.

Fail-closed behavior is part of the control design. It prevents incomplete
support from being hidden inside an ordinary-looking capital result.

## What Counts As Evidence

The evidence for a support claim normally comes from these surfaces:

- package or module README status text
- public API docs and package journey docs
- support matrices or profile-status helpers
- regulatory requirement docs and crosswalk YAML files
- package-local policy data with citation ids
- deterministic fixtures and golden expected outputs
- public API, batch, unsupported-path, audit, replay, attribution, and
  fixture-workflow tests
- `docs/quality/package_maturity.toml`
- generated maturity and crosswalk dashboard:
  [`docs/quality/PACKAGE_STATUS.md`](quality/PACKAGE_STATUS.md)

Evidence is not a single document. The claim is credible only when the docs,
runtime code, tests, and citations agree.

## How To Audit A Support Claim

Use this review path for any package:

1. Identify the exact support box being claimed.
2. Check the owning package or module docs for the stated status.
3. Check regulatory anchors in requirement docs, crosswalk files, policy data,
   or model documentation.
4. Check the runtime gate or public entrypoint that accepts or rejects the
   requested path.
5. Check tests and fixtures for both the supported path and unsupported-path
   behavior.
6. Check package maturity evidence if the support claim affects maturity,
   validation status, or release notes.

Rule of thumb: if the repository cannot point to docs, code, tests, and
citations, the path is not supported.

## Package Examples

DRC `EU_CRR3` securitisation non-CTP is a support box. The package needs
Article 325z and Article 325aa anchors, a row and batch route, typed
risk-weight evidence where required, tests, and fail-closed behavior when that
evidence is missing.

SBM `EU_CRR3` GIRR vega is a support box. The package needs the cited CRR3
GIRR vega mechanics, mapped tenors and risk weights, runtime routing for the
profile/risk-class/measure combination, tests, and fail-closed behavior for
unsupported non-delivered boxes.

CVA full BA-CVA is a support box. The package needs cited MAR50 mechanics,
method-specific inputs, hedge and counterparty evidence, deterministic fixtures,
and fail-closed behavior for unsupported materiality or comparison-profile
paths.

Orchestration support is also scoped. A suite-level aggregation claim needs
component summaries from supported component paths, jurisdiction-family guards,
SA composition evidence, tests, and explicit failure behavior for incompatible
or missing component outputs.

## What This Does Not Prove

This evidence does not prove legal interpretation, supervisory approval,
production market-data quality, operational readiness, or firm-specific model
approval. It proves only that the repository has an explicit, cited,
deterministic engineering basis for the support it claims.
