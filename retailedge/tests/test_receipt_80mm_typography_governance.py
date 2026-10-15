from pathlib import Path

from retailedge import professional_print_formats as managed_formats
from retailedge.print_format_governance import _govern_receipt_80_css

APP_ROOT = Path(__file__).resolve().parents[1]


def test_80mm_receipt_item_table_is_larger_without_changing_column_contract():
    governed = _govern_receipt_80_css(managed_formats._RECEIPT_CSS_80)

    assert ".pe-receipt{width:76mm" in governed
    assert "font-size:8.5pt;line-height:1.2" in governed
    assert "table-layout:fixed;font-size:8.5pt" in governed
    assert ".receipt-items th{font-size:8pt;font-weight:700" in governed
    assert "padding:.8mm .4mm;line-height:1.22" in governed
    assert ".receipt-address{font-size:7.5pt" in governed
    assert ".receipt-footer{text-align:center;margin-top:1.5mm;font-size:7.5pt}" in governed

    for width in ("width:27mm", "width:9mm", "width:16mm", "width:18mm"):
        assert width in governed


def test_80mm_typography_governance_is_idempotent():
    once = _govern_receipt_80_css(managed_formats._RECEIPT_CSS_80)
    twice = _govern_receipt_80_css(once)

    assert twice == once
    assert once.count("table-layout:fixed;font-size:8.5pt") == 1


def test_58mm_receipt_css_remains_at_existing_compact_typography():
    original_58 = managed_formats._RECEIPT_CSS_58
    _govern_receipt_80_css(managed_formats._RECEIPT_CSS_80)

    assert managed_formats._RECEIPT_CSS_58 == original_58
    assert "table-layout:fixed;font-size:6.6pt" in original_58
    assert "width:54mm" in original_58
    assert "table-layout:fixed;font-size:8.5pt" not in original_58


def test_receipt_refresh_patch_is_registered_after_v7():
    patches = (APP_ROOT / "patches.txt").read_text(encoding="utf-8")

    v7 = "retailedge.patches.install_pedge_print_formats_v7"
    v8 = "retailedge.patches.install_pedge_print_formats_v8"
    assert v7 in patches
    assert v8 in patches
    assert patches.index(v7) < patches.index(v8)
