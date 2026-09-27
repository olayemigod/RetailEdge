from __future__ import annotations

import frappe


SETTINGS_DOCTYPE = "RetailEdge Settings"
ASSIGNMENT_CHILD_TABLE = "RetailEdge Branch Assignment Price List"
ASSIGNMENT_PARENTTYPE = "RetailEdge Branch Assignment"

LEGACY_SELLING_POLICY = "Party > POS > Branch > Assigned Choice"
LEGACY_BUYING_POLICY = "Party > Branch > Assigned Choice"

LEGACY_POLICY_SOURCES = {
	"selling": {
		"Party > POS > Branch > Assigned Choice": ("party", "pos", "branch", "assigned_choice"),
		"Party > Branch > POS > Assigned Choice": ("party", "branch", "pos", "assigned_choice"),
		"POS > Party > Branch > Assigned Choice": ("pos", "party", "branch", "assigned_choice"),
		"Branch > Party > POS > Assigned Choice": ("branch", "party", "pos", "assigned_choice"),
		"Assigned Choice > Party > POS > Branch": ("assigned_choice", "party", "pos", "branch"),
	},
	"buying": {
		"Party > Branch > Assigned Choice": ("party", "branch", "assigned_choice"),
		"Branch > Party > Assigned Choice": ("branch", "party", "assigned_choice"),
		"Assigned Choice > Party > Branch": ("assigned_choice", "party", "branch"),
	},
}

SOURCE_TRANSLATION = {
	"party": ("party_default",),
	"pos": ("pos_profile",),
	"branch": ("branch_default",),
	# The V1 assigned choice could fall back to an assigned user default or
	# default User Permission. Explicit branch-assigned switching is preserved
	# separately by the V2 switching controls.
	"assigned_choice": ("user_default", "user_permission"),
}

FINAL_FALLBACKS = ("erpnext_default", "standard_price_list")


def execute():
	_migrate_branch_assignment_parentfield()
	_migrate_legacy_price_list_settings()


def _migrate_branch_assignment_parentfield() -> None:
	if not _table_exists(ASSIGNMENT_CHILD_TABLE):
		return

	frappe.db.sql(
		f"""
		UPDATE `tab{ASSIGNMENT_CHILD_TABLE}`
		SET parentfield = 'allowed_price_lists'
		WHERE parenttype = %s
		  AND parentfield = 'price_lists'
		""",
		(ASSIGNMENT_PARENTTYPE,),
	)


def _migrate_legacy_price_list_settings() -> None:
	# This is intentionally a pre-model-sync migration. On an upgrade from the
	# V1 pricing contract, the legacy field exists in persisted DocField rows
	# while the V2 field does not. Fresh installs have neither persisted schema
	# at this point, and a rerun after model sync has both, so both cases no-op.
	if not _persisted_docfield_exists(SETTINGS_DOCTYPE, "allow_price_list_switch"):
		return
	if _persisted_docfield_exists(SETTINGS_DOCTYPE, "enable_assigned_price_list_switching"):
		return
	if not _table_exists("Singles"):
		return

	selling_policy = str(
		_raw_single_value("selling_price_list_policy") or LEGACY_SELLING_POLICY
	).strip()
	buying_policy = str(
		_raw_single_value("buying_price_list_policy") or LEGACY_BUYING_POLICY
	).strip()
	allow_switch = _as_bool(_raw_single_value("allow_price_list_switch"), default=True)

	_raw_set_single_value(
		"selling_price_list_precedence",
		"\n".join(_translate_policy("selling", selling_policy)),
	)
	_raw_set_single_value(
		"buying_price_list_precedence",
		"\n".join(_translate_policy("buying", buying_policy)),
	)
	_raw_set_single_value("enable_assigned_price_list_switching", "1" if allow_switch else "0")

	# V1 used one global switch. Preserve that merchant decision across every
	# V2 default-source gate instead of silently re-enabling or narrowing it.
	switch_value = "1" if allow_switch else "0"
	for fieldname in (
		"allow_price_list_switch_from_party_default",
		"allow_price_list_switch_from_pos_default",
		"allow_price_list_switch_from_branch_default",
		"allow_price_list_switch_from_user_default",
		"allow_price_list_switch_from_system_default",
	):
		_raw_set_single_value(fieldname, switch_value)


def _translate_policy(mode: str, policy_name: str) -> list[str]:
	orders = LEGACY_POLICY_SOURCES[mode]
	legacy = orders.get(policy_name)
	if legacy is None:
		legacy = orders[
			LEGACY_SELLING_POLICY if mode == "selling" else LEGACY_BUYING_POLICY
		]

	result: list[str] = []
	for source in legacy:
		for translated in SOURCE_TRANSLATION[source]:
			if translated not in result:
				result.append(translated)
	for source in FINAL_FALLBACKS:
		if source not in result:
			result.append(source)
	return result


def _as_bool(value, *, default: bool) -> bool:
	if value in (None, ""):
		return default
	return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _table_exists(doctype: str) -> bool:
	return bool(frappe.db.table_exists(doctype, cached=False))


def _persisted_docfield_exists(parent: str, fieldname: str) -> bool:
	if not _table_exists("DocField"):
		return False
	rows = frappe.db.sql(
		"""
		SELECT 1
		FROM `tabDocField`
		WHERE parent = %s AND fieldname = %s
		LIMIT 1
		""",
		(parent, fieldname),
	)
	return bool(rows)


def _raw_single_value(fieldname: str):
	rows = frappe.db.sql(
		"""
		SELECT value
		FROM `tabSingles`
		WHERE doctype = %s AND field = %s
		LIMIT 1
		""",
		(SETTINGS_DOCTYPE, fieldname),
	)
	return rows[0][0] if rows else None


def _raw_set_single_value(fieldname: str, value: str) -> None:
	rows = frappe.db.sql(
		"""
		SELECT 1
		FROM `tabSingles`
		WHERE doctype = %s AND field = %s
		LIMIT 1
		""",
		(SETTINGS_DOCTYPE, fieldname),
	)
	if rows:
		frappe.db.sql(
			"""
			UPDATE `tabSingles`
			SET value = %s
			WHERE doctype = %s AND field = %s
			""",
			(value, SETTINGS_DOCTYPE, fieldname),
		)
		return
	frappe.db.sql(
		"""
		INSERT INTO `tabSingles` (doctype, field, value)
		VALUES (%s, %s, %s)
		""",
		(SETTINGS_DOCTYPE, fieldname, value),
	)
