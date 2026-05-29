# Regulatory corpus policy

## Purpose

The corpus supports model development, validation, auditability, and cross-checking.
It is not a substitute for legal interpretation, compliance sign-off, model
validation, or supervisory approval.

## Source hierarchy

Use the following precedence when implementing a jurisdictional profile:

1. Binding local rule text and local supervisory statements.
2. Local regulator policy statements, final rules, RTS/ITS, or instructions.
3. Basel standards and explanatory notes.
4. Consultation papers and proposals, clearly tagged as non-final.
5. Industry examples, challenger code, and educational material.

## Source status values

Allowed `status` values:

- `final_rule`
- `in_force`
- `baseline_standard`
- `supervisory_expectation`
- `technical_standard`
- `consultation`
- `proposed_rule`
- `near_final`
- `historical`
- `challenger_reference`
- `placeholder`

## Repo text policy

The committed repository should normally contain links, metadata, section hints,
and short notes only. Full PDFs and long extracted text should not be committed
unless legal/reuse review explicitly approves it.

## Review rule

Any change to:

- rule formulas,
- jurisdictional parameters,
- effective dates,
- regulatory status,
- or source precedence

requires either an ADR or a material-change note in the relevant component
documentation.
