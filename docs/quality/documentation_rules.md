# Documentation rules

This repository uses docstrings as part of its quality-control and auditability
surface. The rule is not "add prose everywhere"; the rule is to make package
boundaries, public contracts, and domain-significant calculation logic legible
without forcing readers to reconstruct intent from implementation details.

These rules apply to runtime Python code under `packages/*/src`. Tests,
notebooks, validation scripts, and one-off research code may follow the same
style, but the initial quality gate is intended for package runtime code.

## Module Docstrings

Every runtime package module should start with a module docstring. It should
explain:

- the role the file plays in the package;
- what kind of logic belongs in the file;
- why the file exists at this package boundary;
- any important regulatory, audit, attribution, or handoff behavior the module
  owns.

Good module docstrings describe purpose and ownership:

```python
"""Bucket-level SBM aggregation for GIRR delta sensitivities.

This module converts validated GIRR delta sensitivities into bucket capital and
scenario audit records. It owns the MAR21 bucket correlation application for
GIRR delta and leaves CRIF parsing to adapter modules.
"""
```

Low-value module docstrings only restate the filename:

```python
"""GIRR delta aggregation."""
```

## Public API Docstrings

Public functions, classes, and methods require meaningful docstrings. Treat an
object as public when it is:

- exported from a package `__init__.py`;
- referenced by `docs/quality/package_maturity.toml`;
- a calculation, validation, configuration, result, audit, or handoff entry
  point used across modules;
- a non-underscore top-level object that callers are expected to import.

Public callable docstrings should use the NumPy convention when they accept
arguments, return meaningful values, or raise domain-significant exceptions.
Use sections only when they add information.

```python
def calculate_bucket_capital(
    sensitivities: Sequence[WeightedSensitivity],
    correlations: CorrelationSet,
) -> BucketCapital:
    """Aggregate weighted sensitivities into one bucket capital result.

    Applies the bucket-level correlation matrix and preserves deterministic
    intermediate totals for later attribution and audit replay.

    Parameters
    ----------
    sensitivities : Sequence[WeightedSensitivity]
        Weighted sensitivities that have already passed risk-factor and bucket
        validation.
    correlations : CorrelationSet
        Correlation parameters for the active regulatory profile.

    Returns
    -------
    BucketCapital
        Bucket capital with the intermediate sums required for audit records.

    Raises
    ------
    UnsupportedRegulatoryFeatureError
        If the selected profile does not define the required correlation set.
    """
```

Class docstrings should explain the contract represented by the type, not every
field. Field-level comments or dataclass field metadata are appropriate only
when a field has non-obvious units, regulatory meaning, or compatibility
constraints.

## Private Helpers

Private helpers need docstrings when they carry domain meaning. Add a docstring
to a private function or method that:

- interprets a regulatory paragraph or profile switch;
- aggregates, buckets, nets, scales, floors, or caps capital inputs;
- validates unsupported-feature boundaries;
- creates or transforms audit records, stable identifiers, attribution records,
  or capital-impact branches;
- normalizes handoff data in a way that affects calculation semantics.

Tiny local helpers may remain undocumented when their role is obvious from the
name, type hints, and nearby call site. For example, a local `_sort_key()`,
`_as_tuple()`, or `_is_blank()` helper usually does not need a docstring unless
it encodes a domain rule.

## Meaningful Content

Docstrings should answer why the object exists and what behavior matters to a
caller or reviewer. Avoid text that merely repeats the object name.

Poor:

```python
def calculate_capital(...):
    """Calculate capital."""
```

Better:

```python
def calculate_capital(...):
    """Aggregate bucket capital into the SBM risk-class total.

    Applies the configured inter-bucket correlation scenario and keeps the
    selected scenario in the result so audit replay can reproduce the capital
    number.
    """
```

When a function implements regulatory behavior, cite the specific paragraph in
the function or module docstring if the citation is not already obvious from a
nearby policy object or test fixture. Do not use generic framework references
as a substitute for paragraph-level traceability.

## Automation Rollout

The repository should enforce these rules in stages:

1. document the standard in this file and point agents and contributors here;
2. add an AST-based inventory checker in report mode;
3. commit an initial baseline of existing findings;
4. fail CI only on newly introduced missing module or public API docstrings;
5. ratchet stricter checks after false positives are understood.

The checker should be conservative about public/private classification. It
should not force blanket docstrings on every private helper, and it should not
turn subjective quality judgement into a hard gate until the findings are
stable enough to review consistently.
