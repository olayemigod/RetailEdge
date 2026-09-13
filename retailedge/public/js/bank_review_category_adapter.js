(function installRetailEdgeBankReviewCategoryAdapter(global) {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const EVIDENCE_METHOD = "retailedge.banking_readiness.get_match_account_evidence";
	const BUSINESS_CATEGORIES = new Set([
		"Customer Receipt",
		"POS Sale",
		"Deposit to Bank",
		"Supplier Payment",
		"Expense",
		"Bank Transfer",
		"Other Income",
		"Other Outflow",
	]);

	if (global.retailedgeBankReviewCategoryAdapterInstalled) return;
	if (!global.frappe?.call) return;

	const originalCall = global.frappe.call.bind(global.frappe);

	function isBankMatchingPage() {
		const route = global.frappe.get_route?.() || [];
		return route[0] === PAGE_NAME;
	}

	function requestMethod(request) {
		if (typeof request === "string") return request;
		return request?.method || "";
	}

	function paymentEntryCategory(row, direction) {
		const paymentType = String(row?.payment_type || "").trim();
		const partyType = String(row?.party_type || "").trim();
		const remarks = String(row?.remarks || "").trim().toLowerCase();

		if (paymentType === "Internal Transfer") {
			if (direction === "Inflow") return "Deposit to Bank";
			if (direction === "Outflow") return "Bank Transfer";
			return "";
		}
		if (direction === "Inflow") {
			return partyType === "Customer" ? "Customer Receipt" : "Other Income";
		}
		if (direction === "Outflow") {
			if (partyType === "Supplier") return "Supplier Payment";
			if (["expense", "charge", "fee", "rent", "utility"].some((token) => remarks.includes(token))) {
				return "Expense";
			}
			return "Other Outflow";
		}
		return "";
	}

	async function enrichPaymentEntryCategory(response) {
		const payload = response?.message || {};
		const existingCategory = String(payload.transaction_category || "").trim();
		if (BUSINESS_CATEGORIES.has(existingCategory)) return response;

		const accounting = payload.accounting || {};
		if (accounting.doctype !== "Payment Entry" || !accounting.name) return response;

		try {
			const paymentResponse = await originalCall({
				method: "frappe.client.get",
				args: { doctype: "Payment Entry", name: accounting.name },
			});
			const category = paymentEntryCategory(paymentResponse?.message || {}, payload.direction);
			if (category && response?.message) response.message.transaction_category = category;
		} catch (error) {
			console.error("Unable to hydrate RetailEdge Payment Entry business category", error);
		}
		return response;
	}

	global.frappe.call = function retailedgeReviewCategoryAwareCall(...args) {
		const method = requestMethod(args[0]);
		const result = originalCall(...args);
		if (!isBankMatchingPage() || method !== EVIDENCE_METHOD || !result?.then) return result;
		return result.then(enrichPaymentEntryCategory);
	};

	global.retailedgeBankReviewCategoryAdapterInstalled = true;
})(window);
