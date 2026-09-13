from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
	ROOT
	/ "retailedge"
	/ "retailedge"
	/ "page"
	/ "transaction_workspace"
	/ "transaction_workspace.py"
)


class TestTransactionWorkspaceFrappeV16Contract(unittest.TestCase):
	def test_current_user_fullname_uses_frappe_v16_safe_helper(self):
		source = SOURCE.read_text()
		self.assertNotIn("frappe.get_user().get_fullname()", source)
		self.assertIn("frappe.utils.get_fullname(frappe.session.user)", source)


if __name__ == "__main__":
	unittest.main()
