(function installRetailEdgeBankReconciliationConfirmation(global) {
	"use strict";

	if (!global.frappe?.confirm || global.__retailedgeBankReconciliationConfirmInstalled) {
		return;
	}

	const BANK_RECONCILIATION_CONFIRM_MESSAGE = __(
		"This match is confirmed and approved. Reconcile it through ERPNext after a fresh safety check?",
	);
	const originalConfirm = frappe.confirm.bind(frappe);

	function setPrimaryDisabled(dialog, disabled) {
		const button = dialog?.get_primary_btn?.();
		if (button?.prop) {
			button.prop("disabled", Boolean(disabled));
		}
	}

	frappe.confirm = function retailedgeConfirm(message, ifYes, ifNo) {
		if (message !== BANK_RECONCILIATION_CONFIRM_MESSAGE) {
			return originalConfirm(message, ifYes, ifNo);
		}

		let submitting = false;
		const dialog = new frappe.ui.Dialog({
			title: __("Final Reconciliation Confirmation"),
			fields: [
				{
					fieldname: "warning",
					fieldtype: "Small Text",
					label: __("Accounting action"),
					read_only: 1,
					default: __(
						"RetailEdge will run a fresh safety check and then reconcile the confirmed accounting candidate through ERPNext Bank Reconciliation. This action should be performed only once.",
					),
				},
			],
			primary_action_label: __("Reconcile Through ERPNext"),
			primary_action: async () => {
				if (submitting) return;
				submitting = true;
				setPrimaryDisabled(dialog, true);
				try {
					await Promise.resolve(ifYes?.());
					dialog.hide();
				} catch (error) {
					console.error("RetailEdge reconciliation confirmation failed", error);
					frappe.msgprint({
						title: __("Reconciliation could not be completed"),
						indicator: "red",
						message:
							error?.message ||
							__("The reconciliation request failed before a confirmed result was returned. Review the error and do not retry blindly."),
					});
					submitting = false;
					setPrimaryDisabled(dialog, false);
				}
			},
			secondary_action_label: __("Cancel"),
			secondary_action: () => {
				if (submitting) return;
				dialog.hide();
				if (typeof ifNo === "function") {
					ifNo();
				}
			},
		});

		dialog.show();
		return dialog;
	};

	global.__retailedgeBankReconciliationConfirmInstalled = true;
})(window);
