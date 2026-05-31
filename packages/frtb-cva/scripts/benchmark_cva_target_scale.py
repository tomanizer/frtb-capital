"""Synthetic large-scale CVA benchmark without dataframe dependencies."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date

from frtb_cva import (
    CreditQuality,
    CvaCalculationContext,
    CvaCounterparty,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    calculate_cva_capital,
    serialize_cva_result,
)


@dataclass(frozen=True)
class CvaBenchmarkConfig:
    netting_sets: int = 10_000
    sensitivities: int = 100_000


def _synthetic_netting_sets(count: int) -> tuple[CvaNettingSet, ...]:
    counterparties = tuple(
        CvaCounterparty(
            counterparty_id=f"ctp-{index % 100}",
            desk_id="desk-a",
            legal_entity="LE-001",
            sector=CvaSector.SOVEREIGN,
            credit_quality=CreditQuality.INVESTMENT_GRADE,
            region="EMEA",
            source_row_id=f"row-ctp-{index % 100}",
        )
        for index in range(100)
    )
    _ = counterparties
    return tuple(
        CvaNettingSet(
            netting_set_id=f"ns-{index}",
            counterparty_id=f"ctp-{index % 100}",
            ead=10_000.0,
            effective_maturity=1.0,
            discount_factor=1.0,
            currency="USD",
            sign_convention="non_negative",
            uses_imm_ead=True,
            source_row_id=f"row-ns-{index}",
        )
        for index in range(count)
    )


def run_benchmark(config: CvaBenchmarkConfig) -> dict[str, object]:
    counterparties = tuple(
        {
            cp.counterparty_id: cp
            for cp in (
                CvaCounterparty(
                    counterparty_id=f"ctp-{index}",
                    desk_id="desk-a",
                    legal_entity="LE-001",
                    sector=CvaSector.SOVEREIGN,
                    credit_quality=CreditQuality.INVESTMENT_GRADE,
                    region="EMEA",
                    source_row_id=f"row-ctp-{index}",
                )
                for index in range(100)
            )
        }.values()
    )
    netting_sets = _synthetic_netting_sets(config.netting_sets)
    context = CvaCalculationContext(
        run_id="cva-benchmark",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_REDUCED,
    )
    started = time.perf_counter()
    result = calculate_cva_capital(context, counterparties, netting_sets)
    elapsed = time.perf_counter() - started
    payload = serialize_cva_result(result)
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "parameters": {
            "netting_sets": config.netting_sets,
            "sensitivities": config.sensitivities,
        },
        "timings": {
            "seconds": elapsed,
            "netting_sets_per_second": config.netting_sets / elapsed if elapsed else 0.0,
        },
        "result": {
            "total_cva_capital": result.total_cva_capital,
            "payload_hash": payload_hash,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_benchmark(CvaBenchmarkConfig(netting_sets=1_000)), indent=2))
