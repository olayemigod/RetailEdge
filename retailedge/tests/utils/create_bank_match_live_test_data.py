
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import frappe
from frappe.utils import add_days, flt, now_datetime, nowdate

PREFIX = "RE-LIVE-BATCH-TEST"
SITE = "posnext.local"

DEFAULT_COUNTS = {
    "exact_payment_entry": 155,
    "pos_payment_row": 85,
    "cash_excluded": 55,
    "duplicate_pressure": 32,
    "amount_mismatch": 32,
    "bank_account_mismatch": 22,
    "broken_candidate": 12,
    "already_handled": 6,
}

SMOKE_COUNTS = {
    "exact_payment_entry": 3,
    "pos_payment_row": 2,
    "cash_excluded": 1,
    "duplicate_pressure": 1,
    "amount_mismatch": 1,
    "bank_account_mismatch": 1,
    "broken_candidate": 1,
    "already_handled": 1,
}


def _require_site(confirm=False):
    if frappe.local.site != SITE:
        frappe.throw(f"This utility only runs on {SITE}. Current site: {frappe.local.site}")
    if not int(confirm or 0):
        frappe.throw("Pass confirm=1 to create or clean up live bank-match sample data.")


def _meta_fields(doctype):
    return {df.fieldname for df in frappe.get_meta(doctype).fields}


def _set_if_field(doc, fieldname, value):
    if fieldname in _meta_fields(doc.doctype):
        setattr(doc, fieldname, value)


def _first_value(doctype, filters=None, fieldname="name"):
    row = frappe.get_all(doctype, filters=filters or {}, fields=[fieldname], limit=1)
    return row[0][fieldname] if row else None


def _company():
    company = _first_value("Company")
    if not company:
        frappe.throw("No Company exists on this site.")
    return company


def _company_abbr(company):
    return frappe.db.get_value("Company", company, "abbr") or company[:3].upper()


def _ensure_account(company, account_name, account_type, root_type, parent_root):
    existing = _first_value("Account", {"company": company, "account_name": account_name, "is_group": 0})
    if existing:
        return existing
    parent = _first_value("Account", {"company": company, "root_type": root_type, "is_group": 1, "account_name": parent_root})
    if not parent:
        parent = _first_value("Account", {"company": company, "root_type": root_type, "is_group": 1})
    doc = frappe.get_doc({
        "doctype": "Account",
        "account_name": account_name,
        "company": company,
        "parent_account": parent,
        "account_type": account_type,
        "root_type": root_type,
        "is_group": 0,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_bank_account(company, ledger_account, label):
    existing = _first_value("Bank Account", {"company": company, "account": ledger_account})
    if existing:
        return existing
    bank_name = f"{PREFIX} Bank"
    if not frappe.db.exists("Bank", bank_name):
        frappe.get_doc({"doctype": "Bank", "bank_name": bank_name}).insert(ignore_permissions=True)
    doc = frappe.get_doc({
        "doctype": "Bank Account",
        "account_name": f"{PREFIX} {label}",
        "bank": bank_name,
        "account": ledger_account,
        "company": company,
        "is_company_account": 1,
    })
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return doc.name


def _ensure_mode_of_payment(name, company, account, mop_type="Bank"):
    if frappe.db.exists("Mode of Payment", name):
        doc = frappe.get_doc("Mode of Payment", name)
    else:
        doc = frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": name, "type": mop_type, "enabled": 1})
        doc.insert(ignore_permissions=True)
    if hasattr(doc, "accounts") and not any(row.company == company for row in doc.accounts):
        doc.append("accounts", {"company": company, "default_account": account})
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_customer(index=0):
    name = f"{PREFIX} Customer {index:03d}"
    if frappe.db.exists("Customer", name):
        return name
    doc = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": name,
        "customer_type": "Individual",
        "customer_group": _first_value("Customer Group", {"is_group": 0}) or "All Customer Groups",
        "territory": _first_value("Territory", {"is_group": 0}) or "All Territories",
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_item(company, income_account):
    code = f"{PREFIX}-SERVICE"
    if frappe.db.exists("Item", code):
        return code
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": code,
        "item_name": f"{PREFIX} Service Item",
        "item_group": _first_value("Item Group", {"is_group": 0}) or "All Item Groups",
        "stock_uom": _first_value("UOM") or "Nos",
        "is_stock_item": 0,
        "is_sales_item": 1,
        "include_item_in_manufacturing": 0,
    })
    if hasattr(doc, "item_defaults"):
        doc.append("item_defaults", {"company": company, "income_account": income_account})
    doc.insert(ignore_permissions=True)
    return doc.name


def _context():
    company = _company()
    income = _first_value("Account", {"company": company, "root_type": "Income", "is_group": 0}) or _ensure_account(company, f"{PREFIX} Sales", "Income Account", "Income", "Income")
    receivable = _first_value("Account", {"company": company, "account_type": "Receivable", "is_group": 0}) or _ensure_account(company, f"{PREFIX} Receivable", "Receivable", "Asset", "Accounts Receivable")
    cost_center = _first_value("Cost Center", {"company": company, "is_group": 0})
    bank_account = _first_value("Account", {"company": company, "account_type": "Bank", "is_group": 0}) or _ensure_account(company, f"{PREFIX} Bank Ledger", "Bank", "Asset", "Bank Accounts")
    alt_bank_account = _ensure_account(company, f"{PREFIX} Alt Bank Ledger", "Bank", "Asset", "Bank Accounts")
    cash_account = _first_value("Account", {"company": company, "account_type": "Cash", "is_group": 0}) or _ensure_account(company, f"{PREFIX} Cash Ledger", "Cash", "Asset", "Cash In Hand")
    bank_transaction_account = _ensure_bank_account(company, bank_account, "Primary")
    alt_bank_transaction_account = _ensure_bank_account(company, alt_bank_account, "Alternate")
    bank_mop = _ensure_mode_of_payment(f"{PREFIX} Bank Transfer", company, bank_account, "Bank")
    card_mop = _ensure_mode_of_payment(f"{PREFIX} POS Card", company, bank_account, "Bank")
    mobile_mop = _ensure_mode_of_payment(f"{PREFIX} Mobile Money", company, bank_account, "Bank")
    cash_mop = _ensure_mode_of_payment(f"{PREFIX} Cash", company, cash_account, "Cash")
    item = _ensure_item(company, income)
    return frappe._dict({
        "company": company,
        "income": income,
        "receivable": receivable,
        "cost_center": cost_center,
        "bank_account": bank_account,
        "alt_bank_account": alt_bank_account,
        "cash_account": cash_account,
        "bank_transaction_account": bank_transaction_account,
        "alt_bank_transaction_account": alt_bank_transaction_account,
        "bank_mop": bank_mop,
        "card_mop": card_mop,
        "mobile_mop": mobile_mop,
        "cash_mop": cash_mop,
        "item": item,
    })


def _submit_doc(doc):
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    doc.submit()
    return doc


def _sales_invoice(ctx, idx, amount, scenario, is_pos=False, mop=None, account=None, reference=None):
    customer = _ensure_customer(idx % 25)
    posting_date = add_days(nowdate(), -(idx % 20))
    doc = frappe.get_doc({
        "doctype": "Sales Invoice",
        "company": ctx.company,
        "customer": customer,
        "posting_date": posting_date,
        "due_date": posting_date,
        "debit_to": ctx.receivable,
        "remarks": f"{PREFIX} {scenario} invoice {idx}",
        "set_posting_time": 1,
        "items": [{
            "item_code": ctx.item,
            "qty": 1,
            "rate": amount,
            "income_account": ctx.income,
            "cost_center": ctx.cost_center,
        }],
    })
    if is_pos:
        doc.is_pos = 1
        doc.update_stock = 0
        doc.append("payments", {
            "mode_of_payment": mop,
            "account": account,
            "amount": amount,
            "reference_no": reference or f"{PREFIX}-{scenario}-{idx:04d}",
        })
        doc.paid_amount = amount
        doc.base_paid_amount = amount
    return _submit_doc(doc)


def _payment_entry(ctx, si, amount, idx, scenario, account=None, mop=None, reference=None):
    ref = reference or f"{PREFIX}-{scenario}-{idx:04d}"
    doc = frappe.get_doc({
        "doctype": "Payment Entry",
        "company": ctx.company,
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": si.customer,
        "posting_date": si.posting_date,
        "paid_from": ctx.receivable,
        "paid_to": account or ctx.bank_account,
        "paid_amount": amount,
        "received_amount": amount,
        "mode_of_payment": mop or ctx.bank_mop,
        "reference_no": ref,
        "reference_date": si.posting_date,
        "remarks": f"{PREFIX} {scenario} payment {idx}",
        "references": [{
            "reference_doctype": "Sales Invoice",
            "reference_name": si.name,
            "allocated_amount": min(amount, flt(si.grand_total)),
            "total_amount": si.grand_total,
            "outstanding_amount": si.outstanding_amount,
        }],
    })
    return _submit_doc(doc)


def _bank_transaction(ctx, amount, idx, scenario, reference, account=None, posting_date=None, description_extra=""):
    doc = frappe.get_doc({"doctype": "Bank Transaction"})
    _set_if_field(doc, "company", ctx.company)
    _set_if_field(doc, "bank_account", account or ctx.bank_transaction_account)
    _set_if_field(doc, "date", posting_date or add_days(nowdate(), -(idx % 20)))
    _set_if_field(doc, "deposit", amount if amount >= 0 else 0)
    _set_if_field(doc, "withdrawal", abs(amount) if amount < 0 else 0)
    _set_if_field(doc, "reference_number", reference)
    _set_if_field(doc, "description", f"{PREFIX} {scenario} bank transaction {idx} {description_extra}")
    _set_if_field(doc, "status", "Pending")
    _set_if_field(doc, "allocated_amount", 0)
    _set_if_field(doc, "unallocated_amount", abs(amount))
    branch = _first_value("RetailEdge Branch") if frappe.db.table_exists("tabRetailEdge Branch") else None
    if branch:
        _set_if_field(doc, "retailedge_branch", branch)
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return doc


def _review(ctx, idx, scenario, bt=None, candidate_doctype=None, candidate_name=None, amount=0, status="Suggested", details=None):
    doc = frappe.get_doc({
        "doctype": "RetailEdge Bank Transaction Match",
        "naming_series": "RE-BTM-.YYYY.-",
        "bank_transaction": bt.name if bt else None,
        "suggested_document_type": candidate_doctype,
        "suggested_document": candidate_name,
        "decision_status": status,
        "review_status": "Pending Review" if status == "Suggested" else status,
        "bank_amount": amount,
        "candidate_amount": amount,
        "match_confidence": "Weak Match",
        "match_score": 50,
        "match_reason": f"{PREFIX} {scenario}",
        "details_json": json.dumps(details or {"source": PREFIX, "scenario": scenario}),
    })
    if scenario.startswith("broken_candidate") or scenario == "confirmed_execution_ready":
        doc.name = f"RE-BTM-LIVE-{frappe.generate_hash(length=10)}"
        doc.flags.ignore_validate = True
        doc.flags.ignore_links = True
        doc.db_insert()
    else:
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return doc


def _create_exact(ctx, idx, scenario="exact_payment_entry", amount=None, bt_account=None, pe_account=None, bt_amount=None, reference=None):
    amount = flt(amount or (1000 + idx * 3))
    ref = reference or f"{PREFIX}-PE-{idx:04d}"
    si = _sales_invoice(ctx, idx, amount, scenario)
    pe = _payment_entry(ctx, si, amount, idx, scenario, account=pe_account or ctx.bank_account, mop=ctx.bank_mop, reference=ref)
    bt = _bank_transaction(ctx, bt_amount if bt_amount is not None else amount, idx, scenario, ref, account=bt_account or ctx.bank_transaction_account, posting_date=si.posting_date, description_extra=pe.name)
    return si, pe, bt


def _create_pos_row(ctx, idx, amount=None):
    amount = flt(amount or (750 + idx * 2))
    ref = f"{PREFIX}-POS-{idx:04d}"
    mop = [ctx.card_mop, ctx.mobile_mop, ctx.bank_mop][idx % 3]
    si = _sales_invoice(ctx, idx, amount, "pos_payment_row", is_pos=True, mop=mop, account=ctx.bank_account, reference=ref)
    bt = _bank_transaction(ctx, amount, idx, "pos_payment_row", ref, account=ctx.bank_transaction_account, posting_date=si.posting_date, description_extra=si.name)
    return si, None, bt


def _create_cash(ctx, idx):
    amount = flt(500 + idx)
    ref = f"{PREFIX}-CASH-{idx:04d}"
    si = _sales_invoice(ctx, idx, amount, "cash_excluded", is_pos=True, mop=ctx.cash_mop, account=ctx.cash_account, reference=ref)
    return si


def _create_all(counts):
    ctx = _context()
    summary = {key: 0 for key in counts}
    created = {"sales_invoices": [], "payment_entries": [], "bank_transactions": [], "reviews": []}
    idx = 1
    for _ in range(counts["exact_payment_entry"]):
        si, pe, bt = _create_exact(ctx, idx)
        created["sales_invoices"].append(si.name); created["payment_entries"].append(pe.name); created["bank_transactions"].append(bt.name)
        summary["exact_payment_entry"] += 1; idx += 1
        if idx % 25 == 0:
            frappe.db.commit()
    for _ in range(counts["pos_payment_row"]):
        si, _, bt = _create_pos_row(ctx, idx)
        created["sales_invoices"].append(si.name); created["bank_transactions"].append(bt.name)
        summary["pos_payment_row"] += 1; idx += 1
        if idx % 25 == 0:
            frappe.db.commit()
    for _ in range(counts["cash_excluded"]):
        si = _create_cash(ctx, idx)
        created["sales_invoices"].append(si.name)
        summary["cash_excluded"] += 1; idx += 1
        if idx % 25 == 0:
            frappe.db.commit()
    for n in range(counts["duplicate_pressure"]):
        si, pe, bt = _create_exact(ctx, idx, scenario="duplicate_pressure", amount=2222, reference=f"{PREFIX}-DUP-{n // 2:04d}")
        created["sales_invoices"].append(si.name); created["payment_entries"].append(pe.name); created["bank_transactions"].append(bt.name)
        summary["duplicate_pressure"] += 1; idx += 1
        if idx % 25 == 0:
            frappe.db.commit()
    for n in range(counts["amount_mismatch"]):
        amount = 1300 + n
        si, pe, bt = _create_exact(ctx, idx, scenario="amount_mismatch", amount=amount, bt_amount=amount + (1 if n % 2 else -1), reference=f"{PREFIX}-MM-{n:04d}")
        created["sales_invoices"].append(si.name); created["payment_entries"].append(pe.name); created["bank_transactions"].append(bt.name)
        summary["amount_mismatch"] += 1; idx += 1
        if idx % 25 == 0:
            frappe.db.commit()
    for n in range(counts["bank_account_mismatch"]):
        si, pe, bt = _create_exact(ctx, idx, scenario="bank_account_mismatch", pe_account=ctx.bank_account, bt_account=ctx.alt_bank_transaction_account, reference=f"{PREFIX}-BAM-{n:04d}")
        created["sales_invoices"].append(si.name); created["payment_entries"].append(pe.name); created["bank_transactions"].append(bt.name)
        summary["bank_account_mismatch"] += 1; idx += 1
        if idx % 25 == 0:
            frappe.db.commit()
    for n in range(counts["broken_candidate"]):
        bt = _bank_transaction(ctx, 999 + n, idx, "broken_candidate", f"{PREFIX}-BROKEN-{n:04d}", account=ctx.bank_transaction_account)
        review = _review(ctx, idx, "broken_candidate_missing_candidate", bt=bt, candidate_doctype=None, candidate_name=None, amount=999 + n, status="Needs Review")
        created["bank_transactions"].append(bt.name); created["reviews"].append(review.name)
        summary["broken_candidate"] += 1; idx += 1
        if idx % 25 == 0:
            frappe.db.commit()
    for n in range(counts["already_handled"]):
        si, pe, bt = _create_exact(ctx, idx, scenario="already_handled", reference=f"{PREFIX}-AH-{n:04d}")
        review = _review(ctx, idx, "already_handled_observability", bt=bt, candidate_doctype="Payment Entry", candidate_name=pe.name, amount=flt(pe.paid_amount), status="Confirmed", details={"source": PREFIX, "scenario": "already_handled"})
        review.execution_status = "Already Handled"
        review.execution_message = f"{PREFIX} observability sample: already handled state for manual UI testing."
        review.execution_reference = f"Bank Transaction {bt.name} -> Payment Entry {pe.name}"
        review.save(ignore_permissions=True)
        created["sales_invoices"].append(si.name); created["payment_entries"].append(pe.name); created["bank_transactions"].append(bt.name); created["reviews"].append(review.name)
        summary["already_handled"] += 1; idx += 1
        if idx % 25 == 0:
            frappe.db.commit()
    return summary, created


def create(confirm=0, scale="full", run_smoke=0):
    _require_site(confirm=confirm)
    counts = SMOKE_COUNTS if scale == "smoke" else DEFAULT_COUNTS
    summary, created = _create_all(counts)
    frappe.db.commit()
    smoke = smoke_checks(prefix=PREFIX, create_batch_job=1) if int(run_smoke or 0) else None
    payload = {
        "prefix": PREFIX,
        "site": frappe.local.site,
        "counts_by_category": summary,
        "created_counts": {key: len(value) for key, value in created.items()},
        "sample_names": {key: value[:10] for key, value in created.items()},
        "smoke_checks": smoke,
        "cleanup_command": "bench --site posnext.local execute retailedge.tests.utils.create_bank_match_live_test_data.cleanup_tagged",
    }
    print(json.dumps(payload, indent=2, default=str))
    return payload



def create_smoke():
    return create(confirm=1, scale="smoke", run_smoke=1)


def create_full():
    return create(confirm=1, scale="full")


def cleanup_tagged():
    return cleanup(prefix=PREFIX, confirm=1)


def _tag_filters(doctype, prefix):
    if doctype == "Sales Invoice":
        return [["remarks", "like", f"%{prefix}%"]]
    if doctype == "Payment Entry":
        return [["remarks", "like", f"%{prefix}%"]]
    if doctype == "Bank Transaction":
        return [["description", "like", f"%{prefix}%"]]
    if doctype == "RetailEdge Bank Transaction Match":
        return [["match_reason", "like", f"%{prefix}%"]]
    if doctype == "RetailEdge Bank Match Batch Job":
        return [["name", "like", f"%{prefix}%"]]
    if doctype == "Customer":
        return [["customer_name", "like", f"%{prefix}%"]]
    if doctype == "Item":
        return [["item_name", "like", f"%{prefix}%"]]
    if doctype == "Mode of Payment":
        return [["name", "like", f"%{prefix}%"]]
    if doctype == "Bank Account":
        return [["account_name", "like", f"%{prefix}%"]]
    if doctype == "Account":
        return [["account_name", "like", f"%{prefix}%"]]
    if doctype == "Bank":
        return [["name", "like", f"%{prefix}%"]]
    return []


def smoke_checks(prefix=PREFIX, create_batch_job=0):
    from retailedge.bank_transaction_matching import get_bank_transaction_matching_rows
    from retailedge.bank_transaction_match_workflow import create_bank_match_reviews_from_suggestions

    rows = get_bank_transaction_matching_rows(filters={"include_confirmed_matches": 1, "show_already_in_review": 1})
    tagged_rows = [row for row in rows if prefix in json.dumps(row, default=str)]
    batch_result = None
    if create_batch_job and len(tagged_rows) >= 201:
        batch_result = create_bank_match_reviews_from_suggestions(rows=tagged_rows[:201])
    payload = {
        "sales_invoices": frappe.db.count("Sales Invoice", _tag_filters("Sales Invoice", prefix)),
        "payment_entries": frappe.db.count("Payment Entry", _tag_filters("Payment Entry", prefix)),
        "bank_transactions": frappe.db.count("Bank Transaction", _tag_filters("Bank Transaction", prefix)),
        "cash_only_records": frappe.db.count("Sales Invoice", [["remarks", "like", f"%{prefix}%cash_excluded%"]]),
        "mismatch_records": frappe.db.count("Bank Transaction", [["description", "like", f"%{prefix}%amount_mismatch%"]]),
        "duplicate_pressure_records": frappe.db.count("Bank Transaction", [["description", "like", f"%{prefix}%duplicate_pressure%"]]),
        "bank_account_mismatch_records": frappe.db.count("Bank Transaction", [["description", "like", f"%{prefix}%bank_account_mismatch%"]]),
        "matching_report_total_rows": len(rows),
        "matching_report_tagged_rows": len(tagged_rows),
        "expected_eligible": frappe.db.count("Bank Transaction", [["description", "like", f"%{prefix}%"], ["description", "not like", "%broken_candidate%"]]),
        "expected_excluded": frappe.db.count("Sales Invoice", [["remarks", "like", f"%{prefix}%cash_excluded%"]]),
        "expected_require_review": (
            frappe.db.count("Bank Transaction", [["description", "like", f"%{prefix}%amount_mismatch%"]])
            + frappe.db.count("Bank Transaction", [["description", "like", f"%{prefix}%bank_account_mismatch%"]])
            + frappe.db.count("RetailEdge Bank Transaction Match", [["match_reason", "like", f"%{prefix}%broken_candidate%"]])
        ),
        "batch_result": batch_result,
    }
    print(json.dumps(payload, indent=2, default=str))
    return payload





def _tagged_payment_entry_suggestion_rows(limit=201):
    rows = []
    transactions = frappe.get_all(
        "Bank Transaction",
        filters=[["description", "like", f"%{PREFIX}%"], ["reference_number", "like", f"%{PREFIX}%"]],
        fields=["name", "date", "deposit", "bank_account", "reference_number", "description"],
        limit=limit * 2,
        order_by="creation asc",
    )
    for tx in transactions:
        pe = frappe.db.get_value(
            "Payment Entry",
            {"reference_no": tx.reference_number, "docstatus": 1},
            ["name", "paid_amount", "posting_date", "party"],
            as_dict=True,
        )
        if not pe:
            continue
        amount = flt(tx.deposit or pe.paid_amount)
        rows.append({
            "bank_transaction": tx.name,
            "transaction_date": tx.date,
            "bank_account": tx.bank_account,
            "bank_amount": amount,
            "suggested_document_type": "Payment Entry",
            "suggested_document": pe.name,
            "candidate_amount": flt(pe.paid_amount),
            "candidate_posting_date": pe.posting_date,
            "candidate_category": "Payment Entry Match",
            "amount_scenario": "Submitted Payment Entry Amount",
            "match_confidence": "Strong Match",
            "match_score": 99,
            "match_reason": f"{PREFIX} light smoke constructed from tagged PE reference",
            "payment_event_source": "Payment Entry",
            "payment_event_amount": flt(pe.paid_amount),
            "party_type": "Customer",
            "party": pe.party,
            "review_queue_status": "Open Suggestions Only",
        })
        if len(rows) >= limit:
            break
    return rows



def create_confirmed_execution_sample():
    _require_site(confirm=1)
    ctx = _context()
    rows = _tagged_payment_entry_suggestion_rows(limit=20)
    for row in rows:
        existing = frappe.db.exists("RetailEdge Bank Transaction Match", {
            "bank_transaction": row["bank_transaction"],
            "suggested_document_type": "Payment Entry",
            "suggested_document": row["suggested_document"],
        })
        if existing:
            continue
        bt = frappe.get_doc("Bank Transaction", row["bank_transaction"])
        review = _review(
            ctx,
            0,
            "confirmed_execution_ready",
            bt=bt,
            candidate_doctype="Payment Entry",
            candidate_name=row["suggested_document"],
            amount=row["bank_amount"],
            status="Confirmed",
            details={"source": PREFIX, "scenario": "confirmed_execution_ready", "payment_event_source": "Payment Entry"},
        )
        frappe.db.commit()
        payload = {"match": review.name, "bank_transaction": row["bank_transaction"], "payment_entry": row["suggested_document"], "prefix": PREFIX}
        print(json.dumps(payload, indent=2, default=str))
        return payload
    frappe.throw("No unused tagged Payment Entry/Bank Transaction pair was available for confirmed execution sample.")


def light_smoke_checks():
    from retailedge.bank_transaction_matching import get_bank_transaction_matching_rows
    from retailedge import api as retailedge_api

    report_rows = get_bank_transaction_matching_rows(filters={"include_confirmed_matches": 1, "show_already_in_review": 1}, limit=5)
    suggestion_rows = _tagged_payment_entry_suggestion_rows(limit=201)
    background_required = retailedge_api.create_bank_match_reviews_from_suggestions(rows=json.dumps(suggestion_rows, default=str), run_background=0)
    batch_job = retailedge_api.create_bank_match_reviews_from_suggestions(rows=json.dumps(suggestion_rows, default=str), run_background=1)
    payload = {
        "sales_invoices": frappe.db.count("Sales Invoice", _tag_filters("Sales Invoice", PREFIX)),
        "payment_entries": frappe.db.count("Payment Entry", _tag_filters("Payment Entry", PREFIX)),
        "bank_transactions": frappe.db.count("Bank Transaction", _tag_filters("Bank Transaction", PREFIX)),
        "cash_only_records": frappe.db.count("Sales Invoice", [["remarks", "like", f"%{PREFIX}%cash_excluded%"]]),
        "mismatch_records": frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%amount_mismatch%"]]),
        "duplicate_pressure_records": frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%duplicate_pressure%"]]),
        "bank_account_mismatch_records": frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%bank_account_mismatch%"]]),
        "report_loaded": True,
        "report_limited_rows": len(report_rows),
        "constructed_suggestion_rows": len(suggestion_rows),
        "constructed_rows_exceed_200": len(suggestion_rows) > 200,
        "expected_eligible": frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%"], ["description", "not like", "%broken_candidate%"]]),
        "expected_excluded": frappe.db.count("Sales Invoice", [["remarks", "like", f"%{PREFIX}%cash_excluded%"]]),
        "expected_require_review": (
            frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%amount_mismatch%"]])
            + frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%bank_account_mismatch%"]])
            + frappe.db.count("RetailEdge Bank Transaction Match", [["match_reason", "like", f"%{PREFIX}%broken_candidate%"]])
        ),
        "background_required": background_required,
        "batch_job": batch_job,
        "batch_job_rows": frappe.db.count("RetailEdge Bank Match Batch Job Row", {"parent": batch_job.get("batch_job")}) if batch_job and batch_job.get("batch_job") else 0,
    }
    frappe.db.commit()
    print(json.dumps(payload, indent=2, default=str))
    return payload


def bounded_smoke_checks():
    from retailedge.bank_transaction_matching import get_bank_transaction_matching_rows
    from retailedge.bank_transaction_match_workflow import create_bank_match_reviews_from_suggestions

    rows = get_bank_transaction_matching_rows(filters={"include_confirmed_matches": 1, "show_already_in_review": 1}, limit=260)
    tagged_rows = [row for row in rows if PREFIX in json.dumps(row, default=str)]
    batch_result = create_bank_match_reviews_from_suggestions(rows=tagged_rows[:201]) if len(tagged_rows) >= 201 else None
    payload = {
        "sales_invoices": frappe.db.count("Sales Invoice", _tag_filters("Sales Invoice", PREFIX)),
        "payment_entries": frappe.db.count("Payment Entry", _tag_filters("Payment Entry", PREFIX)),
        "bank_transactions": frappe.db.count("Bank Transaction", _tag_filters("Bank Transaction", PREFIX)),
        "cash_only_records": frappe.db.count("Sales Invoice", [["remarks", "like", f"%{PREFIX}%cash_excluded%"]]),
        "mismatch_records": frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%amount_mismatch%"]]),
        "duplicate_pressure_records": frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%duplicate_pressure%"]]),
        "bank_account_mismatch_records": frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%bank_account_mismatch%"]]),
        "report_loaded": True,
        "report_limited_rows": len(rows),
        "report_limited_tagged_rows": len(tagged_rows),
        "report_returns_more_than_200": len(tagged_rows) > 200,
        "expected_eligible": frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%"], ["description", "not like", "%broken_candidate%"]]),
        "expected_excluded": frappe.db.count("Sales Invoice", [["remarks", "like", f"%{PREFIX}%cash_excluded%"]]),
        "expected_require_review": (
            frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%amount_mismatch%"]])
            + frappe.db.count("Bank Transaction", [["description", "like", f"%{PREFIX}%bank_account_mismatch%"]])
            + frappe.db.count("RetailEdge Bank Transaction Match", [["match_reason", "like", f"%{PREFIX}%broken_candidate%"]])
        ),
        "batch_result": batch_result,
        "batch_jobs_created": frappe.db.count("RetailEdge Bank Match Batch Job"),
    }
    frappe.db.commit()
    print(json.dumps(payload, indent=2, default=str))
    return payload


def smoke_checks_with_batch():
    return smoke_checks(prefix=PREFIX, create_batch_job=1)


def cleanup(prefix=PREFIX, confirm=0):
    _require_site(confirm=confirm)
    deleted = {}
    for doctype in [
        "RetailEdge Bank Match Batch Job",
        "RetailEdge Bank Transaction Match",
        "Bank Transaction",
        "Payment Entry",
        "Sales Invoice",
        "Mode of Payment",
        "Bank Account",
        "Item",
        "Customer",
        "Account",
        "Bank",
    ]:
        names = frappe.get_all(doctype, filters=_tag_filters(doctype, prefix), pluck="name")
        if doctype == "RetailEdge Bank Match Batch Job":
            tagged_parents = frappe.get_all(
                "RetailEdge Bank Match Batch Job Row",
                filters=[["input_payload_json", "like", f"%{prefix}%"]],
                pluck="parent",
            )
            names = sorted(set(names or []) | set(tagged_parents or []))
        deleted[doctype] = []
        for name in names:
            try:
                doc = frappe.get_doc(doctype, name)
                if getattr(doc, "docstatus", 0) == 1:
                    doc.cancel()
                frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
                deleted[doctype].append(name)
            except Exception as exc:
                deleted[doctype].append(f"FAILED {name}: {exc}")
    frappe.db.commit()
    print(json.dumps({"prefix": prefix, "deleted": deleted}, indent=2, default=str))
    return deleted
