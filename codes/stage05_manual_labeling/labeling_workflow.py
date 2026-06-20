"""Interactive helpers for Stage 05 manual sentence labeling.

This script keeps the round CSV as the auditable source of truth while making
one-row-at-a-time labeling less error-prone.
"""

from __future__ import annotations

import argparse
import csv
import html
import shutil
import sys
import textwrap
from collections import Counter
from datetime import datetime
from pathlib import Path


DEFAULT_BATCH = Path(
    "codes/stage05_manual_labeling/outputs/labeling_batches/"
    "round01_ai_labeling_sample.csv"
)
DEFAULT_EXPORT = Path("codes/stage05_manual_labeling/outputs/labeled_ai_sentences_v2.csv")

LABEL_VALUES = {"0", "1"}
CONFIDENCE_VALUES = {"", "high", "medium", "low"}
REVIEW_VALUES = {"", "0", "1"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_BATCH, help="Round labeling CSV")

    subparsers = parser.add_subparsers(dest="command", required=True)

    show = subparsers.add_parser("show", help="Show one labeling row")
    show.add_argument("--id", help="Specific row id, e.g. R01-0001")
    show.add_argument(
        "--next",
        action="store_true",
        help="Show the next row with a blank ai_label. This is the default.",
    )

    label = subparsers.add_parser("label", help="Write a human label back to the CSV")
    label.add_argument("id", help="Row id, e.g. R01-0001")
    label.add_argument("--ai-label", required=True, choices=sorted(LABEL_VALUES))
    label.add_argument("--confidence", default="", choices=sorted(CONFIDENCE_VALUES))
    label.add_argument("--false-positive", default="")
    label.add_argument("--needs-review", default="", choices=sorted(REVIEW_VALUES))
    label.add_argument("--notes", default="")
    label.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing ai_label.",
    )
    label.add_argument(
        "--backup",
        action="store_true",
        help="Create a timestamped backup before writing. Default is no per-label backup.",
    )

    export = subparsers.add_parser(
        "export",
        help="Export completed 0/1 labels to Stage 06-ready labeled_ai_sentences_v2.csv",
    )
    export.add_argument("--output", type=Path, default=DEFAULT_EXPORT)

    subparsers.add_parser("status", help="Summarize labeling progress")
    return parser.parse_args()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise SystemExit(f"CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise SystemExit(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def backup_csv(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.stem}.backup-{stamp}{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(path)


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return html.unescape(str(value)).strip()


def wrap(value: str, width: int = 96) -> str:
    value = clean(value)
    if not value:
        return ""
    return "\n".join(textwrap.wrap(value, width=width, replace_whitespace=False))


def find_row(rows: list[dict[str, str]], row_id: str | None) -> dict[str, str] | None:
    if row_id:
        return next((row for row in rows if row.get("id") == row_id), None)
    return next((row for row in rows if not clean(row.get("ai_label"))), None)


def print_row(row: dict[str, str]) -> None:
    fields = [
        ("ID", "id"),
        ("Sample type", "sample_type"),
        ("Period/case", "period_or_case"),
        ("Year", "year"),
        ("Company", "company"),
        ("Ticker", "ticker"),
        ("Section", "section"),
        ("Speaker", "speaker"),
        ("Matched terms", "terms"),
        ("Matched text", "matched_text"),
        ("Concept group", "concept_group"),
        ("Priority", "priority"),
        ("Current label", "ai_label"),
        ("Confidence", "confidence"),
        ("False positive", "false_positive"),
        ("Needs review", "needs_review"),
        ("Notes", "notes"),
    ]

    for label, key in fields:
        value = clean(row.get(key))
        if value:
            print(f"{label}: {value}")

    print("\nTarget sentence:")
    print(wrap(row.get("sentence", "")) or "(blank)")

    if clean(row.get("prev_sentence")):
        print("\nPrevious sentence:")
        print(wrap(row.get("prev_sentence", "")))
    if clean(row.get("next_sentence")):
        print("\nNext sentence:")
        print(wrap(row.get("next_sentence", "")))
    if clean(row.get("context_window")):
        print("\nContext window:")
        print(wrap(row.get("context_window", "").replace(" [SEP] ", "\n[SEP] ")))

    print("\nTrace:")
    print(f"candidate_id: {clean(row.get('candidate_id'))}")
    print(f"document_id: {clean(row.get('document_id'))}")
    print(f"sentence_id: {clean(row.get('sentence_id'))}")


def print_status(rows: list[dict[str, str]]) -> None:
    labels = Counter(clean(row.get("ai_label")) for row in rows)
    by_type = Counter(row.get("sample_type", "") for row in rows)
    labeled_by_type = Counter(
        row.get("sample_type", "") for row in rows if clean(row.get("ai_label")) in LABEL_VALUES
    )
    review = Counter(clean(row.get("needs_review")) for row in rows)
    false_positive = Counter(
        clean(row.get("false_positive")) for row in rows if clean(row.get("false_positive"))
    )

    total = len(rows)
    labeled = labels["0"] + labels["1"]
    print(f"Rows: {total}")
    print(f"Labeled: {labeled}")
    print(f"Remaining: {total - labeled}")
    print(f"Positive labels: {labels['1']}")
    print(f"Negative labels: {labels['0']}")
    print(f"Blank labels: {labels['']}")
    print("\nBy sample_type:")
    for sample_type, count in sorted(by_type.items()):
        print(f"  {sample_type}: {labeled_by_type[sample_type]}/{count} labeled")
    if review:
        print("\nneeds_review:")
        for value, count in sorted(review.items()):
            label = value or "(blank)"
            print(f"  {label}: {count}")
    if false_positive:
        print("\nfalse_positive:")
        for value, count in false_positive.most_common():
            print(f"  {value}: {count}")


def update_label(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    row_id: str,
    *,
    ai_label: str,
    confidence: str,
    false_positive: str,
    needs_review: str,
    notes: str,
    overwrite: bool,
    backup: bool,
) -> None:
    row = find_row(rows, row_id)
    if row is None:
        raise SystemExit(f"Row id not found: {row_id}")

    existing = clean(row.get("ai_label"))
    if existing and not overwrite:
        raise SystemExit(
            f"{row_id} already has ai_label={existing}. "
            "Use --overwrite if you really want to replace it."
        )

    row["ai_label"] = ai_label
    row["confidence"] = confidence
    row["false_positive"] = false_positive
    row["needs_review"] = needs_review
    row["notes"] = notes

    backup_path = backup_csv(path) if backup else None
    write_rows(path, fieldnames, rows)
    print(f"Updated {row_id}: ai_label={ai_label}")
    if backup_path:
        print(f"Backup: {backup_path}")


def export_labeled(fieldnames: list[str], rows: list[dict[str, str]], output: Path) -> None:
    export_rows: list[dict[str, str]] = []
    for row in rows:
        label = clean(row.get("ai_label"))
        if label not in LABEL_VALUES:
            continue
        exported = dict(row)
        exported["label_ai_relevant"] = label
        exported.setdefault("label_source", "human")
        export_rows.append(exported)

    export_fields = ["label_ai_relevant"]
    if "label_source" not in fieldnames:
        export_fields.append("label_source")
    export_fields.extend([field for field in fieldnames if field != "label_ai_relevant"])

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=export_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(export_rows)

    print(f"Exported {len(export_rows)} labeled rows to {output}")


def main() -> None:
    args = parse_args()
    fieldnames, rows = read_rows(args.csv)

    if args.command == "status":
        print_status(rows)
        return

    if args.command == "show":
        row = find_row(rows, args.id)
        if row is None:
            if args.id:
                raise SystemExit(f"Row id not found: {args.id}")
            raise SystemExit("No unlabeled rows remain.")
        print_row(row)
        return

    if args.command == "label":
        update_label(
            args.csv,
            fieldnames,
            rows,
            args.id,
            ai_label=args.ai_label,
            confidence=args.confidence,
            false_positive=args.false_positive,
            needs_review=args.needs_review,
            notes=args.notes,
            overwrite=args.overwrite,
            backup=args.backup,
        )
        return

    if args.command == "export":
        export_labeled(fieldnames, rows, args.output)
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
