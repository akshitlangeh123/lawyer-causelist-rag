from __future__ import annotations

from typing import Any

from app.db.database import get_connection


CHILD_TABLES = {
    "case_parties",
    "case_acts",
    "case_fir_details",
    "case_history",
    "case_process_details",
    "case_transfers",
    "case_subordinate_courts",
    "case_orders",
}


def clean(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def metadata_value(value: Any) -> str | int | float | bool:
    if isinstance(value, bool | int | float):
        return value

    return clean(value)


def compact_sentence(value: str) -> str:
    value = clean(value)

    if not value:
        return ""

    if value.endswith("."):
        return value

    return f"{value}."


def join_sentences(parts: list[str]) -> str:
    return " ".join(compact_sentence(part) for part in parts if clean(part))


def grouped(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def case_reference_for_detail(row: dict[str, Any]) -> str:
    case_type = clean(row.get("case_type"))
    registration_number = clean(row.get("registration_number"))

    if case_type and registration_number:
        return f"{case_type}/{registration_number}"

    return case_type or registration_number


def base_case_metadata(row: dict[str, Any], chunk_type: str) -> dict[str, Any]:
    case_reference = case_reference_for_detail(row)
    stage = clean(row.get("stage_of_case"))

    return {
        "chunk_type": chunk_type,
        "document_id": metadata_value(row.get("document_id")),
        "case_detail_id": metadata_value(row.get("id")),
        "source_file": metadata_value(row.get("source_file")),
        "source_page": metadata_value(row.get("source_page")),
        "case_reference": metadata_value(case_reference),
        "case_reference_lower": metadata_value(case_reference.lower()),
        "case_type": metadata_value(row.get("case_type")),
        "registration_number": metadata_value(row.get("registration_number")),
        "cnr_number": metadata_value(row.get("cnr_number")),
        "stage": metadata_value(stage),
        "stage_lower": metadata_value(stage.lower()),
        "court_number_and_judge": metadata_value(row.get("court_number_and_judge")),
    }


def fetch_children(
    connection,
    table_name: str,
    case_detail_id: int,
) -> list[dict[str, Any]]:
    if table_name not in CHILD_TABLES:
        raise ValueError(f"Unsupported child table: {table_name}")

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


def build_cause_list_chunks(document_id: int | None = None) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []

    where_sql = ""
    params: list[Any] = []

    if document_id is not None:
        where_sql = "WHERE document_id = ?"
        params.append(document_id)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
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
            {where_sql}
            ORDER BY listing_date, court_number, serial_number
            """,
            params,
        ).fetchall()

    for row_obj in rows:
        row = dict(row_obj)

        stage = clean(row.get("stage"))
        case_reference = clean(row.get("case_reference"))
        advocate = clean(row.get("advocate"))
        party_name = clean(row.get("party_name"))

        text = join_sentences(
            [
                "Cause-list item",
                f"Listing date: {clean(row.get('listing_date'))}",
                f"Court establishment: {clean(row.get('court_establishment'))}",
                f"Court number: {clean(row.get('court_number'))}",
                f"Judge: {clean(row.get('judge_name'))}",
                f"Case category: {clean(row.get('case_category'))}",
                f"Stage: {stage}",
                f"Serial number: {clean(row.get('serial_number'))}",
                f"Case reference: {case_reference}",
                f"Party name: {party_name}",
                f"Advocate: {advocate}",
                f"Source file: {clean(row.get('source_file'))}, page {clean(row.get('source_page'))}",
            ]
        )

        chunks.append(
            {
                "id": f"cause_list_item:{row['id']}",
                "text": text,
                "metadata": {
                    "chunk_type": "cause_list_item",
                    "document_id": metadata_value(row.get("document_id")),
                    "cause_list_item_id": metadata_value(row.get("id")),
                    "source_file": metadata_value(row.get("source_file")),
                    "source_page": metadata_value(row.get("source_page")),
                    "listing_date": metadata_value(row.get("listing_date")),
                    "court_establishment": metadata_value(row.get("court_establishment")),
                    "court_number": metadata_value(row.get("court_number")),
                    "judge_name": metadata_value(row.get("judge_name")),
                    "case_category": metadata_value(row.get("case_category")),
                    "stage": metadata_value(stage),
                    "stage_lower": metadata_value(stage.lower()),
                    "case_reference": metadata_value(case_reference),
                    "case_reference_lower": metadata_value(case_reference.lower()),
                    "case_type": metadata_value(row.get("case_type")),
                    "case_number": metadata_value(row.get("case_number")),
                    "case_year": metadata_value(row.get("case_year")),
                    "party_name": metadata_value(party_name),
                    "party_name_lower": metadata_value(party_name.lower()),
                    "advocate": metadata_value(advocate),
                    "advocate_lower": metadata_value(advocate.lower()),
                },
            }
        )

    return chunks


def build_case_detail_chunks(document_id: int | None = None) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []

    where_sql = ""
    params: list[Any] = []

    if document_id is not None:
        where_sql = "WHERE document_id = ?"
        params.append(document_id)

    with get_connection() as connection:
        detail_rows = connection.execute(
            f"""
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
            {where_sql}
            ORDER BY id
            """,
            params,
        ).fetchall()

        for detail_obj in detail_rows:
            detail = dict(detail_obj)
            case_detail_id = detail["id"]
            case_reference = case_reference_for_detail(detail)

            parties = fetch_children(connection, "case_parties", case_detail_id)
            acts = fetch_children(connection, "case_acts", case_detail_id)
            fir_details = fetch_children(connection, "case_fir_details", case_detail_id)
            history = fetch_children(connection, "case_history", case_detail_id)
            processes = fetch_children(connection, "case_process_details", case_detail_id)
            transfers = fetch_children(connection, "case_transfers", case_detail_id)
            subordinate_courts = fetch_children(
                connection,
                "case_subordinate_courts",
                case_detail_id,
            )
            orders = fetch_children(connection, "case_orders", case_detail_id)

            summary_text = join_sentences(
                [
                    "Case detail summary",
                    f"Case: {case_reference}",
                    f"Registration number: {clean(detail.get('registration_number'))}",
                    f"CNR number: {clean(detail.get('cnr_number'))}",
                    f"Filing number: {clean(detail.get('filing_number'))}",
                    f"Filing date: {clean(detail.get('filing_date'))}",
                    f"Registration date: {clean(detail.get('registration_date'))}",
                    f"First hearing date: {clean(detail.get('first_hearing_date'))}",
                    f"Next hearing date: {clean(detail.get('next_hearing_date'))}",
                    f"Case status: {clean(detail.get('case_status'))}",
                    f"Stage of case: {clean(detail.get('stage_of_case'))}",
                    f"Court and judge: {clean(detail.get('court_number_and_judge'))}",
                    f"Source file: {clean(detail.get('source_file'))}, page {clean(detail.get('source_page'))}",
                ]
            )

            chunks.append(
                {
                    "id": f"case_detail:{case_detail_id}:summary",
                    "text": summary_text,
                    "metadata": base_case_metadata(detail, "case_detail_summary"),
                }
            )

            if parties:
                party_lines = []

                for party in parties:
                    line = (
                        f"{clean(party.get('party_type')).title()} "
                        f"{clean(party.get('party_number'))}: "
                        f"{clean(party.get('party_name'))}"
                    )

                    if clean(party.get("advocate_name")):
                        line += f"; Advocate: {clean(party.get('advocate_name'))}"

                    party_lines.append(line)

                chunks.append(
                    {
                        "id": f"case_detail:{case_detail_id}:parties",
                        "text": join_sentences(
                            [
                                f"Parties and advocates for case {case_reference}",
                                *party_lines,
                            ]
                        ),
                        "metadata": base_case_metadata(detail, "case_parties"),
                    }
                )

            if acts or fir_details:
                act_lines = [
                    f"Act: {clean(act.get('act_name'))}; Sections: {clean(act.get('section_text'))}"
                    for act in acts
                ]

                fir_lines = [
                    (
                        f"FIR: Police station {clean(fir.get('police_station'))}; "
                        f"FIR number {clean(fir.get('fir_number'))}; "
                        f"Year {clean(fir.get('fir_year'))}"
                    )
                    for fir in fir_details
                ]

                chunks.append(
                    {
                        "id": f"case_detail:{case_detail_id}:acts_fir",
                        "text": join_sentences(
                            [
                                f"Acts and FIR details for case {case_reference}",
                                *act_lines,
                                *fir_lines,
                            ]
                        ),
                        "metadata": base_case_metadata(detail, "case_acts_fir"),
                    }
                )

            for group_index, history_group in enumerate(grouped(history, 12), start=1):
                history_lines = []

                for item in history_group:
                    history_lines.append(
                        (
                            f"Business on date: {clean(item.get('business_on_date'))}; "
                            f"Hearing date: {clean(item.get('hearing_date'))}; "
                            f"Purpose of hearing: {clean(item.get('purpose_of_hearing'))}; "
                            f"Judge: {clean(item.get('judge'))}"
                        )
                    )

                chunks.append(
                    {
                        "id": f"case_detail:{case_detail_id}:history:{group_index}",
                        "text": join_sentences(
                            [
                                f"Case history for case {case_reference}",
                                f"History chunk {group_index}",
                                *history_lines,
                            ]
                        ),
                        "metadata": base_case_metadata(detail, "case_history"),
                    }
                )

            if processes:
                process_lines = [
                    (
                        f"Process id {clean(process.get('process_id'))}; "
                        f"Process date {clean(process.get('process_date'))}; "
                        f"Process title {clean(process.get('process_title'))}; "
                        f"Issued process {clean(process.get('issued_process'))}"
                    )
                    for process in processes
                ]

                chunks.append(
                    {
                        "id": f"case_detail:{case_detail_id}:processes",
                        "text": join_sentences(
                            [
                                f"Process details for case {case_reference}",
                                *process_lines,
                            ]
                        ),
                        "metadata": base_case_metadata(detail, "case_process_details"),
                    }
                )

            if transfers:
                transfer_lines = [
                    (
                        f"Transfer date {clean(transfer.get('transfer_date'))}; "
                        f"From court {clean(transfer.get('from_court'))}; "
                        f"To court {clean(transfer.get('to_court'))}"
                    )
                    for transfer in transfers
                ]

                chunks.append(
                    {
                        "id": f"case_detail:{case_detail_id}:transfers",
                        "text": join_sentences(
                            [
                                f"Transfer details for case {case_reference}",
                                *transfer_lines,
                            ]
                        ),
                        "metadata": base_case_metadata(detail, "case_transfers"),
                    }
                )

            if subordinate_courts:
                subordinate_lines = [
                    (
                        f"Subordinate court {clean(subordinate.get('court_number_and_name'))}; "
                        f"Case number and year {clean(subordinate.get('case_number_and_year'))}; "
                        f"Decision date {clean(subordinate.get('case_decision_date'))}"
                    )
                    for subordinate in subordinate_courts
                ]

                chunks.append(
                    {
                        "id": f"case_detail:{case_detail_id}:subordinate_courts",
                        "text": join_sentences(
                            [
                                f"Subordinate court information for case {case_reference}",
                                *subordinate_lines,
                            ]
                        ),
                        "metadata": base_case_metadata(detail, "case_subordinate_courts"),
                    }
                )

            if orders:
                order_lines = [
                    (
                        f"Order number {clean(order.get('order_number'))}; "
                        f"Order date {clean(order.get('order_date'))}; "
                        f"Order details {clean(order.get('order_details'))}"
                    )
                    for order in orders
                ]

                chunks.append(
                    {
                        "id": f"case_detail:{case_detail_id}:orders",
                        "text": join_sentences(
                            [
                                f"Orders for case {case_reference}",
                                *order_lines,
                            ]
                        ),
                        "metadata": base_case_metadata(detail, "case_orders"),
                    }
                )

    return chunks


def build_chunks_from_db(document_id: int | None = None) -> list[dict[str, Any]]:
    return build_cause_list_chunks(document_id=document_id) + build_case_detail_chunks(
        document_id=document_id
    )