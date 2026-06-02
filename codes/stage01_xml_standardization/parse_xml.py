#!/usr/bin/env python3
"""Parse conference call XML files into database-linkable text tables.

Stage 01 goal:
    XML transcripts -> transcript metadata CSV + sentence-level CSV.
"""

from __future__ import annotations

import argparse
import csv
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path


METADATA_FIELDS = [
    "document_id",
    "event_id",
    "company_name",
    "ticker",
    "call_date",
    "call_year",
    "call_quarter",
    "reported_year",
    "reported_quarter",
    "event_title",
    "headline",
    "xml_path",
    "parse_status",
    "parse_note",
]

SENTENCE_FIELDS = [
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
    "sentence_index",
    "sentence",
    "xml_path",
]

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

ABBREVIATIONS = [
    "Mr.",
    "Mrs.",
    "Ms.",
    "Dr.",
    "Prof.",
    "Sr.",
    "Jr.",
    "Inc.",
    "Ltd.",
    "Co.",
    "Corp.",
    "LLC.",
    "PLC.",
    "S.A.",
    "U.S.",
    "U.K.",
    "e.g.",
    "i.e.",
]


@dataclass
class Transcript:
    metadata: dict[str, str]
    sentences: list[dict[str, str]]


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
        help="Maximum number of XML files to parse. Use 0 or a negative value for all files.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=1000,
        help="Print progress after this many XML files.",
    )
    return parser.parse_args()


def list_xml_files(input_dir: Path, year: str | None) -> list[Path]:
    search_dir = input_dir / year if year else input_dir
    pattern = "*.xml" if year else "*/*.xml"
    return sorted(search_dir.glob(pattern))


def format_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h{minutes:02d}m{seconds:02d}s"
    return f"{minutes:02d}m{seconds:02d}s"


def progress_line(current: int, total: int, started_at: float) -> str:
    width = 30
    ratio = current / total if total else 1
    filled = min(width, int(ratio * width))
    bar = "#" * filled + "-" * (width - filled)
    elapsed = time.monotonic() - started_at
    rate = current / elapsed if elapsed > 0 else 0
    return (
        f"Progress [{bar}] {ratio * 100:5.1f}% "
        f"{current}/{total} XML "
        f"elapsed={format_elapsed(elapsed)} "
        f"rate={rate:,.1f}/s"
    )


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def child_text(root: ET.Element, tag: str) -> str:
    node = root.find(f".//{tag}")
    return clean_text(node.text if node is not None else "")


def raw_child_text(root: ET.Element, tag: str) -> str:
    node = root.find(f".//{tag}")
    return node.text if node is not None and node.text else ""


def parse_call_date(raw_date: str) -> tuple[str, str, str]:
    """Parse dates like '8-May-13 3:45pm GMT' into ISO date and year/quarter."""
    match = re.search(r"(\d{1,2})-([A-Za-z]{3,4})-(\d{2,4})", raw_date or "")
    if not match:
        return "", "", ""

    day = int(match.group(1))
    month_key = match.group(2).lower()
    month = MONTHS.get(month_key, 0)
    year = int(match.group(3))
    if year < 100:
        year += 2000 if year < 50 else 1900
    if not month:
        return "", "", ""

    call_date = date(year, month, day).isoformat()
    call_quarter = ((month - 1) // 3) + 1
    return call_date, str(year), str(call_quarter)


def parse_reported_period(*texts: str) -> tuple[str, str]:
    combined = " ".join(text for text in texts if text)
    match = re.search(r"\bQ([1-4])\s+(?:FY\s*)?(\d{4})\b", combined, flags=re.I)
    if match:
        return match.group(2), match.group(1)
    match = re.search(r"\bQ([1-4])\s*(?:FY)?\s*(\d{2})\b", combined, flags=re.I)
    if match:
        year = int(match.group(2))
        year += 2000 if year < 50 else 1900
        return str(year), match.group(1)
    return "", ""


def is_rule_line(line: str, char: str) -> bool:
    stripped = line.strip()
    return len(stripped) >= 8 and set(stripped) == {char}


def is_heading_line(line: str, heading: str) -> bool:
    return line.strip().lower() == heading.lower()


def find_heading(lines: list[str], heading: str) -> int | None:
    for idx, line in enumerate(lines):
        if is_heading_line(line, heading):
            return idx
    return None


def split_sections(body: str) -> dict[str, list[str]]:
    lines = body.splitlines()
    presentation_idx = find_heading(lines, "Presentation")
    qa_idx = find_heading(lines, "Questions and Answers")
    transcript_idx = find_heading(lines, "Transcript")

    sections: dict[str, list[str]] = {}
    if presentation_idx is not None:
        end_idx = qa_idx if qa_idx is not None and qa_idx > presentation_idx else len(lines)
        sections["presentation"] = lines[presentation_idx + 1 : end_idx]
    if qa_idx is not None:
        sections["qa"] = lines[qa_idx + 1 :]
    if not sections and transcript_idx is not None:
        sections["transcript"] = lines[transcript_idx + 1 :]
    if not sections:
        sections["body"] = lines
    return sections


def is_speaker_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if is_rule_line(stripped, "-") or is_rule_line(stripped, "="):
        return False
    return bool(re.search(r"\[\d+\]\s*$", stripped))


def clean_speaker(line: str) -> str:
    without_id = re.sub(r"\s*\[\d+\]\s*$", "", line).strip()
    without_id = re.sub(r"\s+", " ", without_id)
    return without_id.strip(" ,-")


def parse_turns(section_lines: list[str]) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    current_speaker = ""
    current_text: list[str] = []

    for raw_line in section_lines:
        line = raw_line.strip()
        if not line:
            continue
        if is_rule_line(line, "-") or is_rule_line(line, "="):
            continue
        if is_speaker_header(line):
            if current_text:
                turns.append((current_speaker, clean_text(" ".join(current_text))))
                current_text = []
            current_speaker = clean_speaker(line)
            continue
        current_text.append(line)

    if current_text:
        turns.append((current_speaker, clean_text(" ".join(current_text))))
    return turns


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    protected = text
    for idx, abbreviation in enumerate(ABBREVIATIONS):
        token = f"__ABBR{idx}__"
        protected = protected.replace(abbreviation, abbreviation.replace(".", token))
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\"])", protected)
    sentences = []
    for piece in pieces:
        sentence = piece
        for idx, abbreviation in enumerate(ABBREVIATIONS):
            token = f"__ABBR{idx}__"
            sentence = sentence.replace(abbreviation.replace(".", token), abbreviation)
        sentence = clean_text(sentence)
        if len(sentence) >= 2:
            sentences.append(sentence)
    return sentences


def build_sentence_id(document_id: str, section: str, sentence_index: int) -> str:
    safe_section = re.sub(r"[^a-z0-9]+", "_", section.lower()).strip("_")
    return f"{document_id}_{safe_section}_{sentence_index:05d}"


def parse_xml_file(xml_path: Path, root_dir: Path) -> Transcript:
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        return Transcript(
            metadata={
                "document_id": xml_path.stem.replace("_T", ""),
                "event_id": "",
                "company_name": "",
                "ticker": "",
                "call_date": "",
                "call_year": "",
                "call_quarter": "",
                "reported_year": "",
                "reported_quarter": "",
                "event_title": "",
                "headline": "",
                "xml_path": str(xml_path),
                "parse_status": "xml_error",
                "parse_note": str(exc),
            },
            sentences=[],
        )

    event_id = root.attrib.get("Id", "")
    document_id = event_id or xml_path.stem.replace("_T", "")
    headline = child_text(root, "Headline")
    body = raw_child_text(root, "Body")
    event_title = child_text(root, "eventTitle")
    company_name = child_text(root, "companyName")
    ticker = child_text(root, "companyTicker")
    raw_start_date = child_text(root, "startDate")
    call_date, call_year, call_quarter = parse_call_date(raw_start_date)
    reported_year, reported_quarter = parse_reported_period(event_title, headline, body[:200])

    metadata = {
        "document_id": document_id,
        "event_id": event_id,
        "company_name": company_name,
        "ticker": ticker,
        "call_date": call_date,
        "call_year": call_year,
        "call_quarter": call_quarter,
        "reported_year": reported_year,
        "reported_quarter": reported_quarter,
        "event_title": event_title,
        "headline": headline,
        "xml_path": str(xml_path.relative_to(root_dir.parent) if root_dir.parent in xml_path.parents else xml_path),
        "parse_status": "ok" if body else "missing_body",
        "parse_note": "",
    }

    sentence_rows: list[dict[str, str]] = []
    sentence_index = 0
    if body:
        for section, section_lines in split_sections(body).items():
            for speaker, turn_text in parse_turns(section_lines):
                for sentence in split_sentences(turn_text):
                    sentence_index += 1
                    sentence_rows.append(
                        {
                            "document_id": document_id,
                            "event_id": event_id,
                            "company_name": company_name,
                            "ticker": ticker,
                            "call_date": call_date,
                            "call_year": call_year,
                            "call_quarter": call_quarter,
                            "reported_year": reported_year,
                            "reported_quarter": reported_quarter,
                            "section": section,
                            "speaker": speaker,
                            "sentence_id": build_sentence_id(document_id, section, sentence_index),
                            "sentence_index": str(sentence_index),
                            "sentence": sentence,
                            "xml_path": metadata["xml_path"],
                        }
                    )

    return Transcript(metadata=metadata, sentences=sentence_rows)


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    xml_files = list_xml_files(input_dir, args.year)
    sample_files = xml_files if args.limit <= 0 else xml_files[: args.limit]
    total_files = len(sample_files)

    metadata_path = output_dir / "transcript_metadata.csv"
    sentences_path = output_dir / "transcript_sentences.csv"

    print(f"Found {len(xml_files)} XML files.")
    print(f"Parsing {total_files} XML files.")
    started_at = time.monotonic()

    metadata_count = 0
    sentence_count = 0
    with metadata_path.open("w", newline="", encoding="utf-8") as metadata_handle:
        with sentences_path.open("w", newline="", encoding="utf-8") as sentences_handle:
            metadata_writer = csv.DictWriter(metadata_handle, fieldnames=METADATA_FIELDS)
            sentences_writer = csv.DictWriter(sentences_handle, fieldnames=SENTENCE_FIELDS)
            metadata_writer.writeheader()
            sentences_writer.writeheader()

            for idx, xml_path in enumerate(sample_files, start=1):
                transcript = parse_xml_file(xml_path, input_dir)
                metadata_writer.writerow(transcript.metadata)
                metadata_count += 1
                for sentence_row in transcript.sentences:
                    sentences_writer.writerow(sentence_row)
                    sentence_count += 1

                if args.progress_every > 0 and (idx % args.progress_every == 0 or idx == total_files):
                    print(progress_line(idx, total_files, started_at), flush=True)

    print(f"Parsed {len(sample_files)} XML files.")
    print(f"Wrote {metadata_count} transcript metadata rows.")
    print(f"Wrote {sentence_count} sentence rows.")
    print(f"Output directory: {output_dir}")
    print(f"Metadata CSV: {metadata_path}")
    print(f"Sentences CSV: {sentences_path}")


if __name__ == "__main__":
    main()
