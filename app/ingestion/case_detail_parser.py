from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf


def clean_cell(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def header_text(row: list[Any]) -> str:
    return normalize(" ".join(clean_cell(cell) for cell in row))


def first_non_empty_data_row(rows: list[list[Any]]) -> list[str] | None:
    for row in rows[1:]:
        cells = [clean_cell(cell) for cell in row]

        if any(cells):
            return cells

    return None


def cell_at(row: list[str], index: int) -> str:
    return row[index] if index < len(row) else ""


def extract_detail_text(doc: pymupdf.Document) -> tuple[str, int | None]:
    """
    Extract text from the Case Details section onward.
    """
    started = False
    parts: list[str] = []
    first_page: int | None = None

    for page_index, page in enumerate(doc, start=1):
        text = page.get_text("text")

        if not started:
            start_index = text.find("Case Details")

            if start_index == -1:
                continue

            started = True
            first_page = page_index
            parts.append(f"--- PAGE {page_index} ---\n{text[start_index:]}")

        else:
            parts.append(f"--- PAGE {page_index} ---\n{text}")

    return "\n".join(parts), first_page


def detail_lines(detail_text: str) -> list[str]:
    lines: list[str] = []

    for line in detail_text.splitlines():
        line = clean_cell(line)

        if not line:
            continue

        if line.startswith("--- PAGE"):
            continue

        if line.startswith("22/03/2026"):
            continue

        if "about:blank" in line:
            continue

        if re.fullmatch(r"\d+/\d+", line):
            continue

        lines.append(line)

    return lines


def extract_block(
    lines: list[str],
    start_heading: str,
    end_headings: set[str],
) -> list[str]:
    start_norm = normalize(start_heading)
    start_index = None

    for index, line in enumerate(lines):
        if normalize(line) == start_norm:
            start_index = index + 1
            break

    if start_index is None:
        return []

    block: list[str] = []

    for line in lines[start_index:]:
        if normalize(line) in end_headings:
            break

        block.append(line)

    return block


def parse_party_block(block: list[str], party_type: str) -> list[dict[str, Any]]:
    parties: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current

        if current and current.get("party_name"):
            current["party_name"] = clean_cell(current["party_name"])
            current["advocate_name"] = clean_cell(current.get("advocate_name", ""))
            parties.append(current)

        current = None

    for raw_line in block:
        line = re.sub(r"^[•\-]\s*", "", clean_cell(raw_line))

        if not line:
            continue

        lower = line.lower()

        if lower.startswith("advocate -"):
            if current is not None:
                current["advocate_name"] = clean_cell(line.split("-", 1)[1])
            continue

        match = re.match(r"^(\d+)\)\s*(.+)$", line)

        if match:
            flush()

            current = {
                "party_type": party_type,
                "party_number": int(match.group(1)),
                "party_name": match.group(2).strip(),
                "advocate_name": "",
            }

            continue

        if current is not None:
            current["party_name"] = clean_cell(current["party_name"] + " " + line)

    flush()
    return parties


def parse_parties(detail_text: str) -> list[dict[str, Any]]:
    lines = detail_lines(detail_text)

    petitioner_end_headings = {
        normalize(value)
        for value in [
            "Respondent and Advocate",
            "Acts",
            "FIR Details",
            "IA Status",
            "Case History",
            "Subordinate Court Information",
            "Process Details",
            "Case Transfer Details within Establishment",
            "Orders",
            "Back",
        ]
    }

    respondent_end_headings = {
        normalize(value)
        for value in [
            "Acts",
            "FIR Details",
            "IA Status",
            "Case History",
            "Subordinate Court Information",
            "Process Details",
            "Case Transfer Details within Establishment",
            "Orders",
            "Back",
        ]
    }

    petitioner_block = extract_block(
        lines=lines,
        start_heading="Petitioner and Advocate",
        end_headings=petitioner_end_headings,
    )

    respondent_block = extract_block(
        lines=lines,
        start_heading="Respondent and Advocate",
        end_headings=respondent_end_headings,
    )

    return (
        parse_party_block(petitioner_block, "petitioner")
        + parse_party_block(respondent_block, "respondent")
    )


def extract_court_from_status_header(header_cells: list[str]) -> str:
    if len(header_cells) < 5:
        return ""

    value = clean_cell(header_cells[4])
    match = re.match(r"court number and judge\s+(.+)$", value, flags=re.IGNORECASE)

    if match:
        return clean_cell(match.group(1))

    return ""


def parse_status_row(header_cells: list[str], row: list[str]) -> dict[str, str]:
    """
    Handles normal rows like:
        first, next, status, stage, court

    Also handles shifted rows where Next Hearing Date is missing:
        first, status, stage, court, ""

    Also handles rows where the court value accidentally appears in the header.
    """
    known_statuses = {
        "pending",
        "disposed",
        "decided",
        "closed",
        "transferred",
    }

    court_from_header = extract_court_from_status_header(header_cells)

    first_hearing_date = cell_at(row, 0)
    next_hearing_date = cell_at(row, 1)
    case_status = cell_at(row, 2)
    stage_of_case = cell_at(row, 3)
    court_number_and_judge = cell_at(row, 4) or court_from_header

    if not cell_at(row, 4) and normalize(cell_at(row, 1)) in known_statuses:
        next_hearing_date = ""
        case_status = cell_at(row, 1)
        stage_of_case = cell_at(row, 2)
        court_number_and_judge = cell_at(row, 3) or court_from_header

    return {
        "first_hearing_date": first_hearing_date,
        "next_hearing_date": next_hearing_date,
        "case_status": case_status,
        "stage_of_case": stage_of_case,
        "court_number_and_judge": court_number_and_judge,
    }


def parse_pdf_case_details(pdf_path: Path) -> dict[str, Any] | None:
    pdf_path = Path(pdf_path)
    doc = pymupdf.open(pdf_path)

    detail_text, source_page = extract_detail_text(doc)

    if not detail_text:
        doc.close()
        return None

    case_detail: dict[str, Any] = {
        "source_file": pdf_path.name,
        "source_page": source_page,
        "case_type": "",
        "filing_number": "",
        "filing_date": "",
        "registration_number": "",
        "registration_date": "",
        "cnr_number": "",
        "first_hearing_date": "",
        "next_hearing_date": "",
        "case_status": "",
        "stage_of_case": "",
        "court_number_and_judge": "",
        "detail_text": detail_text,
        "parties": parse_parties(detail_text),
        "acts": [],
        "fir_details": [],
        "case_history": [],
        "process_details": [],
        "case_transfers": [],
        "subordinate_courts": [],
        "orders": [],
    }

    for page_index, page in enumerate(doc, start=1):
        try:
            tables = page.find_tables().tables
        except Exception:
            continue

        for table in tables:
            raw_rows = table.extract()

            if not raw_rows:
                continue

            rows = [[clean_cell(cell) for cell in row] for row in raw_rows]
            header_cells = rows[0]
            header = header_text(header_cells)

            if (
                "case type" in header
                and "filing number" in header
                and "cnr number" in header
                and "serial" not in header
            ):
                row = first_non_empty_data_row(rows)

                if row:
                    case_detail.update(
                        {
                            "case_type": cell_at(row, 0),
                            "filing_number": cell_at(row, 1),
                            "filing_date": cell_at(row, 2),
                            "registration_number": cell_at(row, 3),
                            "registration_date": cell_at(row, 4),
                            "cnr_number": cell_at(row, 5),
                        }
                    )

            elif "first hearing" in header and "stage of case" in header:
                row = first_non_empty_data_row(rows)

                if row and not case_detail["first_hearing_date"]:
                    case_detail.update(parse_status_row(header_cells, row))

            elif "under act" in header and "under section" in header:
                for row in rows[1:]:
                    if any(row):
                        case_detail["acts"].append(
                            {
                                "act_name": cell_at(row, 0),
                                "section_text": cell_at(row, 1),
                            }
                        )

            elif "police station" in header and "fir number" in header:
                for row in rows[1:]:
                    if any(row):
                        case_detail["fir_details"].append(
                            {
                                "police_station": cell_at(row, 0),
                                "fir_number": cell_at(row, 1),
                                "fir_year": cell_at(row, 2),
                            }
                        )

            elif (
                "registration number" in header
                and "business on" in header
                and "purpose" in header
            ):
                for row in rows[1:]:
                    if any(row):
                        case_detail["case_history"].append(
                            {
                                "registration_number": cell_at(row, 0),
                                "judge": cell_at(row, 1),
                                "business_on_date": cell_at(row, 2),
                                "hearing_date": cell_at(row, 3),
                                "purpose_of_hearing": cell_at(row, 4),
                            }
                        )

            elif "process id" in header and "process date" in header:
                for row in rows[1:]:
                    if any(row):
                        case_detail["process_details"].append(
                            {
                                "process_id": cell_at(row, 0),
                                "process_date": cell_at(row, 1),
                                "process_title": cell_at(row, 2),
                                "issued_process": cell_at(row, 3),
                            }
                        )

            elif "transfer date" in header and "from court" in header and "to court" in header:
                for row in rows[1:]:
                    if any(row):
                        case_detail["case_transfers"].append(
                            {
                                "registration_number": cell_at(row, 0),
                                "transfer_date": cell_at(row, 1),
                                "from_court": cell_at(row, 2),
                                "to_court": cell_at(row, 3),
                            }
                        )

            elif "court number and name" in header and "case number and year" in header:
                for row in rows[1:]:
                    if any(row):
                        case_detail["subordinate_courts"].append(
                            {
                                "court_number_and_name": cell_at(row, 0),
                                "case_number_and_year": cell_at(row, 1),
                                "case_decision_date": cell_at(row, 2),
                            }
                        )

            elif "order number" in header and "order date" in header:
                for row in rows[1:]:
                    if any(row):
                        case_detail["orders"].append(
                            {
                                "order_number": cell_at(row, 0),
                                "order_date": cell_at(row, 1),
                                "order_details": cell_at(row, 2),
                            }
                        )

    doc.close()
    return case_detail