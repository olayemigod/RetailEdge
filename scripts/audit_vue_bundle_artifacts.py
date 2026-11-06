"""Read-only audit of Vue bridge and runtime signatures in built Frappe assets.

This diagnostic is deliberately non-blocking until one-Vue-runtime browser acceptance
has been achieved. Manifest resolution and source-only tsconfig assertions cannot
prove that compiled SFC render helpers use EdgeSuite UI's Vue singleton.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

CHECK_BUNDLES = (
    "edgesuite_ui.bundle.js",
    "retailedge_business_hub.bundle.js",
    "professional_selling.bundle.js",
    "make_sale.bundle.js",
    "stock_adjustment.bundle.js",
    "transfer_stock.bundle.js",
    "payment_management.bundle.js",
    "owner_dashboard.bundle.js",
)

BRIDGE_MARKER = "EdgeSuite UI Vue runtime is unavailable"


def inspect(bench: Path) -> list[dict[str, object]]:
    manifest = json.loads((bench / "sites" / "assets" / "assets.json").read_text(encoding="utf-8"))
    rows = []
    for asset in CHECK_BUNDLES:
        url = manifest.get(asset)
        row: dict[str, object] = {"asset": asset, "manifest_url": url or "", "status": "missing"}
        if url:
            path = bench / "sites" / url.lstrip("/")
            if path.is_file():
                source = path.read_text(encoding="utf-8")
                row.update(
                    status="present",
                    bytes=path.stat().st_size,
                    bridge_marker=BRIDGE_MARKER in source,
                    vnode_signature="__v_isVNode" in source,
                    app_signature="__vue_app__" in source,
                )
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", type=Path, default=Path.cwd())
    parser.add_argument("--markdown-summary", action="store_true")
    args = parser.parse_args()
    rows = inspect(args.bench)
    print(json.dumps(rows, indent=2))
    print("Note: signature matches indicate embedded code patterns, not conclusive singleton identity.")
    print("Final gate: browser acceptance for actual EdgeSuite components and product template refs.")
    if args.markdown_summary and os.environ.get("GITHUB_STEP_SUMMARY"):
        lines = [
            "### RetailEdge Vue bridge artifact audit",
            "",
            "| Bundle | Present | Bridge marker | Vue VNode signature |",
            "| --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| `{row['asset']}` | {row['status']} | "
                f"{row.get('bridge_marker', 'n/a')} | {row.get('vnode_signature', 'n/a')} |"
            )
        lines += ["", "Diagnostic only: browser singleton verification remains required.", ""]
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write("\n".join(lines))


if __name__ == "__main__":
    main()
