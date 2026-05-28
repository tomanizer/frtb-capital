# CLAUDE.md — frtb-drc

Review `frtb-drc` as the owner of default risk charge capital only.

Until implementation starts, accepted behavior is explicit
`NotImplementedCapitalComponentError`. Reject silent zero-capital placeholders,
sibling capital-package imports, and issuer aggregation shortcuts that would
hide missing DRC mechanics.
