from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestWorkingBranchSwitcherInitialSelection(unittest.TestCase):
	def test_shell_switcher_remains_available_before_first_branch_selection(self):
		source = (APP_ROOT / "public/js/retailedge_shell_context.js").read_text(encoding="utf-8")

		# A global/native manager can legitimately have an Operating Company while
		# no Working Branch has been selected yet. The shell must remain usable in
		# that state so the user can make the initial selection.
		self.assertIn("const hasSelection = Boolean(activeBranch || companyWide);", source)
		self.assertIn(
			"const canSwitch = optionCount > 0 && (Boolean(current.can_switch_branch) || !hasSelection);",
			source,
		)
		self.assertIn('activeBranch || "Choose Branch"', source)
		self.assertIn("if (!branches.length) return;", source)
		self.assertNotIn("if (!branches.length || (!activeBranch && !companyWide)) return;", source)


if __name__ == "__main__":
	unittest.main()
