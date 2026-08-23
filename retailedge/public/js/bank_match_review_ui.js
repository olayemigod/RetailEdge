(function installRetailEdgeBankMatchReviewUI(global) {
	"use strict";

	const REVIEW_PREFIX = "Review Match";
	const ENHANCED_CLASS = "retailedge-bank-review-enhanced";

	function text(value, fallback = "—") {
		const cleaned = String(value ?? "").trim();
		return cleaned || fallback;
	}

	function money(value, currency) {
		try {
			return format_currency(Number(value || 0), currency || undefined);
		} catch (_error) {
			return String(value || 0);
		}
	}

	function parseDetails(doc) {
		try {
			return JSON.parse(doc.details_json || "{}") || {};
		} catch (_error) {
			return {};
		}
	}

	function make(tag, className, content) {
		const node = document.createElement(tag);
		if (className) node.className = className;
		if (content !== undefined && content !== null) node.textContent = String(content);
		return node;
	}

	function badge(label, tone) {
		return make("span", `retailedge-review-badge retailedge-review-badge--${tone || "neutral"}`, label);
	}

	function evidenceTone(status) {
		if (status === "Match") return "success";
		if (status === "Mismatch") return "danger";
		if (status === "Supporting") return "info";
		return "neutral";
	}

	function evidenceLabel(status) {
		if (status === "Match") return __("Match ✓");
		if (status === "Mismatch") return __("Mismatch ✕");
		return __(status || "Not Available");
	}

	function fieldValue(modal, fieldname) {
		const field = modal.querySelector(`.frappe-control[data-fieldname="${fieldname}"]`);
		if (!field) return "";
		const input = field.querySelector("input, textarea, select");
		if (input && input.value) return input.value;
		const display = field.querySelector(".control-value, .like-disabled-input, .readonly-input");
		return display?.textContent?.trim() || "";
	}

	function valueRow(label, value, options = {}) {
		const row = make("div", "retailedge-review-row");
		const labelNode = make("div", "retailedge-review-label", __(label));
		const valueNode = make("div", "retailedge-review-value");
		if (options.badge) {
			valueNode.appendChild(badge(text(value), options.tone));
		} else if (options.link && value) {
			const button = make("button", "retailedge-review-link", text(value));
			button.type = "button";
			button.addEventListener("click", options.link);
			valueNode.appendChild(button);
		} else {
			valueNode.textContent = text(value);
		}
		if (options.emphasis) valueNode.classList.add("retailedge-review-value--emphasis");
		if (options.positive) valueNode.classList.add("retailedge-review-value--positive");
		row.append(labelNode, valueNode);
		return row;
	}

	function cardHeader(title, badgeLabel, badgeTone) {
		const header = make("div", "retailedge-review-card-header");
		header.appendChild(make("h3", "retailedge-review-card-title", __(title)));
		if (badgeLabel) header.appendChild(badge(badgeLabel, badgeTone));
		return header;
	}

	function evidenceItems(raw) {
		const source = String(raw || "").trim();
		if (!source) return [__("No evidence detail recorded.")];
		const separators = source.includes(" · ") ? " · " : source.includes(";") ? ";" : "\n";
		const items = source.split(separators).map((item) => item.trim()).filter(Boolean);
		return items.length ? items : [source];
	}

	function evidencePanel(title, raw, tone, badgeText) {
		const panel = make("section", `retailedge-review-evidence retailedge-review-evidence--${tone}`);
		const header = make("div", "retailedge-review-evidence-header");
		header.appendChild(make("h3", "retailedge-review-evidence-title", __(title)));
		if (badgeText) header.appendChild(badge(badgeText, tone === "accounting" ? "success" : "info"));
		panel.appendChild(header);
		const list = make("div", "retailedge-review-evidence-list");
		evidenceItems(raw).slice(0, 8).forEach((item) => {
			const line = make("div", "retailedge-review-evidence-item");
			line.appendChild(make("span", "retailedge-review-check", "✓"));
			line.appendChild(make("span", "", item));
			list.appendChild(line);
		});
		panel.appendChild(list);
		return panel;
	}

	function accountSafetyPanel(accountEvidence) {
		const evidence = Array.isArray(accountEvidence?.evidence) ? accountEvidence.evidence : [];
		if (!evidence.length) return null;
		const panel = make("section", "retailedge-review-why");
		panel.appendChild(make("h3", "retailedge-review-section-title", __("Bank Identity & Accounting Safety")));
		const list = make("div", "retailedge-review-why-list");
		evidence.forEach((item) => {
			const row = make("div", "retailedge-review-why-item");
			row.appendChild(make("strong", "", `${__(item.label || item.key)}: `));
			row.appendChild(badge(evidenceLabel(item.status), evidenceTone(item.status)));
			const left = text(item.statement, "");
			const right = text(item.accounting, "");
			if (left || right) {
				row.appendChild(make("span", "", ` ${left || "—"} ↔ ${right || "—"}`));
			}
			list.appendChild(row);
		});
		panel.appendChild(list);
		return panel;
	}

	function approvalTone(status) {
		if (status === "Approved" || status === "Not Required") return "success";
		if (status === "Declined") return "danger";
		return "warning";
	}

	function approvalPanel(modal) {
		const status = fieldValue(modal, "approval_status");
		if (!status) return null;
		const reason = fieldValue(modal, "approval_reason");
		const actor = fieldValue(modal, "approval_actor");
		const panel = make("section", "retailedge-review-approval");
		const header = make("div", "retailedge-review-card-header");
		header.appendChild(make("h3", "retailedge-review-card-title", __("Reconciliation Approval")));
		header.appendChild(badge(status, approvalTone(status)));
		panel.appendChild(header);
		const content = make("div", "retailedge-review-approval-content");
		if (reason) content.appendChild(make("p", "retailedge-review-approval-guidance", reason));
		if (actor) content.appendChild(make("p", "retailedge-review-approval-actor", __("Approved by {0}", [actor])));
		panel.appendChild(content);
		return panel;
	}

	function hideOriginalReviewFields(modal) {
		const hiddenFields = [
			"bank_section", "bank_direction", "bank_amount", "transaction_date", "bank_account",
			"bank_reference", "bank_narration", "candidate_column", "transaction_category",
			"suggested_document_type", "suggested_document", "candidate_amount", "amount_difference",
			"party", "payment_event_source", "payment_mode", "evidence_section", "match_confidence",
			"match_score", "risk_level", "accounting_evidence", "fuzzy_review_evidence",
			"approval_section", "approval_status", "approval_reason", "approval_actor",
			"decision_status", "open_bank_transaction", "open_candidate_document"
		];
		hiddenFields.forEach((fieldname) => {
			const field = modal.querySelector(`.frappe-control[data-fieldname="${fieldname}"], [data-fieldname="${fieldname}"].form-section`);
			if (field) field.classList.add("retailedge-review-hidden-field");
		});
	}

	function moveDecisionControls(modal, root) {
		const decisionArea = make("div", "retailedge-review-decision-area");
		const approvalNote = modal.querySelector('.frappe-control[data-fieldname="approval_note"]');
		const requestApproval = modal.querySelector('.frappe-control[data-fieldname="request_approval"]');
		const approve = modal.querySelector('.frappe-control[data-fieldname="approve_reconciliation"]');
		const decline = modal.querySelector('.frappe-control[data-fieldname="decline_reconciliation"]');
		const note = modal.querySelector('.frappe-control[data-fieldname="decision_note"]');
		const keep = modal.querySelector('.frappe-control[data-fieldname="mark_needs_review"]');
		const audit = modal.querySelector('.frappe-control[data-fieldname="open_audit_record"]');

		if (approvalNote && !approvalNote.classList.contains("hide-control")) {
			const approvalWrap = make("div", "retailedge-review-note retailedge-review-approval-note");
			approvalWrap.appendChild(approvalNote);
			decisionArea.appendChild(approvalWrap);
		}
		const approvalActions = make("div", "retailedge-review-approval-actions");
		[requestApproval, decline, approve].forEach((control) => {
			if (control && !control.classList.contains("hide-control")) approvalActions.appendChild(control);
		});
		if (approvalActions.children.length) decisionArea.appendChild(approvalActions);

		if (note) {
			const noteWrap = make("div", "retailedge-review-note");
			noteWrap.appendChild(note);
			decisionArea.appendChild(noteWrap);
		}
		const auxiliary = make("div", "retailedge-review-aux-actions");
		if (audit) auxiliary.appendChild(audit);
		if (keep) auxiliary.appendChild(keep);
		if (auxiliary.children.length) decisionArea.appendChild(auxiliary);
		if (decisionArea.children.length) root.appendChild(decisionArea);
	}

	async function enhanceModal(modal) {
		if (!modal || modal.classList.contains(ENHANCED_CLASS)) return;
		const titleNode = modal.querySelector(".modal-title");
		const title = titleNode?.textContent?.trim() || "";
		if (!title.startsWith(REVIEW_PREFIX)) return;
		modal.classList.add(ENHANCED_CLASS);

		const matchName = title.includes("·") ? title.split("·").slice(1).join("·").trim() : "";
		if (!matchName) return;

		let doc = {};
		let accountEvidence = {};
		try {
			const [docResponse, evidenceResponse] = await Promise.all([
				frappe.call({
					method: "frappe.client.get",
					args: { doctype: "RetailEdge Bank Transaction Match", name: matchName },
				}),
				frappe.call({
					method: "retailedge.banking_readiness.get_match_account_evidence",
					args: { match_name: matchName },
				}),
			]);
			doc = docResponse?.message || {};
			accountEvidence = evidenceResponse?.message || {};
		} catch (error) {
			console.error("Unable to hydrate RetailEdge Bank Match review UI", error);
			return;
		}

		const details = parseDetails(doc);
		const candidate = details.candidate_context || {};
		const bank = details.bank_context || {};
		const statement = accountEvidence.statement || {};
		const accounting = accountEvidence.accounting || {};
		const body = modal.querySelector(".modal-body");
		if (!body) return;

		const accountingEvidence = fieldValue(modal, "accounting_evidence") || doc.match_reason_summary || doc.match_reason;
		const fuzzyEvidence = fieldValue(modal, "fuzzy_review_evidence") || __("Fuzzy evidence is supplemental only and does not change accounting eligibility.");
		const hardScore = Number(doc.match_score || 0);
		const confidence = text(doc.match_confidence, __("Pending Review"));
		const status = text(doc.decision_status, __("Suggested"));
		const category = candidate.transaction_category || candidate.candidate_category ||
			(doc.suggested_document_type === "Sales Invoice" ? __("Customer Receipt") : "");

		if (titleNode) {
			titleNode.textContent = __("Review Match: {0}", [doc.bank_transaction || matchName]);
			const header = titleNode.parentElement;
			if (header && !header.querySelector(".retailedge-review-title-badge")) {
				const statusBadge = badge(status, status === "Confirmed" ? "success" : "warning");
				statusBadge.classList.add("retailedge-review-title-badge");
				header.appendChild(statusBadge);
			}
		}

		const root = make("div", "retailedge-review-modern");
		const compare = make("div", "retailedge-review-compare");
		const bankCard = make("section", "retailedge-review-card");
		const candidateCard = make("section", "retailedge-review-card");
		bankCard.appendChild(cardHeader("Bank Statement", accountEvidence.direction || doc.bank_direction || bank.bank_direction || "", "info"));
		candidateCard.appendChild(cardHeader("Accounting Record", confidence, confidence === "Strong Match" ? "success" : "warning"));

		const bankRows = make("div", "retailedge-review-card-rows");
		const candidateRows = make("div", "retailedge-review-card-rows");

		bankRows.append(
			valueRow("Bank", statement.bank),
			valueRow("Bank Account", statement.bank_account || doc.bank_account || bank.bank_account),
			valueRow("GL Account", statement.gl_account),
			valueRow("Company", statement.company || doc.company || bank.company),
			valueRow("Branch", statement.branch || doc.branch || bank.branch),
			valueRow("Direction", accountEvidence.direction || doc.bank_direction || bank.bank_direction, { badge: true, tone: "info" }),
			valueRow("Amount", money(statement.amount ?? doc.bank_amount, doc.currency), { emphasis: true }),
			valueRow("Date", statement.date || doc.transaction_date),
			valueRow("Reference", statement.reference || doc.bank_reference || bank.reference),
			valueRow("Narration", doc.bank_narration || bank.description)
		);

		candidateRows.append(
			valueRow("Document", `${text(accounting.doctype || doc.suggested_document_type, "")} ${text(accounting.name || doc.suggested_document, "")}`.trim(), {
				link: () => frappe.set_route("Form", accounting.doctype || doc.suggested_document_type, accounting.name || doc.suggested_document)
			}),
			valueRow("Category", category, { badge: true, tone: "neutral" }),
			valueRow("Bank", accounting.bank),
			valueRow("Bank Account", accounting.bank_account || __("Resolved from GL account")),
			valueRow(accounting.gl_account_label || "Bank-side Account", accounting.gl_account),
			valueRow("Company", accounting.company),
			valueRow("Branch", accounting.branch),
			valueRow("Amount", money(accounting.amount ?? doc.candidate_amount, doc.currency), { emphasis: true }),
			valueRow("Date", accounting.date),
			valueRow("Reference", accounting.reference),
			valueRow("Mode of Payment", accounting.mode_of_payment || doc.payment_mode || candidate.payment_mode)
		);

		bankCard.appendChild(bankRows);
		candidateCard.appendChild(candidateRows);
		compare.append(bankCard, candidateCard);
		root.appendChild(compare);

		const safety = accountSafetyPanel(accountEvidence);
		if (safety) root.appendChild(safety);

		const why = make("section", "retailedge-review-why");
		why.appendChild(make("h3", "retailedge-review-section-title", __("Why this matches")));
		const whyList = make("div", "retailedge-review-why-list");
		evidenceItems(accountingEvidence).slice(0, 5).forEach((item) => {
			const chip = make("div", "retailedge-review-why-item");
			chip.appendChild(make("span", "retailedge-review-check", "✓"));
			chip.appendChild(make("span", "", item));
			whyList.appendChild(chip);
		});
		const fuzzyNote = make("div", "retailedge-review-fuzzy-note");
		fuzzyNote.appendChild(make("span", "retailedge-review-info", "i"));
		fuzzyNote.appendChild(make("span", "", __("Fuzzy evidence is supplemental and cannot change accounting eligibility or confirmation rules.")));
		whyList.appendChild(fuzzyNote);
		why.appendChild(whyList);
		root.appendChild(why);

		const evidenceGrid = make("div", "retailedge-review-evidence-grid");
		evidenceGrid.append(
			evidencePanel("Accounting / Hard Match Evidence", accountingEvidence, "accounting", hardScore ? __(`Score: ${hardScore}`) : __("Accounting evidence")),
			evidencePanel("Fuzzy / Supplemental Evidence", fuzzyEvidence, "fuzzy", __("Supplemental"))
		);
		root.appendChild(evidenceGrid);

		const approval = approvalPanel(modal);
		if (approval) root.appendChild(approval);

		const info = make("div", "retailedge-review-info-banner");
		info.appendChild(make("span", "retailedge-review-info", "i"));
		info.appendChild(make("span", "", __("Matching does not reconcile the bank transaction. Approval also does not reconcile it. ERPNext Banking reconciliation runs only after final confirmation and a fresh safety check.")));
		root.appendChild(info);

		hideOriginalReviewFields(modal);
		body.prepend(root);
		moveDecisionControls(modal, root);
		modal.querySelector(".modal-dialog")?.classList.add("retailedge-review-dialog");
	}

	function inspect() {
		document.querySelectorAll(".modal").forEach((modal) => {
			enhanceModal(modal);
		});
	}

	const observer = new MutationObserver(inspect);
	observer.observe(document.documentElement, { childList: true, subtree: true });
	inspect();

	global.retailedgeBankMatchReviewUIInstalled = true;
})(window);
