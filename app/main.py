from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi.middleware.cors import CORSMiddleware

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from pydantic import BaseModel, Field
from app.rag.llama_rag import answer_question_with_llama, llama_status

from app.retrieval.vector_store import (
    index_document,
    semantic_search,
    vector_index_status,
)

from app.db.database import get_connection, init_db
from app.ingestion.ingest_service import RAW_DIR, ingest_pdf, safe_filename, unique_path


app = FastAPI(
    title="Jammu Cause List RAG",
    description="Search and RAG system for Jammu District Court cause-list PDFs.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    limit: int = Field(default=10, ge=1, le=30)

@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    clean_name = safe_filename(file.filename)
    destination = unique_path(RAW_DIR, clean_name)

    try:
        with destination.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = ingest_pdf(destination)

        if result.get("status") == "ingested" and result.get("document_id"):
            try:
                result["vector_chunks_indexed"] = index_document(result["document_id"])
            except Exception as exc:
                result["vector_index_error"] = str(exc)

        if result["status"] == "already_exists":
            try:
                destination.unlink()
            except FileNotFoundError:
                pass

        return result

    except Exception as exc:
        try:
            destination.unlink()
        except FileNotFoundError:
            pass

        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/documents")
def list_documents() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                file_name,
                stored_path,
                file_hash,
                uploaded_at,
                page_count,
                court_establishment,
                court_number,
                judge_name,
                case_category,
                cause_list_date
            FROM documents
            ORDER BY uploaded_at DESC, id DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


@app.get("/cases")
def search_cases(
    q: str | None = Query(default=None, description="General search text"),
    listing_date: str | None = Query(default=None, description="Example: 20-03-2026"),
    court_number: str | None = Query(default=None, description="Example: 14"),
    stage: str | None = Query(default=None, description="Example: ARGUMENTS"),
    advocate: str | None = Query(default=None, description="Example: AKASH GUPTA"),
    case_reference: str | None = Query(default=None, description="Example: Complaint/1344/2024"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    sql = """
        SELECT
            id,
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
        FROM cause_list_items
        WHERE 1 = 1
    """

    params: list[Any] = []

    if q:
        sql += """
            AND LOWER(
                COALESCE(case_reference, '') || ' ' ||
                COALESCE(party_name, '') || ' ' ||
                COALESCE(advocate, '') || ' ' ||
                COALESCE(stage, '') || ' ' ||
                COALESCE(judge_name, '') || ' ' ||
                COALESCE(court_establishment, '')
            ) LIKE LOWER(?)
        """
        params.append(f"%{q}%")

    if listing_date:
        sql += " AND listing_date = ?"
        params.append(listing_date)

    if court_number:
        sql += " AND court_number = ?"
        params.append(court_number)

    if stage:
        sql += " AND LOWER(stage) LIKE LOWER(?)"
        params.append(f"%{stage}%")

    if advocate:
        sql += " AND LOWER(advocate) LIKE LOWER(?)"
        params.append(f"%{advocate}%")

    if case_reference:
        sql += " AND LOWER(case_reference) LIKE LOWER(?)"
        params.append(f"%{case_reference}%")

    sql += """
        ORDER BY
            listing_date,
            CAST(court_number AS INTEGER),
            serial_number
        LIMIT ?
    """
    params.append(limit)

    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()

    return {
        "count": len(rows),
        "results": [dict(row) for row in rows],
    }

@app.get("/case-details")
def search_case_details(
    q: str | None = Query(default=None, description="General search text"),
    registration_number: str | None = Query(default=None, description="Example: 1344/2024"),
    cnr_number: str | None = Query(default=None, description="Example: JKJM030067592024"),
    stage: str | None = Query(default=None, description="Example: Prosecution Evidence"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    sql = """
        SELECT
            id,
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
            court_number_and_judge
        FROM case_details
        WHERE 1 = 1
    """

    params: list[Any] = []

    if q:
        sql += """
            AND LOWER(
                COALESCE(case_type, '') || ' ' ||
                COALESCE(filing_number, '') || ' ' ||
                COALESCE(registration_number, '') || ' ' ||
                COALESCE(cnr_number, '') || ' ' ||
                COALESCE(stage_of_case, '') || ' ' ||
                COALESCE(court_number_and_judge, '') || ' ' ||
                COALESCE(detail_text, '')
            ) LIKE LOWER(?)
        """
        params.append(f"%{q}%")

    if registration_number:
        sql += " AND registration_number = ?"
        params.append(registration_number)

    if cnr_number:
        sql += " AND cnr_number = ?"
        params.append(cnr_number)

    if stage:
        sql += " AND LOWER(stage_of_case) LIKE LOWER(?)"
        params.append(f"%{stage}%")

    sql += """
        ORDER BY id
        LIMIT ?
    """
    params.append(limit)

    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()

    return {
        "count": len(rows),
        "results": [dict(row) for row in rows],
    }


@app.get("/case-details/{case_detail_id}")
def get_case_detail(case_detail_id: int) -> dict[str, Any]:
    with get_connection() as connection:
        case_row = connection.execute(
            """
            SELECT
                id,
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
            FROM case_details
            WHERE id = ?
            """,
            (case_detail_id,),
        ).fetchone()

        if case_row is None:
            raise HTTPException(status_code=404, detail="Case detail not found.")

        def child_rows(table_name: str) -> list[dict[str, Any]]:
            rows = connection.execute(
                f"""
                SELECT *
                FROM {table_name}
                WHERE case_detail_id = ?
                ORDER BY id
                """,
                (case_detail_id,),
            ).fetchall()

            return [dict(row) for row in rows]

        return {
            "case_detail": dict(case_row),
            "parties": child_rows("case_parties"),
            "acts": child_rows("case_acts"),
            "fir_details": child_rows("case_fir_details"),
            "case_history": child_rows("case_history"),
            "process_details": child_rows("case_process_details"),
            "case_transfers": child_rows("case_transfers"),
            "subordinate_courts": child_rows("case_subordinate_courts"),
            "orders": child_rows("case_orders"),
        }
    
@app.get("/vector/status")
def get_vector_status() -> dict[str, Any]:
    return vector_index_status()


@app.get("/semantic-search")
def semantic_search_endpoint(
    q: str = Query(..., description="Semantic search query"),
    limit: int = Query(default=10, ge=1, le=50),
    chunk_type: str | None = Query(default=None),
    listing_date: str | None = Query(default=None, description="Example: 20-03-2026"),
    stage: str | None = Query(default=None, description="Example: Prosecution Evidence"),
    registration_number: str | None = Query(default=None, description="Example: 1344/2024"),
    cnr_number: str | None = Query(default=None, description="Example: JKJM030067592024"),
    source_file: str | None = Query(default=None),
) -> dict[str, Any]:
    filters: dict[str, Any] = {}

    if chunk_type:
        filters["chunk_type"] = chunk_type

    if listing_date:
        filters["listing_date"] = listing_date

    if stage:
        filters["stage_lower"] = stage.lower().strip()

    if registration_number:
        filters["registration_number"] = registration_number

    if cnr_number:
        filters["cnr_number"] = cnr_number

    if source_file:
        filters["source_file"] = source_file

    results = semantic_search(
        query=q,
        limit=limit,
        filters=filters,
    )

    return {
        "query": q,
        "count": len(results),
        "results": results,
    }

@app.get("/llama/status")
def get_llama_status() -> dict[str, Any]:
    return llama_status()


@app.post("/ask")
def ask_question(request: AskRequest) -> dict[str, Any]:
    return answer_question_with_llama(
        question=request.question,
        limit=request.limit,
    )