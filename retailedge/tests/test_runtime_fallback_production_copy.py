from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOTS = [ROOT / "public" / "js", ROOT / "retailedge" / "page"]
FORBIDDEN = "EdgeSuite UI runtime is unavailable"
BUSINESS_FALLBACK = "This page could not start. Refresh the page or contact your administrator."


def test_runtime_start_failures_use_business_copy_without_changing_runtime_guards():
    sources = []
    for root in RUNTIME_ROOTS:
        for path in root.rglob("*.js"):
            source = path.read_text(encoding="utf-8")
            assert FORBIDDEN not in source, path
            sources.append((path, source))

    assert any(BUSINESS_FALLBACK in source for _, source in sources)

    representative = {
        "public/js/payment_history.bundle.js": "window.EdgeSuiteUI",
        "retailedge/page/payment_history/payment_history.js": "window.EdgeSuiteUI",
        "public/js/forecasting_planning.bundle.js": "window.EdgeSuiteUI",
        "retailedge/page/forecasting_planning/forecasting_planning.js": "window.EdgeSuiteUI",
        "public/js/rfq_history.bundle.js": "window.EdgeSuiteUI",
    }
    for relative, runtime_marker in representative.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert BUSINESS_FALLBACK in source
        assert runtime_marker in source


def test_action_centre_runtime_failure_is_business_facing():
    source = (ROOT / "public/js/action_center.bundle.js").read_text(encoding="utf-8")
    assert "Action Centre could not start." in source
    assert "Refresh the page or contact your administrator." in source
    assert FORBIDDEN not in source
