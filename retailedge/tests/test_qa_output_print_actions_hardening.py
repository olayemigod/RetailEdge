from __future__ import annotations

from pathlib import Path

from retailedge.professional_print_formats import MANAGED_PRINT_FORMATS, _format_values


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_SERVICE = ROOT / "document_output.py"
OUTPUT_PAGE = ROOT / "public/js/document_output_sharing/DocumentOutputSharing.vue"
CONTROL_WORKSPACE = ROOT / "public/js/native_visual_workspaces/NativeERPNextWorkspace.vue"
SELLING_PAGE = ROOT / "public/js/professional_selling/ProfessionalSelling.vue"
PRINT_FORMATS = ROOT / "professional_print_formats.py"
CUSTOMER_PORTAL = ROOT / "www/customer_portal.html"
CUSTOMER_PORTAL_DOWNLOAD = ROOT / "customer_portal_download.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_output_context_uses_frappe_v16_fullname_helper():
	source = _read(OUTPUT_SERVICE)
	assert "from frappe.utils.user import get_user_fullname" in source
	assert "get_user_fullname(frappe.session.user)" in source
	assert "frappe.get_user().get_fullname()" not in source


def test_recent_invoice_target_is_consumed_by_output_workspace():
	source = _read(OUTPUT_PAGE)
	assert "window.retailedgeDocumentOutputTarget" in source
	assert "async applyPendingTarget()" in source
	assert "await this.applyPendingTarget()" in source
	assert "await this.selectDocument({ value: target.name })" in source
	assert "delete window.retailedgeDocumentOutputTarget" in source


def test_invoice_output_view_can_handoff_writable_draft_to_edgesuite_completion():
	output = _read(OUTPUT_PAGE)
	selling = _read(SELLING_PAGE)
	service = _read(OUTPUT_SERVICE)
	assert "canEditSelectedSalesInvoice" in output
	assert "Edit / Complete Draft" in output
	assert "window.retailedgeProfessionalSellingTarget" in output
	assert 'frappe.set_route("professional-selling")' in output
	assert "window.retailedgeProfessionalSellingTarget" in selling
	assert "applyPendingTarget()" in selling
	assert '"can_write": _permission(doctype, "write", name=name)' in service
	assert '"docstatus": cint(doc.docstatus)' in service


def test_shared_control_workspace_uses_edgesuite_button_contract():
	source = _read(CONTROL_WORKSPACE)
	assert 'class="edge-button edge-button--primary"' in source
	assert 'class="edge-button edge-button--secondary"' in source
	assert 'class="edge-primary-button"' not in source
	assert 'class="edge-secondary-button"' not in source


def test_customer_portal_visible_copy_and_pdf_path_are_neutral():
	portal = _read(CUSTOMER_PORTAL)
	download = _read(CUSTOMER_PORTAL_DOWNLOAD)
	assert "RetailEdge" not in portal
	assert "ProcessEdge" not in portal
	assert "get_preferred_print_format" in download
	assert "MANAGED_MARKER" in download


def test_customer_visible_output_copy_has_no_product_or_vendor_alias():
	output_source = _read(OUTPUT_PAGE)
	for spec in MANAGED_PRINT_FORMATS:
		html = _format_values(spec)["html"]
		for forbidden in (
			"RetailEdge",
			"retailedge",
			"Powered by",
			"ProcessEdge Solutions",
			"processedge.com.ng",
		):
			assert forbidden not in html
	for forbidden in (
		">RetailEdge<",
		"RetailEdge Professional",
		"Powered by RetailEdge",
		"ProcessEdge Solutions",
		"processedge.com.ng",
	):
		assert forbidden not in output_source
	# The internal shell uses the production ProcessEdge Retail identity while
	# generated customer documents remain company/ERPNext branded and vendor-neutral.
	assert 'product="retailedge"' in output_source


def test_invoice_edit_and_output_workspaces_use_production_retail_identity_key():
	output = _read(OUTPUT_PAGE)
	selling = _read(SELLING_PAGE)
	assert 'product="retailedge"' in output
	assert 'product="retailedge"' in selling
	assert 'product="Retail"' not in output
	assert 'product="RetailEdge"' not in selling
