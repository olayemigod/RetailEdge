(function installRetailEdgeBankingFuzzyDiscoveryAdapter(global) {
	"use strict";

	const EXACT_WORKSPACE_METHOD = "retailedge.banking_workspace.get_banking_workspace_rows";
	const FUZZY_WORKSPACE_METHOD = "retailedge.banking_workspace_fuzzy.get_fuzzy_banking_workspace_rows";
	const CANDIDATE_METHOD = "retailedge.bank_candidate_engine.get_direction_aware_bank_candidates";
	const DEFAULT_DATE_TOLERANCE_DAYS = 3;
	const MAX_DATE_TOLERANCE_DAYS = 7;

	if (global.retailedgeBankingFuzzyDiscoveryAdapterInstalled) return;
	if (!global.frappe?.call) return;

	const originalCall = global.frappe.call.bind(global.frappe);

	function requestMethod(request) {
		if (typeof request === "string") return request;
		return request?.method || "";
	}

	function configuredTolerance(request) {
		const raw = request?.args?.date_tolerance_days ?? global.retailedgeBankingFuzzyDateToleranceDays ?? DEFAULT_DATE_TOLERANCE_DAYS;
		const value = Number(raw);
		if (!Number.isFinite(value)) return DEFAULT_DATE_TOLERANCE_DAYS;
		return Math.max(0, Math.min(MAX_DATE_TOLERANCE_DAYS, Math.round(value)));
	}

	function percent(value) {
		const number = Number(value || 0);
		return Number.isFinite(number) ? Math.round(number * 100) : 0;
	}

	function dateProximityLabel(evidence) {
		const score = Number(evidence?.date_score || 0);
		if (score >= 1) return "same-day date";
		if (score >= 0.8) return "within 1 day";
		if (score >= 0.6) return "within 3 days";
		if (score >= 0.3) return "within 7 days";
		return "date not close enough for a fuzzy boost";
	}

	function enrichCandidateResponse(response) {
		const payload = response?.message || {};
		if (!Array.isArray(payload.candidates)) return response;
		payload.candidates.forEach((row) => {
			const evidence = row?.fuzzy_evidence || {};
			const dateLabel = dateProximityLabel(evidence);
			const reference = percent(evidence.reference_similarity);
			const narration = percent(evidence.narration_similarity);
			const base = String(row.fuzzy_note || evidence.reason || "").trim();
			const summary = `Fuzzy date: ${dateLabel} · reference similarity ${reference}% · narration/party similarity ${narration}%.`;
			row.fuzzy_note = base ? `${summary} ${base}` : `${summary} Supplemental evidence only; accounting eligibility is unchanged.`;
		});
		return response;
	}

	global.frappe.call = function retailedgeBankingFuzzyAwareCall(...args) {
		const request = args[0];
		const method = requestMethod(request);

		if (method === EXACT_WORKSPACE_METHOD && request && typeof request === "object") {
			const tolerance = configuredTolerance(request);
			global.retailedgeBankingFuzzyDateToleranceDays = tolerance;
			const next = {
				...request,
				method: FUZZY_WORKSPACE_METHOD,
				args: {
					...(request.args || {}),
					date_tolerance_days: tolerance,
				},
			};
			return originalCall(next);
		}

		const result = originalCall(...args);
		if (method === CANDIDATE_METHOD && result?.then) {
			return result.then(enrichCandidateResponse);
		}
		return result;
	};

	global.retailedgeBankingFuzzyDiscoveryAdapterInstalled = true;
	global.retailedgeBankingFuzzyDateToleranceDays = global.retailedgeBankingFuzzyDateToleranceDays ?? DEFAULT_DATE_TOLERANCE_DAYS;
})(window);
