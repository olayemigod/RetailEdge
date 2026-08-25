(() => {
	const TITLE_BY_DOCTYPE = {
		"RetailEdge Settings": "Settings",
		"RetailEdge Branch Profile": "Branch Setup",
		"RetailEdge Cashier Expense": "Cashier Expense",
		"RetailEdge Expense Category": "Expense Category",
		"RetailEdge Daily Sales Audit": "Daily Sales Audit",
		"RetailEdge Payment Statement Import": "Import Bank Statement",
		"RetailEdge Statement Mapping Template": "Bank Statement Mapping",
		"RetailEdge Bank Transaction Match": "Bank Match Review",
	};

	Object.entries(TITLE_BY_DOCTYPE).forEach(([doctype, title]) => {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				if (frm.page && frm.page.set_title) {
					frm.page.set_title(__(title));
				}
			},
		});
	});
})();
