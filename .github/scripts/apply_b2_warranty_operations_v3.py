from pathlib import Path

source_path = Path("/tmp/apply_b2_warranty_operations.py")
source = source_path.read_text()


def replace_prefix(suffix: str, old_tabs: int, new_tabs: int, expected: int) -> None:
    global source
    old = "\\t" * old_tabs + suffix
    new = "\\t" * new_tabs + suffix
    count = source.count(old)
    assert count == expected, f"B2 wrapper expected {expected} occurrences for {suffix!r}, got {count}"
    source = source.replace(old, new)


replace_prefix('tabindex="0"', 6, 9, 1)
replace_prefix(':tabindex="canOpenRow(source) ? 0 : -1"', 6, 9, 1)
replace_prefix(':class="{ \'is-actionable\': canOpenRow(source) }"', 6, 9, 1)
replace_prefix('@click="openRow(source, row)"', 6, 9, 2)
replace_prefix('@keydown.enter="openRow(source, row)"', 6, 9, 2)

exec(compile(source, str(source_path), "exec"))
