export const BRANCH_WAREHOUSE_METHOD =
	"retailedge.guided_entry_context.resolve_branch_warehouse_selection";

export function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

export function errorMessage(error, fallback) {
	if (error?.message) return error.message;
	if (error?.exc_type) return error.exc_type;
	return fallback;
}

export function resolveBranchWarehouse({ company, branch = "", warehouse = "", preference = "default" }) {
	return callMethod(BRANCH_WAREHOUSE_METHOD, {
		company,
		branch,
		warehouse,
		preference,
	});
}

function displayLabel(doc) {
	return (
		doc?.customer_name ||
		doc?.supplier_name ||
		doc?.item_name ||
		doc?.title ||
		doc?.name ||
		""
	);
}

export function quickCreateMaster(doctype, query, initialValues = {}) {
	const value = String(query || "").trim();
	if (!value) return Promise.resolve(null);

	return new Promise((resolve, reject) => {
		let settled = false;
		const finish = (result) => {
			if (settled) return;
			settled = true;
			resolve(result);
		};
		const fail = (error) => {
			if (settled) return;
			settled = true;
			reject(error);
		};

		try {
			const doc = frappe.model.get_new_doc(doctype, null, null, true);
			Object.assign(doc, initialValues || {});

			frappe.ui.form
				.make_quick_entry(
					doctype,
					(created) => {
						finish({
							value: created?.name || "",
							label: displayLabel(created),
							description: doctype,
							raw: created,
						});
					},
					(quickEntry) => {
						const originalOnHide = quickEntry.onhide;
						quickEntry.onhide = (...args) => {
							if (typeof originalOnHide === "function") originalOnHide(...args);
							finish(null);
						};
					},
					doc,
					true
				)
				.catch(fail);
		} catch (error) {
			fail(error);
		}
	});
}

export function quickCreateCustomer(query) {
	return quickCreateMaster("Customer", query, {
		customer_name: String(query || "").trim(),
	});
}

export function quickCreateSupplier(query) {
	return quickCreateMaster("Supplier", query, {
		supplier_name: String(query || "").trim(),
	});
}

export function quickCreateItem(query, { stockItem = null } = {}) {
	const itemCode = String(query || "").trim();
	const initialValues = {
		item_code: itemCode,
		item_name: itemCode,
	};
	if (stockItem !== null) initialValues.is_stock_item = stockItem ? 1 : 0;
	return quickCreateMaster("Item", itemCode, initialValues);
}
