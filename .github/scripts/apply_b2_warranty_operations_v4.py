from pathlib import Path
import re

source_path = Path("/tmp/apply_b2_warranty_operations.py")
source = source_path.read_text()

marker = '"row actionability",'
marker_at = source.index(marker)
block_start = source.rfind("\nvue = replace_once(", 0, marker_at)
block_end = source.index("\nold_note =", marker_at)
assert block_start >= 0 and block_end > block_start
source = source[:block_start] + "\n" + source[block_end:]

exec(compile(source, str(source_path), "exec"))

vue_path = Path("retailedge/public/js/native_visual_workspaces/NativeERPNextWorkspace.vue")
vue = vue_path.read_text()
pattern = re.compile(
    r'(?P<indent>\t+)tabindex="0"\n'
    r'(?P=indent)@click="openRow\(source, row\)"\n'
    r'(?P=indent)@keydown\.enter="openRow\(source, row\)"'
)


def replacement(match: re.Match[str]) -> str:
    indent = match.group("indent")
    return (
        f'{indent}:tabindex="canOpenRow(source) ? 0 : -1"\n'
        f'{indent}:class="{{ \'is-actionable\': canOpenRow(source) }}"\n'
        f'{indent}@click="openRow(source, row)"\n'
        f'{indent}@keydown.enter="openRow(source, row)"'
    )

vue, count = pattern.subn(replacement, vue, count=1)
assert count == 1, f"expected one actual Vue row action block, got {count}"
vue_path.write_text(vue)
