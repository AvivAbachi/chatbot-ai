## Chatbot Server (RAG)

A chatbot API that uses **retrieval-augmented generation (RAG)**.
It can search engineering documentation in Qdrant and search the web to help answer questions.

---

### Prerequisites

| Item                  | Requirement                                                                        |
| --------------------- | ---------------------------------------------------------------------------------- |
| Python                | 3.13 or later                                                                      |
| Package manager       | [uv](https://docs.astral.sh/uv/)                                                   |
| Vector store          | Running **Qdrant** instance                                                        |
| Model provider        | OpenAI-compatible chat and embedding API; the chat model must support tool calling |
| Environment variables | `.env` (copied from `.env.exemple`)                                                |

---

### Install

Run the commands below from the `server` directory.

```bash
uv sync
cp .env.exemple .env
```

On PowerShell, use `Copy-Item .env.exemple .env`. Configure the provider URL, API key, chat and embedding models, embedding dimensions, and Qdrant settings in `.env`. The embedding dimensions must match your provider's output.

---

### Run the server

```bash
# Start a local Qdrant instance
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# Ingest sources in app/utils/data.py if the collection is missing
uv run --env-file .env python -m app.rag

# Start the web API
uv run --env-file .env uvicorn app.api:app

# Start the web API with hot reload for development
uv run --env-file .env uvicorn app.api:app --reload
```

- Running `python -m app.rag` indexes sources if the configured Qdrant collection does not exist. Existing collections are left unchanged.
- Set `FORCE_REBUILD=true` in the environment to delete and recreate the collection. If ingestion fails, the incomplete collection is removed so ingestion can retry. Reset the setting to `false` after rebuilding.
- Ingestion needs network access to the configured sources. Run it again after changing the sources, embedding model, or dimensions.
- The API defaults to `http://127.0.0.1:8000`, with interactive documentation at `/docs`. Use `--port` if your model provider already uses port 8000.

---

### Tests

```bash
uv run pytest
```
