"""Real Chroma persistence/version checks with controlled embeddings; no downloads."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from roadguard.assistant import retrieval
from roadguard.assistant.content import clean_text
from roadguard.assistant.embedding import LocalE5Encoder, RetrievalSettings
from roadguard.assistant.knowledge import load_package
from roadguard.assistant.models import KnowledgeSearchRequest
from roadguard.assistant.vector_store import VectorStore, client_at, make_passages
from roadguard.errors import AppError
from rag_test_support import FixtureEncoder


@pytest.fixture
def store(tmp_path):
    package = load_package()
    return package, VectorStore(RetrievalSettings(tmp_path / 'chroma', tmp_path / 'no-model'), FixtureEncoder(package))


def test_persistence_idempotency_and_queries_do_not_embed_documents(store):
    package, index = store
    first = index.build(package)
    count = index.encoder.document_calls
    assert index.build(package)['reused'] and index.encoder.document_calls == count
    assert first['record_count'] == len(package.chunks)
    hits = index.query(package, 'deep pothole', 5)
    assert hits[0].citation_id == 'rg-kb-demo-rules#demo-rule-table'
    assert hits[0].score == pytest.approx(1) and hits[0].matched_terms == []
    assert index.encoder.document_calls == count
    code = "import chromadb,json,sys; from chromadb.config import Settings; c=chromadb.PersistentClient(path=sys.argv[1],settings=Settings(anonymized_telemetry=False)); print(json.dumps(c.get_collection(sys.argv[2],embedding_function=None).count()))"
    result = subprocess.run([sys.executable, '-c', code, str(index.settings.database_path), first['collection']],
                            capture_output=True, text=True, timeout=60, check=True)
    assert json.loads(result.stdout.strip()) == len(package.chunks)


def test_missing_stale_and_changed_embedding_indexes_are_explicit(store):
    package, index = store
    with pytest.raises(AppError, match='Build'):
        index.query(package, 'deep pothole', 5)
    assert not index.settings.database_path.exists()
    index.build(package)
    changed = replace(package, manifest_sha256='1' * 64, package_version='future-package')
    with pytest.raises(AppError):
        index.query(changed, 'deep pothole', 5)
    index.build(changed)
    assert index.query(changed, 'deep pothole', 5)
    assert client_at(index.settings.database_path).count_collections() == 2
    index.encoder.identity = 'different-embedding-model'
    with pytest.raises(AppError):
        index.query(package, 'deep pothole', 5)


def test_child_match_returns_complete_parent_table_and_qualifiers(tmp_path):
    package = load_package()
    class SplitEncoder(FixtureEncoder):
        identity = 'test-split-parent-v1'
        def __init__(self, package):
            super().__init__(package)
            self.texts = {part: i for text, i in self.texts.items()
                          for part in (text[:len(text)//2], text[len(text)//2:])}
        def spans(self, text):
            return [(0, len(text)//2), (len(text)//2, len(text))]
    index = VectorStore(RetrievalSettings(tmp_path/'parents', tmp_path/'no-model'), SplitEncoder(package))
    index.build(package)
    hit = index.query(package, 'deep pothole', 1)[0]
    parent = next(c for c in package.chunks if c.citation_id == hit.citation_id)
    assert hit.text == parent.text
    assert '| pothole_deep | high | P1 | 240 |' in hit.text
    assert 'demonstration_assumptions' in hit.text


def test_failed_build_is_unqueryable_and_can_be_retried(store, monkeypatch):
    package, index = store
    original = index.encoder.encode
    def fail(*args, **kwargs):
        raise RuntimeError('Simulated interruption')
    monkeypatch.setattr(index.encoder, 'encode', fail)
    with pytest.raises(RuntimeError):
        index.build(package)
    with pytest.raises(AppError):
        index.query(package, 'deep pothole', 5)
    monkeypatch.setattr(index.encoder, 'encode', original)
    assert not index.build(package)['reused']
    assert index.query(package, 'deep pothole', 5)


@pytest.mark.parametrize('kind', ['document', 'metadata', 'missing'])
def test_index_tampering_cannot_supply_unverified_answer_evidence(store, monkeypatch, kind):
    package, index = store
    result = index.build(package)
    record = next(r for r in make_passages(package, index.encoder)
                  if r.metadata['citation_id'] == 'rg-kb-demo-rules#demo-rule-table')
    collection = client_at(index.settings.database_path).get_collection(result['collection'], embedding_function=None)
    if kind == 'document':
        collection.update(ids=[record.record_id], documents=['Forged duration 99999'],
                          embeddings=index.encoder.encode([record.text]))
    elif kind == 'metadata':
        collection.update(ids=[record.record_id], metadatas=[{**record.metadata, 'document_sha256': 'forged'}])
    else:
        collection.delete(ids=[record.record_id])
    monkeypatch.setattr(retrieval, 'get_store', lambda: index)
    with pytest.raises(AppError) as error:
        retrieval.search(package, KnowledgeSearchRequest(query='deep pothole'))
    assert error.value.code == 'knowledge_index_unavailable'
    assert '99999' not in error.value.message
    assert not index.build(package)['reused']
    assert index.query(package, 'deep pothole', 5)


def test_runtime_errors_are_sanitized_and_old_rules_never_query(monkeypatch):
    def broken():
        raise RuntimeError('C:/secret/model-path')
    monkeypatch.setattr(retrieval, 'get_store', broken)
    package = load_package()
    result = retrieval.search(package, KnowledgeSearchRequest(query='deep pothole', rule_version='old'))
    assert result.status == 'rule_version_unavailable'
    with pytest.raises(AppError) as error:
        retrieval.search(package, KnowledgeSearchRequest(query='deep pothole'))
    assert 'secret' not in error.value.message


def test_token_spans_cover_unicode_source_without_truncation():
    from tokenizers import Tokenizer, models, pre_tokenizers
    encoder = LocalE5Encoder.__new__(LocalE5Encoder)
    encoder.tokenizer = Tokenizer(models.WordLevel({'[UNK]': 0}, unk_token='[UNK]'))
    encoder.tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    text = ('RoadGuard \u65bd\u5de5\u961f pothole repair. ' * 200).strip()
    spans = encoder.spans(text)
    assert len(spans) > 1 and spans[0][0] == 0 and spans[-1][1] == len(text)
    assert all(right[0] <= left[1] for left, right in zip(spans, spans[1:]))
    for start, end in spans:
        assert len(encoder.tokenizer.encode(text[start:end], add_special_tokens=False).ids) <= 320
    assert '\u65bd\u5de5\u961f' in text[spans[0][0]:spans[0][1]]


def test_e5_prefix_pooling_and_normalization_are_applied():
    from tokenizers import Tokenizer, models, pre_tokenizers, processors
    encoder = LocalE5Encoder.__new__(LocalE5Encoder)
    tokenizer = Tokenizer(models.WordLevel({'[UNK]': 0, '<pad>': 1, 'query': 2, 'passage': 3, ':': 4, 'road': 5}, unk_token='[UNK]'))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.enable_padding(pad_id=1, pad_token='<pad>')
    encoder.batch_tokenizer = tokenizer
    class Session:
        def get_inputs(self):
            return [type('Input', (), {'name': name})() for name in ['input_ids', 'attention_mask']]
        def run(self, _, feed):
            self.feed = feed
            output = np.ones((*feed['input_ids'].shape, 384), dtype=np.float32)
            output[feed['attention_mask'] == 0] = 99999
            return [output]
    encoder.session = Session()
    result = encoder.encode(['road', 'road road'], query=True)
    assert encoder.session.feed['input_ids'][0, 0] == 2
    assert np.linalg.norm(result, axis=1) == pytest.approx([1, 1])
    assert result[0] == pytest.approx(result[1])
    encoder.encode(['road'])
    assert encoder.session.feed['input_ids'][0, 0] == 3
    with pytest.raises(AppError):
        encoder.encode(['road ' * 600], query=True)


def test_missing_model_is_explicit_and_never_downloaded(tmp_path):
    with pytest.raises(AppError) as error:
        LocalE5Encoder(tmp_path)
    assert error.value.code == 'embedding_model_unavailable'
    assert list(tmp_path.iterdir()) == []
