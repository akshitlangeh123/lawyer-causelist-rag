from pathlib import Path
import re
import sys


EXTRACTED_DIR = Path("data/extracted")


def search_text_files(query: str) -> None:
    query = query.strip()

    if not query:
        print("Usage: python scripts/quick_search.py \"search text\"")
        return

    files = sorted(EXTRACTED_DIR.glob("*.txt"))

    if not files:
        print("No extracted text files found. Run scripts/extract_text.py first.")
        return

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    found_any = False

    for text_file in files:
        text = text_file.read_text(encoding="utf-8", errors="ignore")

        for match in pattern.finditer(text):
            found_any = True
            start = max(match.start() - 180, 0)
            end = min(match.end() + 180, len(text))
            snippet = text[start:end].replace("\n", " ")

            print("\n" + "=" * 80)
            print(f"File: {text_file.name}")
            print(f"Match: {query}")
            print("-" * 80)
            print(snippet)

    if not found_any:
        print(f"No matches found for: {query}")


def main() -> None:
    query = " ".join(sys.argv[1:])
    search_text_files(query)


if __name__ == "__main__":
    main()