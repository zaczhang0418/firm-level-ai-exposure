#!/usr/bin/env python3
"""Extract AI candidate sentences from standardized transcript sentences.

Stage 03 goal:
    transcript_sentences.csv + AI seed lexicon -> AI candidate sentences.

This is a high-recall filtering layer. It does not decide final AI exposure;
it creates the sentence pool that later Word2Vec review and classifier steps
can inspect.
"""

from __future__ import annotations

import argparse
import csv
import glob
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_SENTENCES = "codes/stage01_xml_standardization/outputs/transcript_sentences.csv"
DEFAULT_LEXICON = "codes/stage02_ai_seed_lexicon/ai_seed_lexicon_v1.csv"
DEFAULT_OUTPUT = "codes/stage03_candidate_sentence_extraction/outputs/ai_candidate_sentences.csv"
DEFAULT_SUMMARY = "codes/stage03_candidate_sentence_extraction/outputs/ai_candidate_summary_by_document.csv"

REQUIRED_SENTENCE_COLUMNS = {
    "document_id",
    "event_id",
    "company_name",
    "ticker",
    "call_date",
    "call_year",
    "call_quarter",
    "reported_year",
    "reported_quarter",
    "section",
    "speaker",
    "sentence_id",
    "sentence",
    "xml_path",
}

REQUIRED_LEXICON_COLUMNS = {
    "concept_group",
    "term",
    "match_type",
    "priority",
    "include",
}

PASSTHROUGH_COLUMNS = [
    "document_id",
    "event_id",
    "company_name",
    "ticker",
    "call_date",
    "call_year",
    "call_quarter",
    "reported_year",
    "reported_quarter",
    "section",
    "speaker",
    "sentence_id",
    "sentence",
    "xml_path",
]

SOURCE_COLUMNS = [
    "source_csv",
]

MATCH_COLUMNS = [
    "matched_terms",
    "matched_concept_groups",
    "matched_priorities",
    "matched_term_count",
    "total_match_count",
]

SUMMARY_COLUMNS = [
    "document_id",
    "event_id",
    "company_name",
    "ticker",
    "call_date",
    "call_year",
    "call_quarter",
    "reported_year",
    "reported_quarter",
    "source_csv",
    "total_sentences",
    "candidate_sentences",
    "candidate_sentence_share",
    "total_seed_matches",
    "matched_terms",
    "matched_concept_groups",
]


@dataclass(frozen=True)
class SeedTerm:
    concept_group: str
    term: str
    match_type: str
    priority: str
    pattern: re.Pattern[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract AI candidate sentences using the Stage 02 seed lexicon."
    )
    parser.add_argument(
        "--sentences",
        default=DEFAULT_SENTENCES,
        help="Stage 01 transcript_sentences.csv path, directory, or glob pattern.",
    )
    parser.add_argument(
        "--lexicon",
        default=DEFAULT_LEXICON,
        help="Stage 02 ai_seed_lexicon_v1.csv path.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Candidate sentence output CSV path.",
    )
    parser.add_argument(
        "--summary-output",
        default=DEFAULT_SUMMARY,
        help="Document-level summary output CSV path.",
    )
    parser.add_argument(
        "--include-review",
        action="store_true",
        help="Include lexicon rows with priority=review if include=1.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum input sentence rows to scan for testing.",
    )
    parser.add_argument(
        "--keep-generic-ai-with-longer-match",
        action="store_true",
        help="Keep standalone AI when a longer AI phrase also matches the sentence.",
    )
    return parser.parse_args()


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def flexible_escaped_term(term: str) -> str:
    escaped = re.escape(normalize_whitespace(term))
    return escaped.replace(r"\ ", r"\s+")


def compile_pattern(term: str, match_type: str) -> re.Pattern[str]:
    escaped = flexible_escaped_term(term)
    if match_type in {"phrase", "word_boundary"}:
        pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    else:
        raise ValueError(f"Unsupported match_type for term {term!r}: {match_type!r}")
    return re.compile(pattern, flags=re.IGNORECASE)


def validate_columns(fieldnames: Iterable[str] | None, required: set[str], path: Path) -> None:
    available = set(fieldnames or [])
    missing = sorted(required - available)
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")


def resolve_sentence_paths(sentences_arg: str) -> list[Path]:
    path = Path(sentences_arg)
    if path.exists() and path.is_file():
        return [path]
    if path.exists() and path.is_dir():
        csv_files = sorted(item for item in path.rglob("*.csv") if item.is_file())
        sentence_files = [
            item
            for item in csv_files
            if "sentence" in item.name.lower() and "candidate" not in item.name.lower()
        ]
        return sentence_files or csv_files

    matches = sorted(Path(item) for item in glob.glob(sentences_arg, recursive=True))
    csv_matches = [item for item in matches if item.is_file() and item.suffix.lower() == ".csv"]
    if csv_matches:
        return csv_matches

    raise FileNotFoundError(
        f"No sentence CSV files found for {sentences_arg!r}. "
        "Pass a CSV file, a directory, or a glob such as 'outputs/*/transcript_sentences.csv'."
    )


def load_seed_terms(
    lexicon_path: Path,
    include_review: bool,
    keep_generic_ai_with_longer_match: bool,
) -> list[SeedTerm]:
    terms: list[SeedTerm] = []
    with lexicon_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        validate_columns(reader.fieldnames, REQUIRED_LEXICON_COLUMNS, lexicon_path)
        for row in reader:
            if row["include"].strip() != "1":
                continue
            priority = row["priority"].strip().lower()
            if priority == "review" and not include_review:
                continue
            term = normalize_whitespace(row["term"])
            if not term:
                continue
            if term.lower() == "ai" and not keep_generic_ai_with_longer_match:
                # Keep the seed, but it will be removed sentence-by-sentence if
                # a more specific AI phrase also matched.
                pass
            terms.append(
                SeedTerm(
                    concept_group=row["concept_group"].strip(),
                    term=term,
                    match_type=row["match_type"].strip().lower(),
                    priority=priority,
                    pattern=compile_pattern(term, row["match_type"].strip().lower()),
                )
            )
    return sorted(terms, key=lambda item: len(item.term), reverse=True)


def find_matches(
    sentence: str,
    seed_terms: list[SeedTerm],
    keep_generic_ai_with_longer_match: bool,
) -> list[tuple[SeedTerm, int]]:
    matches: list[tuple[SeedTerm, int]] = []
    for seed in seed_terms:
        count = len(seed.pattern.findall(sentence))
        if count:
            matches.append((seed, count))

    if keep_generic_ai_with_longer_match:
        return matches

    has_longer_ai_match = any(seed.term.lower() != "ai" for seed, _ in matches)
    if has_longer_ai_match:
        matches = [(seed, count) for seed, count in matches if seed.term.lower() != "ai"]
    return matches


def unique_join(values: Iterable[str]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ";".join(ordered)


def update_summary(
    summary: dict[str, object],
    row: dict[str, str],
    source_csv: str,
    matches: list[tuple[SeedTerm, int]],
) -> None:
    summary["total_sentences"] = int(summary.get("total_sentences", 0)) + 1
    for column in SUMMARY_COLUMNS[:9]:
        summary.setdefault(column, row.get(column, ""))
    summary.setdefault("source_csv", source_csv)
    if matches:
        summary["candidate_sentences"] = int(summary.get("candidate_sentences", 0)) + 1
        summary["total_seed_matches"] = int(summary.get("total_seed_matches", 0)) + sum(
            count for _, count in matches
        )
        term_counter = summary.setdefault("term_counter", Counter())
        group_counter = summary.setdefault("group_counter", Counter())
        assert isinstance(term_counter, Counter)
        assert isinstance(group_counter, Counter)
        for seed, count in matches:
            term_counter[seed.term] += count
            group_counter[seed.concept_group] += count


def write_summary(summary_output: Path, summaries: dict[str, dict[str, object]]) -> None:
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    with summary_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for document_id in sorted(summaries):
            summary = summaries[document_id]
            total_sentences = int(summary.get("total_sentences", 0))
            candidate_sentences = int(summary.get("candidate_sentences", 0))
            term_counter = summary.get("term_counter", Counter())
            group_counter = summary.get("group_counter", Counter())
            assert isinstance(term_counter, Counter)
            assert isinstance(group_counter, Counter)
            output_row = {
                column: summary.get(column, "")
                for column in SUMMARY_COLUMNS[:10]
            }
            output_row.update(
                {
                    "total_sentences": total_sentences,
                    "candidate_sentences": candidate_sentences,
                    "candidate_sentence_share": (
                        f"{candidate_sentences / total_sentences:.6f}" if total_sentences else "0.000000"
                    ),
                    "total_seed_matches": int(summary.get("total_seed_matches", 0)),
                    "matched_terms": ";".join(
                        f"{term}:{count}" for term, count in term_counter.most_common()
                    ),
                    "matched_concept_groups": ";".join(
                        f"{group}:{count}" for group, count in group_counter.most_common()
                    ),
                }
            )
            writer.writerow(output_row)


def extract_candidates(
    sentences_path: Path,
    lexicon_path: Path,
    output_path: Path,
    summary_output: Path,
    include_review: bool,
    limit: int | None,
    keep_generic_ai_with_longer_match: bool,
) -> tuple[int, int, int]:
    seed_terms = load_seed_terms(
        lexicon_path=lexicon_path,
        include_review=include_review,
        keep_generic_ai_with_longer_match=keep_generic_ai_with_longer_match,
    )
    if not seed_terms:
        raise ValueError(f"No included seed terms found in {lexicon_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summaries: dict[str, dict[str, object]] = defaultdict(dict)

    scanned_rows = 0
    candidate_rows = 0
    total_matches = 0

    sentence_paths = resolve_sentence_paths(str(sentences_path))

    with output_path.open("w", encoding="utf-8", newline="") as output_handle:
        writer = csv.DictWriter(output_handle, fieldnames=PASSTHROUGH_COLUMNS + SOURCE_COLUMNS + MATCH_COLUMNS)
        writer.writeheader()

        for sentence_path in sentence_paths:
            with sentence_path.open("r", encoding="utf-8-sig", newline="") as input_handle:
                reader = csv.DictReader(input_handle)
                validate_columns(reader.fieldnames, REQUIRED_SENTENCE_COLUMNS, sentence_path)

                for row in reader:
                    if limit is not None and scanned_rows >= limit:
                        break
                    scanned_rows += 1
                    sentence = row.get("sentence", "")
                    matches = find_matches(
                        sentence=sentence,
                        seed_terms=seed_terms,
                        keep_generic_ai_with_longer_match=keep_generic_ai_with_longer_match,
                    )
                    document_id = row.get("document_id", "")
                    update_summary(summaries[document_id], row, str(sentence_path), matches)

                    if not matches:
                        continue

                    candidate_rows += 1
                    total_matches += sum(count for _, count in matches)
                    writer.writerow(
                        {
                            **{column: row.get(column, "") for column in PASSTHROUGH_COLUMNS},
                            "source_csv": str(sentence_path),
                            "matched_terms": unique_join(seed.term for seed, _ in matches),
                            "matched_concept_groups": unique_join(seed.concept_group for seed, _ in matches),
                            "matched_priorities": unique_join(seed.priority for seed, _ in matches),
                            "matched_term_count": len(matches),
                            "total_match_count": sum(count for _, count in matches),
                        }
                    )

                if limit is not None and scanned_rows >= limit:
                    break

    write_summary(summary_output, summaries)
    return scanned_rows, candidate_rows, total_matches


def main() -> None:
    args = parse_args()
    scanned_rows, candidate_rows, total_matches = extract_candidates(
        sentences_path=Path(args.sentences),
        lexicon_path=Path(args.lexicon),
        output_path=Path(args.output),
        summary_output=Path(args.summary_output),
        include_review=args.include_review,
        limit=args.limit,
        keep_generic_ai_with_longer_match=args.keep_generic_ai_with_longer_match,
    )
    share = candidate_rows / scanned_rows if scanned_rows else 0
    print(f"Scanned sentence rows: {scanned_rows}")
    print(f"Candidate sentence rows: {candidate_rows}")
    print(f"Candidate share: {share:.6f}")
    print(f"Total seed matches: {total_matches}")
    print(f"Candidate output: {args.output}")
    print(f"Summary output: {args.summary_output}")


if __name__ == "__main__":
    main()
