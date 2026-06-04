# DRC EU CRR3 Non-Securitisation v1

Deterministic synthetic fixture for the `EU_CRR3` non-securitisation vertical
slice. It uses only CRR3-valid non-securitisation bucket keys and seniority
classes.

| Position | Case | Citation focus |
| --- | --- | --- |
| `eu-corp-alpha-long`, `eu-corp-alpha-short` | Same-obligor senior-debt offset under Article 325x. | `EU_CRR3_ARTICLE_325X` |
| `eu-corp-beta-short` | Residual corporate short used in the Article 325y HBR bucket formula. | `EU_CRR3_ARTICLE_325Y_3_5` |
| `eu-sovereign-long` | Sovereign CQS 2 risk weight. | `EU_CRR3_ARTICLE_325Y_1_2`, `EU_CRR3_ECAI_CQS_MAPPING` |
| `eu-muni-short-maturity` | Article 325x maturity floor for local government / municipal exposure. | `EU_CRR3_ARTICLE_325X` |
