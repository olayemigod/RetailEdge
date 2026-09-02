from pathlib import Path

ROOT = Path("retailedge")
DOCS = Path("docs")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f"{label}: expected one match, got {count}"
    return text.replace(old, new, 1)


guided_backend = r'''from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, getdate, nowdate

WARRANTY_CLAIM_DOCTYPE = "Warranty Claim"
MAX_LINK_RESULTS = 20
EDITABLE_STATUSES = {"Open", "Work In Progress", "Closed"}


@frappe.whitelist()
def get_guided_warranty_claim_context(name: str | None = None) -> dict[str, Any]:
	name = str(name or "").strip()
	if name:
		doc = _get_writable_claim(name)
		company = str(doc.company or "").strip()
		_assert_read_permission("Company", company)
		defaults = _claim_values(doc)
	else:
		_assert_can_create()
		company = str(frappe.defaults.get_user_default("Company") or "").strip()
		if not company:
			frappe.throw(_("Set a default Company before creating a Warranty Claim."))
		_assert_read_permission("Company", company)
		defaults = {
			"name": "",
			"company": company,
			"customer": "",
			"complaint_date": nowdate(),
			"complaint": "",
			"item_code": "",
			"serial_no": "",
			"service_address": "",
			"complaint_raised_by": "",
			"status": "Open",
			"resolution_details": "",
			"warranty_amc_status": "",
			"warranty_expiry_date": "",
			"amc_expiry_date": "",
		}

	return {
		"title": _("Warranty Claim") if name else _("New Warranty Claim"),
		"subtitle": _(
			"Record and manage an ERPNext Warranty Claim without leaving the RetailEdge service workspace."
		),
		"defaults": defaults,
		"status_options": ["Open", "Work In Progress", "Closed"],
		"capabilities": {
			"can_create": int(bool(frappe.has_permission(WARRANTY_CLAIM_DOCTYPE, "create"))),
			"can_write": 1,
			"native_form_fallback": int(bool(_get_edgesuite_access_context().get("can_use_native_desk"))),
		},
		"limits": {"link_results": MAX_LINK_RESULTS},
	}


@frappe.whitelist()
def search_guided_warranty_claim_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_authenticated()
	values = _coerce_values(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	company = _guided_company(values)

	if fieldname == "customer":
		return search_link(
			"Customer",
			txt or "",
			page_length=limit,
			reference_doctype=WARRANTY_CLAIM_DOCTYPE,
			link_fieldname="customer",
		)
	if fieldname == "item_code":
		return search_link(
			"Item",
			txt or "",
			filters={"disabled": 0},
			page_length=limit,
			reference_doctype=WARRANTY_CLAIM_DOCTYPE,
			link_fieldname="item_code",
		)
	if fieldname == "serial_no":
		filters: dict[str, Any] = {"company": company}
		item_code = str(values.get("item_code") or "").strip()
		customer = str(values.get("customer") or "").strip()
		if item_code:
			filters["item_code"] = item_code
		serial_meta = frappe.get_meta("Serial No")
		if customer and serial_meta.has_field("customer"):
			filters["customer"] = customer
		return search_link(
			"Serial No",
			txt or "",
			filters=filters,
			page_length=limit,
			reference_doctype=WARRANTY_CLAIM_DOCTYPE,
			link_fieldname="serial_no",
		)
	frappe.throw(_("Unsupported Warranty Claim search field: {0}").format(fieldname))
	return []


@frappe.whitelist()
def get_guided_warranty_serial_details(
	serial_no: str,
	values: dict | str | None = None,
) -> dict[str, Any]:
	_assert_authenticated()
	values = _coerce_values(values)
	serial_no = str(serial_no or "").strip()
	if not serial_no:
		return {}
	company = _guided_company(values)
	customer = str(values.get("customer") or "").strip()
	item_code = str(values.get("item_code") or "").strip()
	return _validate_serial(serial_no, company=company, customer=customer, item_code=item_code)


@frappe.whitelist(methods=["POST"])
def save_guided_warranty_claim(values: dict | str | None = None) -> dict[str, Any]:
	values = _coerce_values(values)
	name = str(values.get("name") or "").strip()
	if name:
		doc = _get_writable_claim(name)
		if doc.docstatus != 0 or str(doc.status or "") == "Cancelled":
			frappe.throw(_("Cancelled or non-draft Warranty Claims must be handled in the authoritative ERPNext workflow."))
		company = str(doc.company or "").strip()
		requested_company = str(values.get("company") or company).strip()
		if requested_company != company:
			frappe.throw(_("Company cannot be changed from the guided Warranty Claim workflow."))
	else:
		_assert_can_create()
		company = _guided_company(values, require_default=True)
		doc = frappe.new_doc(WARRANTY_CLAIM_DOCTYPE)
		doc.company = company

	_assert_read_permission("Company", company)
	customer = str(values.get("customer") or "").strip()
	if not customer:
		frappe.throw(_("Customer is required."))
	_assert_read_permission("Customer", customer)

	complaint = str(values.get("complaint") or "").strip()
	if not frappe.utils.strip_html(complaint).strip():
		frappe.throw(_("Issue is required."))

	status = str(values.get("status") or "Open").strip() or "Open"
	if status not in EDITABLE_STATUSES:
		frappe.throw(_("Unsupported Warranty Claim status: {0}").format(status))

	item_code = str(values.get("item_code") or "").strip()
	serial_no = str(values.get("serial_no") or "").strip()
	serial_details: dict[str, Any] = {}
	if item_code:
		_assert_read_permission("Item", item_code)
		if cint(frappe.db.get_value("Item", item_code, "disabled")):
			frappe.throw(_("Item {0} is disabled.").format(item_code))
	if serial_no:
		serial_details = _validate_serial(
			serial_no,
			company=company,
			customer=customer,
			item_code=item_code,
		)
		item_code = str(serial_details.get("item_code") or item_code).strip()

	doc.company = company
	doc.customer = customer
	doc.complaint_date = getdate(values.get("complaint_date") or nowdate())
	doc.complaint = complaint
	doc.status = status
	doc.item_code = item_code or None
	doc.serial_no = serial_no or None
	doc.service_address = str(values.get("service_address") or "").strip() or None
	doc.complaint_raised_by = str(values.get("complaint_raised_by") or "").strip() or None
	doc.resolution_details = str(values.get("resolution_details") or "").strip() or None

	if serial_details:
		doc.warranty_amc_status = serial_details.get("warranty_amc_status") or None
		doc.warranty_expiry_date = serial_details.get("warranty_expiry_date") or None
		doc.amc_expiry_date = serial_details.get("amc_expiry_date") or None
	if status == "Closed" and not doc.resolved_by:
		doc.resolved_by = frappe.session.user

	if name:
		doc.save()
	else:
		doc.insert()

	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"status": doc.status,
		"customer": doc.customer,
		"company": doc.company,
		"serial_no": doc.serial_no,
		"item_code": doc.item_code,
		"route": f"/app/warranty-claim/{doc.name}",
	}


def _claim_values(doc) -> dict[str, Any]:
	return {
		"name": doc.name,
		"company": doc.company or "",
		"customer": doc.customer or "",
		"complaint_date": str(doc.complaint_date or nowdate()),
		"complaint": doc.complaint or "",
		"item_code": doc.item_code or "",
		"serial_no": doc.serial_no or "",
		"service_address": doc.service_address or "",
		"complaint_raised_by": doc.complaint_raised_by or "",
		"status": doc.status or "Open",
		"resolution_details": doc.resolution_details or "",
		"warranty_amc_status": doc.warranty_amc_status or "",
		"warranty_expiry_date": str(doc.warranty_expiry_date or ""),
		"amc_expiry_date": str(doc.amc_expiry_date or ""),
	}


def _guided_company(values: dict[str, Any], *, require_default: bool = False) -> str:
	default_company = str(frappe.defaults.get_user_default("Company") or "").strip()
	requested = str(values.get("company") or default_company).strip()
	if require_default and not default_company:
		frappe.throw(_("Set a default Company before creating a Warranty Claim."))
	company = requested or default_company
	if not company:
		frappe.throw(_("Company is required."))
	if default_company and requested and requested != default_company:
		frappe.throw(_("Use your active RetailEdge Company context before creating this Warranty Claim."))
	_assert_read_permission("Company", company)
	return company


def _validate_serial(
	serial_no: str,
	*,
	company: str,
	customer: str = "",
	item_code: str = "",
) -> dict[str, Any]:
	_assert_read_permission("Serial No", serial_no)
	fields = [
		"company",
		"item_code",
		"customer",
		"maintenance_status",
		"warranty_expiry_date",
		"amc_expiry_date",
	]
	serial = frappe.db.get_value("Serial No", serial_no, fields, as_dict=True)
	if not serial:
		frappe.throw(_("Serial No {0} does not exist.").format(serial_no))
	if serial.company and serial.company != company:
		frappe.throw(_("Serial No {0} does not belong to Company {1}.").format(serial_no, company))
	if item_code and serial.item_code and serial.item_code != item_code:
		frappe.throw(_("Serial No {0} belongs to Item {1}, not Item {2}.").format(serial_no, serial.item_code, item_code))
	if customer and serial.customer and serial.customer != customer:
		frappe.throw(_("Serial No {0} is linked to Customer {1}, not Customer {2}.").format(serial_no, serial.customer, customer))
	if serial.item_code:
		_assert_read_permission("Item", serial.item_code)
	return {
		"serial_no": serial_no,
		"item_code": serial.item_code or "",
		"customer": serial.customer or "",
		"warranty_amc_status": serial.maintenance_status or "",
		"warranty_expiry_date": str(serial.warranty_expiry_date or ""),
		"amc_expiry_date": str(serial.amc_expiry_date or ""),
	}


def _get_writable_claim(name: str):
	_assert_read_permission(WARRANTY_CLAIM_DOCTYPE, name)
	if not frappe.has_permission(WARRANTY_CLAIM_DOCTYPE, "write", doc=name):
		frappe.throw(_("You do not have permission to update Warranty Claim {0}.").format(name), frappe.PermissionError)
	return frappe.get_doc(WARRANTY_CLAIM_DOCTYPE, name)


def _assert_can_create() -> None:
	_assert_authenticated()
	if not frappe.db.exists("DocType", WARRANTY_CLAIM_DOCTYPE) or not frappe.has_permission(
		WARRANTY_CLAIM_DOCTYPE, "create"
	):
		frappe.throw(_("You do not have permission to create Warranty Claims."), frappe.PermissionError)


def _assert_read_permission(doctype: str, name: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to use {0} {1}.").format(doctype, name), frappe.PermissionError)


def _assert_authenticated() -> None:
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Sign in to use the RetailEdge Warranty Claim workflow."), frappe.PermissionError)


def _get_edgesuite_access_context() -> dict[str, Any]:
	try:
		from edgesuite_ui.access_control import get_access_context
	except ImportError:
		return {
			"mode": "native_desk",
			"restricted_to_edgesuite": False,
			"can_use_native_desk": True,
			"authorization_source": "frappe_permissions",
		}
	return dict(get_access_context())


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if not values:
		return {}
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if isinstance(values, frappe._dict):
		return dict(values)
	if isinstance(values, dict):
		return dict(values)
	frappe.throw(_("Invalid Warranty Claim values."))
	return {}
'''

warranty_dialog = r'''<template>
	<EdgeModal
		:open="open"
		:title="formContext.title || (claimName ? 'Warranty Claim' : 'New Warranty Claim')"
		:subtitle="formContext.subtitle || 'Record an ERPNext Warranty Claim from the RetailEdge service workspace.'"
		size="lg"
		@close="requestClose"
	>
		<div v-if="loading" class="guided-warranty-state">
			<EdgeLoadingState message="Preparing Warranty Claim..." :skeleton="true" />
		</div>
		<div v-else-if="loadError" class="guided-warranty-state">
			<EdgeErrorState
				title="Warranty Claim unavailable"
				:message="loadError"
				@retry="loadContext"
			/>
		</div>
		<form v-else class="guided-warranty-form" @submit.prevent="saveClaim">
			<div class="guided-warranty-context">
				<div>
					<span>Company</span>
					<strong>{{ values.company || 'Not set' }}</strong>
				</div>
				<div v-if="values.warranty_amc_status">
					<span>Warranty / AMC</span>
					<strong>{{ values.warranty_amc_status }}</strong>
				</div>
				<div v-if="values.warranty_expiry_date">
					<span>Warranty Expiry</span>
					<strong>{{ values.warranty_expiry_date }}</strong>
				</div>
			</div>

			<div v-if="saveError" class="guided-warranty-error" role="alert">{{ saveError }}</div>

			<div class="guided-warranty-grid">
				<EdgeLinkField
					:modelValue="values.customer"
					label="Customer"
					placeholder="Search customer"
					description="Only customers allowed by your ERPNext permissions are shown."
					:required="true"
					:searcher="searchCustomer"
					:context="searchContext"
					@update:modelValue="setCustomer"
				/>

				<label class="guided-field">
					<span>Issue Date <b>*</b></span>
					<input v-model="values.complaint_date" class="form-control" type="date" required />
				</label>

				<EdgeLinkField
					:modelValue="values.item_code"
					label="Item"
					placeholder="Search item"
					description="Optional. Disabled items are excluded."
					:searcher="searchItem"
					:context="searchContext"
					@update:modelValue="setItem"
				/>

				<EdgeLinkField
					:modelValue="values.serial_no"
					label="Serial No"
					placeholder="Search serial number"
					description="Filtered by the active Company and selected Item/Customer where available."
					:searcher="searchSerial"
					:context="searchContext"
					@update:modelValue="setSerial"
				/>

				<label class="guided-field" v-if="claimName">
					<span>Status</span>
					<select v-model="values.status" class="form-control">
						<option v-for="status in statusOptions" :key="status" :value="status">{{ status }}</option>
					</select>
				</label>

				<label class="guided-field">
					<span>Raised By</span>
					<input v-model="values.complaint_raised_by" class="form-control" type="text" placeholder="Customer contact or staff name" />
				</label>
			</div>

			<label class="guided-field guided-field--wide">
				<span>Issue <b>*</b></span>
				<textarea v-model="values.complaint" class="form-control" rows="4" required placeholder="Describe the warranty issue"></textarea>
			</label>

			<label class="guided-field guided-field--wide">
				<span>Service Address</span>
				<textarea v-model="values.service_address" class="form-control" rows="2" placeholder="Use when service location differs from the customer address"></textarea>
			</label>

			<label v-if="claimName" class="guided-field guided-field--wide">
				<span>Resolution Details</span>
				<textarea v-model="values.resolution_details" class="form-control" rows="3" placeholder="Work performed, findings, or resolution"></textarea>
			</label>
		</form>

		<template #footer>
			<div class="guided-warranty-footer">
				<button
					v-if="nativeFallbackEnabled && claimName"
					type="button"
					class="edge-button"
					:disabled="saving"
					@click="openFullForm"
				>
					Open Full Form
				</button>
				<div class="guided-warranty-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button
						type="button"
						class="edge-button edge-button--primary"
						:disabled="saving || loading"
						@click="saveClaim"
					>
						{{ saving ? 'Saving...' : claimName ? 'Save Changes' : 'Save Claim' }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const CONTEXT_METHOD = "retailedge.guided_warranty_claim.get_guided_warranty_claim_context";
const SEARCH_METHOD = "retailedge.guided_warranty_claim.search_guided_warranty_claim_options";
const SERIAL_METHOD = "retailedge.guided_warranty_claim.get_guided_warranty_serial_details";
const SAVE_METHOD = "retailedge.guided_warranty_claim.save_guided_warranty_claim";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function emptyValues() {
	return {
		name: "",
		company: "",
		customer: "",
		complaint_date: "",
		complaint: "",
		item_code: "",
		serial_no: "",
		service_address: "",
		complaint_raised_by: "",
		status: "Open",
		resolution_details: "",
		warranty_amc_status: "",
		warranty_expiry_date: "",
		amc_expiry_date: "",
	};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc_type || fallback;
}

export default {
	name: "GuidedWarrantyClaimDialog",
	components: {
		EdgeModal: runtimeComponents.EdgeModal,
		EdgeLinkField: runtimeComponents.EdgeLinkField,
		EdgeLoadingState: runtimeComponents.EdgeLoadingState,
		EdgeErrorState: runtimeComponents.EdgeErrorState,
	},
	props: {
		open: { type: Boolean, default: false },
		claimName: { type: String, default: "" },
		nativeFallbackEnabled: { type: Boolean, default: true },
	},
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			loading: false,
			saving: false,
			loadError: "",
			saveError: "",
			formContext: {},
			values: emptyValues(),
			statusOptions: ["Open", "Work In Progress", "Closed"],
			serialToken: 0,
		};
	},
	computed: {
		searchContext() {
			return {
				company: this.values.company,
				customer: this.values.customer,
				item_code: this.values.item_code,
				serial_no: this.values.serial_no,
			};
		},
	},
	watch: {
		open(next) {
			if (next) this.loadContext();
		},
		claimName() {
			if (this.open) this.loadContext();
		},
	},
	mounted() {
		if (this.open) this.loadContext();
	},
	methods: {
		async loadContext() {
			this.loading = true;
			this.loadError = "";
			this.saveError = "";
			try {
				const data = await callMethod(CONTEXT_METHOD, { name: this.claimName || "" });
				this.formContext = data || {};
				this.values = { ...emptyValues(), ...(data.defaults || {}) };
				this.statusOptions = data.status_options || this.statusOptions;
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare the Warranty Claim.");
			} finally {
				this.loading = false;
			}
		},
		requestClose() {
			if (!this.saving) this.$emit("close");
		},
		openFullForm() {
			if (!this.nativeFallbackEnabled || !this.claimName) return;
			this.$emit("open-native", this.claimName);
		},
		async searchOptions(fieldname, query) {
			const results = await callMethod(SEARCH_METHOD, {
				fieldname,
				txt: query || "",
				values: this.searchContext,
			});
			return Array.isArray(results) ? results : [];
		},
		searchCustomer(query) {
			return this.searchOptions("customer", query);
		},
		searchItem(query) {
			return this.searchOptions("item_code", query);
		},
		searchSerial(query) {
			return this.searchOptions("serial_no", query);
		},
		setCustomer(next) {
			if (this.values.customer !== (next || "")) this.clearSerialDetails();
			this.values.customer = next || "";
		},
		setItem(next) {
			if (this.values.item_code !== (next || "")) this.clearSerialDetails();
			this.values.item_code = next || "";
		},
		async setSerial(next) {
			const serialNo = next || "";
			this.values.serial_no = serialNo;
			this.values.warranty_amc_status = "";
			this.values.warranty_expiry_date = "";
			this.values.amc_expiry_date = "";
			if (!serialNo) return;
			const token = ++this.serialToken;
			try {
				const details = await callMethod(SERIAL_METHOD, {
					serial_no: serialNo,
					values: this.searchContext,
				});
				if (token !== this.serialToken) return;
				this.values.item_code = details.item_code || this.values.item_code;
				this.values.warranty_amc_status = details.warranty_amc_status || "";
				this.values.warranty_expiry_date = details.warranty_expiry_date || "";
				this.values.amc_expiry_date = details.amc_expiry_date || "";
			} catch (error) {
				if (token !== this.serialToken) return;
				this.clearSerialDetails();
				this.saveError = errorMessage(error, "Unable to use the selected Serial No.");
			}
		},
		clearSerialDetails() {
			this.serialToken += 1;
			this.values.serial_no = "";
			this.values.warranty_amc_status = "";
			this.values.warranty_expiry_date = "";
			this.values.amc_expiry_date = "";
		},
		async saveClaim() {
			if (this.saving || this.loading) return;
			this.saving = true;
			this.saveError = "";
			try {
				const result = await callMethod(SAVE_METHOD, { values: this.values });
				this.$emit("saved", result);
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to save the Warranty Claim.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.guided-warranty-form {
	display: grid;
	gap: 1rem;
}
.guided-warranty-state {
	padding: 1rem 0;
}
.guided-warranty-context {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 0.75rem;
	padding: 0.85rem;
	border: 1px solid var(--edge-border, var(--border-color));
	border-radius: 10px;
	background: var(--edge-surface-subtle, var(--subtle-fg));
}
.guided-warranty-context div {
	display: grid;
	gap: 0.2rem;
}
.guided-warranty-context span,
.guided-field > span {
	font-size: 0.78rem;
	color: var(--edge-text-muted, var(--text-muted));
}
.guided-warranty-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 0.9rem;
}
.guided-field {
	display: grid;
	gap: 0.35rem;
}
.guided-field--wide {
	grid-column: 1 / -1;
}
.guided-warranty-error {
	padding: 0.75rem;
	border: 1px solid var(--red-300, #fca5a5);
	border-radius: 8px;
	color: var(--red-700, #b91c1c);
	background: var(--red-50, #fef2f2);
}
.guided-warranty-footer,
.guided-warranty-footer-actions {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}
.guided-warranty-footer {
	justify-content: space-between;
	width: 100%;
}
.guided-warranty-footer-actions {
	margin-left: auto;
}
@media (max-width: 720px) {
	.guided-warranty-context,
	.guided-warranty-grid {
		grid-template-columns: 1fr;
	}
	.guided-warranty-footer {
		align-items: stretch;
		flex-direction: column;
	}
	.guided-warranty-footer-actions {
		margin-left: 0;
		justify-content: flex-end;
	}
}
</style>
'''

(ROOT / "guided_warranty_claim.py").write_text(guided_backend)
(ROOT / "public/js/native_visual_workspaces/GuidedWarrantyClaimDialog.vue").write_text(warranty_dialog)

backend_path = ROOT / "native_visual_workspaces.py"
backend = backend_path.read_text()
backend = replace_once(
    backend,
    '"description": "Review warranty and maintenance activity in EdgeSuite, then use ERPNext for authoritative creation, editing, submission, scheduling, and lifecycle actions.",',
    '"description": "Manage warranty intake and resolution in EdgeSuite while ERPNext Warranty Claim remains authoritative; maintenance scheduling and visits continue through their permitted native lifecycle.",',
    "service workspace description",
)
backend = replace_once(
    backend,
    '"description": "Customer warranty cases, serial eligibility, complaint status, and ERPNext resolution lifecycle.",',
    '"description": "Customer warranty cases, serial eligibility, complaint status, and permission-aware EdgeSuite resolution updates on the authoritative ERPNext Warranty Claim record.",',
    "warranty source description",
)
backend = replace_once(
    backend,
    '\t\t"native_handoff": 1,\n\t}\n',
    '\t\t"native_handoff": 1,\n\t\t"access": _get_edgesuite_access_context(),\n\t}\n',
    "workspace access context",
)
backend = replace_once(
    backend,
    '\t\t"can_create": int(bool(frappe.has_permission(doctype, "create"))),\n\t\t"columns": columns,\n',
    '\t\t"can_create": int(bool(frappe.has_permission(doctype, "create"))),\n\t\t"can_write": int(bool(frappe.has_permission(doctype, "write"))),\n\t\t"columns": columns,\n',
    "doctype write capability",
)
old_page = '''def _resolve_page_source(source: dict[str, Any]) -> dict[str, Any] | None:\n\tif not frappe.db.exists("Page", source["target"]):\n\t\treturn None\n\treturn {\n'''
new_page = '''def _resolve_page_source(source: dict[str, Any]) -> dict[str, Any] | None:\n\tif not frappe.db.exists("Page", source["target"]):\n\t\treturn None\n\ttry:\n\t\tpage = frappe.get_doc("Page", source["target"])\n\t\tif not page.is_permitted():\n\t\t\treturn None\n\texcept Exception:\n\t\treturn None\n\treturn {\n'''
backend = replace_once(backend, old_page, new_page, "page permission")
backend = replace_once(
    backend,
    '\n\ndef _assert_authenticated() -> None:\n',
    '\n\ndef _get_edgesuite_access_context() -> dict[str, Any]:\n\ttry:\n\t\tfrom edgesuite_ui.access_control import get_access_context\n\texcept ImportError:\n\t\treturn {\n\t\t\t"mode": "native_desk",\n\t\t\t"restricted_to_edgesuite": False,\n\t\t\t"can_use_native_desk": True,\n\t\t\t"authorization_source": "frappe_permissions",\n\t\t}\n\treturn dict(get_access_context())\n\n\ndef _assert_authenticated() -> None:\n',
    "access helper",
)
backend_path.write_text(backend)

vue_path = ROOT / "public/js/native_visual_workspaces/NativeERPNextWorkspace.vue"
vue = vue_path.read_text()
vue = replace_once(
    vue,
    '\t\t\t\t\t<span>Native lifecycle handoff</span>\n',
    '\t\t\t\t\t<span v-if="nativeFallbackEnabled">Native lifecycle handoff</span>\n\t\t\t\t\t<span v-else>EdgeSuite operational access</span>\n',
    "workspace badge",
)
old_actions = '''\t\t\t\t\t\t\t<div class="native-control-card-actions">\n\t\t\t\t\t\t\t\t<button class="edge-primary-button" type="button" @click="openSource(source)">\n\t\t\t\t\t\t\t\t\t{{ source.kind === "report" ? "Open report" : source.kind === "page" ? "Open workspace" : "Open records" }}\n\t\t\t\t\t\t\t\t</button>\n\t\t\t\t\t\t\t\t<button\n\t\t\t\t\t\t\t\t\tv-if="source.kind === 'doctype' && source.can_create"\n\t\t\t\t\t\t\t\t\tclass="edge-secondary-button"\n\t\t\t\t\t\t\t\t\ttype="button"\n\t\t\t\t\t\t\t\t\t@click="createSource(source)"\n\t\t\t\t\t\t\t\t>\n\t\t\t\t\t\t\t\t\tNew\n\t\t\t\t\t\t\t\t</button>\n\t\t\t\t\t\t\t</div>\n'''
new_actions = '''\t\t\t\t\t\t\t<div class="native-control-card-actions">\n\t\t\t\t\t\t\t\t<button\n\t\t\t\t\t\t\t\t\tv-if="isWarrantySource(source) && source.can_create"\n\t\t\t\t\t\t\t\t\tclass="edge-primary-button"\n\t\t\t\t\t\t\t\t\ttype="button"\n\t\t\t\t\t\t\t\t\t@click="openWarrantyClaim()"\n\t\t\t\t\t\t\t\t>\n\t\t\t\t\t\t\t\t\tNew claim\n\t\t\t\t\t\t\t\t</button>\n\t\t\t\t\t\t\t\t<button\n\t\t\t\t\t\t\t\t\tv-if="canOpenSource(source)"\n\t\t\t\t\t\t\t\t\t:class="isWarrantySource(source) && source.can_create ? 'edge-secondary-button' : 'edge-primary-button'"\n\t\t\t\t\t\t\t\t\ttype="button"\n\t\t\t\t\t\t\t\t\t@click="openSource(source)"\n\t\t\t\t\t\t\t\t>\n\t\t\t\t\t\t\t\t\t{{ sourceActionLabel(source) }}\n\t\t\t\t\t\t\t\t</button>\n\t\t\t\t\t\t\t\t<button\n\t\t\t\t\t\t\t\t\tv-if="nativeFallbackEnabled && source.kind === 'doctype' && source.can_create && !isWarrantySource(source)"\n\t\t\t\t\t\t\t\t\tclass="edge-secondary-button"\n\t\t\t\t\t\t\t\t\ttype="button"\n\t\t\t\t\t\t\t\t\t@click="createSource(source)"\n\t\t\t\t\t\t\t\t>\n\t\t\t\t\t\t\t\t\tNew\n\t\t\t\t\t\t\t\t</button>\n\t\t\t\t\t\t\t</div>\n'''
vue = replace_once(vue, old_actions, new_actions, "workspace card actions")
vue = replace_once(
    vue,
    '\t\t\t\t\t\t<button class="edge-secondary-button" type="button" @click="openSource(source)">View all</button>\n',
    '\t\t\t\t\t\t<button v-if="nativeFallbackEnabled" class="edge-secondary-button" type="button" @click="openSource(source)">View all</button>\n',
    "view all fallback",
)
vue = replace_once(
    vue,
    '\t\t\t\t\t\ttabindex="0"\n\t\t\t\t\t\t@click="openRow(source, row)"\n\t\t\t\t\t\t@keydown.enter="openRow(source, row)"\n',
    '\t\t\t\t\t\t:tabindex="canOpenRow(source) ? 0 : -1"\n\t\t\t\t\t\t:class="{ \'is-actionable\': canOpenRow(source) }"\n\t\t\t\t\t\t@click="openRow(source, row)"\n\t\t\t\t\t\t@keydown.enter="openRow(source, row)"\n',
    "row actionability",
)
old_note = '''\t\t\t\t<section class="native-control-note">\n\t\t\t\t\t<strong>Accounting and workflow safety</strong>\n\t\t\t\t\t<p>\n\t\t\t\t\t\tThis EdgeSuite surface is read-only. Creation and changes continue through ERPNext's permitted native document and report workflows; RetailEdge does not create a second ledger, lifecycle, commission engine, or budget engine here.\n\t\t\t\t\t</p>\n\t\t\t\t</section>\n'''
new_note = '''\t\t\t\t<section class="native-control-note">\n\t\t\t\t\t<strong>Accounting and workflow safety</strong>\n\t\t\t\t\t<p v-if="workspaceKey === 'service-warranty'">\n\t\t\t\t\t\tWarranty intake and permitted status/resolution updates write directly to the authoritative ERPNext Warranty Claim record. Maintenance Schedule, Maintenance Visit and advanced native lifecycle actions remain in ERPNext; RetailEdge does not create a parallel service ledger or warranty engine.\n\t\t\t\t\t</p>\n\t\t\t\t\t<p v-else>\n\t\t\t\t\t\tThis EdgeSuite surface is read-only. Creation and changes continue through ERPNext's permitted native document and report workflows; RetailEdge does not create a second ledger, lifecycle, commission engine, or budget engine here.\n\t\t\t\t\t</p>\n\t\t\t\t</section>\n'''
vue = replace_once(vue, old_note, new_note, "safety note")
vue = replace_once(
    vue,
    '\t\t</div>\n\t</EdgeAppShell>\n</template>\n\n<script>\n',
    '\t\t</div>\n\n\t\t<GuidedWarrantyClaimDialog\n\t\t\t:open="warrantyDialogOpen"\n\t\t\t:claim-name="warrantyClaimName"\n\t\t\t:native-fallback-enabled="nativeFallbackEnabled"\n\t\t\t@close="closeWarrantyClaim"\n\t\t\t@saved="handleWarrantySaved"\n\t\t\t@open-native="openNativeWarrantyClaim"\n\t\t/>\n\t</EdgeAppShell>\n</template>\n\n<script>\nimport GuidedWarrantyClaimDialog from "./GuidedWarrantyClaimDialog.vue";\n',
    "guided dialog mount",
)
vue = replace_once(
    vue,
    '\tcomponents: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),\n',
    '\tcomponents: {\n\t\t...Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),\n\t\tGuidedWarrantyClaimDialog,\n\t},\n',
    "guided dialog component",
)
vue = replace_once(
    vue,
    '\t\t\tmenuItems: [],\n\t\t};\n',
    '\t\t\tmenuItems: [],\n\t\t\taccessContext: { mode: "native_desk", restricted_to_edgesuite: false, can_use_native_desk: true },\n\t\t\twarrantyDialogOpen: false,\n\t\t\twarrantyClaimName: "",\n\t\t};\n',
    "workspace access state",
)
vue = replace_once(
    vue,
    '\t\trecordSources() {\n\t\t\treturn this.sources.filter((source) => source.kind === "doctype");\n\t\t},\n',
    '\t\trecordSources() {\n\t\t\treturn this.sources.filter((source) => source.kind === "doctype");\n\t\t},\n\t\tnativeFallbackEnabled() {\n\t\t\treturn this.accessContext.can_use_native_desk !== false;\n\t\t},\n',
    "native fallback computed",
)
vue = replace_once(
    vue,
    '\t\t\t\tthis.sources = Array.isArray(workspace.sources) ? workspace.sources : [];\n\t\t\t\tthis.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);\n',
    '\t\t\t\tthis.sources = Array.isArray(workspace.sources) ? workspace.sources : [];\n\t\t\t\tthis.accessContext = { ...this.accessContext, ...(workspace.access || navigation.access || {}) };\n\t\t\t\tthis.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);\n',
    "workspace access application",
)
methods_anchor = '''\t\tkindLabel(kind) {\n'''
methods_insert = '''\t\tisWarrantySource(source) {\n\t\t\treturn this.workspaceKey === "service-warranty" && source?.kind === "doctype" && source?.target === "Warranty Claim";\n\t\t},\n\t\tcanOpenSource(source) {\n\t\t\tif (source?.kind === "page") return true;\n\t\t\treturn this.nativeFallbackEnabled;\n\t\t},\n\t\tcanOpenRow(source) {\n\t\t\tif (this.isWarrantySource(source)) return Boolean(source?.can_write);\n\t\t\treturn this.nativeFallbackEnabled;\n\t\t},\n\t\tsourceActionLabel(source) {\n\t\t\tif (source?.kind === "report") return "Open report";\n\t\t\tif (source?.kind === "page") return "Open workspace";\n\t\t\treturn "Open records";\n\t\t},\n\t\topenWarrantyClaim(name = "") {\n\t\t\tthis.warrantyClaimName = name || "";\n\t\t\tthis.warrantyDialogOpen = true;\n\t\t},\n\t\tcloseWarrantyClaim() {\n\t\t\tthis.warrantyDialogOpen = false;\n\t\t\tthis.warrantyClaimName = "";\n\t\t},\n\t\thandleWarrantySaved(result) {\n\t\t\tthis.closeWarrantyClaim();\n\t\t\tfrappe.show_alert?.({\n\t\t\t\tmessage: `Warranty Claim ${result?.name || ""} saved`,\n\t\t\t\tindicator: "green",\n\t\t\t});\n\t\t\tthis.loadWorkspace();\n\t\t},\n\t\topenNativeWarrantyClaim(name) {\n\t\t\tif (!this.nativeFallbackEnabled || !name) return;\n\t\t\tthis.closeWarrantyClaim();\n\t\t\tfrappe.set_route("Form", "Warranty Claim", name);\n\t\t},\n\t\tkindLabel(kind) {\n'''
vue = replace_once(vue, methods_anchor, methods_insert, "warranty workspace methods")
vue = replace_once(
    vue,
    '\t\topenSource(source) {\n\t\t\tif (source.kind === "doctype") frappe.set_route("List", source.target);\n\t\t\telse if (source.kind === "report") frappe.set_route("query-report", source.target);\n\t\t\telse if (source.kind === "page") frappe.set_route(source.target);\n\t\t},\n',
    '\t\topenSource(source) {\n\t\t\tif (!this.canOpenSource(source)) return;\n\t\t\tif (source.kind === "doctype") frappe.set_route("List", source.target);\n\t\t\telse if (source.kind === "report") frappe.set_route("query-report", source.target);\n\t\t\telse if (source.kind === "page") frappe.set_route(source.target);\n\t\t},\n',
    "open source guard",
)
vue = replace_once(
    vue,
    '\t\tcreateSource(source) {\n\t\t\tif (source.kind !== "doctype" || !source.can_create) return;\n\t\t\tfrappe.new_doc(source.target);\n\t\t},\n',
    '\t\tcreateSource(source) {\n\t\t\tif (!this.nativeFallbackEnabled || source.kind !== "doctype" || !source.can_create) return;\n\t\t\tfrappe.new_doc(source.target);\n\t\t},\n',
    "create source guard",
)
vue = replace_once(
    vue,
    '\t\topenRow(source, row) {\n\t\t\tif (source.kind !== "doctype" || !row?.name) return;\n\t\t\tfrappe.set_route("Form", source.target, row.name);\n\t\t},\n',
    '\t\topenRow(source, row) {\n\t\t\tif (source.kind !== "doctype" || !row?.name || !this.canOpenRow(source)) return;\n\t\t\tif (this.isWarrantySource(source)) {\n\t\t\t\tthis.openWarrantyClaim(row.name);\n\t\t\t\treturn;\n\t\t\t}\n\t\t\tfrappe.set_route("Form", source.target, row.name);\n\t\t},\n',
    "open row guided warranty",
)
vue = replace_once(
    vue,
    '\t\t\t\titems: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })),\n',
    '\t\t\t\titems: (group.items || []).map((item) => ({\n\t\t\t\t\t...item,\n\t\t\t\t\tlink_type: item.target_type,\n\t\t\t\t\tlink_to: item.target,\n\t\t\t\t\troute: this.routeForItem(item),\n\t\t\t\t})),\n',
    "navigation metadata",
)
vue = replace_once(
    vue,
    '''\t\telse if (item.target_type === "DocType") frappe.set_route("List", item.target);\n\t\t\telse if (item.target_type === "URL" && item.target) window.location.assign(item.target);\n''',
    '''\t\telse if (item.target_type === "DocType" && this.nativeFallbackEnabled) frappe.set_route("List", item.target);\n\t\t\telse if (item.target_type === "URL" && item.target) window.location.assign(item.target);\n''',
    "navigation native guard",
)
vue = replace_once(
    vue,
    '''.native-control-table tbody tr {\n\tcursor: pointer;\n}\n.native-control-table tbody tr:hover,\n.native-control-table tbody tr:focus-within,\n.native-control-table tbody tr:focus {\n''',
    '''.native-control-table tbody tr.is-actionable {\n\tcursor: pointer;\n}\n.native-control-table tbody tr.is-actionable:hover,\n.native-control-table tbody tr.is-actionable:focus-within,\n.native-control-table tbody tr.is-actionable:focus {\n''',
    "row cursor safety",
)
vue_path.write_text(vue)

contract_path = ROOT / "tests/test_native_visual_workspace_contract.py"
contract = contract_path.read_text()
contract = contract.replace('\n\t\t\t"frappe.get_doc(",', '')
contract = replace_once(
    contract,
    '\t\tself.assertIn("get_report_doc(source[\\\"target\\\"])", source)\n',
    '\t\tself.assertIn("get_report_doc(source[\\\"target\\\"])", source)\n\t\tself.assertIn(\'frappe.get_doc("Page", source["target"])\', source)\n\t\tself.assertIn("page.is_permitted()", source)\n',
    "page permission contract",
)
contract_path.write_text(contract)

warranty_test = r'''from __future__ import annotations

import unittest
from pathlib import Path

from retailedge import guided_warranty_claim

APP_ROOT = Path(__file__).resolve().parents[1]


class GuidedWarrantyClaimContractTests(unittest.TestCase):
	def test_status_contract_excludes_cancelled_from_guided_updates(self):
		self.assertEqual(
			guided_warranty_claim.EDITABLE_STATUSES,
			{"Open", "Work In Progress", "Closed"},
		)

	def test_backend_uses_authoritative_warranty_claim_without_unsafe_bypass(self):
		source = (APP_ROOT / "guided_warranty_claim.py").read_text()
		self.assertIn('frappe.new_doc(WARRANTY_CLAIM_DOCTYPE)', source)
		self.assertIn("doc.insert()", source)
		self.assertIn("doc.save()", source)
		self.assertIn('frappe.has_permission(WARRANTY_CLAIM_DOCTYPE, "create")', source)
		self.assertIn('frappe.has_permission(WARRANTY_CLAIM_DOCTYPE, "write", doc=name)', source)
		self.assertIn('_assert_read_permission("Serial No", serial_no)', source)
		self.assertIn("serial.company != company", source)
		self.assertIn("serial.customer != customer", source)
		for forbidden in (
			"ignore_permissions",
			"frappe.db.commit",
			".submit(",
			"GL Entry",
			"Stock Ledger Entry",
		):
			self.assertNotIn(forbidden, source)

	def test_service_workspace_uses_guided_claim_and_hides_native_routes_when_restricted(self):
		component = (
			APP_ROOT / "public/js/native_visual_workspaces/NativeERPNextWorkspace.vue"
		).read_text()
		self.assertIn('import GuidedWarrantyClaimDialog from "./GuidedWarrantyClaimDialog.vue"', component)
		self.assertIn("nativeFallbackEnabled", component)
		self.assertIn("isWarrantySource(source)", component)
		self.assertIn("this.openWarrantyClaim(row.name)", component)
		self.assertIn("link_type: item.target_type", component)
		self.assertIn("if (!this.canOpenSource(source)) return", component)
		self.assertIn("!this.nativeFallbackEnabled", component)

	def test_dialog_cascades_customer_and_item_changes_into_serial_reset(self):
		dialog = (
			APP_ROOT / "public/js/native_visual_workspaces/GuidedWarrantyClaimDialog.vue"
		).read_text()
		self.assertIn("setCustomer(next)", dialog)
		self.assertIn("setItem(next)", dialog)
		self.assertIn("this.clearSerialDetails()", dialog)
		self.assertIn("get_guided_warranty_serial_details", dialog)
		self.assertIn('v-if="nativeFallbackEnabled && claimName"', dialog)

	def test_native_workspace_exposes_access_and_record_write_capability(self):
		source = (APP_ROOT / "native_visual_workspaces.py").read_text()
		self.assertIn('"access": _get_edgesuite_access_context()', source)
		self.assertIn('"can_write": int(bool(frappe.has_permission(doctype, "write")))', source)
		self.assertIn("page.is_permitted()", source)


if __name__ == "__main__":
	unittest.main()
'''
(ROOT / "tests/test_guided_warranty_claim_contract.py").write_text(warranty_test)

b2_doc = r'''# RetailEdge Pre-Reporting B2 — Warranty Operations

## Goal

Close the first confirmed everyday-user gap after B1 by giving permitted service staff an EdgeSuite-first Warranty Claim intake and resolution path without creating a parallel warranty system.

## Authority

ERPNext `Warranty Claim` remains the only warranty-case record and lifecycle source of truth. RetailEdge uses the normal Frappe document API and normal ERPNext permissions to create or update that record.

The guided workflow does not create a RetailEdge warranty DocType, does not submit documents, does not post accounting or stock entries, and does not use `ignore_permissions`.

## Delivered

- New permission-aware guided Warranty Claim backend.
- New EdgeSuite Warranty Claim dialog inside **Service & Warranty**.
- New claim creation for users with native ERPNext `Warranty Claim` Create permission.
- Existing claim updates for users with native Write permission.
- Supported guided statuses are `Open`, `Work In Progress`, and `Closed`.
- Cancellation remains outside the guided workflow.
- Customer, Item and Serial No searches use permission-aware Frappe link search.
- Serial No options are constrained by active Company and selected Item/Customer where supported.
- Server validation re-checks Company, Customer, Item and Serial No relationships before every save.
- Customer or Item changes clear a selected Serial No so stale dependent values cannot survive.
- Closing a claim uses ERPNext's own `WarrantyClaim.validate()` behavior for resolution date; RetailEdge sets the current user as `resolved_by` when closing an otherwise unresolved claim.
- EdgeSuite-only users no longer see native Open/New/View-all controls in the generic C27 control workspace where those controls would route into blocked native Desk surfaces.
- The generic control workspace now preserves `link_type` / `link_to` so the shared EdgeSuite Desk Access guard can filter native menu items correctly.
- Native Page sources are checked with Frappe `Page.is_permitted()` before being advertised.

## Deliberately native / out of scope

B2 Warranty Operations does not replace:

- Maintenance Schedule creation/editing;
- Maintenance Visit creation/editing;
- Warranty Claim cancellation;
- advanced ERPNext support administration;
- Item, Serial No or Customer master-data administration;
- any accounting or stock lifecycle;
- reporting development.

Users with **Native Desk + EdgeSuite** retain native record/list handoffs. `edgesuite_only` users remain inside verified EdgeSuite operational pages.

## Backward compatibility

Existing Warranty Claims are unchanged. The guided form reads and writes the same standard ERPNext fields and invokes normal document validation. Existing native workflows remain available to advanced users.

No schema migration is required.

## Validation required

1. Guest access is denied.
2. Create and update require normal Warranty Claim permissions.
3. Company/Customer/Item/Serial relationships are validated server-side.
4. Disabled Items are rejected.
5. Guided status updates cannot set `Cancelled`.
6. EdgeSuite-only users do not receive native workspace handoff controls.
7. Native Desk users retain native handoffs.
8. Theme, linters, clean Frappe v16 full tests, and governed EdgeSuite UI candidate compatibility pass on the exact B2 head.

## Next B2 audit targets

After this checkpoint is green, continue with the next ordinary-user workflow gaps in priority order: Purchase Order/Receipt, Sales Order/Delivery, and operational review queues. Implement only where the repo audit proves an EdgeSuite-only persona otherwise cannot complete a normal business process.
'''
(DOCS / "prereporting_b2_warranty_operations.md").write_text(b2_doc)
