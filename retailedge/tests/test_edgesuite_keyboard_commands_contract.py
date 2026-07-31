from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "retailedge"


class TestEdgeSuiteKeyboardCommandsContract(unittest.TestCase):
	def test_shared_keyboard_commands_load_before_retailedge_runtime(self):
		hooks = (APP / "hooks.py").read_text()
		keyboard = hooks.index('"/assets/retailedge/js/edgesuite_keyboard_shortcuts.js"')
		runtime = hooks.index('"/assets/retailedge/js/retailedge.js"')
		self.assertLess(keyboard, runtime)

	def test_commands_preserve_erpnext_document_safety(self):
		asset = (APP / "public/js/edgesuite_keyboard_shortcuts.js").read_text()
		for expected in (
			'COMMAND_VERSION = "1.0.0"',
			"registerSaveHandler",
			"edgesuite:save-request",
			"edgesuite:command-palette-request",
			"form.doc.docstatus",
			"form.is_dirty()",
			"form.save()",
			"data-edgesuite-save",
			'key === "s"',
			'key === "k"',
		):
			self.assertIn(expected, asset)
		for forbidden in (
			"ignore_permissions",
			"frappe.db.set_value",
			"frappe.client.save",
			"form.doc.docstatus = 0",
		):
			self.assertNotIn(forbidden, asset)


if __name__ == "__main__":
	unittest.main()
