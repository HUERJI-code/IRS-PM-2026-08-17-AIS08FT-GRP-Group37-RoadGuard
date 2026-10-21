"""Versioned persistent Chroma indexes of verified static knowledge only."""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

from filelock import FileLock

from roadguard.errors import AppError
from .content import clean_text
from .embedding import RetrievalSettings, get_encoder
from .knowledge import KnowledgePackage
from .models import KnowledgeHit

POLICY = 'e5-token320-overlap48-cosine-v1'
OWNER = 'roadguard-static-knowledge'


def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class Passage:
    record_id: str
    text: str
    metadata: dict


def make_passages(package: KnowledgePackage, encoder) -> list[Passage]:
    records = []
    for chunk in package.chunks:
        text = clean_text(chunk.text)
        for index, (start, end) in enumerate(encoder.spans(text)):
            passage = text[start:end]
            metadata = {
                'citation_id': chunk.citation_id, 'document_id': chunk.document_id,
                'document_version': chunk.document_version, 'document_sha256': chunk.document_sha256,
                'document_path': chunk.document_path, 'classification': chunk.classification,
                'package_version': package.package_version, 'manifest_sha256': package.manifest_sha256,
                'passage_index': index, 'start': start, 'end': end, 'text_sha256': digest(passage),
                'source_ids': json.dumps([s.source_id for s in chunk.sources]),
            }
            record_id = digest(f'{chunk.citation_id}:{start}:{end}:{passage}')
            records.append(Passage(record_id, passage, metadata))
    if not records or len(records) > 2000:
        raise ValueError('Invalid static passage count.')
    return records


@lru_cache(maxsize=4)
def client_at(path: Path):
    import chromadb
    from chromadb.config import Settings
    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))


class VectorStore:
    def __init__(self, settings: RetrievalSettings, encoder):
        self.settings, self.encoder = settings, encoder

    def identity(self, package):
        fingerprint = digest(f'{package.manifest_sha256}:{self.encoder.identity}:{POLICY}')
        return 'roadguard-kb-' + fingerprint[:40]

    def metadata(self, package, records):
        return {'owner': OWNER, 'manifest_sha256': package.manifest_sha256,
                'package_version': package.package_version, 'embedding': self.encoder.identity,
                'dimensions': self.encoder.dimensions, 'policy': POLICY, 'record_count': len(records),
                'records_sha256': digest(json.dumps([(r.record_id, r.metadata) for r in records], sort_keys=True)),
                'state': 'ready'}

    def _existing(self, package, records):
        if not (self.settings.database_path / 'chroma.sqlite3').is_file():
            raise AppError('knowledge_index_unavailable', 'Build the current knowledge vector index first.', 503)
        client = client_at(self.settings.database_path)
        try:
            collection = client.get_collection(self.identity(package), embedding_function=None)
        except Exception as exc:
            from chromadb.errors import NotFoundError
            if isinstance(exc, NotFoundError):
                raise AppError('knowledge_index_unavailable', 'Rebuild the vector index for the current knowledge version.', 503) from None
            raise
        if collection.metadata != self.metadata(package, records) or collection.count() != len(records):
            raise AppError('knowledge_index_unavailable', 'The vector index is incomplete or inconsistent. Rebuild it.', 503)
        return collection

    def build(self, package: KnowledgePackage) -> dict:
        """Explicit, idempotent indexing. Interrupted versions never become queryable."""
        records = make_passages(package, self.encoder)
        expected = self.metadata(package, records)
        path = self.settings.database_path
        path.mkdir(parents=True, exist_ok=True)
        with FileLock(str(path / 'roadguard-index.lock'), timeout=120):
            client = client_at(path)
            name = self.identity(package)
            from chromadb.errors import NotFoundError
            try:
                existing = client.get_collection(name, embedding_function=None)
            except NotFoundError:
                existing = None
            if existing is not None:
                if existing.metadata == expected and existing.count() == len(records):
                    try:
                        self._verify_rows(existing.get(include=['documents', 'metadatas']), records)
                    except ValueError:
                        pass  # An explicit build repairs this owned, corrupted cache.
                    else:
                        return {**expected, 'collection': name, 'reused': True}
                if not existing.metadata or existing.metadata.get('owner') != OWNER:
                    raise ValueError('Refusing to replace an unrecognized collection.')
                # Only this deterministic, incomplete version is removed. Other versions remain.
                client.delete_collection(name)
            collection = client.create_collection(name, embedding_function=None,
                configuration={'hnsw': {'space': 'cosine'}}, metadata={**expected, 'state': 'building'})
            for start in range(0, len(records), 16):
                batch = records[start:start + 16]
                embeddings = self.encoder.encode([r.text for r in batch])
                collection.add(ids=[r.record_id for r in batch], documents=[r.text for r in batch],
                               metadatas=[r.metadata for r in batch], embeddings=embeddings)
            self._verify_rows(collection.get(include=['documents', 'metadatas']), records)
            if collection.count() != len(records):
                raise ValueError('Incomplete vector index.')
            collection.modify(metadata=expected)
            return {**expected, 'collection': name, 'reused': False}

    @staticmethod
    def _verify_rows(rows, records, *, complete=True):
        expected = {r.record_id: r for r in records}
        ids = rows['ids']
        if len(ids) != len(set(ids)) or (complete and set(ids) != set(expected)):
            raise ValueError('Unexpected vector index records.')
        for key, text, metadata in zip(ids, rows['documents'], rows['metadatas'], strict=True):
            record = expected.get(key)
            if record is None or text != record.text or metadata != record.metadata:
                raise ValueError('Vector index provenance does not match the verified package.')

    def query(self, package: KnowledgePackage, question: str, limit: int) -> list[KnowledgeHit]:
        records = make_passages(package, self.encoder)
        collection = self._existing(package, records)
        result = collection.query(query_embeddings=self.encoder.encode([question], query=True),
                                  n_results=min(len(records), limit * 4),
                                  include=['documents', 'metadatas', 'distances'])
        rows = {key: result[key][0] for key in ('ids', 'documents', 'metadatas')}
        self._verify_rows(rows, records, complete=False)
        parents = {c.citation_id: c for c in package.chunks}
        best = {}
        for text, metadata, distance in zip(rows['documents'], rows['metadatas'], result['distances'][0], strict=True):
            if not math.isfinite(distance):
                raise ValueError('Invalid vector distance.')
            score = min(1.0, max(-1.0, 1.0 - distance))
            citation = metadata['citation_id']
            if score < self.settings.min_similarity or citation in best:
                continue
            parent = parents[citation]
            # The matched child ranks the parent. Full verified sections preserve
            # table rows, complete sentences and nearby assumption boundaries.
            best[citation] = KnowledgeHit(**parent.model_dump(),
                                         score=round(score, 6), matched_terms=[])
        return sorted(best.values(), key=lambda hit: (-hit.score, hit.citation_id))[:limit]


def get_store() -> VectorStore:
    settings = RetrievalSettings.from_env()
    return VectorStore(settings, get_encoder(settings.model_path))
