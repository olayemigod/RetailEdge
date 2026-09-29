from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMOTED_EDGE_SUITE_SHA = "0c00dd8b4418a37b6c48c4def7721ba7a58e1adc"


def test_release_workflows_use_promoted_edgesuite_global_create_runtime():
    workflows = (
        ".github/workflows/ci.yml",
        ".github/workflows/browser-persona-smoke.yml",
        ".github/workflows/upgrade-validation.yml",
        ".github/workflows/edgesuite-ui-candidate-compat.yml",
    )
    for relative in workflows:
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert f"ref: {PROMOTED_EDGE_SUITE_SHA}" in source, relative
        assert "ref: agent/reporting-standard-v1" not in source, relative
        assert "fb44c72f817751cf7983bf3b69cd9e5f376159c4" not in source, relative
