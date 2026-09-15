<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Document Output & Sharing could not start.</strong>
		<div>Required interface components are unavailable. Refresh the page or contact your administrator.</div>
	</div>

	<EdgeAppShell
		v-else
		product="retailedge"
		title="Document Output & Sharing"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/document-output-sharing"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="document-output-page">
			<EdgePageHeader
				title="Document Output & Sharing"
				description="Preview, print, download and send customer documents from one consistent output workspace."
			/>

			<EdgeLoadingState v-if="loading && !loaded" />
			<EdgeErrorState v-else-if="error" :message="error" @retry="loadWorkspace" />

			<div v-else class="output-content">
				<section class="edge-panel output-policy">
					<div>
						<span class="output-kicker">Document truth</span>
						<h3>ERPNext remains authoritative</h3>
						<p>Output is rendered from the saved ERPNext document. Preview, print, PDF and email use the same selected template and output options without modifying the source transaction.</p>
					</div>
					<EdgeStatusBadge status="Active" />
				</section>

				<section class="edge-panel output-selector">
					<div class="section-heading">
						<div>
							<span class="output-kicker">1. Choose document</span>
							<h3>Find a permitted customer document</h3>
						</div>
						<div v-if="details" class="selected-document-summary">
							<strong>{{ details.name }}</strong>
							<span>{{ details.party || "Customer document" }}<template v-if="details.grand_total"> · {{ details.currency }} {{ formatAmount(details.grand_total) }}</template></span>
						</div>
					</div>

					<div class="selector-grid">
						<EdgeDropdown
							id="output-document-type"
							v-model="selectedDocumentKey"
							:options="readableDocuments.map((document) => ({ value: document.key, label: document.label }))"
							label="Document type"
							placeholder="Choose document type"
							@change="resetDocumentSelection"
						/>
						<div class="document-search-field">
							<EdgeInput
								id="output-document-search"
								v-model="searchText"
								label="Document"
								type="search"
								:disabled="!selectedDocumentKey"
								placeholder="Type document number or customer"
								@input="queueSearch"
							/>
							<button type="button" class="edge-button edge-button--secondary" :disabled="!selectedDocumentKey || searching" @click="searchDocuments">
								{{ searching ? "Searching..." : "Search" }}
							</button>
						</div>
					</div>

					<div v-if="searchResults.length" class="search-results">
						<button v-for="row in searchResults" :key="row.value || row.name" type="button" class="search-result" @click="selectDocument(row)">
							<strong>{{ row.value || row.name }}</strong>
							<span v-if="row.description">{{ row.description }}</span>
						</button>
					</div>
					<EdgeEmptyState v-else-if="searchAttempted && selectedDocumentKey && !searching && !details" title="No permitted documents found" description="Try another document number or check the current Operating Company and Branch." />
				</section>

				<EdgeLoadingState v-if="detailsLoading" message="Loading document output..." />
				<EdgeEmptyState v-else-if="!details" title="Select a document" description="Choose a permitted document to open the live preview and output actions." />

				<div v-else class="output-workbench">
					<section class="edge-panel preview-panel">
						<div class="preview-toolbar">
							<div>
								<span class="output-kicker">2. Preview</span>
								<h3>{{ details.name }}</h3>
								<p>{{ printFormat }}<span v-if="receiptPreview"> · Thermal preview</span></p>
							</div>
							<div class="preview-toolbar-actions">
								<button type="button" class="edge-button edge-button--secondary" :disabled="previewLoading || !details.can_print" @click="refreshPreview">
									{{ previewLoading ? "Refreshing..." : "Refresh" }}
								</button>
								<button type="button" class="edge-button edge-button--secondary" :disabled="!previewHtml || previewLoading" @click="printPreview">
									Print
								</button>
								<button type="button" class="edge-button edge-button--primary" :disabled="!details.can_print" @click="downloadPdf">
									Download PDF
								</button>
							</div>
						</div>

						<p v-if="previewError" class="preview-error" role="alert">{{ previewError }}</p>
						<div class="preview-stage" :class="{ 'receipt-stage': receiptPreview }">
							<EdgeLoadingState v-if="previewLoading && !previewHtml" message="Rendering document preview..." />
							<iframe
								v-else-if="previewHtml"
								ref="documentPreview"
								class="document-preview-frame"
								:class="{ 'receipt-preview-frame': receiptPreview }"
								:srcdoc="previewHtml"
								title="Document print preview"
								sandbox="allow-same-origin allow-modals"
							></iframe>
							<EdgeEmptyState v-else title="Preview unavailable" description="Refresh the preview or select another permitted print format." />
						</div>
					</section>

					<aside class="edge-panel output-actions">
						<div class="section-heading">
							<div>
								<span class="output-kicker">3. Output & share</span>
								<h3>Document options</h3>
							</div>
						</div>

						<EdgeDropdown
							id="output-print-format"
							v-model="printFormat"
							:options="details.print_formats || ['Standard']"
							label="Print Format"
							:disabled="!details.can_print"
							@change="handleOutputOptionChange"
						/>

						<div class="output-option-list">
							<label class="output-toggle">
								<input v-model="useLetterhead" type="checkbox" @change="handleOutputOptionChange" />
								<span><strong>Use ERPNext Letterhead</strong><small>Off by default to avoid duplicating the template logo/header.</small></span>
							</label>
							<label class="output-toggle" :class="{ disabled: !selectedManagedFormat }">
								<input v-model="showLogo" type="checkbox" :disabled="!selectedManagedFormat" @change="handleOutputOptionChange" />
								<span><strong>Include company logo</strong><small>Uses Company Profile logo, then ERPNext Company logo as fallback.</small></span>
							</label>
							<label class="output-toggle" :class="{ disabled: !selectedManagedFormat }">
								<input v-model="includeQr" type="checkbox" :disabled="!selectedManagedFormat" @change="handleOutputOptionChange" />
								<span><strong>Include document QR</strong><small>Adds a document-reference QR to formal documents and receipts.</small></span>
							</label>
						</div>

						<p v-if="!selectedManagedFormat" class="output-note">Logo and QR switches apply to managed Professional/Receipt templates. ERPNext Standard and customer-defined formats render their own layout.</p>

						<div class="secondary-actions">
							<button v-if="canEditSelectedSalesInvoice" type="button" class="edge-button edge-button--secondary" @click="editSelectedSalesInvoice">Edit / Complete Draft</button>
							<button v-if="canUseNativeDesk" type="button" class="edge-button edge-button--secondary" @click="openNativeDocument">Advanced: Open Full Document</button>
						</div>

						<div class="share-section">
							<h4>Email PDF</h4>
							<div v-if="!details.email_configured" class="email-readiness-warning">
								Outgoing email is not configured. Configure a default outgoing Email Account before sending documents.
							</div>
							<EdgeInput id="output-email" v-model="emailRecipient" label="Recipient" type="email" :disabled="!details.can_email || !details.email_configured" placeholder="customer@example.com" />
							<EdgeInput id="output-subject" v-model="emailSubject" label="Subject" type="text" :disabled="!details.can_email || !details.email_configured" />
							<label class="field-label" for="output-message">Message</label>
							<textarea id="output-message" v-model="emailMessage" class="edge-control edge-textarea" :disabled="!details.can_email || !details.email_configured" rows="4"></textarea>
							<button type="button" class="edge-button edge-button--primary" :disabled="!canSendEmail || sendingEmail" @click="sendEmail">
								{{ sendingEmail ? "Queueing..." : "Email PDF" }}
							</button>
						</div>

						<div class="share-section">
							<h4>WhatsApp</h4>
							<p>PDFs remain private. Download the selected PDF, open the prepared message, then attach the PDF in WhatsApp.</p>
							<button type="button" class="edge-button edge-button--secondary" :disabled="preparingWhatsApp" @click="openWhatsApp">
								{{ preparingWhatsApp ? "Preparing..." : "Open WhatsApp Message" }}
							</button>
						</div>
					</aside>
				</div>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const CONTEXT_METHOD = "retailedge.document_output.get_document_output_context";
const SEARCH_METHOD = "retailedge.document_output.search_output_documents";
const DETAILS_METHOD = "retailedge.document_output.get_output_document_details";
const PREVIEW_METHOD = "retailedge.document_output.render_document_preview";
const EMAIL_METHOD = "retailedge.document_output.send_document_email";
const WHATSAPP_METHOD = "retailedge.document_output.get_whatsapp_handoff";
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState", "EdgeStatusBadge", "EdgeDropdown", "EdgeInput"];

function runtimeComponents() {
	const edgeUI = typeof window !== "undefined" ? window.EdgeSuiteUI : null;
	return edgeUI?.components || {};
}

function callMethod(method, args = {}, type = "GET") {
	return new Promise((resolve, reject) => frappe.call({
		method,
		args,
		type,
		callback: (response) => resolve(response.message || {}),
		error: reject,
	}));
}

function doctypeSlug(doctype) {
	return String(doctype || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function parseErrorPayload(value) {
	if (!value) return "";
	if (Array.isArray(value)) {
		for (const item of value) {
			const message = parseErrorPayload(item);
			if (message) return message;
		}
		return "";
	}
	if (typeof value === "object") {
		for (const key of ["message", "description", "exception"]) {
			const message = parseErrorPayload(value[key]);
			if (message) return message;
		}
		return "";
	}
	const text = String(value || "").trim();
	if (!text) return "";
	try {
		const parsed = JSON.parse(text);
		if (parsed !== text) {
			const message = parseErrorPayload(parsed);
			if (message) return message;
		}
	} catch (_error) {
		// Plain text continues below.
	}
	if (/Traceback \(most recent call last\)/i.test(text)) return "";
	return text;
}

function errorMessage(error, fallback) {
	const response = error?.responseJSON || error || {};
	for (const candidate of [response?._server_messages, response?.message, error?.message, response?.exception, response?.exc, error?.exc]) {
		const message = parseErrorPayload(candidate);
		if (message) return message;
	}
	return fallback;
}

export default {
	name: "RetailEdgeDocumentOutputSharing",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			loading: false,
			loaded: false,
			error: "",
			tenantName: "",
			branchName: "",
			userName: "",
			menuItems: [],
			canUseNativeDesk: false,
			documents: [],
			selectedDocumentKey: "",
			searchText: "",
			searching: false,
			searchAttempted: false,
			searchResults: [],
			detailsLoading: false,
			details: null,
			printFormat: "Standard",
			useLetterhead: false,
			showLogo: true,
			includeQr: false,
			previewHtml: "",
			previewLoading: false,
			previewError: "",
			previewToken: 0,
			emailRecipient: "",
			emailSubject: "",
			emailMessage: "",
			sendingEmail: false,
			preparingWhatsApp: false,
			searchTimer: null,
		};
	},
	computed: {
		readableDocuments() {
			return this.documents.filter((row) => row.available && row.can_read);
		},
		selectedDefinition() {
			return this.documents.find((row) => row.key === this.selectedDocumentKey) || null;
		},
		selectedManagedFormat() {
			return Boolean((this.details?.managed_print_formats || []).includes(this.printFormat));
		},
		receiptPreview() {
			return /Receipt\s+(80mm|58mm)$/i.test(String(this.printFormat || ""));
		},
		canSendEmail() {
			return Boolean(
				this.details?.can_email
				&& this.details?.can_print
				&& this.details?.email_configured
				&& String(this.emailRecipient || "").trim()
			);
		},
		canEditSelectedSalesInvoice() {
			return Boolean(
				this.details?.doctype === "Sales Invoice"
				&& Number(this.details?.docstatus || 0) === 0
				&& this.details?.can_write
			);
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
		this._onPageShow = () => this.loadWorkspace();
	},
	mounted() {
		window.addEventListener("retailedge-document-output-page-show", this._onPageShow);
		if (this.edgeUIValid) this.loadWorkspace();
	},
	beforeUnmount() {
		window.removeEventListener("retailedge-document-output-page-show", this._onPageShow);
		if (this.searchTimer) window.clearTimeout(this.searchTimer);
		this.previewToken += 1;
	},
	methods: {
		async loadWorkspace() {
			if (this.loading) return;
			this.loading = true;
			this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [output, navigation] = await Promise.all([callMethod(CONTEXT_METHOD), navigationPromise]);
				this.documents = Array.isArray(output.documents) ? output.documents : [];
				this.tenantName = output.operating?.company || navigation.context?.company || "";
				this.branchName = output.operating?.branch || navigation.context?.branch || "";
				this.userName = navigation.context?.user_name || output.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				this.loaded = true;
				await this.applyPendingTarget();
			} catch (error) {
				this.error = errorMessage(error, "Document Output & Sharing failed to load.");
			} finally {
				this.loading = false;
			}
		},
		async applyPendingTarget() {
			const target = window.retailedgeDocumentOutputTarget;
			if (!target?.document || !target?.name) return;
			const definition = this.documents.find((row) => row.key === target.document && row.available && row.can_read);
			delete window.retailedgeDocumentOutputTarget;
			if (!definition) return;
			this.selectedDocumentKey = definition.key;
			await this.selectDocument({ value: target.name });
		},
		mapNavigationGroups(groups) {
			return (groups || []).map((group) => ({
				...group,
				items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })),
			}));
		},
		routeForItem(item) {
			if (item.target_type === "Page") return `/app/${item.target}`;
			if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "DocType") return `/app/${doctypeSlug(item.target)}`;
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if (["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target) window.open(route || item.target, "_blank", "noopener,noreferrer");
		},
		resetDocumentSelection() {
			this.searchText = "";
			this.searchResults = [];
			this.searchAttempted = false;
			this.details = null;
			this.printFormat = "Standard";
			this.useLetterhead = false;
			this.showLogo = true;
			this.includeQr = false;
			this.previewHtml = "";
			this.previewError = "";
			this.emailRecipient = "";
			this.emailSubject = "";
			this.emailMessage = "";
		},
		queueSearch() {
			if (this.searchTimer) window.clearTimeout(this.searchTimer);
			this.searchTimer = window.setTimeout(() => this.searchDocuments(), 250);
		},
		async searchDocuments() {
			if (!this.selectedDocumentKey || this.searching) return;
			this.searching = true;
			this.searchAttempted = true;
			try {
				const rows = await callMethod(SEARCH_METHOD, { document: this.selectedDocumentKey, txt: this.searchText, limit: 20 });
				this.searchResults = Array.isArray(rows) ? rows : [];
			} catch (error) {
				frappe.msgprint({ title: __("Document search failed"), message: errorMessage(error, "Unable to search documents."), indicator: "red" });
				this.searchResults = [];
			} finally {
				this.searching = false;
			}
		},
		async selectDocument(row) {
			const name = String(row?.value || row?.name || "").trim();
			if (!name || !this.selectedDocumentKey) return;
			this.searchText = name;
			this.searchResults = [];
			this.detailsLoading = true;
			this.previewHtml = "";
			this.previewError = "";
			try {
				this.details = await callMethod(DETAILS_METHOD, { document: this.selectedDocumentKey, name });
				this.printFormat = this.details.recommended_print_format || this.details.print_formats?.[0] || "Standard";
				this.useLetterhead = Boolean(this.details.default_use_letterhead);
				this.showLogo = this.details.default_show_logo !== false;
				this.includeQr = Boolean(this.details.default_include_qr);
				this.emailRecipient = this.details.contact_email || "";
				this.emailSubject = this.details.default_email_subject || "";
				this.emailMessage = this.details.default_email_message || "";
				await this.refreshPreview();
			} catch (error) {
				this.details = null;
				frappe.msgprint({ title: __("Document unavailable"), message: errorMessage(error, "Unable to open this document."), indicator: "red" });
			} finally {
				this.detailsLoading = false;
			}
		},
		outputArgs() {
			return {
				document: this.selectedDocumentKey,
				name: this.details?.name || "",
				print_format: this.printFormat || "Standard",
				no_letterhead: this.useLetterhead ? 0 : 1,
				show_logo: this.selectedManagedFormat && this.showLogo ? 1 : 0,
				include_qr: this.selectedManagedFormat && this.includeQr ? 1 : 0,
			};
		},
		async handleOutputOptionChange() {
			if (!this.details) return;
			await this.refreshPreview();
		},
		async refreshPreview() {
			if (!this.details?.can_print || this.previewLoading) return;
			const token = ++this.previewToken;
			this.previewLoading = true;
			this.previewError = "";
			try {
				const result = await callMethod(PREVIEW_METHOD, this.outputArgs());
				if (token !== this.previewToken) return;
				this.previewHtml = String(result.html || "");
			} catch (error) {
				if (token !== this.previewToken) return;
				this.previewError = errorMessage(error, "Unable to render this preview.");
				this.previewHtml = "";
			} finally {
				if (token === this.previewToken) this.previewLoading = false;
			}
		},
		printPreview() {
			const frame = this.$refs.documentPreview;
			if (!frame?.contentWindow) return;
			frame.contentWindow.focus();
			frame.contentWindow.print();
		},
		downloadPdf() {
			if (!this.details?.can_print) return;
			const query = new URLSearchParams(this.outputArgs()).toString();
			window.open(`/api/method/retailedge.document_output.download_document_pdf?${query}`, "_blank", "noopener,noreferrer");
		},
		editSelectedSalesInvoice() {
			if (!this.canEditSelectedSalesInvoice || !this.details?.name) return;
			window.retailedgeProfessionalSellingTarget = { doctype: "Sales Invoice", name: this.details.name };
			frappe.set_route("professional-selling");
		},
		openNativeDocument() {
			if (!this.canUseNativeDesk) return;
			if (this.details?.native_route) window.open(this.details.native_route, "_blank", "noopener,noreferrer");
		},
		async sendEmail() {
			if (this.sendingEmail) return;
			if (!this.details?.email_configured) {
				this.sendingEmail = false;
				frappe.msgprint({
					title: __("Email not configured"),
					message: __("Configure a default outgoing Email Account before sending documents."),
					indicator: "orange",
				});
				return;
			}
			if (!this.canSendEmail) return;
			this.sendingEmail = true;
			try {
				await callMethod(EMAIL_METHOD, {
					...this.outputArgs(),
					recipient: this.emailRecipient,
					subject: this.emailSubject,
					message: this.emailMessage,
				}, "POST");
				frappe.show_alert({ message: __("Email queued with PDF attachment"), indicator: "green" });
			} catch (error) {
				frappe.msgprint({ title: __("Email failed"), message: errorMessage(error, "Unable to queue the email."), indicator: "red" });
			} finally {
				this.sendingEmail = false;
			}
		},
		async openWhatsApp() {
			if (!this.details || this.preparingWhatsApp) return;
			this.preparingWhatsApp = true;
			try {
				const handoff = await callMethod(WHATSAPP_METHOD, { document: this.selectedDocumentKey, name: this.details.name });
				const phone = String(handoff.phone || "").replace(/[^0-9]/g, "");
				const target = phone
					? `https://wa.me/${phone}?text=${encodeURIComponent(handoff.text || "")}`
					: `https://wa.me/?text=${encodeURIComponent(handoff.text || "")}`;
				window.open(target, "_blank", "noopener,noreferrer");
			} catch (error) {
				frappe.msgprint({ title: __("WhatsApp handoff failed"), message: errorMessage(error, "Unable to prepare the WhatsApp message."), indicator: "red" });
			} finally {
				this.preparingWhatsApp = false;
			}
		},
		formatAmount(value) {
			return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
		},
	},
};
</script>

<style scoped>
.document-output-page{padding-bottom:2rem}.output-content{display:grid;gap:1rem}.output-policy,.section-heading,.preview-toolbar{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start}.output-policy h3,.section-heading h3,.preview-toolbar h3,.share-section h4{margin:.2rem 0 .35rem}.output-policy p,.section-heading p,.preview-toolbar p,.share-section p{margin:0;color:var(--edge-color-ink-500,var(--text-muted))}.output-kicker{display:block;font-size:.75rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--edge-color-ink-500,var(--text-muted))}.output-selector{display:grid;gap:.9rem}.selector-grid{display:grid;grid-template-columns:minmax(14rem,.7fr) minmax(20rem,1.3fr);gap:.85rem;align-items:end}.document-search-field{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.55rem;align-items:end}.selected-document-summary{display:grid;justify-items:end;gap:.1rem;text-align:right}.selected-document-summary span{color:var(--edge-color-ink-500,var(--text-muted));font-size:.82rem}.search-results{display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:.45rem;max-height:15rem;overflow:auto}.search-result{display:grid;gap:.2rem;text-align:left;padding:.65rem .75rem;border:1px solid var(--edge-color-border,var(--border-color));border-radius:.55rem;background:var(--edge-color-surface,var(--card-bg));color:var(--edge-color-ink-950,var(--text-color))}.search-result:hover{background:var(--edge-color-surface-muted,var(--control-bg))}.search-result span{font-size:.8rem;color:var(--edge-color-ink-500,var(--text-muted))}.output-workbench{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(20rem,.65fr);gap:1rem;align-items:start}.preview-panel,.output-actions{display:grid;gap:1rem;min-width:0}.preview-toolbar-actions,.secondary-actions{display:flex;gap:.5rem;flex-wrap:wrap;justify-content:flex-end}.preview-stage{display:grid;place-items:center;min-height:48rem;padding:1rem;border:1px solid var(--edge-color-border,var(--border-color));border-radius:.7rem;background:var(--edge-color-surface-muted,#eef1f4);overflow:auto}.preview-stage.receipt-stage{align-items:start}.document-preview-frame{display:block;width:min(100%,54rem);min-height:46rem;border:0;background:#fff;box-shadow:0 8px 28px rgba(15,23,42,.12)}.receipt-preview-frame{width:min(100%,25rem);min-height:40rem}.preview-error{margin:0;padding:.7rem .85rem;border:1px solid var(--edge-color-danger);border-radius:.55rem;color:var(--edge-color-danger);background:color-mix(in srgb,var(--edge-color-danger) 7%,var(--edge-color-surface))}.output-option-list{display:grid;gap:.55rem}.output-toggle{display:flex;align-items:flex-start;gap:.65rem;padding:.7rem;border:1px solid var(--edge-color-border,var(--border-color));border-radius:.6rem;background:var(--edge-color-surface,var(--card-bg));cursor:pointer}.output-toggle input{margin-top:.2rem}.output-toggle span{display:grid;gap:.15rem}.output-toggle small,.output-note{color:var(--edge-color-ink-500,var(--text-muted));font-size:.78rem}.output-toggle.disabled{opacity:.6;cursor:not-allowed}.output-note{margin:0}.share-section{display:grid;gap:.65rem;padding-top:1rem;border-top:1px solid var(--edge-color-border,var(--border-color))}.field-label{display:block;font-size:.82rem;font-weight:600;margin-bottom:.3rem}.edge-control{width:100%;min-height:2.5rem;border:1px solid var(--edge-color-border,var(--border-color));border-radius:.5rem;background:var(--edge-color-surface,var(--card-bg));color:var(--edge-color-ink-950,var(--text-color));padding:.55rem .7rem}.edge-textarea{resize:vertical}.email-readiness-warning{padding:.7rem .8rem;border:1px solid color-mix(in srgb,var(--edge-color-warning,#f59e0b) 45%,var(--edge-color-border));border-radius:.55rem;background:color-mix(in srgb,var(--edge-color-warning,#f59e0b) 9%,var(--edge-color-surface));color:var(--edge-color-ink-700,var(--text-color));font-size:.8rem}@media(max-width:1100px){.output-workbench{grid-template-columns:1fr}.output-actions{order:-1}}@media(max-width:760px){.selector-grid{grid-template-columns:1fr}.document-search-field{grid-template-columns:1fr}.output-policy,.section-heading,.preview-toolbar{flex-direction:column}.selected-document-summary{justify-items:start;text-align:left}.preview-toolbar-actions,.secondary-actions{justify-content:flex-start}.preview-stage{min-height:35rem;padding:.5rem}.document-preview-frame{min-height:34rem}}
</style>
