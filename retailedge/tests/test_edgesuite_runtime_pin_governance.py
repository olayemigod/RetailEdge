from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNED_EDGESUITE_SHA = "a2d1705f794e17c88d66d7041df4dfb47b2684ff"
OLD_EDGESUITE_SHA = "fb44c72f817751cf7983bf3b69cd9e5f376159c4"
OLD_EDGESUITE_BRANCH = "agent/reporting-standard-v1"

WORKFLOWS = (
    REPO_ROOT / ".github" / "workflows" / "browser-persona-smoke.yml",
    REPO_ROOT / ".github" / "workflows" / "ci.yml",
    REPO_ROOT / ".github" / "workflows" / "upgrade-validation.yml",
    REPO_ROOT / ".github" / "workflows" / "edgesuite-ui-candidate-compat.yml",
)


def test_release_workflows_share_one_governed_edgesuite_runtime():
    for workflow in WORKFLOWS:
        source = workflow.read_text()
        assert f"ref: {GOVERNED_EDGESUITE_SHA}" in source
        assert f'rev-parse HEAD)" = "{GOVERNED_EDGESUITE_SHA}"' in source
        assert OLD_EDGESUITE_SHA not in source
        assert OLD_EDGESUITE_BRANCH not in source
