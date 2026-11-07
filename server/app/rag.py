import logging
from urllib.parse import urlparse

import httpx
from app.config import get_settings
from app.database import qdrantClient, reset_db
from app.monitoring import get_logger
from app.utils.data import Metadata, data
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import (
    HTMLHeaderTextSplitter,
    Language,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

settings = get_settings()
logger = get_logger()

embeddings = OpenAIEmbeddings(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    model=settings.llm_embedd_model,
    dimensions=settings.llm_embedding_dimensions,
    check_embedding_ctx_length=False,
)


vector_store = QdrantVectorStore(
    client=qdrantClient,
    collection_name=settings.qdrant_collection,
    embedding=embeddings,
    validate_collection_config=False,
    vector_name="dense",
)


text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2500,
    chunk_overlap=250,
)
md_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=False,
)
html_splitter = HTMLHeaderTextSplitter(
    headers_to_split_on=[("h1", "h1"), ("h2", "h2"), ("h3", "h3")],
)
rst_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.RST,
    chunk_size=2500,
    chunk_overlap=250,
)


def fetch_documents(source: Metadata) -> list[Document]:
    response = httpx.get(source["source"], timeout=30, follow_redirects=True)
    response.raise_for_status()
    metadata = dict(source)
    if "keywords" in metadata:
        metadata["keywords"] = [value.strip().lower() for value in metadata["keywords"]]
    if "text/html" in response.headers.get("content-type", "").lower():
        metadata["content_type"] = "text/html"
    return [Document(page_content=response.text, metadata=metadata)]


def ingest_source(source: Metadata) -> bool:
    documents = [doc for doc in fetch_documents(source) if doc.page_content.strip()]
    path = urlparse(source["source"]).path.lower()
    if path.endswith((".html", ".htm")) or any(
        doc.metadata.get("content_type") == "text/html" for doc in documents
    ):
        header_splitter = html_splitter
    elif path.endswith(".rst"):
        header_splitter = None
        splitter = rst_splitter
    elif path.endswith(".md"):
        header_splitter = md_splitter
    else:
        header_splitter = None
        splitter = text_splitter
    if header_splitter is not None:
        sections = []
        for document in documents:
            for section in header_splitter.split_text(document.page_content):
                if header_splitter is html_splitter and any(
                    section.page_content.strip() == section.metadata.get(key)
                    for key in ("h1", "h2", "h3")
                ):
                    continue
                section.metadata = {**document.metadata, **section.metadata}
                sections.append(section)
        chunks = text_splitter.split_documents(sections)
    else:
        chunks = splitter.split_documents(documents)
    if not chunks:
        return False

    vector_store.add_documents(chunks)
    return True


def ingest() -> None:
    if not settings.force_rebuild and qdrantClient.collection_exists(
        settings.qdrant_collection
    ):
        logger.info("Collection already exists; skipping ingestion")
        return

    reset_db()
    try:
        for source in data:
            if not ingest_source(source):
                raise ValueError(f"Source produced no content: {source['source']}")
            logger.info(
                "Ingested source: '%s' (%s)",
                source["title"],
                source["source"],
            )
    except Exception:
        logger.exception("Ingestion failed; removing incomplete collection")
        qdrantClient.delete_collection(settings.qdrant_collection)
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest()
