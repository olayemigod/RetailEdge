"""Fail-closed frontend build contract for RetailEdge's shared EdgeSuite Vue runtime.

This is a build artifact safeguard, not a browser acceptance substitute.
"""
from __future__ import annotations

import json
from pathlib import Path

BRIDGE_MARKER = "EdgeSuite UI Vue runtime is unavailable"
SHARED_BUNDLE = "edgesuite_ui.bundle.js"
REQUIRED_PRODUCT_BUNDLES = (
    "retailedge_business_hub.bundle.js",
    "professional_selling.bundle.js",
    "make_sale.bundle.js",
    "stock_adjustment.bundle.js",
    "transfer_stock.bundle.js",
    "payment_management.bundle.js",
    "owner_dashboard.bundle.js",
)


def discover_vue_product_bundles(source_dir: Path) -> tuple[str, ...]:
    """Include all Vue SFC entrypoints, not just the original NEOTEX examples."""
    result = []
    for path in sorted(source_dir.glob("*.bundle.js")):
        source = path.read_text(encoding="utf-8")
        if '.vue"' in source or ".vue'" in source:
            result.append(path.name)
    return tuple(result)


def inspect(bench: Path) -> list[dict[str, object]]:
    manifest_path = bench / "sites" / "assets" / "assets.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Missing or invalid Frappe assets manifest: {manifest_path}") from error

    source_dir = bench / "apps" / "retailedge" / "retailedge" / "public" / "js"
    required = set(REQUIRED_PRODUCT_BUNDLES) | set(discover_vue_product_bundles(source_dir))
    # Indirect Vue imports may come through a JS entrypoint, with no direct
    # .vue import in its source. Check *all* compiled RetailEdge JS bundles
    # for embedded Vue runtime signatures, even when no bridge is required.
    published = {
        name
        for name, value in manifest.items()
        if name.endswith(".bundle.js")
        and isinstance(value, str)
        and value.startswith("/assets/retailedge/dist/js/")
    }
    bundles = (SHARED_BUNDLE, *sorted(required | published))
    rows = []
    for bundle in bundles:
        url = manifest.get(bundle)
        row: dict[str, object] = {
            "asset": bundle,
            "manifest_url": url or "",
            "status": "missing",
            "requires_bridge": bundle in required,
        }
        if isinstance(url, str) and url.startswith("/assets/") and "/dist/js/" in url:
            output = bench / "sites" / url.lstrip("/")
            if output.is_file():
                source = output.read_text(encoding="utf-8")
                row.update(
                    status="present",
                    bytes=output.stat().st_size,
                    bridge_marker=BRIDGE_MARKER in source,
                    vnode_signature="__v_isVNode" in source,
                    app_signature="__vue_app__" in source,
                )
        rows.append(row)
    return rows


def validate_bridge_contract(
    rows: list[dict[str, object]], *, require_shared: bool = True
) -> list[str]:
    """Validate product bundles; require shared assets only at complete-bench gates.

    Frappe calls each app's after_build immediately after its own scoped build.
    The edgesuite_ui app may not have built its assets yet at that point.
    """
    issues: list[str] = []
    if not rows or rows[0].get("asset") != SHARED_BUNDLE:
        return ["Shared EdgeSuite UI asset was not checked."]
    shared = rows[0]
    if shared.get("status") == "present":
        if not shared.get("app_signature"):
            issues.append("Shared EdgeSuite UI runtime bundle is invalid.")
    elif require_shared:
        issues.append(
            "Shared EdgeSuite UI runtime bundle is missing; build edgesuite_ui "
            "and run the complete-bench strict audit before release."
        )
    for row in rows[1:]:
        bundle = str(row["asset"])
        if row.get("status") != "present":
            issues.append(f"{bundle}: compiled asset is missing")
            continue
        embedded_vue = row.get("vnode_signature") or row.get("app_signature")
        if embedded_vue or (row.get("requires_bridge") and not row.get("bridge_marker")):
            issues.append(
                f"{bundle}: compiled Vue runtime mismatch "
                f"(bridge={row.get('bridge_marker')}, vnode={row.get('vnode_signature')}, "
                f"app={row.get('app_signature')})"
            )
    return issues


def verify_retailedge_after_build() -> None:
    """Run after bench build --app retailedge; abort if Frappe emitted duplicate Vue."""
    # Editable-app source may live outside the bench (e.g. GitHub CI checkout).
    # The Frappe bench resolver, not this module's physical path, is authoritative.
    from frappe.utils import get_bench_path

    bench = Path(get_bench_path()).resolve()
    rows = inspect(bench)
    # A scoped 'Install Apps - RetailEdge' build must validate every product
    # artifact, but may run before EdgeSuite UI publishes its own assets.
    # The CLI --strict gate still *requires* the shared asset in a full bench.
    problems = validate_bridge_contract(rows, require_shared=False)
    if problems:
        raise RuntimeError("RetailEdge frontend build rejected:\n" + "\n".join(problems))
    if rows[0].get("status") != "present":
        print(
            "[RetailEdge] EdgeSuite UI bundle is not built at this per-app stage; "
            "complete-bench runtime verification remains mandatory."
        )
