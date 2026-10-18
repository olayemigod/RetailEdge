"""Fail closed when integration code drifts from the reviewed platform candidate."""
import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bench', type=Path, default=Path.cwd())
    parser.add_argument('--include-payments', action='store_true')
    parser.add_argument('--include-pos', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((Path(__file__).resolve().parents[1] / 'platform-baseline.json').read_text())
    required = ['frappe', 'erpnext', 'edgesuite_ui']
    if args.include_payments:
        required.append('payments')
    if args.include_pos:
        required.extend(['pos_next', 'processedge_posnext_override'])
    for app in required:
        expected = manifest['apps'][app]['sha']
        actual = subprocess.check_output(
            ['git', '-C', str(args.bench / 'apps' / app), 'rev-parse', 'HEAD'], text=True,
        ).strip()
        if actual != expected:
            raise SystemExit(f'{app} baseline mismatch: expected {expected}, got {actual}')
        print(f'{app}: {actual}')
    print('Exact platform candidate verified; manual QA remains a separate gate.')


if __name__ == '__main__':
    main()
