# DRC PRA UK CRR Non-Securitisation v1

Deterministic synthetic fixture for the `PRA_UK_CRR` non-securitisation
vertical slice. It uses PRA UK CRR Article 325w, Article 325x, and Article
325y citation ids for LGD, maturity, netting, bucket, risk-weight, HBR, and
category evidence.

| Position | Case | Citation focus |
| --- | --- | --- |
| `pra-corp-alpha-long`, `pra-corp-alpha-short` | Same-obligor senior-debt offset under Article 325x. | `PRA_DRC_ARTICLE_325X` |
| `pra-corp-beta-short` | Residual corporate short used in the Article 325y HBR bucket formula. | `PRA_DRC_ARTICLE_325Y` |
| `pra-sovereign-long` | Sovereign CQS 2 risk weight. | `PRA_DRC_ARTICLE_325Y` |
| `pra-muni-short-maturity` | Article 325x maturity floor for local government / municipal exposure. | `PRA_DRC_ARTICLE_325X` |
