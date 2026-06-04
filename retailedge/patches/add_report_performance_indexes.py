from __future__ import annotations

import frappe


CANDIDATE_INDEXES = [
	("RetailEdge Bank Transaction Match", ["bank_transaction"], "retailedge_btm_bank_transaction_idx"),
	("RetailEdge Bank Transaction Match", ["review_status"], "retailedge_btm_review_status_idx"),
	("RetailEdge Bank Transaction Match", ["action_status"], "retailedge_btm_action_status_idx"),
	("RetailEdge Bank Transaction Match", ["suggested_document_type", "suggested_document"], "retailedge_btm_candidate_idx"),
	("Sales Invoice", ["posting_date"], "retailedge_si_posting_date_idx"),
	("Sales Invoice", ["company"], "retailedge_si_company_idx"),
	("Sales Invoice", ["docstatus"], "retailedge_si_docstatus_idx"),
	("Sales Invoice", ["retailedge_branch"], "retailedge_si_branch_idx"),
	("Sales Invoice Payment", ["parent"], "retailedge_sip_parent_idx"),
	("Sales Invoice Payment", ["mode_of_payment"], "retailedge_sip_mode_idx"),
	("Sales Invoice Payment", ["account"], "retailedge_sip_account_idx"),
	("Payment Entry", ["posting_date"], "retailedge_pe_posting_date_idx"),
	("Payment Entry", ["docstatus"], "retailedge_pe_docstatus_idx"),
	("Payment Entry", ["paid_to"], "retailedge_pe_paid_to_idx"),
	("Payment Entry", ["paid_from"], "retailedge_pe_paid_from_idx"),
	("Payment Entry", ["mode_of_payment"], "retailedge_pe_mode_idx"),
	("Payment Entry", ["reference_no"], "retailedge_pe_reference_idx"),
	("Bank Transaction", ["date"], "retailedge_bt_date_idx"),
	("Bank Transaction", ["transaction_date"], "retailedge_bt_transaction_date_idx"),
	("Bank Transaction", ["posting_date"], "retailedge_bt_posting_date_idx"),
	("Bank Transaction", ["bank_account"], "retailedge_bt_bank_account_idx"),
	("Bank Transaction", ["status"], "retailedge_bt_status_idx"),
	("Bank Transaction", ["company"], "retailedge_bt_company_idx"),
]



def execute():
	for doctype, columns, index_name in CANDIDATE_INDEXES:
		_add_index_if_possible(doctype, columns, index_name)



def _add_index_if_possible(doctype: str, columns: list[str], index_name: str):
	table = f"tab{doctype}"
	if not frappe.db.table_exists(table):
		return
	if any(not frappe.db.has_column(table, column) for column in columns):
		return
	existing = frappe.db.sql(f"SHOW INDEX FROM `{table}` WHERE Key_name = %s", index_name)
	if existing:
		return
	columns_sql = ", ".join(f"`{column}`" for column in columns)
	frappe.db.sql(f"ALTER TABLE `{table}` ADD INDEX `{index_name}` ({columns_sql})")
