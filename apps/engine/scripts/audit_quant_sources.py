"""Read-only source inventory; do not import source projects or read credentials."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

EXCLUDED = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.tools', '.data',
            '.sources', '.flagship-backups', '.pytest_cache', '.test-tmp', 'dist', '.next',
            '.vinext', '.wrangler', '.sites-runtime', 'outputs',
            'build', 'build-cmake', 'build-cuda', '.ipynb_checkpoints', '.codex', '.agents'}
SUFFIXES = {'.py', '.mjs', '.js', '.ts', '.tsx', '.css', '.cpp', '.hpp', '.cu', '.md',
            '.toml', '.json', '.txt', '.ps1', '.ipynb', '.yaml', '.yml'}


def inventory(root: Path):
    records = []
    for folder, directories, files in os.walk(root):
        directories[:] = sorted(d for d in directories if d.lower() not in EXCLUDED and not d.startswith('build-'))
        # A data/ or reports/ Python package is source, unlike a runtime artifact directory.
        directories[:] = [d for d in directories if d.lower() not in {'data', 'reports'}
                          or any(Path(folder, d).glob('*.py'))]
        for name in sorted(files):
            path = Path(folder) / name
            if (path.suffix.lower() not in SUFFIXES or name.startswith('.env')
                    or (path.suffix not in {'.py', '.ts', '.mjs', '.js'} and any(term in name.lower() for term in ('credential', 'secret', 'token')))
                    or path.is_symlink()):
                continue
            data = path.read_bytes()
            records.append({'path': path.relative_to(root).as_posix(), 'bytes': len(data),
                            'sha256': hashlib.sha256(data).hexdigest()})
    return records


def audit(quant: Path):
    target = quant / 'terminal-v2'
    roots = [quant / 'terminal', *sorted((quant / 'projects').iterdir())]
    sources = {root.relative_to(quant).as_posix(): inventory(root) for root in roots if root.is_dir()}
    migration = []
    for row in json.loads((target / 'docs/flagship-source-manifest.json').read_text('utf-8')):
        source = quant / 'projects' / row['source']
        destination = target / row['destination']
        migration.append({**row, 'source_exists': source.is_file(), 'destination_exists': destination.is_file(),
                          'source_matches_import': source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256'],
                          'destination_matches_import': destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == row['sha256']})
    v1_changes = []
    for row in sources.get('terminal', []):
        destination = target / row['path']
        if not destination.is_file():
            v1_changes.append({'path': row['path'], 'status': 'absent_in_v2'})
        elif hashlib.sha256(destination.read_bytes()).hexdigest() != row['sha256']:
            v1_changes.append({'path': row['path'], 'status': 'different_in_v2'})
    return {'scope': 'Source files only; original results, credentials, caches and dependency installations excluded.',
            'sources': sources, 'existing_migration': migration, 'v1_comparison': v1_changes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--quant', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.quant)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'source_files': {k: len(v) for k, v in result['sources'].items()},
                      'migration_records': len(result['existing_migration']),
                      'missing_destinations': [r['destination'] for r in result['existing_migration'] if not r['destination_exists']],
                      'v1_only': [r['path'] for r in result['v1_comparison'] if r['status'] == 'absent_in_v2']}))
