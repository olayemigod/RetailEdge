from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "upgrade-validation.yml"


def test_upgrade_validation_covers_clean_upgrade_and_backup_based_rollback():
    source = WORKFLOW.read_text(encoding="utf-8")
    for expected in (
        "Install frozen pre-MVP RetailEdge baseline",
        "Seed representative pre-upgrade accounting data",
        "Back up frozen rollback point",
        'ROLLBACK_DB_BACKUP: /tmp/retailedge-pre-upgrade-database.sql.gz',
        'bench --site retail-upgrade.localhost backup',
        '--backup-path-db "$ROLLBACK_DB_BACKUP"',
        "Switch RetailEdge to exact current candidate",
        "Build and migrate upgraded site twice",
        "Verify submitted accounting truth survived migration",
        "Run current RetailEdge suite on upgraded site",
        "Restore frozen rollback point under prior RetailEdge code",
        'git -C apps/retailedge checkout --force "$PRIOR_RETAILEDGE_SHA"',
        'bench --site retail-upgrade.localhost restore',
        '--db-root-username root',
        '--db-root-password root',
        "--force",
        "retailedge.tests.upgrade_validation_fixture.verify_upgrade_fixture",
    ):
        assert expected in source


def test_rollback_uses_pre_upgrade_backup_and_prior_code_not_in_place_schema_downgrade():
    source = WORKFLOW.read_text(encoding="utf-8")
    rollback = source.split("Restore frozen rollback point under prior RetailEdge code", 1)[1]
    assert 'test -s "$ROLLBACK_DB_BACKUP"' in rollback
    checkout = rollback.index('git -C apps/retailedge checkout --force "$PRIOR_RETAILEDGE_SHA"')
    restore = rollback.index('bench --site retail-upgrade.localhost restore')
    migrate = rollback.index('bench --site retail-upgrade.localhost migrate')
    verify = rollback.index("retailedge.tests.upgrade_validation_fixture.verify_upgrade_fixture")
    assert checkout < restore < migrate < verify
    assert "CURRENT_RETAILEDGE_SHA" not in rollback.split("- name: Preserve upgrade failure evidence", 1)[0]
