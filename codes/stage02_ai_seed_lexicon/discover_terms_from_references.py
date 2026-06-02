#!/usr/bin/env python3
"""Discover AI expressions from the reference PDFs.

This script is intentionally literature-first:
1. Extract text from teacher-selected AI references.
2. Find sentences/metadata where the paper itself discusses AI.
3. Extract candidate expressions from those sentences.
4. Save the expressions with reference IDs and evidence snippets.

The output is not the final seed lexicon. It is the evidence table used to
decide which literature expressions should enter the seed lexicon.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = ROOT / "Reference"
STAGE_DIR = Path(__file__).resolve().parent

# Broad anchors only define "AI discussion context"; they are not the final
# seed list. Candidate expressions are extracted from the surrounding text.
AI_CONTEXT_ANCHORS = [
    r"\bartificial intelligence\b",
    r"\bAI\b",
    r"\bgenerative\b",
    r"\bChatGPT\b",
    r"\bLLM[s]?\b",
]

STOP_STARTS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "in",
    "on",
    "for",
    "to",
    "with",
    "by",
    "from",
    "our",
    "their",
    "this",
    "that",
}

BAD_PHRASE_WORDS = {
    "between",
    "because",
    "which",
    "where",
    "when",
    "while",
    "whether",
    "using",
    "uses",
    "used",
    "based",
    "relationship",
    "increase",
    "decrease",
    "measure",
    "sample",
    "proportion",
    "comparison",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = text.replace("\x00", "")
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_sources() -> list[dict[str, str]]:
    with (STAGE_DIR / "reference_sources.csv").open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row["priority"] in {"high", "medium"}]


def extract_pdf_text(pdf_path: Path, max_pages: int | None = None) -> tuple[str, dict[str, str]]:
    reader = PdfReader(str(pdf_path))
    pages = reader.pages[:max_pages] if max_pages else reader.pages
    text = "\n".join(page.extract_text() or "" for page in pages)
    metadata = {}
    if reader.metadata:
        for key, value in reader.metadata.items():
            metadata[str(key).lstrip("/")] = str(value)
    return normalize_text(text), metadata


def split_sentences(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [piece.strip() for piece in pieces if len(piece.strip()) >= 20]


def is_ai_context(sentence: str) -> bool:
    return any(re.search(anchor, sentence, flags=re.IGNORECASE) for anchor in AI_CONTEXT_ANCHORS)


def clean_candidate(candidate: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9+\- ]+", "", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip(" -")
    return candidate


def valid_candidate(candidate: str) -> bool:
    if not candidate or len(candidate) < 2:
        return False
    words = candidate.lower().split()
    if words[0] in STOP_STARTS:
        return False
    if any(word in BAD_PHRASE_WORDS for word in words):
        return False
    if len(words) > 6:
        return False
    if len(candidate) == 2 and not candidate.isupper():
        return False
    return True


def extract_candidates(sentence: str) -> set[str]:
    candidates: set[str] = set()

    patterns = [
        # Expressions where AI modifies an economic/technical concept.
        r"\bAI[- ](?:related|based|enabled|powered|skilled|equipped|guided|intensive|driven)?[- ]?(?:investments?|adoption|technolog(?:y|ies)|applications?|systems?|tools?|models?|skills?|workers?|jobs?|labor|human capital|exposure|intensity|innovation|capabilities|solutions|implementation|integration|infrastructure|software)\b",
        r"\bAI\s+(?:analysts?|agents?|economy score|narrative|divide|readiness|strategy|transformation)\b",
        # Expressions where AI is the concept being modified.
        r"\b(?:generative|firm-level|company-level|workplace|frontier|modern|advanced)\s+AI\b",
        # Explicit artificial-intelligence phrases with limited suffixes.
        r"\bartificial intelligence(?:\s+(?:technolog(?:y|ies)|applications?|systems?|tools?|models?|investments?|adoption|innovation|capabilities))?\b",
        # Generative AI and LLM family expressions.
        r"\bgenerative\s+[A-Za-z][A-Za-z+\-]*(?:\s+[A-Za-z][A-Za-z+\-]*){0,3}",
        r"\blarge language models?\b",
        r"\bfoundation models?\b",
        r"\bChatGPT\b",
        r"\bGPT-?[0-9A-Za-z]*\b",
        r"\bLLMs?\b",
        # Common technical noun phrases appearing in AI-context sentences.
        r"\b(?:machine|deep|reinforcement|supervised|unsupervised|statistical|automated)\s+learning\b",
        r"\b(?:neural|deep neural|convolutional neural|artificial neural)\s+networks?\b",
        r"\bnatural language processing\b",
        r"\bcomputer vision\b",
        r"\b(?:image|speech|voice|facial|pattern)\s+recognition\b",
        r"\bautomated underwriting\b",
        r"\bmachine intelligence\b",
        r"\bautomation technologies\b",
        r"\brobotic process automation\b",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, sentence, flags=re.IGNORECASE):
            candidate = clean_candidate(match.group(0))
            if valid_candidate(candidate):
                candidates.add(candidate)
    return candidates


def snippet_for(sentence: str, candidate: str, limit: int = 260) -> str:
    sentence = sentence.strip()
    if len(sentence) <= limit:
        return sentence
    idx = sentence.lower().find(candidate.lower())
    if idx < 0:
        return sentence[:limit].strip()
    start = max(0, idx - 90)
    end = min(len(sentence), idx + len(candidate) + 120)
    return sentence[start:end].strip()


def add_metadata_candidates(
    rows: dict[tuple[str, str], dict[str, str]],
    source: dict[str, str],
    metadata: dict[str, str],
) -> None:
    metadata_text = " ".join(metadata.get(key, "") for key in ["Title", "Subject", "Keywords"])
    for raw_piece in re.split(r"[,;|]", metadata_text):
        piece = clean_candidate(raw_piece)
        if not valid_candidate(piece):
            continue
        if not is_ai_context(piece):
            continue
        key = (source["reference_id"], piece.lower())
        rows.setdefault(
            key,
            {
                "candidate_expression": piece,
                "reference_id": source["reference_id"],
                "short_citation": source["short_citation"],
                "source_location": "pdf_metadata",
                "hit_count": "0",
                "evidence_snippet": piece,
                "decision": "review",
                "decision_note": "",
            },
        )


def main() -> None:
    output_dir = STAGE_DIR / "outputs"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "literature_discovered_terms.csv"

    discovered: dict[tuple[str, str], dict[str, str]] = {}
    hit_counts: defaultdict[tuple[str, str], int] = defaultdict(int)

    for source in load_sources():
        pdf_path = REFERENCE_DIR / source["filename"]
        if not pdf_path.exists():
            continue
        text, metadata = extract_pdf_text(pdf_path)
        add_metadata_candidates(discovered, source, metadata)

        for sentence in split_sentences(text):
            if not is_ai_context(sentence):
                continue
            for candidate in extract_candidates(sentence):
                key = (source["reference_id"], candidate.lower())
                hit_counts[key] += 1
                row = discovered.setdefault(
                    key,
                    {
                        "candidate_expression": candidate,
                        "reference_id": source["reference_id"],
                        "short_citation": source["short_citation"],
                        "source_location": "body_context",
                        "hit_count": "0",
                        "evidence_snippet": snippet_for(sentence, candidate),
                        "decision": "review",
                        "decision_note": "",
                    },
                )
                if row["source_location"] != "pdf_metadata":
                    row["evidence_snippet"] = snippet_for(sentence, candidate)

    rows = []
    for key, row in discovered.items():
        row = dict(row)
        row["hit_count"] = str(hit_counts.get(key, 1 if row["source_location"] == "pdf_metadata" else 0))
        rows.append(row)

    rows.sort(key=lambda row: (row["candidate_expression"].lower(), row["reference_id"]))

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_expression",
                "reference_id",
                "short_citation",
                "source_location",
                "hit_count",
                "evidence_snippet",
                "decision",
                "decision_note",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} discovered expression rows to {output_path}")


if __name__ == "__main__":
    main()
