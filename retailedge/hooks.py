app_name = "retailedge"
app_title = "RetailEdge"
app_publisher = "ProcessEdge Solutions"
app_description = "Retail operations, POS control, sales audit, payment verification, branch workflows, and retail intelligence for ERPNext/POSNext."
app_email = "support@processedge.com.ng"
app_license = "MIT"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "retailedge",
# 		"logo": "/assets/retailedge/logo.png",
# 		"title": "RetailEdge",
# 		"route": "/retailedge",
# 		"has_permission": "retailedge.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/retailedge/css/retailedge.css"
app_include_js = "/assets/retailedge/js/retailedge.js"

# include js, css files in header of web template
# web_include_css = "/assets/retailedge/css/retailedge.css"
# web_include_js = "/assets/retailedge/js/retailedge.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "retailedge/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
page_js = {"query-report": "public/js/query_report.js"}

# include js in doctype views
doctype_js = {
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
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "retailedge/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "retailedge.utils.jinja_methods",
# 	"filters": "retailedge.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "retailedge.install.before_install"
# after_install = "retailedge.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "retailedge.uninstall.before_uninstall"
# after_uninstall = "retailedge.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "retailedge.utils.before_app_install"
# after_app_install = "retailedge.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "retailedge.utils.before_app_uninstall"
# after_app_uninstall = "retailedge.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "retailedge.notifications.get_notification_config"

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }
doc_events = {
	"Sales Invoice": {
		"validate": "retailedge.events.sales_invoice.validate_sales_invoice",
	},
	"POS Closing Shift": {
		"on_submit": "retailedge.events.pos_closing_shift.on_pos_closing_shift_submit",
		"after_insert": "retailedge.events.pos_closing_shift.on_pos_closing_shift_save",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"retailedge.tasks.all"
# 	],
# 	"daily": [
# 		"retailedge.tasks.daily"
# 	],
# 	"hourly": [
# 		"retailedge.tasks.hourly"
# 	],
# 	"weekly": [
# 		"retailedge.tasks.weekly"
# 	],
# 	"monthly": [
# 		"retailedge.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "retailedge.install.before_tests"
after_migrate = ["retailedge.setup_roles.ensure_retailedge_roles"]
boot_session = "retailedge.boot.boot_session"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "retailedge.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "retailedge.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "retailedge.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["retailedge.utils.before_request"]
# after_request = ["retailedge.utils.after_request"]

# Job Events
# ----------
# before_job = ["retailedge.utils.before_job"]
# after_job = ["retailedge.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"retailedge.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
