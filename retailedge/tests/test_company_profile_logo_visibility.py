from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from retailedge.company_profile import ensure_public_profile_logo
from retailedge.patches.publicize_company_profile_logos import execute as publicize_company_profile_logos


class TestCompanyProfileLogoVisibility(unittest.TestCase):
	@patch("retailedge.company_profile.save_file")
	@patch("retailedge.company_profile.frappe.get_doc")
	@patch("retailedge.company_profile.frappe.db.get_value", return_value="FILE-PRIVATE")
	def test_private_attached_logo_is_copied_to_public_files(
		self,
		_get_value,
		get_doc,
		save_file,
	):
		source = Mock()
		source.file_name = "merchant-logo.png"
		source.get_content.return_value = b"image-bytes"
		get_doc.return_value = source
		save_file.return_value = SimpleNamespace(file_url="/files/merchant-logo-ab12cd.png")

		result = ensure_public_profile_logo(
			"RETAIL-COMPANY-PROFILE-0001",
			"/private/files/merchant-logo.png",
		)

		self.assertEqual(result, "/files/merchant-logo-ab12cd.png")
		save_file.assert_called_once_with(
			"merchant-logo.png",
			b"image-bytes",
			"RetailEdge Company Profile",
			"RETAIL-COMPANY-PROFILE-0001",
			is_private=0,
			df="logo",
		)

	@patch("retailedge.company_profile.save_file")
	@patch("retailedge.company_profile.frappe.db.get_value", return_value="FILE-PUBLIC")
	def test_existing_public_logo_is_reused_without_copy(self, _get_value, save_file):
		result = ensure_public_profile_logo(
			"RETAIL-COMPANY-PROFILE-0001",
			"/files/merchant-logo.png",
		)

		self.assertEqual(result, "/files/merchant-logo.png")
		save_file.assert_not_called()

	@patch("retailedge.patches.publicize_company_profile_logos.frappe.db.set_value")
	@patch(
		"retailedge.patches.publicize_company_profile_logos.ensure_public_profile_logo",
		return_value="/files/merchant-logo.png",
	)
	@patch(
		"retailedge.patches.publicize_company_profile_logos.frappe.get_all",
		return_value=[{"name": "PROFILE-1", "logo": "/private/files/merchant-logo.png"}],
	)
	@patch("retailedge.patches.publicize_company_profile_logos.frappe.db.exists", return_value=True)
	def test_migration_repoints_only_private_profile_logo(
		self,
		_exists,
		_get_all,
		ensure_public,
		set_value,
	):
		publicize_company_profile_logos()

		ensure_public.assert_called_once_with("PROFILE-1", "/private/files/merchant-logo.png")
		set_value.assert_called_once_with(
			"RetailEdge Company Profile",
			"PROFILE-1",
			"logo",
			"/files/merchant-logo.png",
			update_modified=False,
		)


if __name__ == "__main__":
	unittest.main()
