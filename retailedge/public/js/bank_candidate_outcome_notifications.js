(function installRetailEdgeBankCandidateOutcomeNotifications(global) {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const CANDIDATE_METHOD = "retailedge.bank_candidate_engine.get_direction_aware_bank_candidates";
	const GENERIC_NO_CANDIDATE_MESSAGE = "No safe accounting candidate was found for this bank transaction.";

	if (global.retailedgeBankCandidateOutcomeNotificationsInstalled) return;
	if (!global.frappe?.call || !global.frappe?.msgprint) return;

	const originalCall = global.frappe.call.bind(global.frappe);
	const originalMsgprint = global.frappe.msgprint.bind(global.frappe);
	let suppressGenericNoCandidateOnce = false;

	function isBankMatchingPage() {
		const route = global.frappe.get_route?.() || [];
		return route[0] === PAGE_NAME;
	}

	function requestMethod(request) {
		if (typeof request === "string") return request;
		return request?.method || "";
	}

	function isGenericNoCandidateMessage(value) {
		const message = typeof value === "string" ? value : value?.message;
		return message === GENERIC_NO_CANDIDATE_MESSAGE || message === __(GENERIC_NO_CANDIDATE_MESSAGE);
	}

	function showOutcome(outcome) {
		if (!outcome?.message) return false;
		const options = {
			title: __(outcome.title || "Bank matching result"),
			message: __(outcome.message),
			indicator: outcome.indicator || "blue",
		};
		if (outcome.action === "banking_readiness") {
			options.primary_action = {
				label: __("Open Banking Readiness"),
				action: () => global.frappe.set_route("banking-readiness"),
			};
		}
		originalMsgprint(options);
		return true;
	}

	global.frappe.call = function retailedgeOutcomeAwareCall(...args) {
		const method = requestMethod(args[0]);
		const result = originalCall(...args);
		if (!isBankMatchingPage() || method !== CANDIDATE_METHOD || !result?.then) return result;

		return result.then((response) => {
			const payload = response?.message || {};
			const outcome = payload.outcome || null;
			const outcomeCode = outcome?.code || "";
			const shouldNotify = Boolean(outcome) && (
				Number(payload.count || 0) === 0 || outcomeCode === "candidate_review_blocked"
			);
			if (!shouldNotify) return response;

			if (showOutcome(outcome)) suppressGenericNoCandidateOnce = true;
			if (outcomeCode === "candidate_review_blocked" && response?.message) {
				response.message = {
					...payload,
					candidates: [],
					count: 0,
				};
			}
			return response;
		});
	};

	global.frappe.msgprint = function retailedgeOutcomeAwareMsgprint(message, ...rest) {
		if (
			isBankMatchingPage()
			&& suppressGenericNoCandidateOnce
			&& isGenericNoCandidateMessage(message)
		) {
			suppressGenericNoCandidateOnce = false;
			return undefined;
		}
		return originalMsgprint(message, ...rest);
	};

	global.retailedgeBankCandidateOutcomeNotificationsInstalled = true;
})(window);
