from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import get_connection, init_db  # noqa: E402
from app.ingestion.case_detail_parser import parse_pdf_case_details  # noqa: E402
from app.ingestion.ingest_service import insert_case_detail  # noqa: E402


def main() -> None:
    init_db()

    with get_connection() as connection:
        documents = connection.execute(
            """
            SELECT id, file_name, stored_path
            FROM documents
            ORDER BY id
            """
        ).fetchall()

        total = 0
        skipped = 0

        for document in documents:
            pdf_path = Path(document["stored_path"])

            if not pdf_path.exists():
                print("missing file:", document["file_name"], "|", pdf_path)
                skipped += 1
                continue

            detail = parse_pdf_case_details(pdf_path)

            if not detail:
                print("no case detail found:", document["file_name"])
                skipped += 1
                continue

            case_detail_id = insert_case_detail(
                connection=connection,
                document_id=document["id"],
                detail=detail,
            )

            total += 1

            print(
                "case detail parsed:",
                document["file_name"],
                "| id:",
                case_detail_id,
                "| registration:",
                detail.get("registration_number"),
                "| cnr:",
                detail.get("cnr_number"),
                "| history rows:",
                len(detail.get("case_history", [])),
            )

    print()
    print("Done.")
    print("Case details parsed:", total)
    print("Skipped:", skipped)


if __name__ == "__main__":
    main()