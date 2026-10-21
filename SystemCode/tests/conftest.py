"""Isolated Chroma storage and explicit embedding doubles for assistant HTTP tests."""
import pytest


@pytest.fixture(scope='session')
def rag_control_store(tmp_path_factory):
    from roadguard.assistant.embedding import RetrievalSettings
    from roadguard.assistant.knowledge import load_package
    from roadguard.assistant.vector_store import VectorStore
    from rag_test_support import FixtureEncoder
    package = load_package()
    directory = tmp_path_factory.mktemp('rag-control')
    store = VectorStore(RetrievalSettings(directory / 'chroma', directory / 'no-model'), FixtureEncoder(package))
    store.build(package)
    return store


@pytest.fixture(autouse=True)
def isolated_assistant_retrieval(request, monkeypatch):
    if request.module.__name__.split('.')[-1] in {
        'test_knowledge_retrieval', 'test_assistant_query', 'test_c_acceptance',
    }:
        store = request.getfixturevalue('rag_control_store')
        monkeypatch.setattr('roadguard.assistant.retrieval.get_store', lambda: store)
