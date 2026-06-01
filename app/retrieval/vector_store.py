from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from app.retrieval.chunk_builder import build_chunks_from_db


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = PROJECT_ROOT / "data" / "vector_store" / "chroma"

COLLECTION_NAME = "jammu_cause_list"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model

    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    return _model


def get_chroma_client() -> chromadb.PersistentClient:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection():
    client = get_chroma_client()

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def reset_collection():
    client = get_chroma_client()

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def embed_texts(
    texts: list[str],
    show_progress_bar: bool = False,
) -> list[list[float]]:
    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=show_progress_bar,
    )

    return embeddings.tolist()


def add_chunks_to_vector_store(
    chunks: list[dict[str, Any]],
    batch_size: int = 64,
    show_progress_bar: bool = False,
) -> int:
    if not chunks:
        return 0

    collection = get_collection()

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]

        ids = [chunk["id"] for chunk in batch]
        documents = [chunk["text"] for chunk in batch]
        metadatas = [chunk["metadata"] for chunk in batch]
        embeddings = embed_texts(
            documents,
            show_progress_bar=show_progress_bar,
        )

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    return len(chunks)


def rebuild_vector_index() -> dict[str, Any]:
    chunks = build_chunks_from_db()

    reset_collection()

    chunks_indexed = add_chunks_to_vector_store(
        chunks,
        show_progress_bar=True,
    )

    return {
        "status": "rebuilt",
        "chunks_indexed": chunks_indexed,
        "collection_count": get_collection().count(),
        "chroma_dir": str(CHROMA_DIR),
        "embedding_model": EMBEDDING_MODEL_NAME,
    }


def index_document(document_id: int) -> int:
    chunks = build_chunks_from_db(document_id=document_id)

    return add_chunks_to_vector_store(
        chunks,
        show_progress_bar=False,
    )


def build_where_filter(filters: dict[str, Any]) -> dict[str, Any] | None:
    clauses = []

    for key, value in filters.items():
        if value is None:
            continue

        value = str(value).strip()

        if not value:
            continue

        clauses.append({key: {"$eq": value}})

    if not clauses:
        return None

    if len(clauses) == 1:
        return clauses[0]

    return {"$and": clauses}


def semantic_search(
    query: str,
    limit: int = 10,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    query = query.strip()

    if not query:
        return []

    collection = get_collection()

    if collection.count() == 0:
        return []

    query_embedding = embed_texts([query])[0]

    where_filter = build_where_filter(filters or {})

    raw_result = collection.query(
        query_embeddings=[query_embedding],
        n_results=limit,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    ids = raw_result.get("ids", [[]])[0]
    documents = raw_result.get("documents", [[]])[0]
    metadatas = raw_result.get("metadatas", [[]])[0]
    distances = raw_result.get("distances", [[]])[0]

    results: list[dict[str, Any]] = []

    for index, chunk_id in enumerate(ids):
        distance = distances[index] if index < len(distances) else None

        results.append(
            {
                "chunk_id": chunk_id,
                "distance": distance,
                "score": None if distance is None else round(1 - distance, 4),
                "text": documents[index] if index < len(documents) else "",
                "metadata": metadatas[index] if index < len(metadatas) else {},
            }
        )

    return results


def vector_index_status() -> dict[str, Any]:
    collection = get_collection()

    return {
        "collection_name": COLLECTION_NAME,
        "collection_count": collection.count(),
        "chroma_dir": str(CHROMA_DIR),
        "embedding_model": EMBEDDING_MODEL_NAME,
    }