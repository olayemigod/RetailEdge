from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt


RETAILEDGE_SETTINGS_DOCTYPE = "RetailEdge Settings"
EXPENSE_CATEGORY_DOCTYPE = "RetailEdge Expense Category"
BRANCH_PROFILE_DOCTYPE = "RetailEdge Branch Profile"
STATEMENT_MAPPING_DOCTYPE = "RetailEdge Statement Mapping Template"

SETTINGS_MANAGED_FIELDS = (
    "enable_posting_date_control",
    "allow_pos_posting_date_override",
    "hide_cost_price_for_selected_roles",
    "enable_sales_payment_audit",
    "enable_cashier_expense_workflow",
    "require_cashier_expense_attachment",
    "include_cashier_expenses_in_variance_report",
    "require_open_shift_for_cashier_expense",
    "allow_cashier_expense_date_edit",
    "include_draft_cashier_expenses_in_cash_check",
    "include_rejected_cashier_expenses_in_cash_check",
    "allow_cashier_expense_without_cash_account",
    "include_draft_cashier_expenses_in_daily_audit",
    "include_submitted_cashier_expenses_in_daily_audit",
    "include_pending_ledger_cashier_expenses_in_daily_audit",
    "include_rejected_cashier_expenses_in_daily_audit",
    "exclude_cancelled_cashier_expenses_from_daily_audit",
    "enable_daily_sales_audit",
    "require_pos_closing_shift_for_daily_audit",
    "include_cashier_expenses_in_daily_sales_audit_preview",
    "include_rejected_cashier_expenses_in_daily_sales_audit_preview",
    "daily_sales_audit_variance_tolerance",
    "allow_self_review_daily_sales_audit",
    "enable_branch_default_application",
    "apply_branch_default_warehouse",
    "apply_branch_default_cost_center",
    "apply_branch_default_accounts",
    "apply_branch_default_pos_profile",
)

SETTINGS_ROLE_TABLES = (
    "posting_date_allowed_roles",
    "cost_price_hidden_roles",
    "daily_sales_audit_reviewer_roles",
)

EXPENSE_CATEGORY_FIELDS = (
    "category_name",
    "category_code",
    "company",
    "expense_account",
    "default_cost_center",
    "is_active",
    "description",
    "notes",
)

BRANCH_PROFILE_FIELDS = (
    "profile_name",
    "enabled",
    "company",
    "branch",
    "is_default_for_company",
    "default_pos_profile",
    "default_pos_opening_cash_account",
    "default_cash_mode_of_payment",
    "default_warehouse",
    "default_source_warehouse",
    "default_target_warehouse",
    "default_returns_warehouse",
    "default_cost_center",
    "default_sales_cost_center",
    "default_expense_cost_center",
    "default_cash_account",
    "default_bank_account",
    "default_card_pos_account",
    "default_mobile_money_account",
    "enable_cashier_expense_control",
    "enable_daily_sales_audit",
    "enable_transaction_branch_attribution",
    "require_pos_closing_shift_for_audit",
    "variance_tolerance",
    "notes",
)

BRANCH_PROFILE_USER_TABLES = {
    "default_cashiers": "Cashier",
    "default_managers": "Manager",
    "default_auditors": "Auditor",
}

STATEMENT_MAPPING_FIELDS = (
    "template_name",
    "enabled",
    "company",
    "statement_type",
    "payment_category",
    "bank_or_provider_name",
    "date_column",
    "value_date_column",
    "reference_column",
    "narration_column",
    "debit_column",
    "credit_column",
    "amount_column",
    "balance_column",
    "account_column",
    "party_column",
    "channel_column",
    "branch_column",
    "currency_column",
    "date_format",
    "amount_format",
    "debit_credit_mode",
    "default_account",
    "reference_keywords",
    "narration_keywords",
    "notes",
)

SETUP_RESOURCES = (
    {
        "key": "settings",
        "label": "RetailEdge Settings",
        "description": "Configure RetailEdge business rules and operating defaults.",
        "doctype": RETAILEDGE_SETTINGS_DOCTYPE,
        "singleton": True,
        "icon": "settings",
        "managed_in_page": True,
    },
    {
        "key": "branches",
        "label": "Branch Profiles",
        "description": "Configure branch-level operating and accounting defaults.",
        "doctype": BRANCH_PROFILE_DOCTYPE,
        "singleton": False,
        "icon": "map-pin",
        "managed_in_page": True,
    },
    {
        "key": "expense_categories",
        "label": "Expense Categories",
        "description": "Maintain the categories used for day-to-day business expenses.",
        "doctype": EXPENSE_CATEGORY_DOCTYPE,
        "singleton": False,
        "icon": "file-text",
        "managed_in_page": True,
    },
    {
        "key": "statement_mappings",
        "label": "Bank Statement Mapping",
        "description": "Maintain reusable bank statement import mapping templates.",
        "doctype": STATEMENT_MAPPING_DOCTYPE,
        "singleton": False,
        "icon": "repeat",
        "managed_in_page": True,
    },
)


def _has_read_permission(doctype: str, doc=None) -> bool:
    return bool(frappe.has_permission(doctype, ptype="read", doc=doc))


def _has_create_permission(doctype: str) -> bool:
    return bool(frappe.has_permission(doctype, ptype="create"))


def _has_write_permission(doc) -> bool:
    return bool(frappe.has_permission(doc.doctype, ptype="write", doc=doc))


def _permission_filtered_count(doctype: str) -> int:
    return len(frappe.get_list(doctype, fields=["name"], limit_page_length=0))


def _parse_payload(values) -> dict:
    return frappe.parse_json(values) if isinstance(values, str) else dict(values or {})


def _normalize_roles(rows) -> list[dict]:
    parsed = frappe.parse_json(rows) if isinstance(rows, str) else (rows or [])
    normalized = []
    seen = set()
    for row in parsed:
        role = (row.get("role") or "").strip()
        if not role:
            continue
        if role in seen:
            frappe.throw(_("A role cannot appear more than once in the same setting."))
        if not frappe.db.exists("Role", role):
            frappe.throw(_("Role {0} does not exist.").format(role))
        seen.add(role)
        normalized.append({"role": role})
    return normalized


@frappe.whitelist()
def get_setup_context() -> dict:
    resources = []
    for definition in SETUP_RESOURCES:
        doctype = definition["doctype"]
        if not frappe.db.exists("DocType", doctype) or not _has_read_permission(doctype):
            continue
        resource = dict(definition)
        resource["can_create"] = _has_create_permission(doctype)
        resource["count"] = None if definition["singleton"] else _permission_filtered_count(doctype)
        resources.append(resource)
    return {"resources": resources, "user": frappe.session.user}


@frappe.whitelist()
def get_retailedge_settings() -> dict:
    if not _has_read_permission(RETAILEDGE_SETTINGS_DOCTYPE):
        frappe.throw(_("You do not have permission to view RetailEdge Settings."), frappe.PermissionError)
    doc = frappe.get_single(RETAILEDGE_SETTINGS_DOCTYPE)
    if not _has_read_permission(RETAILEDGE_SETTINGS_DOCTYPE, doc=doc):
        frappe.throw(_("You do not have permission to view RetailEdge Settings."), frappe.PermissionError)
    values = {fieldname: doc.get(fieldname) for fieldname in SETTINGS_MANAGED_FIELDS}
    for table_field in SETTINGS_ROLE_TABLES:
        values[table_field] = [{"role": row.role} for row in doc.get(table_field) or []]
    return {"values": values, "can_write": _has_write_permission(doc)}


@frappe.whitelist(methods=["POST"])
def save_retailedge_settings(values) -> dict:
    payload = _parse_payload(values)
    doc = frappe.get_single(RETAILEDGE_SETTINGS_DOCTYPE)
    if not _has_write_permission(doc):
        frappe.throw(_("You do not have permission to edit RetailEdge Settings."), frappe.PermissionError)
    currency_fields = {"daily_sales_audit_variance_tolerance"}
    for fieldname in SETTINGS_MANAGED_FIELDS:
        if fieldname not in payload:
            continue
        value = flt(payload.get(fieldname)) if fieldname in currency_fields else cint(payload.get(fieldname))
        doc.set(fieldname, value)
    for table_field in SETTINGS_ROLE_TABLES:
        if table_field in payload:
            doc.set(table_field, _normalize_roles(payload.get(table_field)))
    doc.save()
    return {"saved": True}


@frappe.whitelist()
def get_expense_categories() -> dict:
    if not _has_read_permission(EXPENSE_CATEGORY_DOCTYPE):
        frappe.throw(_("You do not have permission to view Expense Categories."), frappe.PermissionError)
    rows = frappe.get_list(EXPENSE_CATEGORY_DOCTYPE, fields=["name", *EXPENSE_CATEGORY_FIELDS, "modified"], order_by="is_active desc, category_name asc", limit_page_length=200)
    for row in rows:
        doc = frappe.get_doc(EXPENSE_CATEGORY_DOCTYPE, row.name)
        row["can_write"] = _has_write_permission(doc)
    return {"rows": rows, "can_create": _has_create_permission(EXPENSE_CATEGORY_DOCTYPE)}


@frappe.whitelist(methods=["POST"])
def save_expense_category(values, name: str | None = None) -> dict:
    payload = _parse_payload(values)
    name = (name or "").strip() or None
    if name:
        doc = frappe.get_doc(EXPENSE_CATEGORY_DOCTYPE, name)
        if not _has_write_permission(doc):
            frappe.throw(_("You do not have permission to edit this Expense Category."), frappe.PermissionError)
    else:
        if not _has_create_permission(EXPENSE_CATEGORY_DOCTYPE):
            frappe.throw(_("You do not have permission to create Expense Categories."), frappe.PermissionError)
        category_name = (payload.get("category_name") or "").strip()
        if not category_name:
            frappe.throw(_("Category Name is required."))
        doc = frappe.new_doc(EXPENSE_CATEGORY_DOCTYPE)
        doc.category_name = category_name
    for fieldname in EXPENSE_CATEGORY_FIELDS:
        if fieldname == "category_name" and name:
            continue
        if fieldname not in payload:
            continue
        value = payload.get(fieldname)
        if fieldname == "is_active":
            value = cint(value)
        elif isinstance(value, str):
            value = value.strip()
        doc.set(fieldname, value)
    doc.insert() if doc.is_new() else doc.save()
    return {"name": doc.name, "category_name": doc.category_name}


@frappe.whitelist()
def get_branch_profiles() -> dict:
    if not _has_read_permission(BRANCH_PROFILE_DOCTYPE):
        frappe.throw(_("You do not have permission to view Branch Profiles."), frappe.PermissionError)
    rows = frappe.get_list(BRANCH_PROFILE_DOCTYPE, fields=["name", *BRANCH_PROFILE_FIELDS, "modified"], order_by="enabled desc, is_default_for_company desc, company asc, branch asc", limit_page_length=200)
    for row in rows:
        doc = frappe.get_doc(BRANCH_PROFILE_DOCTYPE, row.name)
        row["can_write"] = _has_write_permission(doc)
    return {"rows": rows, "can_create": _has_create_permission(BRANCH_PROFILE_DOCTYPE)}


@frappe.whitelist()
def get_branch_profile_details(name: str) -> dict:
    if not _has_read_permission(BRANCH_PROFILE_DOCTYPE):
        frappe.throw(_("You do not have permission to view Branch Profiles."), frappe.PermissionError)
    doc = frappe.get_doc(BRANCH_PROFILE_DOCTYPE, name)
    if not _has_read_permission(BRANCH_PROFILE_DOCTYPE, doc=doc):
        frappe.throw(_("You do not have permission to view this Branch Profile."), frappe.PermissionError)
    values = {"name": doc.name, **{fieldname: doc.get(fieldname) for fieldname in BRANCH_PROFILE_FIELDS}}
    for table_field in BRANCH_PROFILE_USER_TABLES:
        values[table_field] = [
            {"user": row.user, "is_default": cint(row.is_default), "notes": row.notes or ""}
            for row in doc.get(table_field) or []
        ]
    values["can_write"] = _has_write_permission(doc)
    return values


def _normalize_operational_users(rows, role_type: str) -> list[dict]:
    parsed = frappe.parse_json(rows) if isinstance(rows, str) else (rows or [])
    normalized = []
    seen = set()
    for row in parsed:
        user = (row.get("user") or "").strip()
        if not user:
            continue
        if user in seen:
            frappe.throw(_("A user cannot appear more than once in the same operational role."))
        enabled = frappe.db.get_value("User", user, "enabled")
        if enabled is None:
            frappe.throw(_("User {0} does not exist.").format(user))
        if not cint(enabled):
            frappe.throw(_("User {0} is disabled and cannot be assigned.").format(user))
        seen.add(user)
        normalized.append({
            "user": user,
            "role_type": role_type,
            "is_default": cint(row.get("is_default")),
            "notes": (row.get("notes") or "").strip(),
        })
    return normalized


@frappe.whitelist(methods=["POST"])
def save_branch_profile(values, name: str | None = None) -> dict:
    payload = _parse_payload(values)
    name = (name or "").strip() or None
    if name:
        doc = frappe.get_doc(BRANCH_PROFILE_DOCTYPE, name)
        if not _has_write_permission(doc):
            frappe.throw(_("You do not have permission to edit this Branch Profile."), frappe.PermissionError)
    else:
        if not _has_create_permission(BRANCH_PROFILE_DOCTYPE):
            frappe.throw(_("You do not have permission to create Branch Profiles."), frappe.PermissionError)
        profile_name = (payload.get("profile_name") or "").strip()
        if not profile_name:
            frappe.throw(_("Profile Name is required."))
        doc = frappe.new_doc(BRANCH_PROFILE_DOCTYPE)
        doc.profile_name = profile_name
    check_fields = {"enabled", "is_default_for_company", "enable_cashier_expense_control", "enable_daily_sales_audit", "enable_transaction_branch_attribution", "require_pos_closing_shift_for_audit"}
    for fieldname in BRANCH_PROFILE_FIELDS:
        if fieldname == "profile_name" and name:
            continue
        if fieldname not in payload:
            continue
        value = payload.get(fieldname)
        if fieldname in check_fields:
            value = cint(value)
        elif isinstance(value, str):
            value = value.strip()
        doc.set(fieldname, value)
    for table_field, role_type in BRANCH_PROFILE_USER_TABLES.items():
        if table_field in payload:
            doc.set(table_field, _normalize_operational_users(payload.get(table_field), role_type))
    if not doc.company:
        frappe.throw(_("Company is required."))
    if not doc.branch:
        frappe.throw(_("Branch is required."))
    doc.insert() if doc.is_new() else doc.save()
    return {"name": doc.name, "profile_name": doc.profile_name, "company": doc.company, "branch": doc.branch}


@frappe.whitelist()
def get_statement_mappings() -> dict:
    if not _has_read_permission(STATEMENT_MAPPING_DOCTYPE):
        frappe.throw(_("You do not have permission to view Bank Statement Mapping templates."), frappe.PermissionError)
    rows = frappe.get_list(STATEMENT_MAPPING_DOCTYPE, fields=["name", *STATEMENT_MAPPING_FIELDS, "modified"], order_by="enabled desc, template_name asc", limit_page_length=200)
    for row in rows:
        doc = frappe.get_doc(STATEMENT_MAPPING_DOCTYPE, row.name)
        row["can_write"] = _has_write_permission(doc)
    return {"rows": rows, "can_create": _has_create_permission(STATEMENT_MAPPING_DOCTYPE)}


def _validate_statement_mapping(doc) -> None:
    if not doc.template_name:
        frappe.throw(_("Template Name is required."))
    if doc.statement_type not in {"Bank Transfer", "Card / POS Settlement", "Mobile Money", "Other"}:
        frappe.throw(_("Select a valid Statement Type."))
    if doc.payment_category not in {"Bank Transfer", "Card / POS", "Mobile Money", "Other"}:
        frappe.throw(_("Select a valid Payment Category."))
    if doc.debit_credit_mode and doc.debit_credit_mode not in {"Separate Debit/Credit Columns", "Signed Amount Column", "Credit Only Amount Column"}:
        frappe.throw(_("Select a valid Debit Credit Mode."))
    if not doc.default_account:
        return
    account = frappe.db.get_value("Account", doc.default_account, ["company", "is_group", "disabled"], as_dict=True)
    if not account:
        frappe.throw(_("Default Account does not exist."))
    if cint(account.is_group) or cint(account.disabled):
        frappe.throw(_("Default Account must be an enabled ledger account."))
    if doc.company and account.company != doc.company:
        frappe.throw(_("Default Account must belong to the selected Company."))


@frappe.whitelist(methods=["POST"])
def save_statement_mapping(values, name: str | None = None) -> dict:
    payload = _parse_payload(values)
    name = (name or "").strip() or None
    if name:
        doc = frappe.get_doc(STATEMENT_MAPPING_DOCTYPE, name)
        if not _has_write_permission(doc):
            frappe.throw(_("You do not have permission to edit this mapping template."), frappe.PermissionError)
    else:
        if not _has_create_permission(STATEMENT_MAPPING_DOCTYPE):
            frappe.throw(_("You do not have permission to create mapping templates."), frappe.PermissionError)
        template_name = (payload.get("template_name") or "").strip()
        if not template_name:
            frappe.throw(_("Template Name is required."))
        doc = frappe.new_doc(STATEMENT_MAPPING_DOCTYPE)
        doc.template_name = template_name
    for fieldname in STATEMENT_MAPPING_FIELDS:
        if fieldname == "template_name" and name:
            continue
        if fieldname not in payload:
            continue
        value = payload.get(fieldname)
        if fieldname == "enabled":
            value = cint(value)
        elif isinstance(value, str):
            value = value.strip()
        doc.set(fieldname, value)
    _validate_statement_mapping(doc)
    doc.insert() if doc.is_new() else doc.save()
    return {"name": doc.name, "template_name": doc.template_name}
