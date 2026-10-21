"""Bounded, fail-closed ingestion of the repository-owned knowledge package.

Hashes establish consistency with the trusted repository manifest, not expert
approval or a signature. Context files are metadata only and never indexed.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

from .models import KnowledgeChunk, KnowledgeSource

ROOT = Path(__file__).resolve().parents[4]
PACKAGE_PATH = 'SystemCode/backend/knowledge'
ANCHOR = re.compile(r'<a id="([a-z0-9-]+)"></a>')
CLASSIFICATIONS = {'confirmed_project_fact', 'demo_assumption', 'pending_decision'}


class KnowledgeIntegrityError(ValueError):
    """Internal details must not be exposed by the API."""


def require(condition, reason):
    if not condition:
        raise KnowledgeIntegrityError(reason)


def has_metadata(text: str, key: str, value: str) -> bool:
    """Accept the English corpus and the original full-width punctuation."""
    return re.search(r'\b' + re.escape(key) + r'\s*[:\uff1a]\s*`'
                     + re.escape(value) + '`', text) is not None


def local_file(base: Path, relative: str) -> Path:
    require(isinstance(relative, str) and bool(relative), 'invalid path')
    posix, windows = PurePosixPath(relative), PureWindowsPath(relative)
    require(not posix.is_absolute() and not windows.drive and '\\' not in relative
            and '..' not in posix.parts, 'path traversal')
    path = (base / relative).resolve()
    require(path.is_relative_to(base.resolve()) and path.is_file(), 'missing or escaped file')
    return path


def read_bytes(path: Path, maximum=8_000_000) -> bytes:
    # Read a bounded snapshot; verify and decode these same bytes (no second read).
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    require(len(data) <= maximum, 'file exceeds limit')
    return data


def verified(base: Path, entry: dict) -> bytes:
    require(re.fullmatch('[a-f0-9]{64}', entry['sha256']) is not None, 'invalid digest')
    data = read_bytes(local_file(base, entry['path']))
    require(hashlib.sha256(data).hexdigest() == entry['sha256'], 'digest mismatch')
    return data


def unique(items: list[dict], key: str) -> dict[str, dict]:
    require(isinstance(items, list) and len(items) <= 100, 'invalid list')
    result = {}
    for item in items:
        value = item[key]
        require(isinstance(value, str) and bool(value) and value not in result, 'duplicate or invalid id')
        result[value] = item
    return result


@dataclass(frozen=True)
class KnowledgePackage:
    package_id: str
    package_version: str
    manifest_sha256: str
    versions: dict[str, str]
    chunks: tuple[KnowledgeChunk, ...]


def load_package(root: Path = ROOT) -> KnowledgePackage:
    """Revalidate on every query so a changed source never uses a stale index."""
    try:
        return _load(root.resolve())
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise KnowledgeIntegrityError('Knowledge package validation failed') from exc


def _load(root: Path) -> KnowledgePackage:
    base = (root / PACKAGE_PATH).resolve()
    require(base.is_relative_to(root), 'package escapes repository')
    manifest_bytes = read_bytes(local_file(base, 'manifest.json'), 1_000_000)
    manifest = json.loads(manifest_bytes)
    require(manifest['package_id'] == 'roadguard-a-knowledge'
            and manifest['hash_algorithm'] == 'sha256_raw_file_bytes', 'unsupported package')
    require(isinstance(manifest['package_version'], str) and manifest['package_version'], 'missing version')
    versions = manifest['versions']
    require(isinstance(versions, dict) and 'rule_version' in versions
            and all(isinstance(v, str) and v for v in versions.values()), 'invalid versions')
    require(set(manifest['classification_vocabulary']) == CLASSIFICATIONS, 'classification vocabulary')
    pinned = unique(manifest['sources'], 'source_id')
    contexts = unique(manifest['context_sources'], 'source_id')
    require(not pinned.keys() & contexts.keys(), 'ambiguous source')
    sources = {}
    for key, source in pinned.items():
        verified(root, source)
        sources[key] = KnowledgeSource(source_id=key, path=source['path'],
                                      integrity='sha256_verified', sha256=source['sha256'],
                                      version=source['version'])
    for key, source in contexts.items():
        require(source['integrity'] == 'unhashed_mutable_context' and 'sha256' not in source, 'invalid context')
        local_file(root, source['path'])
        sources[key] = KnowledgeSource(source_id=key, path=source['path'], integrity='unhashed_mutable_context')
    documents = unique(manifest['documents'], 'document_id')
    require(bool(documents), 'empty corpus')
    require(len({d['path'] for d in documents.values()}) == len(documents), 'duplicate document file')
    chunks = []
    for doc_id, document in documents.items():
        text = verified(base, document).decode('utf-8')
        require(has_metadata(text, 'document_id', doc_id)
                and has_metadata(text, 'document_version', document['document_version']), 'document metadata')
        anchors = list(ANCHOR.finditer(text))
        sections = unique(document['sections'], 'section_id')
        require(len(anchors) == len(sections)
                and {a[1] for a in anchors} == set(sections), 'anchors mismatch')
        for index, anchor in enumerate(anchors):
            meta = sections[anchor[1]]
            block = text[anchor.end():anchors[index + 1].start() if index + 1 < len(anchors) else len(text)].strip()
            citation = f'{doc_id}#{anchor[1]}'
            require(meta['citation_id'] == citation and meta['classification'] in CLASSIFICATIONS
                    and has_metadata(block, 'citation_id', citation)
                    and has_metadata(block, 'classification', meta['classification']), 'section metadata')
            require(meta['source_ids'] and len(set(meta['source_ids'])) == len(meta['source_ids']), 'invalid sources')
            refs = []
            for key in meta['source_ids']:
                require(key in sources, 'unknown source')
                hrefs = re.findall(r'\[' + re.escape(key) + r'\]\(([^)]+)\)', block)
                require(len(hrefs) == 1 and (base / document['path']).parent.joinpath(hrefs[0]).resolve()
                        == (root / sources[key].path).resolve(), 'citation link mismatch')
                refs.append(sources[key])
            heading = re.match(r'## ([^\n]+)', block)
            require(heading is not None and len(block) <= 32_000, 'invalid section text')
            chunks.append(KnowledgeChunk(
                citation_id=citation, document_id=doc_id, section_id=anchor[1],
                document_version=document['document_version'], document_sha256=document['sha256'],
                document_path=f'{PACKAGE_PATH}/{document["path"]}', title=heading[1],
                classification=meta['classification'], text=block, sources=refs))
    require(len(chunks) <= 200, 'too many sections')
    verified(base, manifest['ingestion_guide'])
    suite = json.loads(verified(base, manifest['acceptance_cases']))
    cases = unique(suite['cases'], 'case_id')
    require(suite['package_version'] == manifest['package_version']
            and suite['package_id'] == manifest['package_id']
            and len(cases) == manifest['acceptance_cases']['case_count'], 'acceptance metadata')
    citations = {chunk.citation_id: chunk for chunk in chunks}
    for case in cases.values():
        require(case['expected_citations'] and all(c in citations for c in case['expected_citations']), 'unknown acceptance citation')
        expected = {s.source_id for c in case['expected_citations'] for s in citations[c].sources}
        require(set(case['source_ids']) == expected, 'acceptance sources mismatch')
    return KnowledgePackage(manifest['package_id'], manifest['package_version'],
                            hashlib.sha256(manifest_bytes).hexdigest(), versions, tuple(chunks))
