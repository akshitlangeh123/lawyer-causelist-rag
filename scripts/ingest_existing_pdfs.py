from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.ingest_service import ingest_folder  # noqa: E402


def main() -> None:
    results = ingest_folder()

    total_added = 0
    total_skipped = 0

    for result in results:
        total_added += result["rows_added"]
        total_skipped += result["rows_skipped_as_duplicates"]

        print(
            result["status"],
            "|",
            result["file_name"],
            "| rows found:",
            result["rows_found_in_pdf"],
            "| added:",
            result["rows_added"],
            "| skipped:",
            result["rows_skipped_as_duplicates"],
        )

    print()
    print("Done.")
    print("Total rows added:", total_added)
    print("Total rows skipped:", total_skipped)


if __name__ == "__main__":
    main()