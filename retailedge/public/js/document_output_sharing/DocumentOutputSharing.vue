<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Document Output & Sharing could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="Retail"
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
				description="Print, download and send customer documents using ERPNext Print Formats, Letterheads and document permissions."
			/>

			<EdgeLoadingState v-if="loading && !loaded" />
			<EdgeErrorState v-else-if="error" :message="error" @retry="loadWorkspace" />

			<div v-else class="output-content">
				<section class="edge-panel output-policy">
					<div>
						<span class="output-kicker">Document truth</span>
						<h3>ERPNext remains authoritative</h3>
						<p>Print Formats and Letterheads come from ERPNext. PDFs stay private. Sending or downloading never changes the source business document.</p>
					</div>
					<EdgeStatusBadge status="Active" />
				</section>

				<div class="output-grid">
					<section class="edge-panel output-selector">
						<div class="section-heading">
							<span class="output-kicker">1. Choose document</span>
							<h3>Find a permitted customer document</h3>
						</div>

						<label class="field-label" for="output-document-type">Document type</label>
						<select id="output-document-type" v-model="selectedDocumentKey" class="edge-control" @change="resetDocumentSelection">
							<option value="">Choose document type</option>
							<option v-for="document in readableDocuments" :key="document.key" :value="document.key">{{ document.label }}</option>
						</select>

						<label class="field-label" for="output-document-search">Document</label>
						<div class="search-row">
							<input id="output-document-search" v-model="searchText" class="edge-control" type="search" :disabled="!selectedDocumentKey" placeholder="Type document number or customer" @input="queueSearch" />
							<button type="button" class="edge-button edge-button--secondary" :disabled="!selectedDocumentKey || searching" @click="searchDocuments">Search</button>
						</div>

						<EdgeLoadingState v-if="searching" message="Searching permitted documents..." />
						<div v-else-if="searchResults.length" class="search-results">
							<button v-for="row in searchResults" :key="row.value || row.name" type="button" class="search-result" @click="selectDocument(row)">
								<strong>{{ row.value || row.name }}</strong>
								<span v-if="row.description">{{ row.description }}</span>
							</button>
						</div>
						<EdgeEmptyState v-else-if="searchAttempted && selectedDocumentKey" title="No permitted documents found" description="Try another document number or check the current Operating Company and Branch." />
					</section>

					<section class="edge-panel output-actions">
						<div class="section-heading">
							<span class="output-kicker">2. Output & share</span>
							<h3>{{ details?.name || "Select a document" }}</h3>
							<p v-if="details">{{ details.party || "Customer document" }}<span v-if="details.company"> · {{ details.company }}</span><span v-if="details.grand_total"> · {{ details.currency }} {{ formatAmount(details.grand_total) }}</span></p>
						</div>

						<EdgeLoadingState v-if="detailsLoading" message="Loading document controls..." />
						<EdgeEmptyState v-else-if="!details" title="Nothing selected" description="Choose a permitted document to see Print, PDF, Email and WhatsApp options." />
						<div v-else class="action-form">
							<div class="field-grid">
								<div>
									<label class="field-label" for="output-print-format">Print Format</label>
									<select id="output-print-format" v-model="printFormat" class="edge-control" :disabled="!details.can_print">
										<option v-for="format in details.print_formats || ['Standard']" :key="format" :value="format">{{ format }}</option>
									</select>
								</div>
								<label class="letterhead-toggle"><input v-model="useLetterhead" type="checkbox" /><span>Use ERPNext Letterhead</span></label>
							</div>

							<div class="primary-actions">
								<button type="button" class="edge-button edge-button--secondary" :disabled="!details.can_print" @click="previewDocument">Print Preview</button>
								<button type="button" class="edge-button edge-button--primary" :disabled="!details.can_print" @click="downloadPdf">Download PDF</button>
								<button type="button" class="edge-button edge-button--secondary" @click="openNativeDocument">Open Full Document</button>
							</div>

							<div class="share-section">
								<h4>Email PDF</h4>
								<div class="field-grid">
									<div><label class="field-label" for="output-email">Recipient</label><input id="output-email" v-model="emailRecipient" class="edge-control" type="email" :disabled="!details.can_email" placeholder="customer@example.com" /></div>
									<div><label class="field-label" for="output-subject">Subject</label><input id="output-subject" v-model="emailSubject" class="edge-control" type="text" :disabled="!details.can_email" /></div>
								</div>
								<label class="field-label" for="output-message">Message</label>
								<textarea id="output-message" v-model="emailMessage" class="edge-control edge-textarea" :disabled="!details.can_email" rows="3"></textarea>
								<button type="button" class="edge-button edge-button--primary" :disabled="!canSendEmail || sendingEmail" @click="sendEmail">{{ sendingEmail ? "Queueing..." : "Email PDF" }}</button>
							</div>

							<div class="share-section">
								<h4>WhatsApp</h4>
								<p>Private PDFs are not published to create a WhatsApp link. Download the PDF, then open the prepared message and attach the PDF in WhatsApp.</p>
								<button type="button" class="edge-button edge-button--secondary" :disabled="preparingWhatsApp" @click="openWhatsApp">{{ preparingWhatsApp ? "Preparing..." : "Open WhatsApp Message" }}</button>
							</div>
						</div>
					</section>
				</div>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const CONTEXT_METHOD = "retailedge.document_output.get_document_output_context";
const SEARCH_METHOD = "retailedge.document_output.search_output_documents";
const DETAILS_METHOD = "retailedge.document_output.get_output_document_details";
const EMAIL_METHOD = "retailedge.document_output.send_document_email";
const WHATSAPP_METHOD = "retailedge.document_output.get_whatsapp_handoff";
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState", "EdgeStatusBadge"];

function runtimeComponents() {
	const edgeUI = typeof window !== "undefined" ? window.EdgeSuiteUI : null;
	return edgeUI?.components || {};
}
function callMethod(method, args = {}, type = "GET") { return new Promise((resolve, reject) => frappe.call({ method, args, type, callback: (response) => resolve(response.message || {}), error: reject })); }
function doctypeSlug(doctype) { return String(doctype || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }

export default {
	name: "RetailEdgeDocumentOutputSharing",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() { return { edgeUIValid: true, missingComponents: [], loading: false, loaded: false, error: "", tenantName: "", branchName: "", userName: "", menuItems: [], documents: [], selectedDocumentKey: "", searchText: "", searching: false, searchAttempted: false, searchResults: [], detailsLoading: false, details: null, printFormat: "Standard", useLetterhead: true, emailRecipient: "", emailSubject: "", emailMessage: "", sendingEmail: false, preparingWhatsApp: false, searchTimer: null }; },
	computed: {
		readableDocuments() { return this.documents.filter((row) => row.available && row.can_read); },
		selectedDefinition() { return this.documents.find((row) => row.key === this.selectedDocumentKey) || null; },
		canSendEmail() { return Boolean(this.details?.can_email && this.details?.can_print && String(this.emailRecipient || "").trim()); },
	},
	created() { const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; this._onPageShow = () => this.loadWorkspace(); },
	mounted() { window.addEventListener("retailedge-document-output-page-show", this._onPageShow); if (this.edgeUIValid) this.loadWorkspace(); },
	beforeUnmount() { window.removeEventListener("retailedge-document-output-page-show", this._onPageShow); if (this.searchTimer) window.clearTimeout(this.searchTimer); },
	methods: {
		async loadWorkspace() { if (this.loading) return; this.loading = true; this.error = ""; try { const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.master_experience.get_retailedge_business_hub_context"); const [output, navigation] = await Promise.all([callMethod(CONTEXT_METHOD), navigationPromise]); this.documents = Array.isArray(output.documents) ? output.documents : []; this.tenantName = output.operating?.company || navigation.context?.company || ""; this.branchName = output.operating?.branch || navigation.context?.branch || ""; this.userName = navigation.context?.user_name || output.user_name || ""; this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []); this.loaded = true; } catch (error) { this.error = errorMessage(error, "Document Output & Sharing failed to load."); } finally { this.loading = false; } },
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${doctypeSlug(item.target)}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target) window.open(route || item.target, "_blank", "noopener,noreferrer"); },
		resetDocumentSelection() { this.searchText = ""; this.searchResults = []; this.searchAttempted = false; this.details = null; this.printFormat = "Standard"; this.emailRecipient = ""; this.emailSubject = ""; this.emailMessage = ""; },
		queueSearch() { if (this.searchTimer) window.clearTimeout(this.searchTimer); this.searchTimer = window.setTimeout(() => this.searchDocuments(), 250); },
		async searchDocuments() { if (!this.selectedDocumentKey || this.searching) return; this.searching = true; this.searchAttempted = true; try { const rows = await callMethod(SEARCH_METHOD, { document: this.selectedDocumentKey, txt: this.searchText, limit: 20 }); this.searchResults = Array.isArray(rows) ? rows : []; } catch (error) { frappe.msgprint({ title: __("Document search failed"), message: errorMessage(error, "Unable to search documents."), indicator: "red" }); this.searchResults = []; } finally { this.searching = false; } },
		async selectDocument(row) { const name = String(row?.value || row?.name || "").trim(); if (!name || !this.selectedDocumentKey) return; this.searchText = name; this.searchResults = []; this.detailsLoading = true; try { this.details = await callMethod(DETAILS_METHOD, { document: this.selectedDocumentKey, name }); this.printFormat = this.details.recommended_print_format || this.details.print_formats?.[0] || "Standard"; this.emailRecipient = this.details.contact_email || ""; this.emailSubject = this.details.default_email_subject || ""; this.emailMessage = this.details.default_email_message || ""; } catch (error) { this.details = null; frappe.msgprint({ title: __("Document unavailable"), message: errorMessage(error, "Unable to open this document."), indicator: "red" }); } finally { this.detailsLoading = false; } },
		printQuery() { return new URLSearchParams({ doctype: this.details.doctype, name: this.details.name, format: this.printFormat || "Standard", no_letterhead: this.useLetterhead ? "0" : "1" }).toString(); },
		previewDocument() { if (this.details?.can_print) window.open(`/printview?${this.printQuery()}`, "_blank", "noopener,noreferrer"); },
		downloadPdf() { if (!this.details?.can_print) return; const query = new URLSearchParams({ document: this.selectedDocumentKey, name: this.details.name, print_format: this.printFormat || "Standard", no_letterhead: this.useLetterhead ? "0" : "1" }).toString(); window.open(`/api/method/retailedge.document_output.download_document_pdf?${query}`, "_blank", "noopener,noreferrer"); },
		openNativeDocument() { if (this.details?.native_route) window.open(this.details.native_route, "_blank", "noopener,noreferrer"); },
		async sendEmail() { if (!this.canSendEmail || this.sendingEmail) return; this.sendingEmail = true; try { await callMethod(EMAIL_METHOD, { document: this.selectedDocumentKey, name: this.details.name, recipient: this.emailRecipient, subject: this.emailSubject, message: this.emailMessage, print_format: this.printFormat || "Standard", no_letterhead: this.useLetterhead ? 0 : 1 }, "POST"); frappe.show_alert({ message: __("Email queued with PDF attachment"), indicator: "green" }); } catch (error) { frappe.msgprint({ title: __("Email failed"), message: errorMessage(error, "Unable to queue the email."), indicator: "red" }); } finally { this.sendingEmail = false; } },
		async openWhatsApp() { if (!this.details || this.preparingWhatsApp) return; this.preparingWhatsApp = true; try { const handoff = await callMethod(WHATSAPP_METHOD, { document: this.selectedDocumentKey, name: this.details.name }); const phone = String(handoff.phone || "").replace(/[^0-9]/g, ""); const target = phone ? `https://wa.me/${phone}?text=${encodeURIComponent(handoff.text || "")}` : `https://wa.me/?text=${encodeURIComponent(handoff.text || "")}`; window.open(target, "_blank", "noopener,noreferrer"); } catch (error) { frappe.msgprint({ title: __("WhatsApp handoff failed"), message: errorMessage(error, "Unable to prepare the WhatsApp message."), indicator: "red" }); } finally { this.preparingWhatsApp = false; } },
		formatAmount(value) { return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); },
	},
};
</script>

<style scoped>
.document-output-page{padding-bottom:2rem}.output-content{display:grid;gap:1rem}.output-policy,.section-heading{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start}.output-policy h3,.section-heading h3,.share-section h4{margin:.2rem 0 .35rem}.output-policy p,.section-heading p,.share-section p{margin:0;color:var(--text-muted)}.output-kicker{display:block;font-size:.75rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--text-muted)}.output-grid{display:grid;grid-template-columns:minmax(18rem,.8fr) minmax(24rem,1.2fr);gap:1rem}.output-selector,.output-actions{display:grid;gap:.9rem;align-content:start}.field-label{display:block;font-size:.82rem;font-weight:600;margin-bottom:.3rem}.edge-control{width:100%;min-height:2.5rem;border:1px solid var(--border-color);border-radius:var(--border-radius-md,.5rem);background:var(--control-bg,var(--card-bg));color:var(--text-color);padding:.55rem .7rem}.edge-textarea{resize:vertical}.search-row,.primary-actions{display:flex;gap:.6rem;flex-wrap:wrap}.search-row .edge-control{flex:1 1 12rem}.search-results{display:grid;gap:.4rem;max-height:19rem;overflow:auto}.search-result{display:grid;gap:.2rem;text-align:left;padding:.65rem .75rem;border:1px solid var(--border-color);border-radius:var(--border-radius-md,.5rem);background:var(--card-bg);color:var(--text-color)}.search-result:hover{background:var(--subtle-fg,var(--control-bg))}.search-result span{font-size:.8rem;color:var(--text-muted)}.action-form{display:grid;gap:1rem}.field-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem;align-items:end}.letterhead-toggle{display:flex;align-items:center;gap:.5rem;min-height:2.5rem}.share-section{display:grid;gap:.65rem;padding-top:1rem;border-top:1px solid var(--border-color)}@media(max-width:900px){.output-grid,.field-grid{grid-template-columns:1fr}.output-policy{flex-direction:column}}
</style>