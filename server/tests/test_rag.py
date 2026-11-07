import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from qdrant_client import QdrantClient

os.environ.setdefault("LLM_BASE_URL", "http://localhost:8888/v1")
os.environ.setdefault("LLM_API_KEY", "test")

from app import database, rag, tools


def test_source_metadata_classification():
    doc_ids = [source["doc_id"] for source in rag.data]
    assert all(isinstance(doc_id, str) and doc_id for doc_id in doc_ids)
    assert len(doc_ids) == len(set(doc_ids))
    for source in rag.data:
        assert set(source) == {"doc_id", "title", "source", "keywords"}
        assert all(
            isinstance(source[key], str) and source[key] for key in ("title", "source")
        )
        assert isinstance(source["keywords"], list) and source["keywords"]
        assert all(
            isinstance(value, str) and value and value == value.lower()
            for value in source["keywords"]
        )


@pytest.fixture
def local_qdrant(monkeypatch):
    monkeypatch.setattr(rag.settings, "force_rebuild", True)
    client = QdrantClient(":memory:")
    monkeypatch.setattr(database, "qdrantClient", client)
    monkeypatch.setattr(rag, "qdrantClient", client)
    monkeypatch.setattr(
        rag,
        "vector_store",
        rag.QdrantVectorStore(
            client=client,
            collection_name=database.settings.qdrant_collection,
            embedding=rag.embeddings,
            validate_collection_config=False,
            vector_name="dense",
        ),
    )
    database.init_db()
    yield client
    client.close()


@pytest.mark.parametrize("extension", ["md", "txt", "rst"])
def test_text_formats(monkeypatch, extension):
    url = f"https://example.com/document.{extension}"
    monkeypatch.setattr(
        rag.httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            200, text="Document text", request=httpx.Request("GET", url)
        ),
    )
    documents = rag.fetch_documents(
        {"file_name": "document." + extension, "source": url}
    )
    assert documents[0].page_content == "Document text"
    assert documents[0].metadata == {
        "file_name": "document." + extension,
        "source": url,
    }


def test_ingestion_replaces_existing_data(monkeypatch, local_qdrant):
    source = {
        "doc_id": "example-text",
        "file_name": "Text",
        "title": "Text",
        "source": "https://example.com/text",
        "keywords": ["Python", "Programming languages", "Programming"],
    }
    empty = {
        "file_name": "Empty",
        "title": "Empty",
        "source": "https://example.com/empty",
    }
    monkeypatch.setattr(rag, "data", [source])
    monkeypatch.setattr(
        rag.httpx,
        "get",
        lambda url, **kwargs: httpx.Response(
            200,
            text="Hello world" if url == source["source"] else "  ",
            request=httpx.Request("GET", url),
        ),
    )
    embed = MagicMock(return_value=[[0.1] * 768])
    monkeypatch.setattr(type(rag.embeddings), "embed_documents", embed)
    rag.ingest()
    embed.assert_called_once_with(["Hello world"])
    rag.ingest()
    points, _ = local_qdrant.scroll(
        database.settings.qdrant_collection, with_payload=True
    )
    assert len(points) == 1
    assert points[0].payload["page_content"] == "Hello world"
    assert points[0].payload["metadata"]["doc_id"] == "example-text"
    assert points[0].payload["metadata"]["keywords"] == [
        "python",
        "programming languages",
        "programming",
    ]

    monkeypatch.setattr(tools, "qdrantClient", local_qdrant)
    monkeypatch.setattr(
        type(rag.embeddings), "embed_query", lambda self, text: [0.1] * 768
    )
    result = tools.rag_search_tool.invoke(
        {
            "query": "Hello",
            "keywords": ["PYTHON", "Programming Languages", "PROGRAMMING"],
        }
    )
    assert "Hello world" in result


def test_ingestion_creates_indexes_on_configured_collection(monkeypatch):
    monkeypatch.setattr(rag.settings, "force_rebuild", True)
    client = MagicMock()
    client.collection_exists.side_effect = [True, False]
    monkeypatch.setattr(database, "qdrantClient", client)
    monkeypatch.setattr(rag, "data", [])
    rag.ingest()
    client.delete_collection.assert_called_once_with(
        database.settings.qdrant_collection
    )
    client.create_collection.assert_called_once()
    assert {
        call.kwargs["field_name"] for call in client.create_payload_index.call_args_list
    } == {"metadata.doc_id", "metadata.keywords", "page_content"}
    assert all(
        call.kwargs["collection_name"] == rag.settings.qdrant_collection
        for call in client.create_payload_index.call_args_list
    )
    text_index = next(
        call.kwargs["field_schema"]
        for call in client.create_payload_index.call_args_list
        if call.kwargs["field_name"] == "page_content"
    )
    assert text_index.scoring is True
    assert text_index.lowercase is True


def test_ingestion_preserves_existing_collection_by_default(monkeypatch, local_qdrant):
    monkeypatch.setattr(rag.settings, "force_rebuild", False)
    process = MagicMock()
    monkeypatch.setattr(rag, "ingest_source", process)
    monkeypatch.setattr(rag, "data", [{"title": "Example", "source": "example"}])
    rag.ingest()
    process.assert_not_called()
    assert local_qdrant.collection_exists(database.settings.qdrant_collection)


def test_ingestion_initializes_missing_collection(monkeypatch, local_qdrant):
    monkeypatch.setattr(rag.settings, "force_rebuild", False)
    local_qdrant.delete_collection(database.settings.qdrant_collection)
    monkeypatch.setattr(rag, "data", [])
    rag.ingest()
    assert local_qdrant.collection_exists(database.settings.qdrant_collection)


def test_ingestion_failure_is_reported(monkeypatch, local_qdrant):
    sources = [
        {"file_name": "Bad", "title": "Bad", "source": "https://example.com/bad"},
        {"file_name": "Good", "title": "Good", "source": "https://example.com/good"},
    ]
    monkeypatch.setattr(rag, "data", sources)
    process = MagicMock(side_effect=RuntimeError("download failed"))
    monkeypatch.setattr(rag, "ingest_source", process)
    with pytest.raises(RuntimeError, match="download failed"):
        rag.ingest()
    assert process.call_count == 1
    assert not local_qdrant.collection_exists(database.settings.qdrant_collection)


def test_dense_search_after_ingestion(monkeypatch, local_qdrant):
    source = {"title": "Example", "source": "https://example.com/test.txt"}
    monkeypatch.setattr(rag, "data", [source])
    monkeypatch.setattr(
        rag,
        "fetch_documents",
        lambda _: [rag.Document(page_content="Python retrieval", metadata=source)],
    )
    monkeypatch.setattr(
        type(rag.embeddings),
        "embed_documents",
        lambda self, texts: [[0.1] * 768 for _ in texts],
    )
    monkeypatch.setattr(
        type(rag.embeddings), "embed_query", lambda self, text: [0.1] * 768
    )
    rag.ingest()
    results = rag.vector_store.similarity_search("Python", k=1)
    assert results[0].page_content == "Python retrieval"


def test_embeddings_send_text_strings(monkeypatch):
    create = MagicMock(return_value={"data": [{"embedding": [0.1]}]})
    monkeypatch.setattr(rag.embeddings, "client", SimpleNamespace(create=create))

    rag.embeddings.embed_documents(["Hello world"])

    assert create.call_args.kwargs["input"] == ["Hello world"]


@pytest.mark.parametrize(("extension", "splitter_name"), [("rst", "rst_splitter")])
def test_format_uses_expected_splitter(monkeypatch, extension, splitter_name):
    source = {
        "file_name": "Document",
        "source": f"https://example.com/file.{extension}?download=1",
    }
    document = rag.Document(page_content="Document text", metadata=source)
    monkeypatch.setattr(rag, "fetch_documents", lambda _: [document])
    splitter = MagicMock()
    splitter.split_documents.return_value = [document]
    monkeypatch.setattr(rag, splitter_name, splitter)
    store = MagicMock()
    monkeypatch.setattr(rag, "vector_store", store)

    assert rag.ingest_source(source)
    splitter.split_documents.assert_called_once_with([document])
    store.add_documents.assert_called_once_with([document])


def test_html_content_type_uses_html_splitter(monkeypatch):
    source = {"file_name": "Page", "source": "https://example.com/page/"}
    monkeypatch.setattr(
        rag.httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body><h1>Heading</h1><p>Content</p></body></html>",
            request=httpx.Request("GET", source["source"]),
        ),
    )
    splitter = MagicMock(wraps=rag.html_splitter)
    monkeypatch.setattr(rag, "html_splitter", splitter)
    store = MagicMock()
    monkeypatch.setattr(rag, "vector_store", store)

    assert rag.ingest_source(source)
    splitter.split_text.assert_called_once()
    chunks = store.add_documents.call_args.args[0]
    content_chunk = next(chunk for chunk in chunks if "Content" in chunk.page_content)
    assert content_chunk.metadata["h1"] == "Heading"
    assert content_chunk.metadata["source"] == source["source"]


def test_html_headings_are_not_ingested_as_content(monkeypatch):
    source = {"source": "https://example.com/spec.html"}
    content = (
        "<h2>Statements</h2><h3>Assignment statements</h3>"
        "<p>Assignments replace values stored in variables.</p>"
    )
    monkeypatch.setattr(
        rag,
        "fetch_documents",
        lambda _: [rag.Document(page_content=content, metadata=source)],
    )
    store = MagicMock()
    monkeypatch.setattr(rag, "vector_store", store)

    assert rag.ingest_source(source)
    chunks = store.add_documents.call_args.args[0]
    assert [chunk.page_content for chunk in chunks] == [
        "Assignments replace values stored in variables."
    ]
    assert chunks[0].metadata["h2"] == "Statements"
    assert chunks[0].metadata["h3"] == "Assignment statements"


@pytest.mark.parametrize(
    ("extension", "content"),
    [
        ("md", "# Heading\n\n## Section\n\n" + "word " * 600),
        ("html", "<h1>Heading</h1><h2>Section</h2><p>" + "word " * 600 + "</p>"),
    ],
)
def test_header_chunks_preserve_source_and_heading_metadata(
    monkeypatch, extension, content
):
    source = {
        "file_name": "Document",
        "source": f"https://example.com/file.{extension}",
    }
    monkeypatch.setattr(
        rag,
        "fetch_documents",
        lambda _: [rag.Document(page_content=content, metadata=source)],
    )
    store = MagicMock()
    monkeypatch.setattr(rag, "vector_store", store)

    assert rag.ingest_source(source)
    chunks = store.add_documents.call_args.args[0]
    assert len(chunks) > 1
    assert all(len(chunk.page_content) <= 2500 for chunk in chunks)
    assert all(chunk.metadata["source"] == source["source"] for chunk in chunks)
    content_chunks = [chunk for chunk in chunks if "word" in chunk.page_content]
    assert content_chunks
