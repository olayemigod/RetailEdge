from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SUFFIXES = {".js", ".ts", ".vue", ".jsx", ".tsx"}


def test_retailedge_frontend_has_no_coreedge_asset_dependency():
	for path in APP_ROOT.rglob("*"):
		if not path.is_file() or path.suffix.lower() not in FRONTEND_SUFFIXES:
			continue

		source = path.read_text(encoding="utf-8").lower()
		for forbidden in (
			"coreedge/public",
			"coreedge/coreedge/public",
			"../coreedge/",
			"../../coreedge/",
		):
			assert forbidden not in source, path
