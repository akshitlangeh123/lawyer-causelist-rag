from pathlib import Path

import pymupdf


RAW_DIR = Path("data/raw")
EXTRACTED_DIR = Path("data/extracted")


def extract_pdf_text(pdf_path: Path) -> str:
    doc = pymupdf.open(pdf_path)
    pages = []

    for page_number, page in enumerate(doc, start=1):
        text = page.get_text("text")
        pages.append(f"\n\n--- PAGE {page_number} ---\n{text}")

    return "\n".join(pages)


def main() -> None:
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(RAW_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDFs found in {RAW_DIR.resolve()}")
        return

    for pdf_path in pdf_files:
        text = extract_pdf_text(pdf_path)
        output_path = EXTRACTED_DIR / f"{pdf_path.stem}.txt"
        output_path.write_text(text, encoding="utf-8")

        print(f"Extracted: {pdf_path.name} -> {output_path}")


if __name__ == "__main__":
    main()