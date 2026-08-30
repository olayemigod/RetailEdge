<template>
	<div v-if="!edgeUIValid" class="supplier-review-fallback">
		<strong>Supplier Document Review could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="Retail"
		title="Supplier Document Review"
		:tenantName="tenantName || filters.company"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/supplier-document-review"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<section class="supplier-review-page">
			<header class="supplier-review-hero">
				<div>
					<div class="supplier-review-eyebrow">Suppliers & Payables</div>
					<h2>Supplier Document Review</h2>
					<p>Review private supplier invoices, record advisory extraction evidence, and explicitly prepare ERPNext Purchase Invoice drafts from the authoritative Purchase Order.</p>
				</div>
				<div class="supplier-review-actions">
					<button class="edge-secondary-button" type="button" @click="openPurchaseInvoices">Purchase Invoices</button>
					<button class="edge-secondary-button" type="button" :disabled="loading" @click="loadRows">{{ loading ? "Refreshing…" : "Refresh" }}</button>
				</div>
			</header>

			<div class="supplier-review-metrics">
				<article><span>Open Review</span><strong>{{ summary.open || 0 }}</strong></article>
				<article><span>Needs Extraction</span><strong>{{ summary.pending_extraction || 0 }}</strong></article>
				<article><span>Needs Extraction Review</span><strong>{{ summary.pending_extraction_review || 0 }}</strong></article>
				<article><span>Ready for Draft</span><strong>{{ summary.ready_for_invoice || 0 }}</strong></article>
			</div>

			<section class="supplier-review-panel">
				<div class="supplier-review-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.supplier" :selectedLabel="supplierLabel" label="Supplier" placeholder="All suppliers" :searcher="supplierSearch" @select="onSupplierSelected" @clear="clearSupplier" />
					<label class="supplier-review-select">
						<span>Status</span>
						<select v-model="filters.status" @change="loadRows">
							<option>Open</option><option>Pending Review</option><option>In Review</option><option>Accepted</option><option>Rejected</option><option>All</option>
						</select>
					</label>
					<div class="supplier-review-filter-action"><button class="edge-primary-button" type="button" :disabled="loading" @click="loadRows">Apply Filters</button></div>
				</div>

				<div v-if="error" class="supplier-review-error">{{ error }}</div>
				<div v-else-if="loading" class="supplier-review-state">Loading supplier document review queue…</div>
				<div v-else-if="!rows.length" class="supplier-review-state">No supplier documents match the current permitted scope.</div>
				<div v-else class="supplier-review-table-wrap">
					<table class="supplier-review-table">
						<thead><tr><th>Document</th><th>Supplier / PO</th><th>Intake</th><th>Extraction</th><th class="num">Extracted Total</th><th>Purchase Invoice</th><th>Actions</th></tr></thead>
						<tbody>
							<tr v-for="row in rows" :key="row.intake">
								<td><strong>{{ row.original_file_name }}</strong><small>{{ row.document_type }} · {{ formatDateTime(row.submitted_on) }}</small><button v-if="row.source_file_url" class="edge-link-button" type="button" @click="openSourceFile(row)">View private source</button></td>
								<td><strong>{{ row.supplier }}</strong><button class="edge-link-button" type="button" @click="openPurchaseOrder(row.purchase_order)">{{ row.purchase_order }}</button><small>{{ row.company }}<template v-if="row.branch"> · {{ row.branch }}</template></small></td>
								<td><span class="review-status" :data-status="row.intake_review_status">{{ row.intake_review_status }}</span><small v-if="row.intake_review_notes">{{ row.intake_review_notes }}</small></td>
								<td><template v-if="row.extraction"><strong>{{ row.extracted_document_number || "No document number" }}</strong><small>{{ row.extraction_method }} · {{ row.extraction_review_status }}</small><small v-if="row.extracted_currency">{{ row.extracted_currency }}</small></template><span v-else>Not recorded</span></td>
								<td class="num">{{ formatMoney(row.extracted_total, row.extracted_currency || row.purchase_order_currency) }}</td>
								<td><button v-if="row.purchase_invoice" class="edge-link-button" type="button" @click="openPurchaseInvoice(row.purchase_invoice)">{{ row.purchase_invoice }}</button><span v-else>—</span><small v-if="row.purchase_invoice">Draft prepared from ERPNext PO mapping</small></td>
								<td class="supplier-review-row-actions">
									<button v-if="row.intake_review_status === 'Pending Review'" class="edge-small-button" type="button" @click="setIntakeStatus(row, 'In Review')">Start Review</button>
									<button v-if="!row.extraction && !isIntakeFinal(row)" class="edge-small-button" type="button" @click="openExtractionModal(row)">Record Extraction</button>
									<template v-if="row.extraction && row.extraction_review_status === 'Pending Review'"><button class="edge-small-button" type="button" @click="reviewExtraction(row, 'Accepted')">Accept Extraction</button><button class="edge-small-button danger" type="button" @click="openReviewModal('extraction', row, 'Rejected')">Reject Extraction</button></template>
									<template v-if="row.extraction_review_status === 'Accepted' && !isIntakeFinal(row)"><button class="edge-small-button" type="button" @click="setIntakeStatus(row, 'Accepted')">Accept Document</button><button class="edge-small-button danger" type="button" @click="openReviewModal('intake', row, 'Rejected')">Reject Document</button></template>
									<button v-if="row.ready_for_draft_purchase_invoice" class="edge-primary-button compact" type="button" @click="prepareDraft(row)">Prepare Draft PI</button>
									<button v-if="row.purchase_invoice" class="edge-secondary-button compact" type="button" @click="openPurchaseInvoice(row.purchase_invoice)">Open Draft</button>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>

			<div class="supplier-review-safety"><strong>Accounting safety:</strong> Extraction values are review evidence only. Purchase Invoice items, quantities, rates, taxes and Purchase Order links come from ERPNext's native Purchase Order mapper. This workspace creates drafts only and never submits Purchase Invoices or posts payments, GL Entries or Stock Ledger Entries.</div>
		</section>

		<div v-if="modal.type" class="edge-modal-backdrop" @click.self="closeModal">
			<section class="edge-modal-card" role="dialog" aria-modal="true" :aria-label="modalTitle">
				<header><div><div class="supplier-review-eyebrow">Human review required</div><h3>{{ modalTitle }}</h3></div><button class="edge-secondary-button compact" type="button" @click="closeModal">Close</button></header>
				<div v-if="modal.type === 'extraction'" class="edge-modal-form">
					<label><span>Supplier Document Number</span><input v-model.trim="modal.form.document_number" type="text" required /></label>
					<label><span>Document Date</span><input v-model="modal.form.document_date" type="date" /></label>
					<label><span>Currency</span><input v-model.trim="modal.form.currency" type="text" maxlength="20" placeholder="e.g. NGN" /></label>
					<label><span>Subtotal</span><input v-model="modal.form.subtotal" type="number" step="0.01" /></label>
					<label><span>Tax</span><input v-model="modal.form.tax_amount" type="number" step="0.01" /></label>
					<label><span>Total</span><input v-model="modal.form.total" type="number" step="0.01" /></label>
					<label class="wide"><span>Purchase Order reference visible on supplier document</span><input v-model.trim="modal.form.purchase_order_reference" type="text" /></label>
				</div>
				<div v-else class="edge-modal-form"><label class="wide"><span>Review Notes</span><textarea v-model.trim="modal.form.review_notes" rows="5" :required="modal.decision === 'Rejected'"></textarea></label></div>
				<div v-if="modal.error" class="supplier-review-error">{{ modal.error }}</div>
				<footer><button class="edge-secondary-button" type="button" @click="closeModal">Cancel</button><button class="edge-primary-button" type="button" :disabled="modal.saving" @click="submitModal">{{ modal.saving ? "Saving…" : modalSubmitLabel }}</button></footer>
			</section>
		</div>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeLinkField"];
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "SupplierDocumentReview",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() { return { edgeUIValid: true, missingComponents: [], loading: false, error: "", rows: [], summary: {}, menuItems: [], tenantName: "", branchName: "", userName: "", supplierLabel: "", filters: { company: "", branch: "", supplier: "", status: "Open" }, modal: { type: "", row: null, decision: "", saving: false, error: "", form: {} } }; },
	computed: {
		modalTitle() { if (this.modal.type === "extraction") return "Record Manual Extraction"; if (this.modal.type === "extraction-review") return `${this.modal.decision} Extraction`; if (this.modal.type === "intake-review") return `${this.modal.decision} Supplier Document`; return "Supplier Document Review"; },
		modalSubmitLabel() { if (this.modal.type === "extraction") return "Record Immutable Extraction"; return this.modal.decision || "Save"; },
	},
	created() { const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; },
	mounted() { if (this.edgeUIValid) this.loadMetadata(); },
	methods: {
		async loadMetadata() {
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod("retailedge.supplier_document_review.get_supplier_document_review_context", { status: "Open" }), navigationPromise]);
				this.applyContext(context); this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
			} catch (error) { this.error = errorMessage(error, "Supplier Document Review controls failed to load."); }
		},
		applyContext(context) { const defaults = context.default_filters || {}; if (!this.filters.company) this.filters.company = defaults.company || ""; if (!this.filters.branch) this.filters.branch = defaults.branch || ""; this.tenantName = context.tenant_name || this.filters.company; this.branchName = context.branch_name || this.filters.branch; this.userName = context.user_name || this.userName; this.rows = context.rows || []; this.summary = context.summary || {}; },
		async loadRows() { this.loading = true; this.error = ""; try { const context = await callMethod("retailedge.supplier_document_review.get_supplier_document_review_context", { company: this.filters.company, branch: this.filters.branch, supplier: this.filters.supplier, status: this.filters.status, limit: 100 }); this.applyContext(context); } catch (error) { this.rows = []; this.summary = {}; this.error = errorMessage(error, "Supplier document review queue failed to load."); } finally { this.loading = false; } },
		async searchOptions(kind, txt) { const result = await callMethod("retailedge.supplier_document_review.search_supplier_document_review_options", { kind, txt, company: this.filters.company }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); }, supplierSearch(txt) { return this.searchOptions("supplier", txt); },
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.filters.supplier = ""; this.branchName = ""; this.supplierLabel = ""; this.loadRows(); },
		onBranchSelected(option) { this.filters.branch = option.value; this.branchName = option.label || option.value; this.loadRows(); }, clearBranch() { this.filters.branch = ""; this.branchName = ""; this.loadRows(); },
		onSupplierSelected(option) { this.filters.supplier = option.value; this.supplierLabel = option.label || option.value; this.loadRows(); }, clearSupplier() { this.filters.supplier = ""; this.supplierLabel = ""; this.loadRows(); },
		isIntakeFinal(row) { return ["Accepted", "Rejected"].includes(row.intake_review_status); },
		openExtractionModal(row) { this.modal = { type: "extraction", row, decision: "", saving: false, error: "", form: { document_number: "", document_date: "", currency: row.purchase_order_currency || "", subtotal: "", tax_amount: "", total: "", purchase_order_reference: row.purchase_order || "" } }; },
		openReviewModal(kind, row, decision) { this.modal = { type: kind === "intake" ? "intake-review" : "extraction-review", row, decision, saving: false, error: "", form: { review_notes: "" } }; },
		closeModal() { if (!this.modal.saving) this.modal = { type: "", row: null, decision: "", saving: false, error: "", form: {} }; },
		async submitModal() { if (!this.modal.row) return; this.modal.saving = true; this.modal.error = ""; try { if (this.modal.type === "extraction") { if (!this.modal.form.document_number) throw new Error("Supplier Document Number is required."); await callMethod("retailedge.supplier_document_extraction.record_manual_extraction", { intake_name: this.modal.row.intake, ...this.modal.form }); } else if (this.modal.type === "extraction-review") { await callMethod("retailedge.supplier_document_extraction.record_extraction_review", { extraction_name: this.modal.row.extraction, decision: this.modal.decision, review_notes: this.modal.form.review_notes || "" }); } else if (this.modal.type === "intake-review") { await callMethod("retailedge.supplier_document_review.review_supplier_document_intake", { intake_name: this.modal.row.intake, review_status: this.modal.decision, review_notes: this.modal.form.review_notes || "" }); } this.closeModal(); await this.loadRows(); } catch (error) { this.modal.error = errorMessage(error, "Review action failed."); } finally { this.modal.saving = false; } },
		async reviewExtraction(row, decision) { try { await callMethod("retailedge.supplier_document_extraction.record_extraction_review", { extraction_name: row.extraction, decision, review_notes: "" }); await this.loadRows(); } catch (error) { this.error = errorMessage(error, "Extraction review failed."); } },
		async setIntakeStatus(row, reviewStatus) { try { await callMethod("retailedge.supplier_document_review.review_supplier_document_intake", { intake_name: row.intake, review_status: reviewStatus, review_notes: "" }); await this.loadRows(); } catch (error) { this.error = errorMessage(error, "Supplier document review failed."); } },
		async prepareDraft(row) { try { const result = await callMethod("retailedge.supplier_document_review.prepare_draft_purchase_invoice", { extraction_name: row.extraction }); frappe.show_alert({ message: result.created ? __("Draft Purchase Invoice prepared from ERPNext Purchase Order.") : __("Existing Purchase Invoice handoff reopened."), indicator: "green" }); await this.loadRows(); if (result.purchase_invoice) this.openPurchaseInvoice(result.purchase_invoice); } catch (error) { this.error = errorMessage(error, "Purchase Invoice draft could not be prepared."); } },
		openSourceFile(row) { if (row.source_file_url) window.open(row.source_file_url, "_blank", "noopener,noreferrer"); }, openPurchaseOrder(name) { frappe.set_route("Form", "Purchase Order", name); }, openPurchaseInvoices() { frappe.set_route("List", "Purchase Invoice"); }, openPurchaseInvoice(name) { frappe.set_route("Form", "Purchase Invoice", name); },
		formatDateTime(value) { return value ? frappe.datetime.str_to_user(value) : "—"; }, formatMoney(value, currency) { if (value === null || value === undefined || value === "") return "—"; return format_currency(Number(value || 0), currency || undefined); },
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); else if (item.target_type === "URL") window.location.href = item.target; },
	},
};
</script>

<style scoped>
.supplier-review-page{display:grid;gap:1rem;padding:1rem}.supplier-review-hero,.supplier-review-panel,.supplier-review-safety,.edge-modal-card{background:var(--edge-surface,var(--card-bg));border:1px solid var(--edge-border,var(--border-color));border-radius:16px}.supplier-review-hero{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;padding:1.25rem}.supplier-review-hero h2,.edge-modal-card h3{margin:.2rem 0 .45rem;color:var(--edge-text,var(--text-color))}.supplier-review-hero p{margin:0;max-width:820px;color:var(--edge-text-muted,var(--text-muted))}.supplier-review-eyebrow{font-size:.75rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--edge-text-muted,var(--text-muted))}.supplier-review-actions,.supplier-review-row-actions{display:flex;gap:.45rem;flex-wrap:wrap}.supplier-review-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem}.supplier-review-metrics article{background:var(--edge-surface,var(--card-bg));border:1px solid var(--edge-border,var(--border-color));border-radius:14px;padding:1rem;display:grid;gap:.25rem}.supplier-review-metrics span,.supplier-review-table small{color:var(--edge-text-muted,var(--text-muted));font-size:.78rem}.supplier-review-metrics strong{font-size:1.45rem}.supplier-review-panel{padding:1rem;overflow:hidden}.supplier-review-filter-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr)) auto;gap:.75rem;align-items:end;margin-bottom:1rem}.supplier-review-select{display:grid;gap:.35rem}.supplier-review-select>span,.edge-modal-form label>span{font-size:.78rem;font-weight:600;color:var(--edge-text-muted,var(--text-muted))}.supplier-review-select select,.edge-modal-form input,.edge-modal-form textarea{width:100%;min-height:38px;padding:.5rem .65rem;border:1px solid var(--edge-border,var(--border-color));border-radius:10px;background:var(--edge-input-bg,var(--control-bg));color:var(--edge-text,var(--text-color))}.supplier-review-table-wrap{overflow-x:auto}.supplier-review-table{width:100%;border-collapse:collapse;min-width:1080px}.supplier-review-table th,.supplier-review-table td{padding:.75rem;border-bottom:1px solid var(--edge-border,var(--border-color));text-align:left;vertical-align:top}.supplier-review-table th{color:var(--edge-text-muted,var(--text-muted));font-size:.75rem;text-transform:uppercase;letter-spacing:.04em}.supplier-review-table td{color:var(--edge-text,var(--text-color))}.supplier-review-table td>strong,.supplier-review-table td>small{display:block}.supplier-review-table .num{text-align:right;white-space:nowrap}.review-status{display:inline-flex;border-radius:999px;padding:.2rem .55rem;font-size:.75rem;border:1px solid var(--edge-border,var(--border-color))}.review-status[data-status="Accepted"],.review-status[data-status="Rejected"]{font-weight:700}.edge-link-button{border:0;padding:0;background:transparent;color:var(--primary);cursor:pointer;text-align:left}.edge-primary-button,.edge-secondary-button,.edge-small-button{border-radius:10px;min-height:36px;padding:.45rem .75rem;cursor:pointer;border:1px solid var(--edge-border,var(--border-color))}.edge-primary-button{background:var(--primary);color:var(--fg-color,#fff);border-color:var(--primary)}.edge-secondary-button,.edge-small-button{background:var(--edge-surface,var(--card-bg));color:var(--edge-text,var(--text-color))}.edge-small-button{min-height:30px;padding:.3rem .55rem;font-size:.78rem}.compact{min-height:30px;padding:.3rem .55rem}.danger{color:var(--red-600,#c92a2a)}.supplier-review-error,.supplier-review-state,.supplier-review-safety{padding:1rem}.supplier-review-error{border-radius:12px;background:var(--red-50,rgba(220,53,69,.08));color:var(--red-700,#b02a37)}.supplier-review-state{color:var(--edge-text-muted,var(--text-muted));text-align:center}.supplier-review-safety{color:var(--edge-text-muted,var(--text-muted))}.edge-modal-backdrop{position:fixed;inset:0;z-index:1050;background:rgba(0,0,0,.46);display:grid;place-items:center;padding:1rem}.edge-modal-card{width:min(760px,96vw);max-height:90vh;overflow:auto;padding:1rem;box-shadow:0 18px 60px rgba(0,0,0,.24)}.edge-modal-card>header,.edge-modal-card>footer{display:flex;justify-content:space-between;gap:.75rem;align-items:center}.edge-modal-card>footer{justify-content:flex-end;margin-top:1rem}.edge-modal-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem;margin-top:1rem}.edge-modal-form label{display:grid;gap:.35rem}.edge-modal-form .wide{grid-column:1/-1}@media(max-width:900px){.supplier-review-hero{flex-direction:column}.supplier-review-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.supplier-review-filter-grid{grid-template-columns:1fr 1fr}}@media(max-width:620px){.supplier-review-page{padding:.5rem}.supplier-review-metrics,.supplier-review-filter-grid,.edge-modal-form{grid-template-columns:1fr}.edge-modal-form .wide{grid-column:auto}}
</style>
