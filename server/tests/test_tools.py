import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

os.environ.setdefault("LLM_BASE_URL", "http://localhost:8888/v1")
os.environ.setdefault("LLM_API_KEY", "test")

from app import rag, tools


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("(1.5 + 2) * -3", "-10.5"),
        ("25 + 5 / 5", "26.0"),
        ("2 ** 3 + 7 % 4 + 7 // 2", "14.0"),
        ("sqrt(9) + abs(-2) + round(1.234, 2)", "6.23"),
        ("sin(pi / 2)", "1.0"),
        ("isqrt(9) + gcd(12, 8) + lcm(3, 4)", "19"),
        ("gcd(isqrt(16), 6)", "2"),
        ("isqrt(2.5)", "Invalid or unsupported arithmetic expression."),
        ("1 ** 1001", "Invalid or unsupported arithmetic expression."),
        ("cos(tau)", "1.0"),
        ("sqrt(-1)", "Invalid or unsupported arithmetic expression."),
        ("1 / 0", "Cannot divide by zero."),
        ("9**9**9", "Invalid or unsupported arithmetic expression."),
        ("__import__('os')", "Invalid or unsupported arithmetic expression."),
        ("1 +", "Invalid or unsupported arithmetic expression."),
        ("1" * 501, "Expression is too long."),
    ],
)
def test_calculator(expression, expected):
    assert tools.calucator.invoke({"expression": expression}) == expected


def test_datetime_tool_returns_current_utc_time():
    before = datetime.now(UTC).replace(microsecond=0)
    result = datetime.fromisoformat(tools.datetime_tool.invoke({}))
    after = datetime.now(UTC)
    assert result.utcoffset() == UTC.utcoffset(result)
    assert before <= result <= after


def test_web_search_formats_results(monkeypatch):
    search = MagicMock(return_value=[{"title": "Docs", "href": "https://example.com", "body": "Details"}])
    monkeypatch.setattr(tools, "DDGS", lambda: SimpleNamespace(text=search))
    assert tools.web_search_tool.invoke({"query": "example"}) == (
        "Title: Docs\nLink: https://example.com\nSnippet: Details\n---"
    )
    search.assert_called_once_with("example", max_results=5)


@pytest.mark.parametrize("failure", [False, True])
def test_web_search_empty_or_failed(monkeypatch, failure):
    search = MagicMock(side_effect=RuntimeError("unavailable") if failure else None, return_value=[])
    monkeypatch.setattr(tools, "DDGS", lambda: SimpleNamespace(text=search))
    result = tools.web_search_tool.invoke({"query": "example"})
    assert result == ("An error occurred during the metasearch: unavailable" if failure else "No search results found.")


@pytest.mark.parametrize(
    ("content_type", "body", "expected"),
    [
        ("text/html", b"<header>Menu</header><p>Hello</p><script>bad()</script>", "Hello"),
        ("application/json", b'{"answer":42}', '{\n  "answer": 42\n}'),
        ("text/plain", b"plain text", "plain text"),
    ],
)
def test_web_fetch_formats_content(monkeypatch, content_type, body, expected):
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, headers={"content-type": content_type}, content=body, request=request
    ))
    client = httpx.Client(transport=transport)
    monkeypatch.setattr(tools.httpx, "Client", lambda **kwargs: client)
    assert tools.web_fetch_tool.invoke({"url": "https://example.com/"}) == (
        f"Source: https://example.com/\nContent:\n{expected}"
    )


def test_web_fetch_rejects_invalid_url():
    assert tools.web_fetch_tool.invoke({"url": "file:///etc/passwd"}) == "Invalid URL."


@pytest.mark.parametrize("status,body,expected", [
    (200, b"x" * 1_000_001, "Response exceeds the size limit."),
    (404, b"missing", "Failed to fetch the URL."),
])
def test_web_fetch_handles_errors(monkeypatch, status, body, expected):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, content=body, request=request))
    client = httpx.Client(transport=transport)
    monkeypatch.setattr(tools.httpx, "Client", lambda **kwargs: client)
    assert tools.web_fetch_tool.invoke({"url": "https://example.com/"}) == expected


def test_rag_tool_returns_document_id(monkeypatch):
    search = MagicMock(
        return_value=SimpleNamespace(
            points=[
                SimpleNamespace(
                    payload={
                        "page_content": "Useful text",
                        "metadata": {
                            "doc_id": "example-document",
                            "title": "Example title",
                            "source": "https://example.com/document",
                            "h1": "Chapter",
                            "h2": "Section",
                            "h3": "Subsection",
                        },
                    }
                )
            ]
        )
    )
    monkeypatch.setattr(tools, "qdrantClient", SimpleNamespace(query_points=search))
    monkeypatch.setattr(
        type(rag.embeddings), "embed_query", lambda self, text: [0.1] * 768
    )
    result = tools.rag_search_tool.invoke({"query": "question"})
    assert result == (
        "doc_id: example-document\n"
        "title: Example title\n"
        "source: https://example.com/document\n"
        "h1: Chapter\n"
        "h2: Section\n"
        "h3: Subsection\n"
        "Useful text"
    )
    args = search.call_args.kwargs
    assert args["prefetch"][0].using == "dense"
    assert args["prefetch"][1].using == "page_content"
    assert args["prefetch"][1].query.text == "question"
    assert args["query"].fusion.value == "rrf"
    assert all(prefetch.filter is None for prefetch in args["prefetch"])


@pytest.mark.parametrize(
    "keywords",
    [
        ["Python"],
        ["Code review"],
        ["Python", "Coding style", "Development"],
    ],
)
def test_rag_tool_metadata_filters(monkeypatch, keywords):
    search = MagicMock(return_value=SimpleNamespace(points=[]))
    monkeypatch.setattr(tools, "qdrantClient", SimpleNamespace(query_points=search))
    monkeypatch.setattr(
        type(rag.embeddings), "embed_query", lambda self, text: [0.1] * 768
    )
    tools.rag_search_tool.invoke({"query": "question", "keywords": keywords})
    for prefetch in search.call_args.kwargs["prefetch"]:
        assert all(
            condition.key == "metadata.keywords" for condition in prefetch.filter.must
        )
        assert [condition.match.value for condition in prefetch.filter.must] == [
            value.lower() for value in keywords
        ]


def test_rag_tool_document_id_lookup(monkeypatch):
    scroll = MagicMock(return_value=([SimpleNamespace(payload={
        "page_content": "Document text", "metadata": {"doc_id": "example"}
    })], "next"))
    monkeypatch.setattr(tools, "qdrantClient", SimpleNamespace(scroll=scroll))
    result = tools.rag_search_tool.invoke({"doc_id": "example"})
    assert "Document text" in result
    assert scroll.call_args.kwargs["scroll_filter"].must[0].match.value == "example"
    assert scroll.call_args.kwargs["limit"] == 10


def test_rag_tool_query_filters_by_document_id(monkeypatch):
    search = MagicMock(return_value=SimpleNamespace(points=[]))
    monkeypatch.setattr(tools, "qdrantClient", SimpleNamespace(query_points=search))
    monkeypatch.setattr(type(rag.embeddings), "embed_query", lambda self, text: [0.1] * 768)
    tools.rag_search_tool.invoke({"query": "question", "doc_id": "example"})
    for prefetch in search.call_args.kwargs["prefetch"]:
        assert prefetch.filter.must[0].key == "metadata.doc_id"
        assert prefetch.filter.must[0].match.value == "example"


def test_rag_tool_requires_query_or_document_id():
    assert "Provide a query or a document ID" in tools.rag_search_tool.invoke({})


def test_rag_tool_handles_retrieval_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Qdrant unavailable")

    monkeypatch.setattr(tools, "qdrantClient", SimpleNamespace(query_points=fail))
    monkeypatch.setattr(
        type(rag.embeddings), "embed_query", lambda self, text: [0.1] * 768
    )
    assert "unavailable" in tools.rag_search_tool.invoke({"query": "question"})


