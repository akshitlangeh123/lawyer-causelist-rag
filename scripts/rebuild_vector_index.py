from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import init_db  # noqa: E402
from app.retrieval.vector_store import rebuild_vector_index  # noqa: E402


def main() -> None:
    init_db()

    result = rebuild_vector_index()

    print("Vector index rebuilt.")
    print("Chunks indexed:", result["chunks_indexed"])
    print("Collection count:", result["collection_count"])
    print("Chroma dir:", result["chroma_dir"])
    print("Embedding model:", result["embedding_model"])


if __name__ == "__main__":
    main()