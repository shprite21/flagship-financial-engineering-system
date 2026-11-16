"""Explicit read-only import of cached source-project PDFs into Q's private store."""
import argparse
import json
import os
from pathlib import Path

from evidence.storage import Store
from qmodules.intelligence import ReportConfig, freeze_document


def import_reports(source: Path, destination: Path):
    root = source.resolve()
    metadata = json.loads((root / 'Code/report_data.json').read_text('utf-8'))
    db = Store(destination)
    imported, seen = [], set()
    for report in metadata:
        location = report.get('file_location')
        if not report.get('cached') or not location:
            continue
        file = (root / 'Code' / location).resolve()
        if not file.is_relative_to(root / 'Reports') or file.suffix.lower() != '.pdf':
            raise ValueError('Report metadata points outside the source Reports folder')
        if not file.is_file() or file in seen:
            continue
        seen.add(file)
        config = ReportConfig(company=report['company_name'], report=report['report_name'],
                              period=report['report_name'].split('-', 1)[-1], published=report.get('published', ''),
                              source_url=report.get('url') or '', filename=file.name)
        key = freeze_document(db, config, raw=file.read_bytes())
        saved = db.get(key, 'intelligence_document')
        imported.append({'source_file': file.name, 'id': key, 'pages': len(saved['pages']),
                         'source_sha256': saved['source_sha256'], 'metadata_verified': False})
        print(json.dumps(imported[-1]), flush=True)
    return imported


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--store', type=Path, default=Path(os.environ.get('Q_FLAGSHIP_DATA', Path(__file__).resolve().parents[3] / '.data/flagship')) / 'evidence')
    parser.add_argument('--record', type=Path, required=True)
    args = parser.parse_args()
    result = import_reports(args.source, args.store)
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
