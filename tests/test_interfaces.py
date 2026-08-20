import pytest

from common.config.embedder_profile import ACTIVE_PROFILE
from common.config.llm_config import DEFAULT_LLM_CONFIG
from common.interfaces.embedder import Embedder
from common.interfaces.llm_client import LLMClient
from common.interfaces.vector_store import VectorRecord, VectorStore


def test_embedder_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Embedder(ACTIVE_PROFILE)


def test_llm_client_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        LLMClient(DEFAULT_LLM_CONFIG)


def test_vector_store_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        VectorStore()


def test_embedder_subclass_must_implement_embed():
    class Incomplete(Embedder):
        pass

    with pytest.raises(TypeError):
        Incomplete(ACTIVE_PROFILE)


def test_embedder_subclass_carries_profile_and_can_implement_embed():
    class FakeEmbedder(Embedder):
        def embed(self, texts):
            return [[0.0] for _ in texts]

    embedder = FakeEmbedder(ACTIVE_PROFILE)
    assert embedder.profile is ACTIVE_PROFILE
    assert embedder.embed(["a", "b"]) == [[0.0], [0.0]]


def test_vector_record_carries_vector_content_and_metadata():
    record = VectorRecord(vector=[0.1, 0.2], content="text", metadata={"page": 1})
    assert record.vector == [0.1, 0.2]
    assert record.content == "text"
    assert record.metadata == {"page": 1}
