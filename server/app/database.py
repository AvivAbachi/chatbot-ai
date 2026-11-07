from app.config import get_settings
from qdrant_client import QdrantClient, models

settings = get_settings()
qdrantClient = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


def init_db():
    if not qdrantClient.collection_exists(settings.qdrant_collection):
        qdrantClient.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config={
                "dense": models.VectorParams(
                    size=settings.llm_embedding_dimensions,
                    distance=models.Distance.COSINE,
                ),
            },
        )
        qdrantClient.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="metadata.doc_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        qdrantClient.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="metadata.keywords",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        qdrantClient.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="page_content",
            field_schema=models.TextIndexParams(
                type=models.TextIndexType.TEXT,
                tokenizer=models.TokenizerType.WORD,
                lowercase=True,
                scoring=True,
            ),
        )


def reset_db():
    if qdrantClient.collection_exists(settings.qdrant_collection):
        qdrantClient.delete_collection(settings.qdrant_collection)
    init_db()


if __name__ == "__main__":
    init_db()
