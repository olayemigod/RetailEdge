from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/native_visual_workspaces/NativeERPNextWorkspace.vue"
BACKEND = ROOT / "native_visual_workspaces.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_native_visual_workspace_fails_closed_and_uses_final_access_context():
	source = _read(COMPONENT)
	assert "canUseNativeDesk: false" in source
	assert "retailedge.master_experience.get_master_retailedge_business_hub_context" in source
	assert "this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);" in source


def test_native_visual_workspace_keeps_edgesuite_pages_but_hides_native_source_actions():
	source = _read(COMPONENT)
	assert 'v-if="source.kind === \'page\' || canUseNativeDesk"' in source
	assert 'v-if="canUseNativeDesk && source.kind === \'doctype\' && source.can_create"' in source
	assert 'v-if="canUseNativeDesk" class="edge-secondary-button" type="button" @click="openSource(source)">View all</button>' in source
	assert ':tabindex="canUseNativeDesk ? 0 : undefined"' in source
	assert ":class=\"{ 'native-control-row--clickable': canUseNativeDesk }\"" in source


def test_native_visual_workspace_code_guards_every_native_handoff():
	source = _read(COMPONENT)
	assert 'if (source.kind !== "page" && !this.canUseNativeDesk) return;' in source
	assert 'if (!this.canUseNativeDesk || source.kind !== "doctype" || !source.can_create) return;' in source
	assert 'if (!this.canUseNativeDesk || source.kind !== "doctype" || !row?.name) return;' in source
	assert 'if ((item.target_type === "DocType" || item.target_type === "Report") && !this.canUseNativeDesk) return;' in source


def test_native_visual_workspace_menu_filters_native_targets_for_edgesuite_only_users():
	source = _read(COMPONENT)
	assert '.filter((item) => this.canUseNativeDesk || !["DocType", "Report"].includes(item.target_type))' in source
	assert '.filter((group) => group.items.length);' in source


def test_native_visual_backend_remains_preview_only():
	source = _read(BACKEND)
	for forbidden in (
		".submit(",
		".db_set(",
		"frappe.db.commit(",
		"ignore_permissions=True",
	):
		assert forbidden not in source
