import ProfessionalPurchaseReturnReviewOverlay from "./ProfessionalPurchaseReturnReviewOverlay.vue";

const OPEN_EVENT = "retailedge-open-professional-purchase-return-review";
const PURCHASE_RETURN_LABELS = new Set(["Prepare Draft Return", "Review & Submit Return"]);
const DEBIT_NOTE_LABELS = new Set(["Prepare Draft Debit Note", "Review & Submit Debit Note"]);

function normaliseLabel(button) {
	return String(button?.textContent || "").replace(/\s+/g, " ").trim();
}

function sourceValue(button) {
	const card = button?.closest?.(".return-card");
	if (!card) return "";
	const input = card.querySelector('input:not([type="hidden"]), input');
	return String(input?.value || "").trim();
}

function applyOwnership(root) {
	if (!root) return;
	for (const button of root.querySelectorAll(".returns-panel .return-card button")) {
		const label = normaliseLabel(button);
		if (PURCHASE_RETURN_LABELS.has(label)) {
			button.textContent = __("Review & Submit Return");
			button.setAttribute("title", __("Review ERPNext's mapped Purchase Return inside RetailEdge before submission."));
			button.setAttribute("data-retailedge-return-review", "purchase_receipt");
		}
		if (DEBIT_NOTE_LABELS.has(label)) {
			button.textContent = __("Review & Submit Debit Note");
			button.setAttribute("title", __("Review ERPNext's mapped supplier Debit Note inside RetailEdge before submission."));
			button.setAttribute("data-retailedge-return-review", "purchase_invoice");
		}
	}
}

export function installProfessionalPurchaseReturnOwnership(root) {
	if (!root || root._retailedgePurchaseReturnOwnershipInstalled) return () => {};
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");

	const overlayRoot = document.createElement("div");
	overlayRoot.className = "retailedge-professional-purchase-return-review-overlay-root";
	(root.parentNode || root).appendChild(overlayRoot);
	const overlayApp = edgeUI.createEdgeApp(ProfessionalPurchaseReturnReviewOverlay);
	overlayApp.mount(overlayRoot);

	let scheduled = false;
	const scheduleApply = () => {
		if (scheduled) return;
		scheduled = true;
		window.requestAnimationFrame(() => {
			scheduled = false;
			applyOwnership(root);
		});
	};
	const handler = (event) => {
		const button = event.target?.closest?.("button");
		if (!button || !root.contains(button)) return;
		const sourceType = button.getAttribute("data-retailedge-return-review") || (
			PURCHASE_RETURN_LABELS.has(normaliseLabel(button)) ? "purchase_receipt" :
			DEBIT_NOTE_LABELS.has(normaliseLabel(button)) ? "purchase_invoice" : ""
		);
		if (!sourceType) return;
		event.preventDefault();
		event.stopPropagation();
		event.stopImmediatePropagation();
		const sourceName = sourceValue(button);
		if (!sourceName) {
			frappe.show_alert({ message: __("Select the submitted source document before reviewing the return."), indicator: "orange" }, 5);
			return;
		}
		window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { source_type: sourceType, source_name: sourceName } }));
	};

	root.addEventListener("click", handler, true);
	const observer = new MutationObserver(scheduleApply);
	observer.observe(root, { childList: true, subtree: true });
	root._retailedgePurchaseReturnOwnershipInstalled = true;
	scheduleApply();

	return () => {
		observer.disconnect();
		root.removeEventListener("click", handler, true);
		overlayApp.unmount?.();
		overlayRoot.remove();
		root._retailedgePurchaseReturnOwnershipInstalled = false;
	};
}
