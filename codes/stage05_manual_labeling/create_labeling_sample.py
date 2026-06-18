"""Create readable manual-labeling samples from the Stage 05 candidate pool."""

from __future__ import annotations

import argparse
import csv
import random
import re
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_INPUT = Path("codes/stage05_manual_labeling/outputs/ai_candidate_sentences_v2.csv")
DEFAULT_OUTPUT_DIR = Path("codes/stage05_manual_labeling/outputs/labeling_batches")

OUTPUT_COLUMNS = [
    "id",
    "round",
    "sample_type",
    "period_or_case",
    "why_sampled",
    "ai_label",
    "confidence",
    "false_positive",
    "needs_review",
    "notes",
    "year",
    "quarter",
    "company",
    "ticker",
    "date",
    "section",
    "speaker",
    "terms",
    "matched_text",
    "concept_group",
    "priority",
    "sentence",
    "prev_sentence",
    "next_sentence",
    "context_window",
    "candidate_id",
    "document_id",
    "event_id",
    "sentence_id",
    "source_csv",
    "xml_path",
    "term_count",
    "match_count",
]

PERIODS = [
    ("2001-2015", 2001, 2015),
    ("2016-2020", 2016, 2020),
    ("2021-2022", 2021, 2022),
    ("2023-2024", 2023, 2024),
]

STRONG_AI_PATTERNS = [
    r"\bartificial intelligence\b",
    r"\bmachine learning\b",
    r"\bdeep learning\b",
    r"\bgenerative ai\b",
    r"\bgen ai\b",
    r"\blarge language model(s)?\b",
    r"\bllm(s)?\b",
    r"\bchatgpt\b",
    r"\bnatural language processing\b",
    r"\bnlp\b",
    r"\bcomputer vision\b",
    r"\bai[- ]powered\b",
    r"\bai model(s)?\b",
    r"\bai platform(s)?\b",
]

WEAK_OR_NOISY_PATTERNS = [
    r"\bautomation\b",
    r"\bautomated\b",
    r"\balgorithm(s|ic)?\b",
    r"\banalytics?\b",
    r"\bdigital\b",
    r"\btechnology\b",
    r"\bplatform(s)?\b",
    r"\bdata[- ]driven\b",
]

STRONG_AI_RE = re.compile("|".join(STRONG_AI_PATTERNS), re.IGNORECASE)
WEAK_OR_NOISY_RE = re.compile("|".join(WEAK_OR_NOISY_PATTERNS), re.IGNORECASE)
STANDALONE_AI_RE = re.compile(r"\bAI\b")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--round", default="round01")
    parser.add_argument("--seed", type=int, default=20260618)
    parser.add_argument("--stratified-n", type=int, default=400)
    parser.add_argument("--positive-n", type=int, default=400)
    parser.add_argument("--hard-negative-n", type=int, default=200)
    return parser.parse_args()


def period_for_year(year_value: str) -> str:
    try:
        year = int(year_value)
    except (TypeError, ValueError):
        return "unknown"
    for label, start, end in PERIODS:
        if start <= year <= end:
            return label
    return "unknown"


def combined_text(row: dict[str, str]) -> str:
    return " ".join(
        [
            row.get("matched_terms", ""),
            row.get("matched_texts", ""),
            row.get("sentence", ""),
        ]
    )


def is_strong_ai(row: dict[str, str]) -> bool:
    return bool(STRONG_AI_RE.search(combined_text(row)))


def is_standalone_ai(row: dict[str, str]) -> bool:
    text = combined_text(row)
    return bool(STANDALONE_AI_RE.search(text)) and not is_strong_ai(row)


def is_weak_or_noisy(row: dict[str, str]) -> bool:
    return bool(WEAK_OR_NOISY_RE.search(combined_text(row))) and not is_strong_ai(row)


def format_row(
    row: dict[str, str],
    *,
    sample_round: str,
    sample_type: str,
    period_or_case: str,
    why_sampled: str,
) -> dict[str, str]:
    return {
        "id": "",
        "round": sample_round,
        "sample_type": sample_type,
        "period_or_case": period_or_case,
        "why_sampled": why_sampled,
        "ai_label": "",
        "confidence": "",
        "false_positive": "",
        "needs_review": "",
        "notes": "",
        "year": row.get("call_year", ""),
        "quarter": row.get("call_quarter", ""),
        "company": row.get("company_name", ""),
        "ticker": row.get("ticker", ""),
        "date": row.get("call_date", ""),
        "section": row.get("section", ""),
        "speaker": row.get("speaker", ""),
        "terms": row.get("matched_terms", ""),
        "matched_text": row.get("matched_texts", ""),
        "concept_group": row.get("matched_concept_groups", ""),
        "priority": row.get("matched_priorities", ""),
        "sentence": row.get("sentence", ""),
        "prev_sentence": row.get("previous_sentence", ""),
        "next_sentence": row.get("next_sentence", ""),
        "context_window": row.get("context_window", ""),
        "candidate_id": row.get("candidate_id", ""),
        "document_id": row.get("document_id", ""),
        "event_id": row.get("event_id", ""),
        "sentence_id": row.get("sentence_id", ""),
        "source_csv": row.get("source_csv", ""),
        "xml_path": row.get("xml_path", ""),
        "term_count": row.get("matched_term_count", ""),
        "match_count": row.get("total_match_count", ""),
    }


def sample_evenly_by_period(
    pools_by_period: dict[str, list[dict[str, str]]],
    total_n: int,
    rng: random.Random,
    selected_ids: set[str],
    *,
    sample_round: str,
    sample_type: str,
    reason: str,
) -> list[dict[str, str]]:
    period_labels = [label for label, _, _ in PERIODS]
    base_n = total_n // len(period_labels)
    remainder = total_n % len(period_labels)
    targets = {
        label: base_n + (1 if i < remainder else 0)
        for i, label in enumerate(period_labels)
    }

    selected: list[dict[str, str]] = []
    shortfall = 0
    for label in period_labels:
        available = [
            row for row in pools_by_period.get(label, [])
            if row.get("candidate_id", "") not in selected_ids
        ]
        take = min(targets[label], len(available))
        if take < targets[label]:
            shortfall += targets[label] - take
        if take:
            for row in rng.sample(available, take):
                selected_ids.add(row.get("candidate_id", ""))
                selected.append(
                    format_row(
                        row,
                        sample_round=sample_round,
                        sample_type=sample_type,
                        period_or_case=label,
                        why_sampled=reason,
                    )
                )

    if shortfall:
        available = [
            row
            for label in period_labels
            for row in pools_by_period.get(label, [])
            if row.get("candidate_id", "") not in selected_ids
        ]
        for row in rng.sample(available, min(shortfall, len(available))):
            selected_ids.add(row.get("candidate_id", ""))
            selected.append(
                format_row(
                    row,
                    sample_round=sample_round,
                    sample_type=sample_type,
                    period_or_case=period_for_year(row.get("call_year", "")),
                    why_sampled=reason + "; period shortfall top-up",
                )
            )

    return selected


def assign_review_ids(rows: list[dict[str, str]], sample_round: str) -> None:
    prefix = sample_round.upper().replace("ROUND", "R")
    for i, row in enumerate(rows, start=1):
        row["id"] = f"{prefix}-{i:04d}"


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)

    all_by_period: dict[str, list[dict[str, str]]] = defaultdict(list)
    strong_by_period: dict[str, list[dict[str, str]]] = defaultdict(list)
    standalone_ai_rows: list[dict[str, str]] = []
    weak_or_noisy_rows: list[dict[str, str]] = []
    frame_counts = Counter()

    with args.input.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            period = period_for_year(row.get("call_year", ""))
            all_by_period[period].append(row)
            frame_counts[("all", period)] += 1

            if is_strong_ai(row):
                strong_by_period[period].append(row)
                frame_counts[("strong_ai", period)] += 1
            if is_standalone_ai(row):
                standalone_ai_rows.append(row)
                frame_counts[("standalone_ai", period)] += 1
            elif is_weak_or_noisy(row):
                weak_or_noisy_rows.append(row)
                frame_counts[("weak_or_noisy", period)] += 1

    selected_ids: set[str] = set()
    output_rows: list[dict[str, str]] = []

    output_rows.extend(
        sample_evenly_by_period(
            all_by_period,
            args.stratified_n,
            rng,
            selected_ids,
            sample_round=args.round,
            sample_type="random",
            reason="period-stratified random draw from full Stage 05 candidate pool",
        )
    )

    output_rows.extend(
        sample_evenly_by_period(
            strong_by_period,
            args.positive_n,
            rng,
            selected_ids,
            sample_round=args.round,
            sample_type="likely_ai",
            reason="strong AI term matched; enrich likely positive examples",
        )
    )

    hard_target_standalone = args.hard_negative_n // 2
    hard_rows: list[dict[str, str]] = []
    for source_rows, target, label, reason in [
        (
            standalone_ai_rows,
            hard_target_standalone,
            "standalone_ai",
            'standalone "AI" without stronger AI phrase; likely ambiguous/noisy',
        ),
        (
            weak_or_noisy_rows,
            args.hard_negative_n - hard_target_standalone,
            "weak_or_noisy_terms",
            "weak or generic technology term; likely hard negative",
        ),
    ]:
        available = [
            row for row in source_rows
            if row.get("candidate_id", "") not in selected_ids
        ]
        for row in rng.sample(available, min(target, len(available))):
            selected_ids.add(row.get("candidate_id", ""))
            hard_rows.append(
                format_row(
                    row,
                    sample_round=args.round,
                    sample_type="hard_case",
                    period_or_case=label,
                    why_sampled=reason,
                )
            )

    hard_shortfall = args.hard_negative_n - len(hard_rows)
    if hard_shortfall:
        available = [
            row for row in standalone_ai_rows + weak_or_noisy_rows
            if row.get("candidate_id", "") not in selected_ids
        ]
        for row in rng.sample(available, min(hard_shortfall, len(available))):
            selected_ids.add(row.get("candidate_id", ""))
            hard_rows.append(
                format_row(
                    row,
                    sample_round=args.round,
                    sample_type="hard_case",
                    period_or_case="hard_case_topup",
                    why_sampled="hard-case shortfall top-up",
                )
            )
    output_rows.extend(hard_rows)

    rng.shuffle(output_rows)
    assign_review_ids(output_rows, args.round)

    sample_path = args.output_dir / f"{args.round}_ai_labeling_sample.csv"
    summary_path = args.output_dir / f"{args.round}_sampling_summary.csv"
    write_csv(sample_path, output_rows, OUTPUT_COLUMNS)

    summary_rows = []
    selected_counts = Counter(
        (row["sample_type"], row["period_or_case"]) for row in output_rows
    )
    for (group, stratum), count in sorted(selected_counts.items()):
        summary_rows.append(
            {
                "round": args.round,
                "sample_type": group,
                "period_or_case": stratum,
                "rows": count,
            }
        )
    for (group, period), count in sorted(frame_counts.items()):
        summary_rows.append(
            {
                "round": args.round,
                "sample_type": f"frame_{group}",
                "period_or_case": period,
                "rows": count,
            }
        )
    write_csv(
        summary_path,
        summary_rows,
        ["round", "sample_type", "period_or_case", "rows"],
    )

    print(f"Wrote {len(output_rows):,} rows to {sample_path}")
    print(f"Wrote sampling summary to {summary_path}")


if __name__ == "__main__":
    main()
