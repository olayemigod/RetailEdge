from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPENSE = ROOT / "public/js/expense_register/ExpenseRegisterReport.vue"
WORKFLOW = ROOT.parent / ".github/workflows/edgesuite-ui-candidate-compat.yml"


def test_cached_expense_report_claims_handoff_before_async_metadata_work():
    source = EXPENSE.read_text()
    fetch = source.split("async fetchMetadata()", 1)[1]
    assert "this.consumeBusinessHubHandoff()" in fetch
    assert fetch.index("this.consumeBusinessHubHandoff()") < fetch.index("navigationPromise")
    assert 'document.addEventListener("page-change", this.handleRouteActivation);' not in source


def test_edgesuite_candidate_workflow_validates_exact_financial_dashboard_head_with_pytest():
    workflow = WORKFLOW.read_text()
    assert "026e32813b044d57d961fe668cec3487798135da" in workflow
    assert "python -m pip install --upgrade frappe-bench pytest" in workflow
    assert "python -m pytest -q apps/edgesuite_ui/edgesuite_ui/tests/test_financial_dashboard_contract.py" in workflow
    assert "./env/bin/python -m pytest" not in workflow
