from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CONTEXT = APP_ROOT / "print_output_context.py"
HOOKS = APP_ROOT / "hooks.py"
FORMATS = APP_ROOT / "professional_print_formats.py"


def read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_business_print_context_uses_company_profile_and_request_scoped_options():
	source = read(CONTEXT)
	for contract in (
		"resolve_company_profile(company)",
		'options.get("show_logo", 1)',
		'options.get("include_qr", 0)',
		'"logo": logo',
		'"address": address',
		'"qr_data_uri": _qr_data_uri(qr_payload) if qr_payload else ""',
	):
		assert contract in source
	assert "doc.save(" not in source
	assert "frappe.db.set_value" not in source


def test_qr_payload_is_document_reference_not_public_pdf_link():
	source = read(CONTEXT)
	for contract in (
		'f"Company: {company_label',
		'f"Document: {_clean(doc.doctype)} {_clean(doc.name)}"',
		'f"Date: {document_date}"',
		'f"Total: {currency} {total:.2f}"',
	):
		assert contract in source
	for forbidden in (
		"public_pdf",
		"/files/",
		"frappe.db.commit",
	):
		assert forbidden not in source


def test_jinja_hook_exposes_neutral_business_print_helper():
	hooks = read(HOOKS)
	formats = read(FORMATS)
	assert '"retailedge.print_output_context.get_business_print_context"' in hooks
	assert "get_business_print_context(doc)" in formats
	assert "get_retailedge_print_context" not in formats


def test_v4_templates_recognize_v3_as_owned_for_idempotent_upgrade():
	source = read(FORMATS)
	assert 'MANAGED_MARKER = "<!-- managed-business-print-format:v4 -->"' in source
	assert '"<!-- managed-business-print-format:v3 -->"' in source
