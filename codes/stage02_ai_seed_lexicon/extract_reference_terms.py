#!/usr/bin/env python3
"""Scan AI reference PDFs for seed-term evidence.

This script is only for Stage 02 literature grounding. It extracts text from
priority AI PDFs and reports which candidate terms appear in which references.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = ROOT / "Reference"
STAGE_DIR = Path(__file__).resolve().parent

SCAN_TERMS = [
    "artificial intelligence",
    "AI",
    "machine learning",
    "deep learning",
    "neural network",
    "natural language processing",
    "NLP",
    "computer vision",
    "image recognition",
    "speech recognition",
    "reinforcement learning",
    "predictive analytics",
    "prediction",
    "algorithmic",
    "generative AI",
    "large language model",
    "LLM",
    "ChatGPT",
    "GPT",
    "foundation model",
    "prompt",
    "chatbot",
    "recommendation",
    "automated underwriting",
    "robotic process automation",
    "robotics",
    "automation",
]


def load_sources() -> list[dict[str, str]]:
    path = STAGE_DIR / "reference_sources.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def extract_text(pdf_path: Path, max_pages: int | None = None) -> str:
    reader = PdfReader(str(pdf_path))
    pages = reader.pages[:max_pages] if max_pages else reader.pages
    text_parts: list[str] = []
    for page in pages:
        text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def count_term(text: str, term: str) -> int:
    if term.isupper() and len(term) <= 4:
        pattern = rf"\b{re.escape(term)}s?\b"
    else:
        pattern = rf"\b{re.escape(term)}s?\b"
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def main() -> None:
    output_dir = STAGE_DIR / "outputs"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "reference_term_hits.csv"

    rows: list[dict[str, str]] = []
    for source in load_sources():
        pdf_path = REFERENCE_DIR / source["filename"]
        if not pdf_path.exists():
            rows.append(
                {
                    "reference_id": source["reference_id"],
                    "short_citation": source["short_citation"],
                    "term": "",
                    "hit_count": "0",
                    "status": "missing_pdf",
                }
            )
            continue
        text = extract_text(pdf_path)
        for term in SCAN_TERMS:
            hits = count_term(text, term)
            if hits:
                rows.append(
                    {
                        "reference_id": source["reference_id"],
                        "short_citation": source["short_citation"],
                        "term": term,
                        "hit_count": str(hits),
                        "status": "ok",
                    }
                )

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["reference_id", "short_citation", "term", "hit_count", "status"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
