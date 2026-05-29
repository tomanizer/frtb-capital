# CLAUDE.md — frtb-drc

Review `frtb-drc` as the owner of default risk charge capital only.

The package has a capital-producing partial implementation for
non-securitisation DRC. Unsupported securitisation and CTP paths must still fail
explicitly before producing capital.

Reject silent zero-capital placeholders, sibling capital-package imports,
uncited capital-producing inputs, scoped runs that mix desks or legal entities,
and issuer aggregation shortcuts that would hide missing DRC mechanics.
