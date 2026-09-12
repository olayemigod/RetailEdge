from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "public/js/document_output_sharing/DocumentOutputSharing.vue"


def _method_block(source: str, name: str, size: int = 1100) -> str:
	start = source.index(f"{name}(")
	return source[start : start + size]


def test_document_output_reads_native_desk_capability():
	source = PAGE.read_text(encoding="utf-8")
	assert "canUseNativeDesk: false" in source
	assert "Boolean(navigation.access?.can_use_native_desk)" in source


def test_full_document_action_and_handler_require_native_desk():
	source = PAGE.read_text(encoding="utf-8")
	assert 'v-if="canUseNativeDesk"' in source
	assert "Advanced: Open Full Document" in source
	block = _method_block(source, "openNativeDocument")
	assert "if (!this.canUseNativeDesk) return" in block
	assert "details?.native_route" in block


def test_shell_native_navigation_fails_closed():
	source = PAGE.read_text(encoding="utf-8")
	block = _method_block(source, "handleNavigation", 1400)
	assert '["DocType", "Report"].includes(item.target_type)' in block
	assert "!this.canUseNativeDesk" in block
	assert 'item.target_type === "Page"' in block


def test_edgesuite_output_actions_remain_available():
	source = PAGE.read_text(encoding="utf-8")
	for contract in (
		'@click="previewDocument"',
		'@click="downloadPdf"',
		'@click="sendEmail"',
		'@click="openWhatsApp"',
	):
		assert contract in source
