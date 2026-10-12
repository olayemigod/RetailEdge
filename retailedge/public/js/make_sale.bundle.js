import MakeSale from "./make_sale/MakeSale.vue";
import { callMethod, errorMessage } from "./retailedge_business_hub/guidedEntryUtils";

const COMMERCIAL_PREVIEW_METHOD = "retailedge.sales_commercial_preview.get_sales_invoice_commercial_preview";

MakeSale.methods.refreshCommercialPreview = async function refreshCommercialPreview() {
	if (!this.commercialPreviewRequired) {
		this.previewLoading = false;
		return;
	}
	const signature = this.commercialPreviewSignature;
	const token = ++this.previewToken;
	this.previewLoading = true;
	this.previewError = "";
	const args = { values: this.values };
	if (this.editingSavedDraft && this.savedDocument?.name) {
		args.document_name = this.savedDocument.name;
	}
	try {
		const result = await callMethod(COMMERCIAL_PREVIEW_METHOD, args, "POST");
		if (token !== this.previewToken || signature !== this.commercialPreviewSignature) return;
		this.commercialPreview = result || null;
		this.previewAppliedSignature = signature;
		this.applyCommercialPreviewItems(result?.items || []);
	} catch (error) {
		if (token !== this.previewToken) return;
		this.commercialPreview = null;
		this.previewAppliedSignature = "";
		this.previewError = errorMessage(error, "Check the Customer, items, pricing or tax setup and try again.");
	} finally {
		if (token === this.previewToken) this.previewLoading = false;
	}
};

function mountRetailEdgeMakeSale(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Make Sale mount target is required");
	const app = edgeUI.createEdgeApp(MakeSale);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeMakeSale = MakeSale;
	window.mountRetailEdgeMakeSale = mountRetailEdgeMakeSale;
}

export { mountRetailEdgeMakeSale };
export default MakeSale;