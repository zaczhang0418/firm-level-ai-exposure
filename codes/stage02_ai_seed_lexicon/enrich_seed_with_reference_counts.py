#!/usr/bin/env python3
"""Add reference frequency evidence to the AI seed lexicon.

Input:
    ai_seed_lexicon_v1.csv
    outputs/literature_discovered_terms.csv

Output:
    ai_seed_lexicon_v1.csv with evidence columns:
        reference_count
        total_hit_count
        reference_hit_counts
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


STAGE_DIR = Path(__file__).resolve().parent
LEXICON_PATH = STAGE_DIR / "ai_seed_lexicon_v1.csv"
DISCOVERED_PATH = STAGE_DIR / "outputs" / "literature_discovered_terms.csv"

OUTPUT_FIELDS = [
    "concept_group",
    "term",
    "match_type",
    "priority",
    "include",
    "reference_count",
    "total_hit_count",
    "reference_ids",
    "reference_hit_counts",
    "evidence_terms",
    "notes",
]


def normalize(value: str) -> str:
    return value.strip().lower().replace("-", " ")


def load_discovered_counts() -> dict[str, Counter[str]]:
    if not DISCOVERED_PATH.exists():
        raise FileNotFoundError(
            f"Missing {DISCOVERED_PATH}. Run discover_terms_from_references.py first."
        )

    counts: dict[str, Counter[str]] = defaultdict(Counter)
    with DISCOVERED_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            expression = normalize(row["candidate_expression"])
            reference_id = row["reference_id"].strip()
            hit_count = int(row["hit_count"] or 0)
            if expression and reference_id:
                counts[expression][reference_id] += max(hit_count, 1)
    return counts


def counts_for_row(row: dict[str, str], discovered_counts: dict[str, Counter[str]]) -> Counter[str]:
    candidates = [row["term"]]
    candidates.extend(part.strip() for part in row.get("evidence_terms", "").split(";") if part.strip())

    merged: Counter[str] = Counter()
    for normalized in {normalize(candidate) for candidate in candidates if candidate.strip()}:
        if normalized in discovered_counts:
            merged.update(discovered_counts[normalized])

    if not merged:
        for reference_id in row["reference_ids"].split(";"):
            reference_id = reference_id.strip()
            if reference_id:
                merged[reference_id] += 0
    return merged


def main() -> None:
    discovered_counts = load_discovered_counts()

    with LEXICON_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    enriched_rows: list[dict[str, str]] = []
    for row in rows:
        reference_counts = counts_for_row(row, discovered_counts)
        positive_counts = Counter({key: value for key, value in reference_counts.items() if value > 0})

        if positive_counts:
            reference_ids = sorted(positive_counts)
            reference_hit_counts = ";".join(f"{key}:{positive_counts[key]}" for key in reference_ids)
            reference_count = len(reference_ids)
            total_hit_count = sum(positive_counts.values())
        else:
            reference_ids = [ref.strip() for ref in row["reference_ids"].split(";") if ref.strip()]
            reference_hit_counts = ";".join(f"{key}:0" for key in reference_ids)
            reference_count = len(reference_ids)
            total_hit_count = 0

        enriched_row = dict(row)
        enriched_row["reference_count"] = str(reference_count)
        enriched_row["total_hit_count"] = str(total_hit_count)
        enriched_row["reference_ids"] = ";".join(reference_ids)
        enriched_row["reference_hit_counts"] = reference_hit_counts
        enriched_rows.append({field: enriched_row.get(field, "") for field in OUTPUT_FIELDS})

    with LEXICON_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(enriched_rows)

    print(f"Enriched {len(enriched_rows)} seed rows in {LEXICON_PATH}")


if __name__ == "__main__":
    main()
