#!/usr/bin/env python3
"""FRTB Capital Suite UI Dashboard Server.

A standard-library HTTP server that serves static files and provides a
lightweight API endpoint to run capital calculations and handle desk-level routing,
using authentic mock data models based on the frtb-capital packages.
"""

import http.server
import socketserver
import json
import logging
from urllib.parse import urlparse, parse_qs
from datetime import date
import random
import math

PORT = 8080
DIRECTORY = "static"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("frtb-dashboard")

# --- Mock Data Generation based on Researched Data Models ---

def generate_sbm_mock() -> dict:
    """Mock SbmCapitalResult"""
    def make_bucket(b_id, risk_class, measure, kb, floor):
        sensitivities = []
        for i in range(1, 6):
            raw = random.uniform(-1000000, 1000000)
            rw = random.uniform(0.01, 0.20)
            sensitivities.append({
                "sensitivity_id": f"{b_id}_{i}",
                "risk_class": risk_class,
                "risk_measure": measure,
                "bucket": b_id,
                "raw_amount": raw,
                "risk_weight": rw,
                "scaled_amount": raw * rw,
                "citation_ids": ["MAR21.3"]
            })
        return {
            "bucket_id": b_id,
            "risk_class": risk_class,
            "risk_measure": measure,
            "kb": kb,
            "weighted_sensitivities": sensitivities,
            "citation_ids": ["MAR21.4"],
            "floor_applied": floor
        }
        
    girr_delta_buckets = [
        make_bucket("USD", "GIRR", "DELTA", 15000000, False),
        make_bucket("EUR", "GIRR", "DELTA", 8000000, False),
        make_bucket("GBP", "GIRR", "DELTA", 4500000, True)
    ]
    
    return {
        "total_capital": 32500000.0,
        "profile_id": "BASEL_MAR21",
        "profile_hash": "a1b2c3d4",
        "input_hash": "e5f6g7h8",
        "selected_portfolio_scenario": "MEDIUM",
        "portfolio_scenario_totals": {"LOW": 28000000.0, "MEDIUM": 32500000.0, "HIGH": 31000000.0},
        "risk_classes": [
            {
                "risk_class": "GIRR",
                "risk_measure": "DELTA",
                "selected_capital": 25000000.0,
                "selected_scenario": "MEDIUM",
                "scenario_totals": {"LOW": 22000000.0, "MEDIUM": 25000000.0, "HIGH": 24000000.0},
                "buckets": girr_delta_buckets,
                "citation_ids": ["MAR21.1"]
            },
            {
                "risk_class": "CSR_NONSEC",
                "risk_measure": "DELTA",
                "selected_capital": 7500000.0,
                "selected_scenario": "HIGH",
                "scenario_totals": {"LOW": 5000000.0, "MEDIUM": 6000000.0, "HIGH": 7500000.0},
                "buckets": [make_bucket("IG_SOV", "CSR_NONSEC", "DELTA", 7500000, False)],
                "citation_ids": ["MAR21.2"]
            }
        ],
        "warnings": [],
        "unsupported_flags": []
    }

def generate_drc_mock() -> dict:
    """Mock DrcCapitalResult"""
    def make_net_jtd(n_id, obl, sen, net_amt, net_dir):
        return {
            "net_jtd_id": n_id,
            "netting_group_id": f"NG_{obl}",
            "risk_class": "NON_SECURITISATION",
            "bucket_key": "CORPORATE",
            "obligor_or_tranche_key": obl,
            "seniority_layer": sen,
            "gross_long": max(0, net_amt),
            "gross_short": abs(min(0, net_amt)),
            "scaled_long": max(0, net_amt) * 0.5,
            "scaled_short": abs(min(0, net_amt)) * 0.5,
            "net_amount": net_amt,
            "net_direction": net_dir,
            "position_ids": [f"POS_{n_id}_1", f"POS_{n_id}_2"],
            "scaled_jtd_ids": [f"SJTD_{n_id}_1"],
            "rejected_offsets": []
        }
        
    buckets = [
        {
            "bucket_id": "B1",
            "bucket_key": "CORPORATE",
            "risk_class": "NON_SECURITISATION",
            "hbr": {
                "hbr_id": "HBR1",
                "bucket_key": "CORPORATE",
                "aggregate_net_long": 10000000,
                "aggregate_net_short": 5000000,
                "denominator": 15000000,
                "ratio": 0.5,
                "citations": ["MAR22.3"]
            },
            "weighted_long": 1500000,
            "weighted_short": 750000,
            "capital": 1125000,
            "floor_applied": False,
            "net_jtd_ids": ["NJTD_1", "NJTD_2"],
            "citations": ["MAR22.4"]
        }
    ]
    
    return {
        "result_id": "DRC_RUN_001",
        "run_id": "RUN_123",
        "calculation_date": "2026-06-03",
        "base_currency": "USD",
        "profile_id": "BASEL_MAR21",
        "profile_hash": "a1b2c3d4",
        "input_hash": "e5f6g7h8",
        "total_drc": 1125000.0,
        "categories": [
            {
                "category_id": "NON_SEC",
                "risk_class": "NON_SECURITISATION",
                "bucket_results": buckets,
                "capital": 1125000.0,
                "unsupported_features": []
            }
        ],
        "net_jtds": [
            make_net_jtd("NJTD_1", "OBL_A", "SENIOR_UNSECURED", 5000000, "LONG"),
            make_net_jtd("NJTD_2", "OBL_B", "SUBORDINATED", -2000000, "SHORT")
        ],
        "attribution_records": [
            {"contribution_id": "ATT_1", "source_id": "OBL_A", "source_level": "net_jtd", "bucket_key": "CORPORATE", "category": "NON_SECURITISATION", "base_amount": 5000000, "contribution": 1000000, "method": "ANALYTICAL_EULER"},
            {"contribution_id": "ATT_2", "source_id": "OBL_B", "source_level": "net_jtd", "bucket_key": "CORPORATE", "category": "NON_SECURITISATION", "base_amount": -2000000, "contribution": 125000, "method": "ANALYTICAL_EULER"}
        ],
        "citations": ["MAR22.1"],
        "warnings": []
    }

def generate_ima_mock() -> dict:
    """Mock DeskAuditRecords for IMA"""
    def make_desk(desk_id, eligibility, pla_zone, backtest_hpl, backtest_apl):
        imcc = {
            "alpha": 1.5,
            "estimator": "EXPECTED_SHORTFALL",
            "unconstrained_weight": 0.5,
            "unconstrained": {
                "alpha": 1.5,
                "lha_es": 4500000,
                "components": [
                    {"liquidity_horizon": "LH10", "weight": 1.0, "expected_shortfall": 2000000, "weighted_square": 4000000000000, "present": True},
                    {"liquidity_horizon": "LH20", "weight": 0.707, "expected_shortfall": 3000000, "weighted_square": 4500000000000, "present": True}
                ]
            },
            "constrained_components": [
                {"risk_class": "GIRR", "lha_es_result": {"lha_es": 3000000}},
                {"risk_class": "FX", "lha_es_result": {"lha_es": 2500000}}
            ],
            "constrained_lha_es": 5500000,
            "imcc": 5000000
        }
        
        ses = {
            "type_a_count": 15,
            "type_b_count": 5,
            "type_a_sum_of_squares": 2500000000000,
            "type_b_correlated_term": 500000,
            "type_b_sum_of_squares": 1000000000000,
            "type_b_linear_sum": 2000000,
            "type_b_rho": 0.36,
            "total_ses": 1500000 + 500000 + 2000000  # Simplified
        }
        
        pla = {
            "ks_statistic": random.uniform(0.01, 0.15) if pla_zone == "GREEN" else random.uniform(0.12, 0.25),
            "zone": pla_zone,
            "n_hpl": 250,
            "n_rtpl": 250
        }
        
        backtesting = {
            "levels": [
                {"confidence_level": 0.99, "apl_exceptions": backtest_apl, "hpl_exceptions": backtest_hpl, "exception_limit": 4, "apl_passed": backtest_apl <= 4, "hpl_passed": backtest_hpl <= 4, "level_passed": True, "window_size": 250}
            ],
            "window_size": 250,
            "model_eligible": eligibility == "IMA_ELIGIBLE"
        }
        
        capital = {
            "imcc_t_minus_1": 4800000,
            "ses_t_minus_1": 3800000,
            "imcc_60d_avg": 5000000,
            "ses_60d_avg": 4000000,
            "multiplier": 1.5,
            "pla_addon": 250000 if pla_zone == "AMBER" else 0.0,
            "models_based_capital": (5000000 * 1.5) + 4000000 + (250000 if pla_zone == "AMBER" else 0.0),
            "binding_term": "AVERAGE"
        }
        
        return {
            "run_id": "RUN_123",
            "desk_id": desk_id,
            "regime": "BASEL_MAR21",
            "desk_eligibility": eligibility,
            "imcc": imcc,
            "ses": ses,
            "pla": pla,
            "backtesting": backtesting,
            "capital": capital
        }

    return {
        "desk_records": [
            make_desk("Rates_G10", "IMA_ELIGIBLE", "GREEN", 2, 1),
            make_desk("Rates_EM", "SA_FALLBACK", "RED", 6, 5),
            make_desk("FX_Options", "IMA_ELIGIBLE", "AMBER", 3, 2),
            make_desk("Credit_Flow", "IMA_ELIGIBLE", "GREEN", 1, 1)
        ],
        "total_market_risk_capital": 35000000.0  # Sum of eligible desk MBC
    }

def handle_calculation(post_data: dict) -> dict:
    """
    Generate authentic mock capital run results based on requested state.
    """
    ima_eligibility_overrides = post_data.get("ima_desk_eligibility", {})
    
    # Generate mock components
    sbm_mock = generate_sbm_mock()
    drc_mock = generate_drc_mock()
    ima_mock = generate_ima_mock()
    
    # Apply routing logic
    fallback_routes = []
    total_sa = 0.0
    
    for desk in ima_mock["desk_records"]:
        # Apply override if exists
        desk_id = desk["desk_id"]
        status = ima_eligibility_overrides.get(desk_id, desk["desk_eligibility"])
        desk["desk_eligibility"] = status
        
        if status == "SA_FALLBACK":
            fallback_routes.append({
                "desk_id": desk_id,
                "source_eligibility_status": "SA_FALLBACK",
                "route": "STANDARDISED_APPROACH",
                "reason_code": "ima_desk_not_model_eligible"
            })
            
    # Mocking SA component totals
    sbm_total = sbm_mock["total_capital"]
    drc_total = drc_mock["total_drc"]
    rrao_total = 11000000.0 # Mock flat number
    
    # In reality SA capital is floor + fallback desks. 
    # For mock, we just say Standardised Approach has these subtotals:
    sa_result = {
        "run_id": "RUN_123",
        "calculation_date": "2026-06-03",
        "base_currency": "USD",
        "jurisdiction_family": "BASEL",
        "total_capital": sbm_total + drc_total + rrao_total,
        "component_subtotals": [
            {"component": "SBM", "package_name": "frtb-sbm", "total_capital": sbm_total, "subtotal_count": 50},
            {"component": "DRC", "package_name": "frtb-drc", "total_capital": drc_total, "subtotal_count": 25},
            {"component": "RRAO", "package_name": "frtb-rrao", "total_capital": rrao_total, "subtotal_count": 10}
        ],
        "fallback_routes": fallback_routes,
        "citations": ["MAR20.1"],
        "warnings": ["Warning: Missing correlations defaulted to 1.0"]
    }
    
    # Recalculate IMA total based on active eligible desks
    active_ima_total = sum(d["capital"]["models_based_capital"] for d in ima_mock["desk_records"] if d["desk_eligibility"] == "IMA_ELIGIBLE")
    ima_mock["total_market_risk_capital"] = active_ima_total

    return {
        "orchestration": sa_result,
        "ima": ima_mock,
        "components": {
            "sbm": sbm_mock,
            "drc": drc_mock
        }
    }


class DashboardRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/api/capital-run':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                request_json = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                request_json = {}

            response_data = handle_calculation(request_json)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            
    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), DashboardRequestHandler) as httpd:
        logger.info(f"Serving authentic FRTB dashboard at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
