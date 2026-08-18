app_name = "retailedge"
app_title = "RetailEdge"
app_publisher = "ProcessEdge Solutions"
app_description = "Retail operations, POS control, sales audit, payment verification, branch workflows, and retail intelligence for ERPNext/POSNext."
app_email = "support@processedge.com.ng"
app_license = "MIT"

# The standalone ProcessEdge EdgeSuite UI app is the only supported shared
# frontend runtime for new RetailEdge product pages. RetailEdge must not depend
# on CoreEdge for Vue components, bundles, or browser UI runtime objects.
required_apps = ["edgesuite_ui"]

app_include_css = [
	"/assets/retailedge/css/retailedge_cards.css",
	"/assets/retailedge/css/retailedge_workspace_home.css",
]
app_include_js = [
	"/assets/retailedge/js/retailedge.js",
	"/assets/retailedge/js/retailedge_business_hub_page.js",
	"/assets/retailedge/js/retailedge_reporting_actions.js",
]

doctype_js = {
	"Bank Account": "public/js/bank_account.js",
	"Item": "public/js/inventory_documents.js",
	"Material Request": "public/js/material_request.js",
	"Purchase Invoice": "public/js/purchase_documents.js",
	"Purchase Order": "public/js/purchase_order.js",
	"Purchase Receipt": "public/js/purchase_documents.js",
	"Quotation": "public/js/sales_documents.js",
	"Sales Invoice": "public/js/sales_documents.js",
	"Sales Order": "public/js/sales_documents.js",
	"Delivery Note": "public/js/sales_documents.js",
	"Stock Reconciliation": "public/js/inventory_documents.js",
	"Stock Ledger Entry": "public/js/inventory_documents.js",
	"Bin": "public/js/inventory_documents.js",
	"Serial No": "public/js/inventory_documents.js",
	"Item Price": "public/js/cost_visibility_doctype.js",
	"Supplier Quotation": "public/js/cost_visibility_doctype.js",
	"Stock Entry": "public/js/stock_entry.js",
	"Material Request Item": "public/js/material_request.js",
	"Purchase Invoice Item": "public/js/purchase_documents.js",
	"Purchase Order Item": "public/js/purchase_order.js",
	"Purchase Receipt Item": "public/js/purchase_documents.js",
	"Quotation Item": "public/js/sales_documents.js",
	"Sales Invoice Item": "public/js/sales_documents.js",
	"Sales Order Item": "public/js/sales_documents.js",
	"Delivery Note Item": "public/js/sales_documents.js",
	"Stock Reconciliation Item": "public/js/inventory_documents.js",
	"Packed Item": "public/js/cost_visibility_child_table.js",
	"Item Default": "public/js/inventory_documents.js",
}

doctype_list_js = {
	"Purchase Receipt": "public/js/purchase_documents_list.js",
	"Purchase Invoice": "public/js/purchase_documents_list.js",
	"Purchase Order": "public/js/purchase_documents_list.js",
	"RetailEdge Cashier Expense": "public/js/retailedge_cashier_expense_list.js",
	"RetailEdge Payment Statement Import": "public/js/payment_statement_import_list.js",
}

doc_events = {
	"Bank Account": {
		"validate": "retailedge.bank_account_policy.validate_bank_account_branch",
	},
	"Sales Invoice": {
		"validate": "retailedge.branch_defaults_application.apply_branch_attribution_and_defaults",
	},
	"POS Invoice": {
		"validate": "retailedge.branch_defaults_application.apply_branch_attribution_and_defaults",
	},
	"Sales Order": {
		"validate": "retailedge.branch_defaults_application.apply_branch_attribution_and_defaults",
	},
	"Delivery Note": {
		"validate": "retailedge.branch_defaults_application.apply_branch_attribution_and_defaults",
	},
	"Payment Entry": {
		"validate": "retailedge.transaction_branch_attribution.apply_transaction_branch_attribution",
		"before_submit": "retailedge.cash_custody.validate_cash_deposit_before_submit",
	},
	"Payment Request": {
		"validate": "retailedge.transaction_branch_attribution.apply_transaction_branch_attribution",
	},
	"Material Request": {
		"validate": "retailedge.branch_defaults_application.apply_branch_attribution_and_defaults",
	},
	"Stock Entry": {
		"validate": "retailedge.branch_defaults_application.apply_branch_attribution_and_defaults",
	},
	"Stock Reconciliation": {
		"validate": "retailedge.transaction_branch_attribution.apply_transaction_branch_attribution",
	},
	"Purchase Order": {
		"validate": "retailedge.branch_defaults_application.apply_branch_attribution_and_defaults",
	},
	"Purchase Receipt": {
		"validate": "retailedge.branch_defaults_application.apply_branch_attribution_and_defaults",
	},
	"Purchase Invoice": {
		"validate": "retailedge.branch_defaults_application.apply_branch_attribution_and_defaults",
	},
	"POS Opening Shift": {
		"validate": "retailedge.transaction_branch_attribution.apply_transaction_branch_attribution",
	},
	"POS Closing Shift": {
		"validate": "retailedge.transaction_branch_attribution.apply_transaction_branch_attribution",
		"on_submit": "retailedge.events.pos_closing_shift.on_pos_closing_shift_submit",
		"after_insert": "retailedge.events.pos_closing_shift.on_pos_closing_shift_save",
	},
	"RetailEdge Cashier Expense": {
		"validate": "retailedge.branch_defaults_application.apply_branch_profile_defaults_to_doc",
	},
	"RetailEdge Daily Sales Audit": {
		"validate": "retailedge.branch_defaults_application.apply_branch_profile_defaults_to_doc",
	},
}

after_migrate = [
	"retailedge.setup_roles.ensure_retailedge_roles",
	"retailedge.transaction_branch_attribution.ensure_transaction_branch_custom_fields",
	"retailedge.cash_custody.ensure_cash_custody_custom_fields",
	"retailedge.sales_invoice_verification_sync.ensure_sales_invoice_verification_custom_fields",
	"retailedge.workspace_sync.sync_retailedge_workspace_layout",
]
boot_session = "retailedge.boot.boot_session"

override_whitelisted_methods = {
	"retailedge.guided_sales_invoice.search_simple_sales_invoice_options": "retailedge.guided_link_search.search_simple_sales_invoice_options",
	"retailedge.guided_purchase_invoice.search_simple_purchase_invoice_options": "retailedge.guided_link_search.search_simple_purchase_invoice_options",
	"retailedge.guided_payment.search_simple_payment_options": "retailedge.guided_link_search.search_simple_payment_options",
	"retailedge.guided_stock_transfer.search_simple_stock_transfer_options": "retailedge.guided_link_search_extended.search_simple_stock_transfer_options",
	"retailedge.guided_stock_adjustment.search_simple_stock_adjustment_options": "retailedge.guided_link_search_extended.search_simple_stock_adjustment_options",
	"retailedge.guided_cash_transfer.search_simple_cash_transfer_options": "retailedge.guided_link_search_extended.search_simple_cash_transfer_options",
	"retailedge.cash_custody.search_cash_deposit_options": "retailedge.guided_link_search_extended.search_cash_deposit_options",
}
