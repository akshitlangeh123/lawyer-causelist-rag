from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from app.ingestion.case_detail_parser import parse_pdf_case_details
from app.db.database import get_connection, init_db
from app.ingestion.cause_list_parser import parse_pdf


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

def safe_filename(file_name: str) -> str:
    name = Path(file_name).name
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)

    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"

    return name


def unique_path(folder: Path, file_name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)

    candidate = folder / file_name

    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix

    counter = 1

    while True:
        new_candidate = folder / f"{stem}_{counter}{suffix}"

        if not new_candidate.exists():
            return new_candidate

        counter += 1


def insert_cause_list_rows(
    connection: sqlite3.Connection,
    document_id: int,
    rows: list[dict[str, Any]],
) -> tuple[int, int]:
    rows_added = 0
    rows_skipped = 0

    for row in rows:
        try:
            cursor = connection.execute(
                """
                INSERT INTO cause_list_items (
                    document_id,
                    source_file,
                    source_page,
                    listing_date,
                    court_establishment,
                    court_number,
                    judge_name,
                    case_category,
                    stage,
                    serial_number,
                    case_reference,
                    case_type,
                    case_number,
                    case_year,
                    party_name,
                    advocate
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    row.get("source_file"),
                    row.get("source_page"),
                    row.get("listing_date"),
                    row.get("court_establishment"),
                    row.get("court_number"),
                    row.get("judge_name"),
                    row.get("case_category"),
                    row.get("stage"),
                    row.get("serial_number"),
                    row.get("case_reference"),
                    row.get("case_type"),
                    row.get("case_number"),
                    row.get("case_year"),
                    row.get("party_name"),
                    row.get("advocate"),
                ),
            )

            if cursor.rowcount:
                rows_added += 1
            else:
                rows_skipped += 1

        except sqlite3.IntegrityError:
            rows_skipped += 1

    return rows_added, rows_skipped

def insert_case_detail(
    connection: sqlite3.Connection,
    document_id: int,
    detail: dict[str, Any],
) -> int:
    connection.execute(
        """
        INSERT INTO case_details (
            document_id,
            source_file,
            source_page,
            case_type,
            filing_number,
            filing_date,
            registration_number,
            registration_date,
            cnr_number,
            first_hearing_date,
            next_hearing_date,
            case_status,
            stage_of_case,
            court_number_and_judge,
            detail_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(document_id, registration_number, cnr_number)
        DO UPDATE SET
            source_file = excluded.source_file,
            source_page = excluded.source_page,
            case_type = excluded.case_type,
            filing_number = excluded.filing_number,
            filing_date = excluded.filing_date,
            registration_date = excluded.registration_date,
            first_hearing_date = excluded.first_hearing_date,
            next_hearing_date = excluded.next_hearing_date,
            case_status = excluded.case_status,
            stage_of_case = excluded.stage_of_case,
            court_number_and_judge = excluded.court_number_and_judge,
            detail_text = excluded.detail_text
        """,
        (
            document_id,
            detail.get("source_file"),
            detail.get("source_page"),
            detail.get("case_type"),
            detail.get("filing_number"),
            detail.get("filing_date"),
            detail.get("registration_number"),
            detail.get("registration_date"),
            detail.get("cnr_number"),
            detail.get("first_hearing_date"),
            detail.get("next_hearing_date"),
            detail.get("case_status"),
            detail.get("stage_of_case"),
            detail.get("court_number_and_judge"),
            detail.get("detail_text"),
        ),
    )

    row = connection.execute(
        """
        SELECT id
        FROM case_details
        WHERE document_id = ?
          AND registration_number = ?
          AND cnr_number = ?
        """,
        (
            document_id,
            detail.get("registration_number"),
            detail.get("cnr_number"),
        ),
    ).fetchone()

    if row is None:
        raise RuntimeError("Failed to insert or fetch case detail.")

    case_detail_id = row["id"]

    child_tables = [
        "case_parties",
        "case_acts",
        "case_fir_details",
        "case_history",
        "case_process_details",
        "case_transfers",
        "case_subordinate_courts",
        "case_orders",
    ]

    for table in child_tables:
        connection.execute(
            f"DELETE FROM {table} WHERE case_detail_id = ?",
            (case_detail_id,),
        )

    for party in detail.get("parties", []):
        connection.execute(
            """
            INSERT INTO case_parties (
                case_detail_id,
                party_type,
                party_number,
                party_name,
                advocate_name
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                case_detail_id,
                party.get("party_type"),
                party.get("party_number"),
                party.get("party_name"),
                party.get("advocate_name"),
            ),
        )

    for act in detail.get("acts", []):
        connection.execute(
            """
            INSERT INTO case_acts (
                case_detail_id,
                act_name,
                section_text
            )
            VALUES (?, ?, ?)
            """,
            (
                case_detail_id,
                act.get("act_name"),
                act.get("section_text"),
            ),
        )

    for fir in detail.get("fir_details", []):
        connection.execute(
            """
            INSERT INTO case_fir_details (
                case_detail_id,
                police_station,
                fir_number,
                fir_year
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                case_detail_id,
                fir.get("police_station"),
                fir.get("fir_number"),
                fir.get("fir_year"),
            ),
        )

    for history in detail.get("case_history", []):
        connection.execute(
            """
            INSERT INTO case_history (
                case_detail_id,
                registration_number,
                judge,
                business_on_date,
                hearing_date,
                purpose_of_hearing
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                case_detail_id,
                history.get("registration_number"),
                history.get("judge"),
                history.get("business_on_date"),
                history.get("hearing_date"),
                history.get("purpose_of_hearing"),
            ),
        )

    for process in detail.get("process_details", []):
        connection.execute(
            """
            INSERT INTO case_process_details (
                case_detail_id,
                process_id,
                process_date,
                process_title,
                issued_process
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                case_detail_id,
                process.get("process_id"),
                process.get("process_date"),
                process.get("process_title"),
                process.get("issued_process"),
            ),
        )

    for transfer in detail.get("case_transfers", []):
        connection.execute(
            """
            INSERT INTO case_transfers (
                case_detail_id,
                registration_number,
                transfer_date,
                from_court,
                to_court
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                case_detail_id,
                transfer.get("registration_number"),
                transfer.get("transfer_date"),
                transfer.get("from_court"),
                transfer.get("to_court"),
            ),
        )

    for subordinate in detail.get("subordinate_courts", []):
        connection.execute(
            """
            INSERT INTO case_subordinate_courts (
                case_detail_id,
                court_number_and_name,
                case_number_and_year,
                case_decision_date
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                case_detail_id,
                subordinate.get("court_number_and_name"),
                subordinate.get("case_number_and_year"),
                subordinate.get("case_decision_date"),
            ),
        )

    for order in detail.get("orders", []):
        connection.execute(
            """
            INSERT INTO case_orders (
                case_detail_id,
                order_number,
                order_date,
                order_details
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                case_detail_id,
                order.get("order_number"),
                order.get("order_date"),
                order.get("order_details"),
            ),
        )

    return case_detail_id

def ingest_pdf(pdf_path: Path) -> dict[str, Any]:
    init_db()

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    metadata, rows = parse_pdf(pdf_path)

    file_hash = metadata["file_hash"]

    with get_connection() as connection:
        existing_document = connection.execute(
            """
            SELECT id, file_name, stored_path
            FROM documents
            WHERE file_hash = ?
            """,
            (file_hash,),
        ).fetchone()

        if existing_document:
            return {
                "file_name": pdf_path.name,
                "status": "already_exists",
                "document_id": existing_document["id"],
                "existing_file_name": existing_document["file_name"],
                "stored_path": existing_document["stored_path"],
                "rows_found_in_pdf": len(rows),
                "rows_added": 0,
                "rows_skipped_as_duplicates": len(rows),
            }

        cursor = connection.execute(
            """
            INSERT INTO documents (
                file_name,
                stored_path,
                file_hash,
                page_count,
                court_establishment,
                court_number,
                judge_name,
                case_category,
                cause_list_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pdf_path.name,
                str(pdf_path),
                file_hash,
                metadata.get("page_count"),
                metadata.get("court_establishment"),
                metadata.get("court_number"),
                metadata.get("judge_name"),
                metadata.get("case_category"),
                metadata.get("cause_list_date"),
            ),
        )

        document_id = cursor.lastrowid

        rows_added, rows_skipped = insert_cause_list_rows(
            connection=connection,
            document_id=document_id,
            rows=rows,
        )

        case_detail_id = None

        case_detail = parse_pdf_case_details(pdf_path)

        if case_detail:
            case_detail_id = insert_case_detail(
                connection=connection,
                document_id=document_id,
            detail=case_detail,
        )

    return {
        "file_name": pdf_path.name,
        "status": "ingested",
        "document_id": document_id,
        "rows_found_in_pdf": len(rows),
        "rows_added": rows_added,
        "rows_skipped_as_duplicates": rows_skipped,
        "case_detail_id": case_detail_id,
        "case_detail_added": case_detail_id is not None,
    }


def ingest_folder(folder: Path = RAW_DIR) -> list[dict[str, Any]]:
    folder = Path(folder)

    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    results = []

    for pdf_path in sorted(folder.glob("*.pdf")):
        result = ingest_pdf(pdf_path)
        results.append(result)

    return results