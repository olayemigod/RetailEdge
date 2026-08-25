(() => {
	const TITLE_BY_DOCTYPE = {
		"RetailEdge Cashier Expense": "Cashier Expense",
		"RetailEdge Expense Category": "Expense Category",
		"RetailEdge Daily Sales Audit": "Daily Sales Audit",
		"RetailEdge Payment Statement Import": "Import Bank Statement",
		"RetailEdge Statement Mapping Template": "Bank Statement Mapping",
		"RetailEdge Bank Transaction Match": "Bank Match Review",
	};

	const doctype = window.cur_frm && window.cur_frm.doctype;
	const title = doctype && TITLE_BY_DOCTYPE[doctype];
	if (!doctype || !title) {
		return;
	}

	frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (frm.page && frm.page.set_title) {
				frm.page.set_title(__(title));
			}
		},
	});
})();
