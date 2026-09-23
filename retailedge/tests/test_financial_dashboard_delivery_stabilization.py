from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPENSE = ROOT / "public/js/expense_register/ExpenseRegisterReport.vue"
WORKFLOW = ROOT.parent / ".github/workflows/edgesuite-ui-candidate-compat.yml"


def test_cached_expense_report_reconsumes_fresh_business_hub_handoff_on_page_activation():
    source = EXPENSE.read_text()
    assert 'document.addEventListener("page-change", this.handleRouteActivation);' in source
    assert 'document.removeEventListener("page-change", this.handleRouteActivation);' in source
    assert "handleRouteActivation()" in source
    assert "this.consumeBusinessHubHandoff()" in source
    assert "this.syncSmartDateFromFilters();" in source
    assert "this.currentPage = 1;" in source
    assert "if (this.filters.company) this.fetchData();" in source


def test_edgesuite_candidate_workflow_validates_exact_financial_dashboard_head_with_pytest():
    workflow = WORKFLOW.read_text()
    assert "026e32813b044d57d961fe668cec3487798135da" in workflow
    assert "python -m pip install --upgrade frappe-bench pytest" in workflow
    assert "python -m pytest -q apps/edgesuite_ui/edgesuite_ui/tests/test_financial_dashboard_contract.py" in workflow
    assert "./env/bin/python -m pytest" not in workflow
