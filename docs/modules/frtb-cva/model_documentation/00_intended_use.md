# Intended Use

## Model Purpose

`frtb-cva` calculates Credit Valuation Adjustment capital for supported Basel
MAR50 CVA paths from prepared counterparty, netting-set, hedge, and sensitivity
inputs. It is an ex-post capital component; it does not simulate exposures,
price derivatives, source market data, approve SA-CVA use, or perform
firm-level capital aggregation.

## Supported Scope

The current partial runtime supports:

- reduced BA-CVA and full BA-CVA under MAR50.14-MAR50.26;
- SA-CVA delta and vega risk-class capital across the implemented Basel MAR50
  risk classes under MAR50.42-MAR50.77;
- mixed SA-CVA plus BA-CVA netting-set carve-out assembly under MAR50.8;
- eligible hedge recognition under MAR50.18-MAR50.19 and MAR50.37-MAR50.39;
- qualified-index routing where MAR50.50 metadata is supplied;
- CRIF, Arrow/batch, attribution, impact, audit, and replay helpers that do not
  change capital totals.

`BASEL_MAR50_2020` is the capital-producing profile. U.S. NPR 2.0, EU CRR3,
and PRA UK CRR comparison profiles remain unsupported runtime paths.

## Out Of Scope

- MAR50.9 materiality-threshold 100% CCR alternative;
- regulatory approval workflow for SA-CVA use;
- exposure simulation and sensitivity generation under MAR50.31-MAR50.36;
- live hedge execution, hedge accounting, or desk governance;
- final regulatory reporting or supervisory capital submission.
