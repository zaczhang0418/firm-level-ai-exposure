#!/usr/bin/env python3
"""Validate the Stage 02 AI seed lexicon CSV."""

from __future__ import annotations

import csv
from pathlib import Path


REQUIRED_COLUMNS = [
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

ALLOWED_INCLUDE_VALUES = {"0", "1"}
ALLOWED_MATCH_TYPES = {"phrase", "word_boundary"}
ALLOWED_PRIORITIES = {"high", "medium", "review"}


def validate(path: Path) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing_columns = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        seen_terms: set[str] = set()
        errors: list[str] = []
        row_count = 0
        included_count = 0
        for row_count, row in enumerate(reader, start=1):
            term = row["term"].strip()
            normalized_term = term.lower()
            if not term:
                errors.append(f"row {row_count}: empty term")
            if normalized_term in seen_terms:
                errors.append(f"row {row_count}: duplicate term '{term}'")
            seen_terms.add(normalized_term)

            if row["include"] not in ALLOWED_INCLUDE_VALUES:
                errors.append(f"row {row_count}: invalid include value '{row['include']}'")
            if row["include"] == "1":
                included_count += 1
            for numeric_col in ["reference_count", "total_hit_count"]:
                if not row[numeric_col].isdigit():
                    errors.append(f"row {row_count}: {numeric_col} must be a nonnegative integer")
            if row["match_type"] not in ALLOWED_MATCH_TYPES:
                errors.append(f"row {row_count}: invalid match_type '{row['match_type']}'")
            if row["priority"] not in ALLOWED_PRIORITIES:
                errors.append(f"row {row_count}: invalid priority '{row['priority']}'")

        if errors:
            raise ValueError("\n".join(errors))

    print("Seed lexicon validation passed.")
    print(f"Rows: {row_count}")
    print(f"Included terms: {included_count}")


def main() -> None:
    path = Path(__file__).with_name("ai_seed_lexicon_v1.csv")
    validate(path)


if __name__ == "__main__":
    main()
