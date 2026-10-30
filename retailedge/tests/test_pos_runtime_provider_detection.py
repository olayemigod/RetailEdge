from __future__ import annotations

from retailedge.pos_runtime import get_pos_runtime_capabilities


def _targets(*existing: tuple[str, str]):
	allowed = set(existing)
	return lambda target_type, target: (target_type, target) in allowed


def test_installed_posnext_keeps_web_runtime_when_shift_schema_is_partial():
	runtime = get_pos_runtime_capabilities(
		target_exists=_targets(("DocType", "POS Opening Shift"), ("Page", "point-of-sale")),
		app_installed=lambda app: app == "pos_next",
	)

	assert runtime.provider == "posnext"
	assert runtime.start_link_type == "URL"
	assert runtime.start_target == "/pos/"
	assert runtime.start_url == "/pos/"
	assert runtime.opening_doctype == "POS Opening Shift"
	assert runtime.closing_doctype is None


def test_posnext_shift_schema_remains_backward_compatible_without_app_probe():
	runtime = get_pos_runtime_capabilities(
		target_exists=_targets(
			("DocType", "POS Opening Shift"),
			("DocType", "POS Closing Shift"),
			("Page", "point-of-sale"),
		),
		app_installed=lambda _app: False,
	)

	assert runtime.provider == "posnext"
	assert runtime.start_link_type == "URL"
	assert runtime.start_target == "/pos/"


def test_native_erpnext_pos_is_used_when_posnext_is_not_installed():
	runtime = get_pos_runtime_capabilities(
		target_exists=_targets(
			("DocType", "POS Opening Entry"),
			("DocType", "POS Closing Entry"),
			("Page", "point-of-sale"),
		),
		app_installed=lambda _app: False,
	)

	assert runtime.provider == "erpnext"
	assert runtime.start_link_type == "Page"
	assert runtime.start_target == "point-of-sale"
	assert runtime.start_url is None
	assert runtime.opening_doctype == "POS Opening Entry"
	assert runtime.closing_doctype == "POS Closing Entry"
