export const BRANCH_WAREHOUSE_METHOD =
	"retailedge.guided_entry_context.resolve_branch_warehouse_selection";

const PRICING_BATCH_METHODS = {
	"retailedge.guided_sales_invoice.get_simple_sales_invoice_item_pricing":
		"retailedge.guided_pricing_api.get_sales_item_pricing_batch",
	"retailedge.guided_purchase_invoice.get_simple_purchase_invoice_item_pricing":
		"retailedge.guided_pricing_api.get_purchase_item_pricing_batch",
};
const pricingQueues = new Map();

function rawCall(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function pricingContext(args = {}) {
	if (!args.values || typeof args.values !== "object" || Array.isArray(args.values)) return null;
	const values = { ...args.values };
	delete values.qty;
	return values;
}

function pricingQueueKey(method, values) {
	return `${method}:${JSON.stringify(values)}`;
}

function flushPricingQueue(key) {
	const queue = pricingQueues.get(key);
	if (!queue) return;
	pricingQueues.delete(key);
	queue.timer = null;

	const items = queue.entries.map((entry, index) => ({
		index,
		item_code: entry.args.item_code,
		qty: entry.args.values?.qty || 1,
	}));
	rawCall(queue.batchMethod, { items, values: queue.values })
		.then((result) => {
			const rows = Array.isArray(result?.rows) ? result.rows : [];
			const byIndex = new Map(rows.map((row) => [Number(row.index), row]));
			queue.entries.forEach((entry, index) => entry.resolve(byIndex.get(index) || {}));
		})
		.catch((error) => queue.entries.forEach((entry) => entry.reject(error)));
}

function queuePricingCall(method, args, batchMethod, values) {
	const key = pricingQueueKey(method, values);
	return new Promise((resolve, reject) => {
		let queue = pricingQueues.get(key);
		if (!queue) {
			queue = { method, batchMethod, values, entries: [], timer: null };
			pricingQueues.set(key, queue);
		}
		queue.entries.push({ args, resolve, reject });
		if (!queue.timer) queue.timer = setTimeout(() => flushPricingQueue(key), 0);
	});
}

export function callMethod(method, args = {}) {
	const batchMethod = PRICING_BATCH_METHODS[method];
	const values = batchMethod ? pricingContext(args) : null;
	if (batchMethod && values && args.item_code) {
		return queuePricingCall(method, args, batchMethod, values);
	}
	return rawCall(method, args);
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
