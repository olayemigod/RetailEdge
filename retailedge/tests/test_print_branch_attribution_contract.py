from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
THERMAL_RECEIPT = APP_ROOT / "thermal_receipt.py"
PRINT_OUTPUT_CONTEXT = APP_ROOT / "print_output_context.py"


def _source(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_print_paths_prefer_stored_retailedge_branch_before_generic_fields():
	for path, helper in (
		(THERMAL_RECEIPT, "def _branch(doc) -> str:"),
		(PRINT_OUTPUT_CONTEXT, "def _document_branch(doc) -> str:"),
	):
		source = _source(path)
		start = source.index(helper)
		end = source.index("\n\ndef ", start + len(helper))
		body = source[start:end]
		canonical = body.index('doc.meta.has_field("retailedge_branch")')
		fallback = body.index("for fieldname in BRANCH_FIELD_CANDIDATES")
		assert canonical < fallback
		assert 'doc.get("retailedge_branch")' in body


def test_print_branch_resolution_never_uses_current_working_branch_or_writes_documents():
	for path in (THERMAL_RECEIPT, PRINT_OUTPUT_CONTEXT):
		source = _source(path)
		for forbidden in (
			"get_operating_context",
			"get_user_default",
			"frappe.defaults",
			"frappe.db.set_value",
			"ignore_permissions=True",
			"doc.save(",
			"doc.submit(",
		):
			assert forbidden not in source
