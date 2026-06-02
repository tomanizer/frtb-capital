# CLAUDE.md — frtb-rrao

Review `frtb-rrao` as the owner of residual risk add-on capital only.

The package has an implemented v1 canonical-input calculation path for Basel
MAR23, U.S. NPR 2.0 proposed section `__.211`, and the EU CRR3 Article 325u
comparison profile. Reviewers should verify that supported inputs produce cited
line add-ons and zero-capital exclusion records, while PRA UK CRR, unmapped
profile features, ambiguous evidence, and unsupported adapter paths fail
explicitly before a capital result is emitted.

Reject silent zero-capital placeholders, sibling capital-package imports,
free-form residual-risk classification shortcuts, and any documentation claim
that treats U.S. NPR 2.0 output as final regulatory capital.
