from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any

import pymupdf


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

DOCUMENTS_CSV = PROCESSED_DIR / "documents.csv"
CAUSE_LIST_CSV = PROCESSED_DIR / "cause_list_items.csv"


def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def repair_case_reference(prefix: str, case_reference: str) -> str:
    """
    Fix small table-extraction issues where the first character of a linked
    case reference sometimes lands in the serial-number cell.

    Example:
    serial cell: 'C 58 C'
    case cell:   'hallan ase/24037/2011'
    fixed:       'Challan Case/24037/2011'
    """
    combined = clean_cell((prefix + " " + case_reference).strip())

    replacements = [
        (r"^C\s+C\s+hallan\s+ase/", "Challan Case/"),
        (r"^C\s+hallan\s+ase/", "Challan Case/"),
        (r"^C\s+hallan\s+Case/", "Challan Case/"),
        (r"^hallan\s+ase/", "Challan Case/"),
        (r"^hallan\s+Case/", "Challan Case/"),
        (r"^1\s+38\b", "138"),
    ]

    for pattern, replacement in replacements:
        combined = re.sub(pattern, replacement, combined, flags=re.IGNORECASE)

    combined = re.sub(r"\s+/", "/", combined)
    return combined


def parse_case_reference(case_reference: str) -> tuple[str, str, str]:
    """
    Convert:
        Complaint/1344/2024
    into:
        Complaint, 1344, 2024
    """
    parts = case_reference.rsplit("/", 2)

    if (
        len(parts) == 3
        and parts[1].strip().isdigit()
        and re.fullmatch(r"\d{4}", parts[2].strip())
    ):
        return parts[0].strip(), parts[1].strip(), parts[2].strip()

    return case_reference, "", ""


def extract_lines(page: pymupdf.Page) -> list[dict[str, Any]]:
    page_dict = page.get_text("dict")
    lines: list[dict[str, Any]] = []

    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            text = clean_cell(text)

            if not text:
                continue

            lines.append(
                {
                    "text": text,
                    "bbox": line["bbox"],
                }
            )

    return lines


def first_back_y(lines: list[dict[str, Any]]) -> float | None:
    """
    Cause-list tables appear before the Back button.
    Case Details tables usually appear after the Back button.
    """
    ys = [
        line["bbox"][1]
        for line in lines
        if line["text"].strip().lower() == "back"
    ]

    return min(ys) if ys else None


def is_cause_list_table(table: Any) -> bool:
    rows = table.extract()

    if not rows:
        return False

    header = " ".join(clean_cell(cell).lower() for cell in rows[0])

    return (
        "serial" in header
        and "case type" in header
        and "party name" in header
        and "advocate" in header
    )


def likely_stage_text(text: str) -> bool:
    text = text.strip()
    lower = text.lower()

    if not text:
        return False

    ignore_exact = {
        "audio",
        "refresh",
        "search",
        "reset",
        "back",
        "court complex",
        "court establishment",
        "court complex *",
        "select court complex",
        "court number *",
        "select court",
        "cause list date *",
        "mm/dd/yy",
        "calendar",
        "civil",
        "criminal",
        "please select radio button",
        "please enter the captcha *",
        "enter captch",
        "this form needs javascript activated to work.",
        "all fields marked with * are required",
    }

    if lower in ignore_exact:
        return False

    if lower.startswith("about:blank"):
        return False

    if "in the court of" in lower:
        return False

    if "cases listed on" in lower:
        return False

    if any(token in lower for token in ["serial", "case type", "party name", "advocate"]):
        return False

    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}.*", text):
        return False

    if re.fullmatch(r"\d+/\d+", text):
        return False

    if len(text) > 90:
        return False

    return True


def stage_above_table(
    lines: list[dict[str, Any]],
    table_bbox: tuple[float, float, float, float],
    current_stage: str,
) -> str:
    """
    Finds the heading immediately above a table.

    Example:
        ARGUMENTS
        [table]

    If a table continues on the next page and no heading is visible,
    keep the previous stage.
    """
    _x0, y0, _x1, _y1 = table_bbox

    candidates: list[tuple[float, str]] = []

    for line in lines:
        text = line["text"]
        _lx0, ly0, _lx1, ly1 = line["bbox"]

        if ly1 <= y0 + 4 and ly0 >= y0 - 45 and likely_stage_text(text):
            candidates.append((ly1, text))

    if not candidates:
        return current_stage

    return sorted(candidates, key=lambda item: item[0])[-1][1]


def parse_document_metadata(pdf_path: Path, doc: pymupdf.Document) -> dict[str, Any]:
    first_page_text = doc[0].get_text("text") if len(doc) else ""
    lines = [clean_cell(line) for line in first_page_text.splitlines() if clean_cell(line)]

    court_establishment = ""
    court_number = ""
    judge_name = ""
    case_category = ""
    cause_list_date = ""

    for index, line in enumerate(lines):
        if line.startswith("In The Court Of"):
            if index > 0:
                court_establishment = lines[index - 1]

            match = re.search(r"In The Court Of\s*:\s*(\d+)\s*(.*)$", line)

            if match:
                court_number = match.group(1).strip()
                judge_name = match.group(2).strip()

            break

    match = re.search(
        r"(Civil|Criminal)\s+Cases Listed on\s*:\s*(\d{2}-\d{2}-\d{4})",
        first_page_text,
    )

    if match:
        case_category = match.group(1)
        cause_list_date = match.group(2)

    return {
        "file_name": pdf_path.name,
        "file_hash": file_hash(pdf_path),
        "page_count": len(doc),
        "court_establishment": court_establishment,
        "court_number": court_number,
        "judge_name": judge_name,
        "case_category": case_category,
        "cause_list_date": cause_list_date,
    }


def parse_pdf(pdf_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    doc = pymupdf.open(pdf_path)

    metadata = parse_document_metadata(pdf_path, doc)
    rows_out: list[dict[str, Any]] = []

    current_stage = ""

    for page_index, page in enumerate(doc, start=1):
        lines = extract_lines(page)
        back_y = first_back_y(lines)

        try:
            tables = page.find_tables().tables
        except Exception as exc:
            print(f"WARNING: table extraction failed for {pdf_path.name}, page {page_index}: {exc}")
            continue

        for table in tables:
            _x0, table_y0, _x1, _table_y1 = table.bbox

            # Skip Case Details tables after the Back button.
            if back_y is not None and table_y0 > back_y:
                continue

            if not is_cause_list_table(table):
                continue

            current_stage = stage_above_table(lines, table.bbox, current_stage)

            extracted_rows = table.extract()

            for row in extracted_rows[1:]:
                cells = [clean_cell(cell) for cell in row]

                if len(cells) < 4:
                    continue

                serial_cell = cells[0]
                serial_match = re.search(r"\d+", serial_cell)

                if not serial_match:
                    continue

                serial_number = int(serial_match.group())

                case_prefix = clean_cell(
                    (
                        serial_cell[: serial_match.start()]
                        + " "
                        + serial_cell[serial_match.end() :]
                    ).strip()
                )

                case_reference = repair_case_reference(case_prefix, cells[1])
                party_name = cells[2]
                advocate = cells[3]

                if not case_reference:
                    continue

                case_type, case_number, case_year = parse_case_reference(case_reference)

                rows_out.append(
                    {
                        "source_file": pdf_path.name,
                        "source_page": page_index,
                        "listing_date": metadata["cause_list_date"],
                        "court_establishment": metadata["court_establishment"],
                        "court_number": metadata["court_number"],
                        "judge_name": metadata["judge_name"],
                        "case_category": metadata["case_category"],
                        "stage": current_stage,
                        "serial_number": serial_number,
                        "case_reference": case_reference,
                        "case_type": case_type,
                        "case_number": case_number,
                        "case_year": case_year,
                        "party_name": party_name,
                        "advocate": advocate,
                    }
                )

    doc.close()
    return metadata, rows_out


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Some PDFs repeat the same visible cause-list table but show details
    for different clicked cases. Deduplicate the cause-list rows.
    """
    seen: set[tuple[Any, ...]] = set()
    unique_rows: list[dict[str, Any]] = []

    for row in rows:
        key = (
            row["listing_date"],
            row["court_number"],
            row["stage"].lower(),
            row["serial_number"],
            row["case_reference"].lower(),
            row["party_name"].lower(),
        )

        if key in seen:
            continue

        seen.add(key)
        unique_rows.append(row)

    return unique_rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(RAW_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {RAW_DIR.resolve()}")
        return

    documents: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []

    for pdf_path in pdf_files:
        metadata, rows = parse_pdf(pdf_path)
        documents.append(metadata)
        all_rows.extend(rows)

        print(f"{pdf_path.name}: {len(rows)} cause-list rows extracted")

    unique_rows = dedupe_rows(all_rows)

    document_fields = [
        "file_name",
        "file_hash",
        "page_count",
        "court_establishment",
        "court_number",
        "judge_name",
        "case_category",
        "cause_list_date",
    ]

    row_fields = [
        "source_file",
        "source_page",
        "listing_date",
        "court_establishment",
        "court_number",
        "judge_name",
        "case_category",
        "stage",
        "serial_number",
        "case_reference",
        "case_type",
        "case_number",
        "case_year",
        "party_name",
        "advocate",
    ]

    write_csv(DOCUMENTS_CSV, documents, document_fields)
    write_csv(CAUSE_LIST_CSV, unique_rows, row_fields)

    print()
    print("Done.")
    print(f"Documents written to: {DOCUMENTS_CSV}")
    print(f"Cause-list rows written to: {CAUSE_LIST_CSV}")
    print(f"Extracted rows before dedupe: {len(all_rows)}")
    print(f"Unique cause-list rows: {len(unique_rows)}")


if __name__ == "__main__":
    main()