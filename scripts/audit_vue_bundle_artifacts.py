"""Read-only audit of compiled Vue runtime ownership in Frappe asset bundles.

With --strict, the same validation is enforced by RetailEdge's after_build hook.
Browser rendering acceptance remains a separate, mandatory release gate.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# CI invokes this script with the global Python, not the Frappe bench virtualenv.
# Make the checked-out app package importable without relying on environment state.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retailedge.vue_runtime_build_guard import inspect, validate_bridge_contract  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", type=Path, default=Path.cwd())
    parser.add_argument("--markdown-summary", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    rows = inspect(args.bench)
    print(json.dumps(rows, indent=2))
    print("Note: signature checks are build provenance only, not browser acceptance.")
    if args.markdown_summary and os.environ.get("GITHUB_STEP_SUMMARY"):
        lines = [
            "### RetailEdge Vue bridge artifact audit",
            "",
            "| Bundle | Present | Bridge marker | Vue VNode signature |",
            "| --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| \`{row['asset']}\` | {row['status']} | "
                f"{row.get('bridge_marker', 'n/a')} | {row.get('vnode_signature', 'n/a')} |"
            )
        lines += ["", "Browser and hosted production acceptance remain required.", ""]
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write("\n".join(lines))

    if args.strict:
        problems = validate_bridge_contract(rows)
        if problems:
            raise SystemExit("INVALID COMPILED VUE BRIDGE:\n" + "\n".join(problems))
        print(f"Compiled Vue bridge gate PASS: {len(rows) - 1} product bundles checked.")


if __name__ == "__main__":
    main()
