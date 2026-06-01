from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv
from ollama import Client

from app.db.database import get_connection
from app.retrieval.vector_store import semantic_search


load_dotenv()


REGISTRATION_PATTERN = re.compile(r"\b\d{1,6}/\d{4}\b")
CNR_PATTERN = re.compile(r"\b[A-Z]{4}\d{8,}\b", flags=re.IGNORECASE)

SYSTEM_PROMPT = """
You are a Jammu District Court cause-list assistant.

Rules:
1. Answer only from the provided context.
2. Do not invent facts.
3. If the answer is not found in the context, say: "I could not find this in the indexed documents."
4. Cite factual claims using source markers like [S1], [S2].
5. Do not give legal advice. Only summarize the indexed court/cause-list data.
6. Prefer exact case-detail records over semantic/vector snippets when both are available.
7. Keep the answer practical and concise for a lawyer checking cause-list information.
8. Do not mention that it is according to retrieved context or similar, just give the answer.
""".strip()


def clean(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def extract_registration_numbers(question: str) -> list[str]:
    return list(dict.fromkeys(REGISTRATION_PATTERN.findall(question)))


def extract_cnr_numbers(question: str) -> list[str]:
    return list(dict.fromkeys(match.upper() for match in CNR_PATTERN.findall(question)))


def case_label(row: dict[str, Any]) -> str:
    case_type = clean(row.get("case_type"))
    registration_number = clean(row.get("registration_number"))

    if case_type and registration_number:
        return f"{case_type}/{registration_number}"

    return registration_number or case_type or "Case"


def case_detail_to_text(row: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in [
            "Case detail record.",
            f"Case: {case_label(row)}.",
            f"Registration number: {clean(row.get('registration_number'))}.",
            f"CNR number: {clean(row.get('cnr_number'))}.",
            f"Filing number: {clean(row.get('filing_number'))}.",
            f"Filing date: {clean(row.get('filing_date'))}.",
            f"Registration date: {clean(row.get('registration_date'))}.",
            f"First hearing date: {clean(row.get('first_hearing_date'))}.",
            f"Next hearing date: {clean(row.get('next_hearing_date'))}.",
            f"Case status: {clean(row.get('case_status'))}.",
            f"Stage of case: {clean(row.get('stage_of_case'))}.",
            f"Court and judge: {clean(row.get('court_number_and_judge'))}.",
            f"Source file: {clean(row.get('source_file'))}, page {clean(row.get('source_page'))}.",
        ]
        if clean(part)
    )


def cause_list_to_text(row: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in [
            "Cause-list item.",
            f"Listing date: {clean(row.get('listing_date'))}.",
            f"Court establishment: {clean(row.get('court_establishment'))}.",
            f"Court number: {clean(row.get('court_number'))}.",
            f"Judge: {clean(row.get('judge_name'))}.",
            f"Case category: {clean(row.get('case_category'))}.",
            f"Stage: {clean(row.get('stage'))}.",
            f"Serial number: {clean(row.get('serial_number'))}.",
            f"Case reference: {clean(row.get('case_reference'))}.",
            f"Party name: {clean(row.get('party_name'))}.",
            f"Advocate: {clean(row.get('advocate'))}.",
            f"Source file: {clean(row.get('source_file'))}, page {clean(row.get('source_page'))}.",
        ]
        if clean(part)
    )


def fetch_child_rows(connection, table_name: str, case_detail_id: int) -> list[dict[str, Any]]:
    allowed_tables = {
        "case_parties",
        "case_acts",
        "case_fir_details",
        "case_history",
        "case_process_details",
        "case_transfers",
        "case_subordinate_courts",
        "case_orders",
    }

    if table_name not in allowed_tables:
        raise ValueError(f"Unsupported table: {table_name}")

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


def enrich_case_detail_text(connection, row: dict[str, Any]) -> str:
    case_detail_id = row["id"]

    parts = [case_detail_to_text(row)]

    parties = fetch_child_rows(connection, "case_parties", case_detail_id)
    acts = fetch_child_rows(connection, "case_acts", case_detail_id)
    firs = fetch_child_rows(connection, "case_fir_details", case_detail_id)
    processes = fetch_child_rows(connection, "case_process_details", case_detail_id)
    transfers = fetch_child_rows(connection, "case_transfers", case_detail_id)
    subordinate_courts = fetch_child_rows(connection, "case_subordinate_courts", case_detail_id)

    recent_history = connection.execute(
        """
        SELECT *
        FROM case_history
        WHERE case_detail_id = ?
        ORDER BY id DESC
        LIMIT 12
        """,
        (case_detail_id,),
    ).fetchall()

    history = [dict(item) for item in reversed(recent_history)]

    for party in parties:
        parts.append(
            (
                f"{clean(party.get('party_type')).title()} "
                f"{clean(party.get('party_number'))}: "
                f"{clean(party.get('party_name'))}; "
                f"Advocate: {clean(party.get('advocate_name')) or 'not recorded'}."
            )
        )

    for act in acts:
        parts.append(
            f"Act: {clean(act.get('act_name'))}; Sections: {clean(act.get('section_text'))}."
        )

    for fir in firs:
        parts.append(
            (
                f"FIR details: Police station {clean(fir.get('police_station'))}; "
                f"FIR number {clean(fir.get('fir_number'))}; "
                f"Year {clean(fir.get('fir_year'))}."
            )
        )

    for process in processes:
        parts.append(
            (
                f"Process details: Process date {clean(process.get('process_date'))}; "
                f"Process title {clean(process.get('process_title'))}; "
                f"Issued process {clean(process.get('issued_process'))}."
            )
        )

    for transfer in transfers:
        parts.append(
            (
                f"Transfer details: Transfer date {clean(transfer.get('transfer_date'))}; "
                f"From court {clean(transfer.get('from_court'))}; "
                f"To court {clean(transfer.get('to_court'))}."
            )
        )

    for subordinate in subordinate_courts:
        parts.append(
            (
                f"Subordinate court information: Court {clean(subordinate.get('court_number_and_name'))}; "
                f"Case number and year {clean(subordinate.get('case_number_and_year'))}; "
                f"Decision date {clean(subordinate.get('case_decision_date'))}."
            )
        )

    if history:
        parts.append("Recent case history:")
        for item in history:
            parts.append(
                (
                    f"Business on date {clean(item.get('business_on_date'))}; "
                    f"Hearing date {clean(item.get('hearing_date'))}; "
                    f"Purpose {clean(item.get('purpose_of_hearing'))}; "
                    f"Judge {clean(item.get('judge'))}."
                )
            )

    return " ".join(parts)


def sql_exact_retrieve(question: str, limit: int = 6) -> list[dict[str, Any]]:
    registration_numbers = extract_registration_numbers(question)
    cnr_numbers = extract_cnr_numbers(question)

    if not registration_numbers and not cnr_numbers:
        return []

    evidence: list[dict[str, Any]] = []

    with get_connection() as connection:
        conditions = []
        params: list[Any] = []

        for registration_number in registration_numbers:
            conditions.append("registration_number = ?")
            params.append(registration_number)

        for cnr_number in cnr_numbers:
            conditions.append("UPPER(cnr_number) = ?")
            params.append(cnr_number)

        if conditions:
            rows = connection.execute(
                f"""
                SELECT *
                FROM case_details
                WHERE {" OR ".join(conditions)}
                ORDER BY id
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()

            for row_obj in rows:
                row = dict(row_obj)

                evidence.append(
                    {
                        "chunk_id": f"sql_case_detail:{row['id']}",
                        "score": 1.0,
                        "text": enrich_case_detail_text(connection, row),
                        "metadata": {
                            "chunk_type": "sql_case_detail",
                            "source_file": row.get("source_file"),
                            "source_page": row.get("source_page"),
                            "case_reference": case_label(row),
                            "registration_number": row.get("registration_number"),
                            "cnr_number": row.get("cnr_number"),
                            "stage": row.get("stage_of_case"),
                        },
                    }
                )

        for registration_number in registration_numbers:
            rows = connection.execute(
                """
                SELECT *
                FROM cause_list_items
                WHERE case_reference LIKE ?
                ORDER BY listing_date, CAST(court_number AS INTEGER), serial_number
                LIMIT ?
                """,
                (f"%{registration_number}%", limit),
            ).fetchall()

            for row_obj in rows:
                row = dict(row_obj)

                evidence.append(
                    {
                        "chunk_id": f"sql_cause_list_item:{row['id']}",
                        "score": 0.98,
                        "text": cause_list_to_text(row),
                        "metadata": {
                            "chunk_type": "sql_cause_list_item",
                            "source_file": row.get("source_file"),
                            "source_page": row.get("source_page"),
                            "case_reference": row.get("case_reference"),
                            "listing_date": row.get("listing_date"),
                            "stage": row.get("stage"),
                            "court_number": row.get("court_number"),
                            "judge_name": row.get("judge_name"),
                            "party_name": row.get("party_name"),
                            "advocate": row.get("advocate"),
                        },
                    }
                )

    return evidence[:limit]


def dedupe_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []

    for item in evidence:
        key = clean(item.get("chunk_id"))

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


def retrieve_evidence(question: str, limit: int = 10) -> list[dict[str, Any]]:
    exact = sql_exact_retrieve(question, limit=max(4, limit // 2))
    semantic = semantic_search(question, limit=limit)

    combined = dedupe_evidence(exact + semantic)

    combined.sort(
        key=lambda item: item.get("score") if item.get("score") is not None else 0,
        reverse=True,
    )

    return combined[:limit]


def build_context(evidence: list[dict[str, Any]], max_chars: int = 14000) -> str:
    blocks = []
    used_chars = 0

    for index, item in enumerate(evidence, start=1):
        metadata = item.get("metadata", {})

        header = " | ".join(
            part
            for part in [
                f"Source [S{index}]",
                f"file={clean(metadata.get('source_file'))}",
                f"page={clean(metadata.get('source_page'))}",
                f"chunk_type={clean(metadata.get('chunk_type'))}",
                f"case_reference={clean(metadata.get('case_reference'))}",
                f"registration_number={clean(metadata.get('registration_number'))}",
                f"cnr_number={clean(metadata.get('cnr_number'))}",
                f"stage={clean(metadata.get('stage'))}",
            ]
            if not part.endswith("=")
        )

        block = f"{header}\n{clean(item.get('text'))}"

        if used_chars + len(block) > max_chars:
            break

        blocks.append(block)
        used_chars += len(block)

    return "\n\n".join(blocks)


def build_sources(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = []

    for index, item in enumerate(evidence, start=1):
        metadata = item.get("metadata", {})

        sources.append(
            {
                "source_number": f"S{index}",
                "chunk_id": item.get("chunk_id"),
                "score": item.get("score"),
                "source_file": metadata.get("source_file"),
                "source_page": metadata.get("source_page"),
                "chunk_type": metadata.get("chunk_type"),
                "case_reference": metadata.get("case_reference"),
                "registration_number": metadata.get("registration_number"),
                "cnr_number": metadata.get("cnr_number"),
                "stage": metadata.get("stage"),
                "listing_date": metadata.get("listing_date"),
                "court_number": metadata.get("court_number"),
                "judge_name": metadata.get("judge_name"),
                "party_name": metadata.get("party_name"),
                "advocate": metadata.get("advocate"),
                "text_preview": clean(item.get("text"))[:500],
            }
        )

    return sources


def generate_llama_answer(question: str, evidence: list[dict[str, Any]]) -> str:
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    context = build_context(evidence)

    user_prompt = f"""
Question:
{question}

Retrieved context:
{context}

Answer the question using only the retrieved context.
Use source markers like [S1], [S2].
""".strip()

    client = Client(host=host)

    response = client.chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        options={
            "temperature": 0,
            "num_predict": 700,
        },
        stream=False,
    )

    return response["message"]["content"]


def answer_question_with_llama(question: str, limit: int = 10) -> dict[str, Any]:
    question = clean(question)

    if not question:
        return {
            "question": question,
            "mode": "llama_local_error",
            "answer": "Please provide a question.",
            "evidence_count": 0,
            "sources": [],
        }

    evidence = retrieve_evidence(question, limit=limit)

    if not evidence:
        return {
            "question": question,
            "mode": "llama_local_no_evidence",
            "answer": "I could not find this in the indexed documents.",
            "evidence_count": 0,
            "sources": [],
        }

    answer = generate_llama_answer(question, evidence)

    return {
        "question": question,
        "mode": "llama_local_ollama",
        "model": os.getenv("OLLAMA_MODEL", "llama3.2"),
        "answer": answer,
        "evidence_count": len(evidence),
        "sources": build_sources(evidence),
    }


def llama_status() -> dict[str, Any]:
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    client = Client(host=host)

    try:
        models = client.list()
        return {
            "status": "ok",
            "host": host,
            "configured_model": model,
            "models": models,
        }
    except Exception as exc:
        return {
            "status": "error",
            "host": host,
            "configured_model": model,
            "error": str(exc),
        }