from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH_SHA = "c9d12503d9d7fbfd94086c3de3cd4ac23dd44823"


def test_release_workflows_pin_frappe_bench_for_python_314():
    workflows = (
        ".github/workflows/ci.yml",
        ".github/workflows/upgrade-validation.yml",
        ".github/workflows/browser-persona-smoke.yml",
        ".github/workflows/edgesuite-ui-candidate-compat.yml",
    )
    for relative in workflows:
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert 'python-version: "3.14"' in source, relative
        assert f"git+https://github.com/frappe/bench.git@{BENCH_SHA}" in source, relative
        assert "pip install --upgrade frappe-bench" not in source, relative
