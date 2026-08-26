(function installRetailEdgeBankingEdgeSuiteCompletion(global) {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const MATCH_DOCTYPE = "RetailEdge Bank Transaction Match";
	const EVIDENCE_METHOD = "retailedge.banking_readiness.get_match_account_evidence";
	const OPERATIONAL_METHOD = "retailedge.banking_operations.get_bank_match_operational_status";
	const payloads = new Map();
	let latestMatchName = "";
	let scheduled = false;

	if (global.retailedgeBankingEdgeSuiteCompletionInstalled) return;
	if (!global.frappe?.call) return;

	const originalCall = global.frappe.call.bind(global.frappe);

	function clean(value) {
		return String(value ?? "").trim();
	}

	function t(text, args) {
		return typeof global.__ === "function" ? global.__(text, args) : text;
	}

	function humanize(value) {
		return clean(value)
			.replace(/[_-]+/g, " ")
			.replace(/([a-z0-9])([A-Z])/g, "$1 $2")
			.replace(/\b\w/g, (letter) => letter.toUpperCase());
	}

	function parseDetails(doc) {
		try {
			return JSON.parse(doc?.details_json || "{}") || {};
		} catch (_error) {
			return {};
		}
	}

	function isBankingPage() {
		const route = global.frappe.get_route?.() || [];
		return route[0] === PAGE_NAME;
	}

	function requestMethod(request) {
		return typeof request === "string" ? request : request?.method || "";
	}

	function ensurePayload(matchName) {
		const name = clean(matchName);
		if (!name) return null;
		if (!payloads.has(name)) payloads.set(name, { doc: {}, evidence: {}, operational: {} });
		latestMatchName = name;
		return payloads.get(name);
	}

	function captureResponse(request, response) {
		const method = requestMethod(request);
		const message = response?.message || {};
		if (method === "frappe.client.get" && request?.args?.doctype === MATCH_DOCTYPE) {
			const name = clean(message.name || request.args.name);
			const payload = ensurePayload(name);
			if (payload) payload.doc = message;
			return;
		}
		if (method === EVIDENCE_METHOD) {
			const name = clean(message.match_name || request?.args?.match_name);
			const payload = ensurePayload(name);
			if (payload) payload.evidence = message;
			return;
		}
		if (method === OPERATIONAL_METHOD) {
			const name = clean(message.match_name || request?.args?.match_name);
			const payload = ensurePayload(name);
			if (payload) payload.operational = message;
		}
	}

	async function hydrateOperational(matchName) {
		const payload = ensurePayload(matchName);
		if (!payload || payload.operational?.operational_status) return;
		try {
			const response = await originalCall({
				method: OPERATIONAL_METHOD,
				args: { match_name: matchName, include_gate: 0 },
			});
			payload.operational = response?.message || {};
		} catch (_error) {
			// The primary EdgeSuite review remains usable even if guidance hydration fails.
		}
	}

	function node(tag, className, text) {
		const element = document.createElement(tag);
		if (className) element.className = className;
		if (text !== undefined && text !== null) element.textContent = String(text);
		return element;
	}

	function contextItem(label, value, note) {
		if (!clean(value)) return null;
		const item = node("div", "retailedge-bank-completion-item");
		item.appendChild(node("strong", "", label));
		item.appendChild(node("span", "", value));
		if (note) item.appendChild(node("small", "", note));
		return item;
	}

	function evidencePanel(title, body, tone) {
		const section = node("section", `retailedge-bank-completion-evidence is-${tone}`);
		section.appendChild(node("h4", "", title));
		section.appendChild(node("p", "", clean(body) || t("No evidence detail recorded.")));
		return section;
	}

	function findReviewModal() {
		return Array.from(document.querySelectorAll(".edge-modal--xl, .edge-modal"))
			.find((modal) => clean(modal.textContent).includes(t("Review Match:"))) || null;
	}

	async function enhanceReviewModal() {
		scheduled = false;
		if (!isBankingPage()) return;
		const modal = findReviewModal();
		if (!modal || modal.dataset.retailedgeCompletion === "1") return;
		const matchName = latestMatchName;
		if (!matchName) return;
		const payload = ensurePayload(matchName);
		if (!payload?.doc?.name || !payload?.evidence?.match_name) return;

		await hydrateOperational(matchName);
		const doc = payload.doc || {};
		const evidence = payload.evidence || {};
		const operational = payload.operational || {};
		const statement = evidence.statement || {};
		const accounting = evidence.accounting || {};
		const details = parseDetails(doc);
		const candidate = details.candidate_context || {};
		const body = modal.querySelector(".edge-modal__body") || modal;
		const recordLinks = body.querySelector(".retailedge-bank-record-links");
		const insertBefore = recordLinks || null;

		const context = node("section", "retailedge-bank-review-section retailedge-bank-completion-context");
		context.appendChild(node("h3", "", t("Operational Context")));
		const grid = node("div", "retailedge-bank-completion-grid");
		[
			contextItem(t("Bank Narration"), doc.bank_narration || statement.description || details.bank_context?.description),
			contextItem(t("Branch"), [statement.branch, accounting.branch].filter(Boolean).join(" ↔ ") || doc.branch, t("Supporting context; company and bank/GL identity remain authoritative.")),
			contextItem(t("Mode of Payment"), accounting.mode_of_payment || doc.payment_mode || candidate.payment_mode, t("Supporting evidence only; it cannot override a bank/GL mismatch.")),
			contextItem(t("Payment Event Source"), doc.payment_event_source || candidate.payment_event_source),
			contextItem(t("Business Category"), humanize(evidence.transaction_category || evidence.candidate_category || candidate.transaction_category || candidate.candidate_category)),
		].filter(Boolean).forEach((item) => grid.appendChild(item));
		context.appendChild(grid);

		const hardEvidence = doc.match_reason_summary || doc.match_reason || candidate.accounting_evidence;
		const fuzzyEvidence = candidate.fuzzy_note || candidate.fuzzy_review_evidence || candidate.fuzzy_evidence?.reason || t("No supplemental fuzzy evidence recorded.");
		const evidenceGrid = node("section", "retailedge-bank-review-section retailedge-bank-completion-evidence-grid");
		evidenceGrid.appendChild(node("h3", "retailedge-bank-completion-evidence-title", t("Matching Evidence")));
		const panels = node("div", "retailedge-bank-completion-evidence-panels");
		panels.appendChild(evidencePanel(t("Accounting / Hard Match Evidence"), hardEvidence, "accounting"));
		panels.appendChild(evidencePanel(t("Fuzzy / Supplemental Evidence"), fuzzyEvidence, "fuzzy"));
		evidenceGrid.appendChild(panels);

		const guidance = node("section", "retailedge-bank-review-section retailedge-bank-completion-guidance");
		guidance.appendChild(node("h3", "", t("Operational Guidance")));
		const action = clean(operational.recommended_action);
		if (action) guidance.appendChild(node("p", "retailedge-bank-completion-action", action));
		const explanation = node("p", "retailedge-bank-completion-info", t("Matching does not reconcile the Bank Transaction. Approval also does not reconcile it. ERPNext Banking reconciliation runs only after final confirmation and a fresh safety check."));
		guidance.appendChild(explanation);

		body.insertBefore(guidance, insertBefore);
		body.insertBefore(evidenceGrid, guidance);
		body.insertBefore(context, evidenceGrid);
		modal.dataset.retailedgeCompletion = "1";
	}

	function scheduleEnhancement() {
		if (scheduled) return;
		scheduled = true;
		setTimeout(enhanceReviewModal, 0);
	}

	global.frappe.call = function retailedgeBankingCompletionCall(...args) {
		const request = args[0];
		const result = originalCall(...args);
		if (!isBankingPage() || !result?.then) return result;
		return result.then((response) => {
			captureResponse(request, response);
			scheduleEnhancement();
			return response;
		});
	};

	const observer = new MutationObserver(scheduleEnhancement);
	observer.observe(document.documentElement, { childList: true, subtree: true });
	global.retailedgeBankingEdgeSuiteCompletionInstalled = true;
})(window);
