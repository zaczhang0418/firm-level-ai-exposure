#!/usr/bin/env python3
"""Parse conference call XML files into database-linkable text tables.

Stage 01 goal:
    XML transcripts -> transcript metadata CSV + sentence-level CSV.

This first version is a scaffold. The next implementation step is to extract
metadata, split transcript sections, segment sentences, and write CSV outputs.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse conference call XML files.")
    parser.add_argument(
        "--input-dir",
        default="Data/Data_Conference call transcripts",
        help="Directory containing year folders with XML files.",
    )
    parser.add_argument(
        "--output-dir",
        default="codes/stage01_xml_standardization/outputs",
        help="Directory for parsed CSV outputs.",
    )
    parser.add_argument(
        "--year",
        default=None,
        help="Optional year folder to scan, for example 2013.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of XML files to parse for a test run.",
    )
    return parser.parse_args()


def list_xml_files(input_dir: Path, year: str | None) -> list[Path]:
    search_dir = input_dir / year if year else input_dir
    pattern = "*.xml" if year else "*/*.xml"
    return sorted(search_dir.glob(pattern))


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    xml_files = list_xml_files(input_dir, args.year)
    sample_files = xml_files[: args.limit]

    print(f"Found {len(xml_files)} XML files.")
    print(f"Ready to parse {len(sample_files)} sample files.")
    print(f"Output directory: {output_dir}")
    print("Next: extract metadata, section-aware sentences, and database-linkable IDs.")


if __name__ == "__main__":
    main()

