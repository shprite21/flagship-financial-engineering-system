"""Shared Q admission and artifact contracts; no separate scheduler or public service."""
from importlib.metadata import version
from pathlib import Path
import json
import platform

from evidence.storage import digest
from . import economy, intelligence, semantic

ROOT = Path(__file__).parent
SOURCES = {p.relative_to(ROOT).as_posix(): p.read_text('utf-8') for p in sorted(ROOT.rglob('*'))
           if p.suffix in {'.py', '.cpp', '.hpp', '.cu'}}
PROVENANCE = {'python': platform.python_version(), 'dependencies': {p: version(p) for p in ['pydantic', 'pypdf', 'ziglang', 'numpy']},
              'source_hashes': {name: digest(code.encode()) for name, code in SOURCES.items()},
              'native_origin': json.loads((ROOT / 'native/source-manifest.json').read_text('utf-8-sig'))}
ACTIONS = {
    'economy-simulation': (economy.EconomyConfig, economy.simulate),
    'economy-benchmark': (economy.BenchmarkConfig, economy.benchmark),
    'intelligence-import': (intelligence.ReportConfig, None),
    'intelligence-search': (intelligence.SearchConfig, intelligence.search),
    'intelligence-answer': (intelligence.AnswerConfig, intelligence.answer),
    'intelligence-news': (intelligence.NewsConfig, intelligence.news),
    'intelligence-index': (semantic.IndexConfig, semantic.index),
    'intelligence-semantic-search': (semantic.SemanticConfig, semantic.search),
}


def catalog():
    return {name: {'schema': schema.model_json_schema(), 'defaults': schema().model_dump()}
            for name, (schema, _) in ACTIONS.items()}


def freeze_request(db, action, config):
    """Retain source/config identity even for failed, cancelled or interrupted jobs."""
    configuration = config.model_dump()
    for field in ('text', 'pdf_base64'):
        value = configuration.pop(field, None)
        if value:
            configuration[field + '_submitted_sha256'] = digest(value.encode())
            configuration[field + '_submitted_bytes'] = len(value.encode())
    source_id = db.put('module_source', {'name': 'Q consolidated module source snapshot',
                                        'code': PROVENANCE, 'source_files': SOURCES})
    return {'action': action, 'configuration': configuration, 'source_id': source_id}


def run(db, action, config, cancel, progress):
    if action == 'intelligence-import':
        return intelligence.freeze_document(db, config, cancel=cancel)
    result = ACTIONS[action][1](config, db, cancel, progress)
    if cancel():
        raise InterruptedError()
    return db.put('intelligence_index' if action == 'intelligence-index' else 'module_result', {**result, 'action': action, 'configuration': config.model_dump(),
                                   'code': PROVENANCE, 'source_files': SOURCES})
