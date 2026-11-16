"""Isolated, time-bounded PDF text extraction; no network or provider configuration."""
import json
import sys
from pathlib import Path


def extract(source, destination):
    from pypdf import PdfReader
    reader = PdfReader(source)
    if reader.is_encrypted:
        raise ValueError('Encrypted reports are unsupported')
    if len(reader.pages) > 1200:
        raise ValueError('Report exceeds 1,200 pages')
    pages, total = [], 0
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ''
        total += len(text)
        if total > 8_000_000:
            raise ValueError('Report text exceeds eight million characters')
        pages.append({'page': number, 'text': text})
    if not any(p['text'].strip() for p in pages):
        raise ValueError('No readable text. Scanned reports require OCR before import.')
    Path(destination).write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    extract(sys.argv[1], sys.argv[2])
