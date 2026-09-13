from __future__ import annotations

from pathlib import Path


def test_banking_candidate_rpc_endpoints_are_whitelisted():
	engine_path = Path(__file__).resolve().parents[1] / "bank_candidate_engine.py"
	source = engine_path.read_text(encoding="utf-8")

	for function_name in (
		"get_direction_aware_bank_candidates",
		"prepare_direction_aware_bank_candidate",
	):
		decorated_definition = f'@frappe.whitelist()\ndef {function_name}('
		assert decorated_definition in source, f"{function_name} must remain explicitly whitelisted for Banking workspace RPC"
