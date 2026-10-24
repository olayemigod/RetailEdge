from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
WIZARD_VUE = APP_ROOT / "public" / "js" / "retailedge_setup" / "UserOnboardingManager.vue"
ONBOARDING_PY = APP_ROOT / "user_onboarding.py"


class TestUserOnboardingWizardWording(unittest.TestCase):
	def test_wizard_uses_business_facing_language(self):
		source = WIZARD_VUE.read_text(encoding="utf-8")

		for technical_phrase in (
			"ERPNext",
			"System User",
			"native permissions",
		):
			self.assertNotIn(technical_phrase, source)

		for business_phrase in (
			"staff account",
			"Business permissions are managed separately.",
			"Branch's POS Profile",
			"business permissions",
		):
			self.assertIn(business_phrase, source)

	def test_backend_validation_does_not_expose_system_user_terminology(self):
		source = ONBOARDING_PY.read_text(encoding="utf-8")
		self.assertNotIn("RetailEdge operational access requires a System User.", source)
		self.assertIn("This account cannot be used for RetailEdge operations.", source)


if __name__ == "__main__":
	unittest.main()
