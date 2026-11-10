from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRINTING = ROOT / "public/js/thermalReceiptPrinting.js"
OUTPUT = ROOT / "public/js/document_output_sharing/DocumentOutputSharing.vue"


def test_document_output_reports_busy_tab_without_opening_another_setup_tab():
    source = PRINTING.read_text(encoding="utf-8")
    output = OUTPUT.read_text(encoding="utf-8")

    assert '"SERIAL_TAB_IN_USE"' in source
    assert '"SERIAL_TAB_COORDINATION_UNAVAILABLE"' in source
    assert '"RETAIL_PRINTER_TAB_BUSY"' in source
    assert '"RETAIL_PRINTER_TAB_BUSY"' not in output.split("const setupRequired =", 1)[1].split("].includes", 1)[0]
    assert 'errorMessage(error, "Unable to print the receipt.")' in output


def test_document_output_requires_exact_resolved_printer_after_handoff():
    source = PRINTING.read_text(encoding="utf-8")

    assert 'adapter.devices?.bindingMatchesStatus?.(profile.name, current || {})' in source
    assert 'adapter.devices?.bindingMatchesStatus?.(profile.name, restored.status || {})' in source
    assert 'if (!restored?.status?.connected || !restoredMatchesBinding)' in source
    assert "portInfoMatchesBinding" not in source
    assert 'current?.connected && (sharedMatch || legacySerialMatch)' not in source
    assert '"RETAIL_PRINTER_SETUP_REQUIRED"' in source
