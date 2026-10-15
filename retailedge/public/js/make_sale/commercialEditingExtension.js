import { callMethod, errorMessage } from "../retailedge_business_hub/guidedEntryUtils";

const GUIDED_SEARCH_METHOD = "retailedge.guided_sales_invoice.search_simple_sales_invoice_options";
const SAVED_TERM_SEARCH_METHOD = "retailedge.sales_commercial_terms.search_sales_commercial_term_options";
const UPDATE_WITH_TERMS_METHOD = "retailedge.sales_commercial_draft_update.update_sales_invoice_draft_with_commercial_terms";

const MANUAL_PERCENTAGE = "manual_discount_percentage";
const MANUAL_AMOUNT = "manual_discount_amount";
const MANUAL_MODE = "manual_discount_mode";
const MANUAL_VALUE = "manual_discount_value";
const DISCOUNT_MODE_PERCENTAGE = "percentage";
const DISCOUNT_MODE_AMOUNT = "amount";

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

function discountEditorState(row = {}) {
	const percentage = Number(row?.[MANUAL_PERCENTAGE] || 0);
	const amount = Number(row?.[MANUAL_AMOUNT] || 0);
	if (percentage) return { [MANUAL_MODE]: DISCOUNT_MODE_PERCENTAGE, [MANUAL_VALUE]: percentage };
	if (amount) return { [MANUAL_MODE]: DISCOUNT_MODE_AMOUNT, [MANUAL_VALUE]: amount };
	return { [MANUAL_MODE]: "", [MANUAL_VALUE]: "" };
}

function withManualDiscountColumns(columns = []) {
	const hiddenFields = [MANUAL_PERCENTAGE, MANUAL_AMOUNT, MANUAL_MODE, MANUAL_VALUE];
	const base = columns.filter((column) => !hiddenFields.includes(column?.fieldname));
	const result = [];
	for (const column of base) {
		if (column?.fieldname === "discount_percentage") {
			result.push(
				{
					fieldname: MANUAL_MODE,
					label: "Discount",
					fieldtype: "Select",
					options: [
						{ value: DISCOUNT_MODE_PERCENTAGE, label: "Percentage" },
						{ value: DISCOUNT_MODE_AMOUNT, label: "Amount / unit" },
					],
					default: "",
				},
				{
					fieldname: MANUAL_VALUE,
					label: "Value",
					fieldtype: "Float",
					default: "",
					read_only_depends_on: `eval:!doc.${MANUAL_MODE}`,
				},
			);
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
		[MANUAL_MODE]: "",
		[MANUAL_VALUE]: "",
	}));
}

function mapEditableItems(rows = []) {
	return rows.map((row) => ({
		name: row.name || "",
		item_code: row.item_code || "",
		qty: row.qty,
		rate: row.selling_rate ?? row.rate,
		uom: row.uom || "",
		discount_percentage: Number(row.discount_percentage || 0),
		amount: Number(row.amount || 0),
		[MANUAL_PERCENTAGE]: Number(row[MANUAL_PERCENTAGE] || 0),
		[MANUAL_AMOUNT]: Number(row[MANUAL_AMOUNT] || 0),
		...discountEditorState(row),
	}));
}

function previousDiscountRow(row, index, previousRows = []) {
	const name = String(row?.name || "").trim();
	if (name) {
		const named = previousRows.find((candidate) => String(candidate?.name || "").trim() === name);
		if (named) return named;
	}

	const temporaryKey = String(row?.__temporary_key || "").trim();
	if (temporaryKey) {
		const temporary = previousRows.find(
			(candidate) => String(candidate?.__temporary_key || "").trim() === temporaryKey,
		);
		if (temporary) return temporary;
	}

	const sameReference = previousRows.find((candidate) => candidate === row);
	if (sameReference) return sameReference;

	return previousRows[index] || {};
}

function normaliseManualDiscountRows(nextRows = [], previousRows = []) {
	return nextRows.map((row, index) => {
		const prior = previousDiscountRow(row, index, previousRows);
		if ((row?.item_code || "") !== (prior?.item_code || "")) {
			return {
				...row,
				[MANUAL_PERCENTAGE]: 0,
				[MANUAL_AMOUNT]: 0,
				[MANUAL_MODE]: "",
				[MANUAL_VALUE]: "",
			};
		}

		const priorEditor = {
			...discountEditorState(prior),
			...(prior?.[MANUAL_MODE] !== undefined ? { [MANUAL_MODE]: prior[MANUAL_MODE] } : {}),
			...(prior?.[MANUAL_VALUE] !== undefined ? { [MANUAL_VALUE]: prior[MANUAL_VALUE] } : {}),
		};
		const mode = String(row?.[MANUAL_MODE] || "");
		if (mode !== String(priorEditor[MANUAL_MODE] || "")) {
			return {
				...row,
				[MANUAL_PERCENTAGE]: 0,
				[MANUAL_AMOUNT]: 0,
				[MANUAL_MODE]: mode,
				[MANUAL_VALUE]: "",
			};
		}

		const value = row?.[MANUAL_VALUE] === "" ? 0 : Number(row?.[MANUAL_VALUE]);
		if (mode === DISCOUNT_MODE_PERCENTAGE) {
			return {
				...row,
				[MANUAL_PERCENTAGE]: Number.isFinite(value) ? value : 0,
				[MANUAL_AMOUNT]: 0,
			};
		}
		if (mode === DISCOUNT_MODE_AMOUNT) {
			return {
				...row,
				[MANUAL_PERCENTAGE]: 0,
				[MANUAL_AMOUNT]: Number.isFinite(value) ? value : 0,
			};
		}
		return {
			...row,
			[MANUAL_PERCENTAGE]: 0,
			[MANUAL_AMOUNT]: 0,
			[MANUAL_MODE]: "",
			[MANUAL_VALUE]: "",
		};
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
			[MANUAL_MODE, MANUAL_VALUE].includes(column?.fieldname)
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
		const rows = normaliseManualDiscountRows(nextRows || [], this.values.items || []);
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
