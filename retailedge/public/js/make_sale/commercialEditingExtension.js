import { callMethod, errorMessage } from "../retailedge_business_hub/guidedEntryUtils";

const GUIDED_SEARCH_METHOD = "retailedge.guided_sales_invoice.search_simple_sales_invoice_options";
const SAVED_TERM_SEARCH_METHOD = "retailedge.sales_commercial_terms.search_sales_commercial_term_options";
const UPDATE_WITH_TERMS_METHOD = "retailedge.sales_commercial_draft_update.update_sales_invoice_draft_with_commercial_terms";

const MANUAL_PERCENTAGE = "manual_discount_percentage";
const MANUAL_AMOUNT = "manual_discount_amount";

function commercialSignature(values = {}) {
	return JSON.stringify({
		company: values.company || "",
		branch: values.branch || "",
		warehouse: values.warehouse || "",
		customer: values.customer || "",
		price_list: values.price_list || "",
		posting_date: values.posting_date || "",
		update_stock: Number(values.update_stock || 0),
		coupon_code: values.coupon_code || "",
		tax_category: values.tax_category || "",
		taxes_and_charges: values.taxes_and_charges || "",
		additional_discount_percentage: Number(values.additional_discount_percentage || 0),
		discount_amount: Number(values.discount_amount || 0),
		apply_discount_on: values.apply_discount_on || "Grand Total",
		items: (values.items || [])
			.filter((row) => row?.item_code)
			.map((row) => ({
				item_code: row.item_code,
				qty: Number(row.qty || 0),
				rate: row.rate === "" ? "" : Number(row.rate || 0),
				manual_discount_percentage: Number(row[MANUAL_PERCENTAGE] || 0),
				manual_discount_amount: Number(row[MANUAL_AMOUNT] || 0),
			})),
	});
}

function withManualDiscountColumns(columns = []) {
	const base = columns.filter((column) => ![MANUAL_PERCENTAGE, MANUAL_AMOUNT].includes(column?.fieldname));
	const result = [];
	for (const column of base) {
		if (column?.fieldname === "discount_percentage") {
			result.push(
				{ fieldname: MANUAL_PERCENTAGE, label: "Manual Discount %", fieldtype: "Float", default: 0 },
				{ fieldname: MANUAL_AMOUNT, label: "Discount per Unit", fieldtype: "Currency", default: 0 },
			);
			result.push({ ...column, label: "Applied %", read_only: 1 });
			continue;
		}
		result.push(column);
	}
	return result;
}

function clearLockedManualDiscounts(instance) {
	instance.values.items = (instance.values.items || []).map((row) => ({
		...row,
		[MANUAL_PERCENTAGE]: 0,
		[MANUAL_AMOUNT]: 0,
	}));
}

function mapEditableItems(rows = []) {
	return rows.map((row) => ({
		name: row.name || "",
		item_code: row.item_code || "",
		qty: row.qty,
		rate: row.rate,
		uom: row.uom || "",
		discount_percentage: Number(row.discount_percentage || 0),
		amount: Number(row.amount || 0),
		[MANUAL_PERCENTAGE]: Number(row[MANUAL_PERCENTAGE] || 0),
		[MANUAL_AMOUNT]: Number(row[MANUAL_AMOUNT] || 0),
	}));
}

function mutuallyExclusiveManualDiscountRows(nextRows = [], previousRows = []) {
	return nextRows.map((row, index) => {
		const prior = previousRows[index] || {};
		const percentageChanged = String(row?.[MANUAL_PERCENTAGE] ?? "") !== String(prior?.[MANUAL_PERCENTAGE] ?? "");
		const amountChanged = String(row?.[MANUAL_AMOUNT] ?? "") !== String(prior?.[MANUAL_AMOUNT] ?? "");
		if (percentageChanged && Number(row?.[MANUAL_PERCENTAGE] || 0) > 0) {
			return { ...row, [MANUAL_AMOUNT]: 0 };
		}
		if (amountChanged && Number(row?.[MANUAL_AMOUNT] || 0) > 0) {
			return { ...row, [MANUAL_PERCENTAGE]: 0 };
		}
		return { ...row };
	});
}

export function applyMakeSaleCommercialEditing(MakeSale) {
	if (!MakeSale || MakeSale.__retailedgeCommercialEditingApplied) return MakeSale;
	MakeSale.__retailedgeCommercialEditingApplied = true;

	const baseData = MakeSale.data;
	MakeSale.data = function retailedgeCommercialEditingData() {
		const data = baseData.call(this);
		data.itemColumns = withManualDiscountColumns(data.itemColumns || []);
		if (!Object.prototype.hasOwnProperty.call(data.values || {}, "tax_category")) data.values.tax_category = "";
		return data;
	};

	MakeSale.computed.commercialPreviewSignature = function retailedgeCommercialPreviewSignature() {
		return commercialSignature(this.values || {});
	};

	const baseApplyRatePermission = MakeSale.methods.applyRatePermission;
	MakeSale.methods.applyRatePermission = function retailedgeApplyRatePermission(pricing = this.formContext.pricing || {}) {
		baseApplyRatePermission.call(this, pricing);
		const readOnly = pricing?.allow_rate_change === false;
		this.itemColumns = (this.itemColumns || []).map((column) =>
			[MANUAL_PERCENTAGE, MANUAL_AMOUNT].includes(column?.fieldname)
				? { ...column, read_only: readOnly ? 1 : 0 }
				: column
		);
		if (readOnly && (this.values.items || []).some((row) => Number(row?.[MANUAL_PERCENTAGE] || 0) || Number(row?.[MANUAL_AMOUNT] || 0))) {
			clearLockedManualDiscounts(this);
			this.invalidateCommercialPreview();
			this.queueCommercialPreview(0);
		}
	};

	const baseUpdateItems = MakeSale.methods.updateItems;
	MakeSale.methods.updateItems = function retailedgeUpdateItems(nextRows) {
		const rows = mutuallyExclusiveManualDiscountRows(nextRows || [], this.values.items || []);
		return baseUpdateItems.call(this, rows);
	};

	const baseSetCustomer = MakeSale.methods.setCustomer;
	MakeSale.methods.setCustomer = function retailedgeSetCustomer(next) {
		if ((this.values.customer || "") !== (next || "")) this.values.tax_category = "";
		return baseSetCustomer.call(this, next);
	};

	MakeSale.methods.searchCommercialTerm = async function retailedgeSearchCommercialTerm(fieldname, query) {
		const values = {
			company: this.values.company,
			branch: this.values.branch,
			warehouse: this.values.warehouse,
			customer: this.values.customer,
			price_list: this.values.price_list,
			coupon_code: this.values.coupon_code,
			tax_category: this.values.tax_category,
			taxes_and_charges: this.values.taxes_and_charges,
		};
		if (this.editingSavedDraft && this.savedDocument?.name) {
			values.document_name = this.savedDocument.name;
			const results = await callMethod(SAVED_TERM_SEARCH_METHOD, { fieldname, txt: query || "", values });
			return Array.isArray(results) ? results : [];
		}
		const results = await callMethod(GUIDED_SEARCH_METHOD, { fieldname, txt: query || "", values });
		return Array.isArray(results) ? results : [];
	};

	const baseSyncPageFromDraftPreview = MakeSale.methods.syncPageFromDraftPreview;
	MakeSale.methods.syncPageFromDraftPreview = function retailedgeSyncPageFromDraftPreview(result) {
		baseSyncPageFromDraftPreview.call(this, result);
		if (Array.isArray(result?.editable_items)) this.values.items = mapEditableItems(result.editable_items);
	};

	const baseSaveDraft = MakeSale.methods.saveDraft;
	MakeSale.methods.saveDraft = async function retailedgeSaveDraft() {
		if (!(this.savedDocument?.name && this.editingSavedDraft)) return baseSaveDraft.call(this);
		if (this.saving || this.loading || !this.transactionContextReady) return;
		if (this.commercialPreviewBlocked) {
			this.saveError = this.previewError || "Wait for the current invoice total to finish updating before saving.";
			this.queueCommercialPreview(0);
			return;
		}
		this.saveError = "";
		this.saving = true;
		try {
			const result = await callMethod(UPDATE_WITH_TERMS_METHOD, {
				name: this.savedDocument.name,
				expected_modified: this.savedDocument.modified || "",
				values: {
					posting_date: this.values.posting_date,
					remarks: this.values.remarks || "",
					coupon_code: this.values.coupon_code || "",
					tax_category: this.values.tax_category || "",
					taxes_and_charges: this.values.taxes_and_charges || "",
					additional_discount_percentage: Number(this.values.additional_discount_percentage || 0),
					discount_amount: Number(this.values.discount_amount || 0),
					apply_discount_on: this.values.apply_discount_on || "Grand Total",
					items: (this.values.items || []).filter((row) => row?.item_code).map((row) => ({
						name: row.name || "",
						item_code: row.item_code,
						qty: Number(row.qty || 0),
						rate: row.rate,
						[MANUAL_PERCENTAGE]: Number(row[MANUAL_PERCENTAGE] || 0),
						[MANUAL_AMOUNT]: Number(row[MANUAL_AMOUNT] || 0),
					})),
				},
			}, "POST");
			this.syncPageFromDraftPreview(result);
			this.savedDocument = { ...this.savedDocument, ...result, doctype: "Sales Invoice" };
			this.editingSavedDraft = false;
			this.savedCommercialTermCapabilities = null;
			this.invalidateCommercialPreview();
			await this.refreshSavedDocumentPreview({ silent: true });
			frappe.show_alert?.({ message: `Sales Invoice ${result.name} draft updated`, indicator: "green" });
		} catch (error) {
			this.saveError = errorMessage(error, "Unable to save the Sales Invoice draft.");
		} finally {
			this.saving = false;
		}
	};

	const existingWatch = MakeSale.watch || {};
	MakeSale.watch = {
		...existingWatch,
		"formContext.pricing.allow_rate_change"(value, previous) {
			if (value !== previous) this.applyRatePermission(this.formContext.pricing || {});
		},
	};

	return MakeSale;
}

export default applyMakeSaleCommercialEditing;
