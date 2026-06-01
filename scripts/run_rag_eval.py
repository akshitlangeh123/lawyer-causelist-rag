from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.llama_rag import answer_question_with_llama, retrieve_evidence  # noqa: E402


DEFAULT_EVAL_FILE = PROJECT_ROOT / "data" / "eval" / "questions.jsonl"
RESULTS_DIR = PROJECT_ROOT / "data" / "eval" / "results"


def clean(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def normalize_text(value: Any) -> str:
    value = clean(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def contains_term(text: str, term: str) -> bool:
    return normalize_text(term) in normalize_text(text)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    cases = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc

    return cases


def evidence_to_text(evidence: list[dict[str, Any]]) -> str:
    parts = []

    for item in evidence:
        metadata = item.get("metadata", {})
        parts.append(clean(item.get("text")))
        parts.append(" ".join(clean(value) for value in metadata.values()))

    return "\n".join(parts)


def evidence_sources(evidence: list[dict[str, Any]]) -> list[str]:
    sources = []

    for item in evidence:
        metadata = item.get("metadata", {})
        source_file = clean(metadata.get("source_file"))

        if source_file:
            sources.append(source_file)

    return sorted(set(sources))


def ask_result_to_text(result: dict[str, Any]) -> str:
    parts = [clean(result.get("answer"))]

    for source in result.get("sources", []):
        parts.append(" ".join(clean(value) for value in source.values()))

    return "\n".join(parts)


def ask_result_sources(result: dict[str, Any]) -> list[str]:
    sources = []

    for source in result.get("sources", []):
        source_file = clean(source.get("source_file"))

        if source_file:
            sources.append(source_file)

    return sorted(set(sources))


def check_expected_terms(
    text: str,
    expected_terms: list[str],
) -> tuple[list[str], list[str], float]:
    matched = []
    missing = []

    for term in expected_terms:
        if contains_term(text, term):
            matched.append(term)
        else:
            missing.append(term)

    if not expected_terms:
        score = 1.0
    else:
        score = len(matched) / len(expected_terms)

    return matched, missing, score


def check_expected_sources(
    actual_sources: list[str],
    expected_sources: list[str],
) -> bool:
    if not expected_sources:
        return True

    actual_normalized = [normalize_text(source) for source in actual_sources]

    for expected_source in expected_sources:
        expected_normalized = normalize_text(expected_source)

        if not any(expected_normalized in actual for actual in actual_normalized):
            return False

    return True


def run_retrieve_eval_case(
    case: dict[str, Any],
    limit: int,
    min_term_score: float,
) -> dict[str, Any]:
    question = case["question"]

    evidence = retrieve_evidence(question, limit=limit)

    text_to_check = evidence_to_text(evidence)
    actual_sources = evidence_sources(evidence)

    matched_terms, missing_terms, term_score = check_expected_terms(
        text=text_to_check,
        expected_terms=case.get("expected_terms", []),
    )

    source_ok = check_expected_sources(
        actual_sources=actual_sources,
        expected_sources=case.get("expected_sources", []),
    )

    passed = term_score >= min_term_score and source_ok

    return {
        "id": case.get("id"),
        "category": case.get("category"),
        "question": question,
        "mode": "retrieve",
        "passed": passed,
        "term_score": round(term_score, 3),
        "source_ok": source_ok,
        "expected_terms": case.get("expected_terms", []),
        "matched_terms": matched_terms,
        "missing_terms": missing_terms,
        "expected_sources": case.get("expected_sources", []),
        "actual_sources": actual_sources,
        "evidence_count": len(evidence),
        "answer_preview": text_to_check[:700],
    }


def run_ask_eval_case(
    case: dict[str, Any],
    limit: int,
    min_term_score: float,
) -> dict[str, Any]:
    question = case["question"]

    result = answer_question_with_llama(
        question=question,
        limit=limit,
    )

    text_to_check = ask_result_to_text(result)
    actual_sources = ask_result_sources(result)

    matched_terms, missing_terms, term_score = check_expected_terms(
        text=text_to_check,
        expected_terms=case.get("expected_terms", []),
    )

    source_ok = check_expected_sources(
        actual_sources=actual_sources,
        expected_sources=case.get("expected_sources", []),
    )

    passed = term_score >= min_term_score and source_ok

    return {
        "id": case.get("id"),
        "category": case.get("category"),
        "question": question,
        "mode": "ask",
        "passed": passed,
        "term_score": round(term_score, 3),
        "source_ok": source_ok,
        "expected_terms": case.get("expected_terms", []),
        "matched_terms": matched_terms,
        "missing_terms": missing_terms,
        "expected_sources": case.get("expected_sources", []),
        "actual_sources": actual_sources,
        "evidence_count": result.get("evidence_count"),
        "answer_preview": clean(result.get("answer"))[:700],
        "raw_result": result,
    }


def write_reports(results: list[dict[str, Any]], mode: str) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = RESULTS_DIR / f"rag_eval_{mode}_{timestamp}.json"
    csv_path = RESULTS_DIR / f"rag_eval_{mode}_{timestamp}.csv"

    json_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    fieldnames = [
        "id",
        "category",
        "mode",
        "passed",
        "term_score",
        "source_ok",
        "evidence_count",
        "missing_terms",
        "actual_sources",
        "question",
        "answer_preview",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    "id": result.get("id"),
                    "category": result.get("category"),
                    "mode": result.get("mode"),
                    "passed": result.get("passed"),
                    "term_score": result.get("term_score"),
                    "source_ok": result.get("source_ok"),
                    "evidence_count": result.get("evidence_count"),
                    "missing_terms": "; ".join(result.get("missing_terms", [])),
                    "actual_sources": "; ".join(result.get("actual_sources", [])),
                    "question": result.get("question"),
                    "answer_preview": result.get("answer_preview"),
                }
            )

    return json_path, csv_path


def print_summary(results: list[dict[str, Any]]) -> None:
    total = len(results)
    passed = sum(1 for result in results if result["passed"])
    failed = total - passed

    print()
    print("=" * 90)
    print("RAG EVAL SUMMARY")
    print("=" * 90)
    print(f"Total:  {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if total:
        print(f"Pass rate: {passed / total:.1%}")

    print()

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"

        print(
            f"{status} | {result['id']} | {result['category']} | "
            f"term_score={result['term_score']} | source_ok={result['source_ok']}"
        )

        if not result["passed"]:
            print(f"  Question: {result['question']}")
            print(f"  Missing terms: {', '.join(result.get('missing_terms', []))}")
            print(f"  Actual sources: {', '.join(result.get('actual_sources', []))}")
            print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=DEFAULT_EVAL_FILE,
    )
    parser.add_argument(
        "--mode",
        choices=["retrieve", "ask"],
        default="retrieve",
        help="retrieve = no Llama call; ask = full local Llama /ask evaluation",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--min-term-score",
        type=float,
        default=0.8,
        help="Minimum fraction of expected terms that must appear.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Run only the first N eval cases.",
    )

    args = parser.parse_args()

    cases = load_jsonl(args.eval_file)

    if args.max_cases:
        cases = cases[: args.max_cases]

    results = []

    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']}: {case['question']}")

        if args.mode == "retrieve":
            result = run_retrieve_eval_case(
                case=case,
                limit=args.limit,
                min_term_score=args.min_term_score,
            )
        else:
            result = run_ask_eval_case(
                case=case,
                limit=args.limit,
                min_term_score=args.min_term_score,
            )

        results.append(result)

    print_summary(results)

    json_path, csv_path = write_reports(results, mode=args.mode)

    print()
    print("Reports written:")
    print(json_path)
    print(csv_path)

    failed = [result for result in results if not result["passed"]]

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()