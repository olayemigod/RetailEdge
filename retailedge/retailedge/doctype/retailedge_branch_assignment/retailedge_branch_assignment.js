const CONFIGURED_BRANCH_QUERY = "retailedge.branch_profile_queries.search_configured_company_branches";
const TRANSFER_METHOD = "retailedge.branch_assignment.transfer_branch_assignment";

function setBranchQuery(frm) {
	frm.set_query("branch", () => ({
		query: CONFIGURED_BRANCH_QUERY,
		filters: { company: frm.doc.company || "" },
	}));
	frm.toggle_enable("branch", Boolean(frm.doc.company));
}

function clearBranchContext(frm) {
	if (frm.doc.branch) frm.set_value("branch", null);
	if (frm.doc.branch_setup) frm.set_value("branch_setup", null);
}

function addTransferAction(frm) {
	if (frm.is_new() || !frm.doc.name || frm.doc.status !== "Active" || !frm.perm?.[0]?.write) {
		return;
	}
	frm.add_custom_button(__("Transfer to Branch"), () => openTransferDialog(frm), __("Actions"));
}

function openTransferDialog(frm) {
	let dialog;
	dialog = new frappe.ui.Dialog({
		title: __("Transfer User to Branch"),
		fields: [
			{ fieldname: "new_company", fieldtype: "Link", label: __("New Company"), options: "Company", reqd: 1, default: frm.doc.company },
			{
				fieldname: "new_branch",
				fieldtype: "Link",
				label: __("New Branch"),
				options: "Branch",
				reqd: 1,
				get_query: () => ({ query: CONFIGURED_BRANCH_QUERY, filters: { company: dialog.get_value("new_company") || "" } }),
			},
			{ fieldname: "effective_date", fieldtype: "Date", label: __("Transfer Date"), reqd: 1, default: frappe.datetime.get_today() },
			{ fieldname: "branch_role", fieldtype: "Select", label: __("Branch Role"), options: "Cashier\nManager\nAuditor\nSales\nStock\nAccounts\nPurchasing\nOther", default: frm.doc.branch_role || "Other" },
			{ fieldname: "reason", fieldtype: "Small Text", label: __("Transfer Reason"), reqd: 1 },
			{ fieldname: "notes", fieldtype: "Small Text", label: __("Notes") },
		],
		primary_action_label: __("Transfer"),
		primary_action(values) {
			frappe.call({
				method: TRANSFER_METHOD,
				args: { name: frm.doc.name, ...values },
				freeze: true,
				freeze_message: __("Transferring branch assignment..."),
				callback: (response) => {
					dialog.hide();
					const next = response.message?.current;
					frappe.show_alert({ message: __("Branch transfer recorded."), indicator: "green" });
					if (next?.name) frappe.set_route("Form", "RetailEdge Branch Assignment", next.name);
					else frm.reload_doc();
				},
			});
		},
	});
	dialog.fields_dict.new_company.df.onchange = () => dialog.set_value("new_branch", null);
	dialog.show();
}

frappe.ui.form.on("RetailEdge Branch Assignment", {
	setup(frm) {
		setBranchQuery(frm);
	},
	refresh(frm) {
		setBranchQuery(frm);
		addTransferAction(frm);
	},
	company(frm) {
		clearBranchContext(frm);
		setBranchQuery(frm);
	},
});
