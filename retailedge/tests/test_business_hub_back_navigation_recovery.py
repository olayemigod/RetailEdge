from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE_LOADER = ROOT / "retailedge" / "page" / "retailedge_business_hub" / "retailedge_business_hub.js"


def source() -> str:
	return PAGE_LOADER.read_text(encoding="utf-8")


class TestBusinessHubBackNavigationRecovery(unittest.TestCase):
	def test_back_navigation_recovery_detects_stale_connected_vue_mount(self):
		text = source()
		for contract in (
			'const MOUNT_CONTENT_SELECTOR = ".retailedge-business-hub, .hub-state";',
			"if (!wrapper?._retailedgeBusinessHub || !root?.isConnected) return false;",
			"return !root.querySelector(MOUNT_CONTENT_SELECTOR);",
			"if (staleMountedHub(wrapper)) {",
			"window.retailedgeTeardownBusinessHubPage?.();",
			"return bootCurrentWrapper();",
		):
			self.assertIn(contract, text)

	def test_back_navigation_recovery_is_route_scoped_and_history_aware(self):
		text = source()
		for contract in (
			"if (!activeRoute()) return false;",
			'"page-change"',
			'"popstate"',
			'"hashchange"',
			'"pageshow"',
			'window.frappe?.router?.on?.("change", scheduleBackNavigationRecovery);',
		):
			self.assertIn(contract, text)

	def test_back_navigation_recovery_installs_once_and_keeps_existing_route_bridge(self):
		text = source()
		self.assertIn("window.__retailedgeBusinessHubBackRecoveryInstalled", text)
		self.assertIn("installBackNavigationRecovery();", text)
		self.assertIn("loadRouteBridge();", text)
		self.assertIn("retailedgeBusinessHubRouteBridge", text)
