"""Local Ollama embeddings with immutable, model-identified indexes inside Q."""
import math
import os
import re

from pydantic import BaseModel, ConfigDict, Field
from evidence.storage import digest
from .intelligence import SearchConfig, documents, request_json, NOTES


class IndexConfig(SearchConfig):
    # Reuse the exact document/period/as-of selection contract.
    pass


class SemanticConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    index_id: str = Field('', max_length=64)
    query: str = Field('', max_length=2000)
    top_k: int = Field(6, ge=1, le=20, strict=True)


def model_identity():
    model = os.environ.get('Q_INTELLIGENCE_EMBEDDING_MODEL', '').strip()
    if not model:
        raise ValueError('Semantic retrieval is unconfigured. Set Q_INTELLIGENCE_EMBEDDING_MODEL on the backend, or use lexical report search.')
    response = request_json('http://127.0.0.1:11434/api/tags', None, 10)
    for item in response.get('models', []):
        if item.get('name') in {model, model + ':latest'} and re.fullmatch('[a-f0-9]{64}', item.get('digest', '')):
            return {'name': item['name'], 'digest': item['digest']}
    raise ValueError('Configured embedding model is not installed in the local Ollama service')


def vectors(texts, model):
    response = request_json('http://127.0.0.1:11434/api/embed',
                            {'model': model['name'], 'input': texts, 'truncate': False, 'keep_alive': 0}, 90)
    values = response.get('embeddings')
    if not isinstance(values, list) or len(values) != len(texts):
        raise ValueError('Embedding provider returned an incomplete batch')
    dimension = len(values[0]) if isinstance(values[0], list) else 0
    if not 1 <= dimension <= 4096:
        raise ValueError('Embedding dimension outside supported bounds')
    normalized = []
    for vector in values:
        if (not isinstance(vector, list) or len(vector) != dimension
                or any(type(x) not in {float, int} or not math.isfinite(x) for x in vector)):
            raise ValueError('Embedding provider returned malformed or non-finite vectors')
        norm = math.sqrt(math.fsum(x*x for x in vector))
        if not math.isfinite(norm) or norm <= 0:
            raise ValueError('Embedding provider returned a zero or unbounded vector')
        normalized.append([x / norm for x in vector])
    return normalized


def index(config, db, cancel=lambda: False, progress=lambda *_: None):
    selected = documents(db, config)
    model = model_identity()
    chunks = []
    for document in selected:
        record = document['artifact']
        for page in record['pages']:
            for start in range(0, len(page['text']), 1600):
                text = page['text'][start:start + 1800]
                if text.strip():
                    chunks.append({'document_id': document['id'], 'page': page['page'], 'start': start,
                                   'company': record['metadata']['company'], 'report': record['metadata']['report'],
                                   'period': record['metadata']['period'], 'source_sha256': record['source_sha256'], 'excerpt': text})
    if not 1 <= len(chunks) <= 2000:
        raise ValueError('Select reports containing between one and 2,000 text chunks per index')
    embeddings = []
    for offset in range(0, len(chunks), 8):
        if cancel():
            raise InterruptedError()
        embeddings.extend(vectors([r['excerpt'] for r in chunks[offset:offset + 8]], model))
        progress(min(offset + 8, len(chunks)), len(chunks))
    if model_identity() != model:
        raise ValueError('Embedding model changed during indexing; retry with a stable model')
    if len({len(v) for v in embeddings}) != 1:
        raise ValueError('Embedding dimensions changed between batches')
    return {'name': 'Local semantic report index · ' + (config.company or 'selected reports'),
            'inputs': {'documents': selected}, 'model': model, 'chunks': chunks, 'embeddings': embeddings,
            'content_hash': digest({'chunks': chunks, 'embeddings': embeddings, 'model': model}),
            'results': {'Report index': {'metrics': {'reports': len(selected), 'chunks': len(chunks), 'dimensions': len(embeddings[0])}}},
            'limitations': NOTES + ['Vectors are saved local-model observations, stored in Q. No report data or credentials are copied to Pinecone. Model generation is not claimed bitwise deterministic.']}


def rank(saved, query_vector, top_k):
    if saved['content_hash'] != digest({k: saved[k] for k in ('chunks', 'embeddings', 'model')}):
        raise ValueError('Saved semantic index integrity failure')
    if len(saved['chunks']) != len(saved['embeddings']) or not saved['chunks']:
        raise ValueError('Saved semantic index is incomplete')
    ranked = []
    for chunk, vector in zip(saved['chunks'], saved['embeddings']):
        if len(query_vector) != len(vector):
            raise ValueError('Query embedding dimension does not match the frozen index')
        score = math.fsum(x*y for x, y in zip(query_vector, vector))
        if not math.isfinite(score):
            raise ValueError('Non-finite semantic similarity')
        ranked.append({**chunk, 'score': max(-1, min(1, score))})
    ranked.sort(key=lambda r: (-r['score'], r['document_id'], r['page'], r['start']))
    hits, seen = [], set()
    for row in ranked:
        key = row['document_id'], row['page']
        if key not in seen:
            seen.add(key)
            hits.append({'citation': f'S{len(hits)+1}', **row})
        if len(hits) == top_k:
            break
    return hits


def search(config, db, cancel=lambda: False, progress=lambda *_: None):
    if not config.query.strip():
        raise ValueError('Enter a report question')
    saved = db.get(config.index_id, 'intelligence_index')
    model = model_identity()
    if saved['model'] != model:
        raise ValueError('Embedding model differs from the frozen index; rebuild the index explicitly')
    if cancel():
        raise InterruptedError()
    query_vector = vectors([config.query], model)[0]
    if model_identity() != model:
        raise ValueError('Embedding model changed while encoding the query')
    hits = rank(saved, query_vector, config.top_k)
    progress(1, 1)
    return {'name': 'Semantic report search', 'synthetic': False,
            'method': 'Cosine similarity over frozen local embeddings; similarity is not factual confidence',
            'inputs': {'index_id': config.index_id, 'index': saved, 'query_vector': query_vector},
            'results': {'Report evidence': {'citations': hits}}, 'limitations': NOTES}
