from __future__ import annotations

import frappe

from retailedge.company_profile import PROFILE_DOCTYPE, ensure_public_profile_logo


def execute() -> None:
	"""Make existing Company Profile logos readable by every authenticated product role.

	Only branding files already attached to RetailEdge Company Profile records are
	considered. Private source files are preserved; the profile is repointed to a public
	copy so shell image requests no longer depend on the viewer having File/profile read
	permission. The patch is idempotent because public URLs are left unchanged.
	"""
	if not frappe.db.exists("DocType", PROFILE_DOCTYPE):
		return

	rows = frappe.get_all(
		PROFILE_DOCTYPE,
		filters={"logo": ["like", "/private/files/%"]},
		fields=["name", "logo"],
	)
	for row in rows:
		profile_name = str(row.get("name") or "").strip()
		private_url = str(row.get("logo") or "").strip()
		if not profile_name or not private_url:
			continue
		public_url = ensure_public_profile_logo(profile_name, private_url)
		if public_url and public_url != private_url:
			frappe.db.set_value(PROFILE_DOCTYPE, profile_name, "logo", public_url, update_modified=False)
