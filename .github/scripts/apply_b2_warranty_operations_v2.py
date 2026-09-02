from pathlib import Path

source_path = Path("/tmp/apply_b2_warranty_operations.py")
source = source_path.read_text()

replacements = {
    r"\t\t\t\t\t\ttabindex=\"0\"": r"\t\t\t\t\t\t\t\t\ttabindex=\"0\"",
    r"\t\t\t\t\t\t:tabindex=\"canOpenRow(source) ? 0 : -1\"": r"\t\t\t\t\t\t\t\t\t:tabindex=\"canOpenRow(source) ? 0 : -1\"",
    r"\t\t\t\t\t\t:class=\"{ \'is-actionable\': canOpenRow(source) }\"": r"\t\t\t\t\t\t\t\t\t:class=\"{ \'is-actionable\': canOpenRow(source) }\"",
}
for old, new in replacements.items():
    count = source.count(old)
    assert count == 1, f"B2 wrapper expected one {old!r}, got {count}"
    source = source.replace(old, new, 1)

old_click_block = r"\t\t\t\t\t\t@click=\"openRow(source, row)\"\n\t\t\t\t\t\t@keydown.enter=\"openRow(source, row)\""
new_click_block = r"\t\t\t\t\t\t\t\t\t@click=\"openRow(source, row)\"\n\t\t\t\t\t\t\t\t\t@keydown.enter=\"openRow(source, row)\""
count = source.count(old_click_block)
assert count == 2, f"B2 wrapper expected old/new click blocks, got {count}"
source = source.replace(old_click_block, new_click_block)

exec(compile(source, str(source_path), "exec"))
