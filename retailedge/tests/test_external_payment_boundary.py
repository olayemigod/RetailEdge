from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


def _runtime_python_files():
	for path in APP_ROOT.rglob("*.py"):
		if "tests" in path.parts:
			continue
		yield path


def test_retailedge_runtime_has_no_local_edgepay_package_imports():
	violations = []
	for path in _runtime_python_files():
		text = path.read_text(encoding="utf-8")
		if "import edgepay" in text or "from edgepay" in text:
			violations.append(str(path.relative_to(APP_ROOT)))

	assert violations == []


def test_retailedge_package_does_not_require_edgepay_app():
	pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
	assert '"edgepay' not in pyproject
	assert "'edgepay" not in pyproject


def test_external_payment_review_keeps_candidate_ownership_in_retailedge():
	service = (
		APP_ROOT / "services" / "edgepay_bank_match_review.py"
	).read_text(encoding="utf-8")

	assert "validate_locked_candidate_from_selected_row" in service
	assert "locked_candidate=locked_candidate" in service
	assert "allow_fallback=False" in service
	assert '"candidate_owner": "RetailEdge"' in service


def test_external_payment_review_does_not_reconcile_bank_transaction_directly():
	service = (
		APP_ROOT / "services" / "edgepay_bank_match_review.py"
	).read_text(encoding="utf-8")

	assert 'db_set("status", "Reconciled")' not in service
	assert "reconcile_vouchers" not in service
	assert "make_reconciliation" not in service
