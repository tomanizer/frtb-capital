# CLAUDE.md — frtb-drc

Review `frtb-drc` as the owner of default risk charge capital only.

The package has a capital-producing partial implementation for U.S. NPR 2.0
non-securitisation, securitisation non-CTP, and correlation trading portfolio
(CTP) DRC row and batch paths, plus Basel MAR22 non-securitisation row and
batch paths and Basel MAR22 securitisation non-CTP row and batch paths. Basel
MAR22 CTP, EU CRR3, and PRA UK CRR paths must fail explicitly until cited
profile mappings and deterministic tests exist.

Reject silent zero-capital placeholders, sibling capital-package imports,
uncited capital-producing inputs, scoped runs that mix desks or legal entities,
and issuer aggregation shortcuts that would hide missing DRC mechanics.
