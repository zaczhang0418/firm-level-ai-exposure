#!/usr/bin/env python3
"""Auto-screen Stage 04 Word2Vec expansion candidates.

This is a conservative triage helper, not a replacement for final review. It
fills review_decision/include_v2 drafts so the reviewer can focus on gray-area
terms instead of coding every candidate from scratch.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


DEFAULT_INPUT = "codes/stage04_word2vec_expansion/outputs/expanded_ai_terms_candidates.csv"
DEFAULT_OUTPUT = (
    "codes/stage04_word2vec_expansion/outputs/expanded_ai_terms_candidates_screened.csv"
)
DEFAULT_SUMMARY = "codes/stage04_word2vec_expansion/outputs/stage04_auto_screen_summary.csv"

REQUIRED_COLUMNS = {
    "candidate_term",
    "candidate_token",
    "neighbor_count",
    "seed_count",
    "best_rank",
    "max_similarity",
    "mean_similarity",
    "review_decision",
    "include_v2",
    "review_notes",
}

EXPLICIT_AI_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bai\b",
        r"\bgen\s*ai\b",
        r"\bgenai\b",
        r"\bartificial intelligence\b",
        r"\bmachine[-\s]learning\b",
        r"\bdeep[-\s]learning\b",
        r"\bneural\b",
        r"\bllm'?s?\b",
        r"\blarge[-\s]language[-\s]models?\b",
        r"\bchat\s*gpt\b",
        r"\bchatgpt[-\w']*\b",
        r"\bgpt[-\w']*\b",
        r"\bopenai\b",
        r"\btransformer(s)?\b",
        r"\bnatural[-\s]language(?:[-\s]processing)?\b",
        r"\bnlp\b",
        r"\bnlu\b",
        r"\bcomputer[-\s]vision\b",
        r"\breinforcement[-\s]learning\b",
        r"\b(supervised|unsupervised)[-\s]learning\b",
        r"\brecommender[-\s]systems?\b",
        r"\bxgboost\b",
        r"\bpre[-\s]?trained\b",
        r"\bpretrained[-\s]models?\b",
        r"\bartificial[-\s]intelligent\b",
        r"\bcognitive[-\s]computing\b",
        r"\baugmented[-\s]intelligence\b",
        r"\bneuromorphic[-\s]computing\b",
        r"\baigc\b",
        r"\baiml\b",
        r"\bautoml\b",
        r"\bcopilots?\b",
        r"\bgithub[-\s]copilot\b",
        r"\bmicrosoft[-\s]copilot\b",
        r"\blangchain\b",
        r"\bdall[-\s]?e\b",
        r"\bchatbots?\b",
        r"\btext[-\s]to[-\s](image|code|speech)\b",
        r"\brlhf\b",
        r"\bdnns?\b",
        r"\bcnn[-\s]based\b",
    ]
]

BROAD_TERMS = {
    "algorithm",
    "algorithms",
    "analytic",
    "analytics",
    "application",
    "applications",
    "automation",
    "automate",
    "automating",
    "autonomous",
    "capabilities",
    "capability",
    "camera",
    "compute",
    "computing",
    "computational",
    "cutting-edge",
    "digital",
    "digitalization",
    "instrumentation",
    "intelligence",
    "intelligent",
    "investments",
    "model",
    "models",
    "prediction",
    "predictive",
    "robot",
    "robotic",
    "robots",
    "scoring",
    "software",
    "tool",
    "tools",
    "underwriting",
    "workflow",
    "workflows",
}

COMPANY_OR_PRODUCT_HINTS = {
    "academy",
    "arteria",
    "charter",
    "coles",
    "digilens",
    "jll",
    "moneyswitch",
    "superannuation",
    "trustee",
    "wesfarmers",
}

@dataclass(frozen=True)
class Metrics:
    term: str
    token: str
    neighbor_count: int
    seed_count: int
    best_rank: int
    max_similarity: float
    mean_similarity: float


@dataclass(frozen=True)
class Decision:
    review_decision: str
    include_v2: str
    confidence: str
    reason: str


@dataclass(frozen=True)
class ReviewGroup:
    priority: int
    label: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Conservatively auto-screen Stage 04 Word2Vec candidate terms."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Candidate CSV from Stage 04.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Screened candidate CSV.")
    parser.add_argument("--summary", default=DEFAULT_SUMMARY, help="Decision count summary CSV.")
    parser.add_argument(
        "--explicit-ai-min-similarity",
        type=float,
        default=0.62,
        help="Minimum max_similarity for auto-accepting explicit AI/method terms.",
    )
    parser.add_argument(
        "--low-evidence-max-similarity",
        type=float,
        default=0.62,
        help="Single-seed non-explicit terms below this are auto-rejected.",
    )
    parser.add_argument(
        "--low-evidence-rank",
        type=int,
        default=30,
        help="Single-seed non-explicit terms with worse ranks are auto-rejected.",
    )
    parser.add_argument(
        "--high-frequency-threshold",
        type=int,
        default=100000,
        help="Very frequent non-explicit single-seed terms are treated as too broad.",
    )
    return parser.parse_args()


def to_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fieldnames
        if missing:
            raise ValueError(f"Missing required columns in {path}: {sorted(missing)}")
        return list(reader)


def metrics_from_row(row: dict[str, str]) -> Metrics:
    return Metrics(
        term=(row.get("candidate_term") or "").strip().lower(),
        token=(row.get("candidate_token") or "").strip().lower(),
        neighbor_count=to_int(row.get("neighbor_count", "")),
        seed_count=to_int(row.get("seed_count", "")),
        best_rank=to_int(row.get("best_rank", "")),
        max_similarity=to_float(row.get("max_similarity", "")),
        mean_similarity=to_float(row.get("mean_similarity", "")),
    )


def has_explicit_ai_signal(term: str) -> bool:
    return any(pattern.search(term) for pattern in EXPLICIT_AI_PATTERNS)


def is_broad(term: str) -> bool:
    pieces = set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", term.lower()))
    return term.lower() in BROAD_TERMS or bool(pieces & BROAD_TERMS)


def has_company_or_product_hint(term: str) -> bool:
    pieces = set(re.findall(r"[a-z0-9]+", term.lower()))
    return bool(pieces & COMPANY_OR_PRODUCT_HINTS)


def decide(metrics: Metrics, args: argparse.Namespace) -> Decision:
    explicit_ai = has_explicit_ai_signal(metrics.term)
    broad = is_broad(metrics.term)
    company_hint = has_company_or_product_hint(metrics.term)

    if explicit_ai and metrics.max_similarity >= args.explicit_ai_min_similarity:
        if metrics.seed_count >= 2 or metrics.best_rank <= 20 or metrics.neighbor_count >= 5:
            return Decision(
                "accept",
                "1",
                "high",
                "explicit_ai_signal_with_word2vec_support",
            )

    if broad and not explicit_ai:
        return Decision("too_broad", "0", "high", "generic_business_or_tech_term")

    if (
        metrics.neighbor_count >= args.high_frequency_threshold
        and metrics.seed_count <= 2
        and not explicit_ai
    ):
        return Decision("too_broad", "0", "high", "very_high_frequency_without_ai_signal")

    if (
        metrics.seed_count == 1
        and not explicit_ai
        and (
            metrics.max_similarity < args.low_evidence_max_similarity
            or metrics.best_rank > args.low_evidence_rank
        )
    ):
        return Decision("reject", "0", "high", "single_seed_low_similarity_or_rank")

    if company_hint and not explicit_ai and metrics.seed_count <= 2:
        return Decision("reject", "0", "medium", "likely_company_or_product_name")

    if metrics.seed_count >= 8 and metrics.max_similarity >= 0.70 and not broad:
        return Decision("maybe", "", "medium", "strong_word2vec_support_needs_domain_review")

    if metrics.seed_count >= 3 and metrics.mean_similarity >= 0.68 and not broad:
        return Decision("maybe", "", "medium", "multi_seed_support_needs_domain_review")

    return Decision("maybe", "", "low", "manual_review_needed")


def review_group(metrics: Metrics, decision: Decision) -> ReviewGroup:
    if decision.review_decision == "maybe":
        if metrics.seed_count >= 8 and metrics.max_similarity >= 0.70:
            return ReviewGroup(1, "maybe_1_strong_multi_seed_support")
        if metrics.seed_count >= 3 and metrics.mean_similarity >= 0.68:
            return ReviewGroup(2, "maybe_2_multi_seed_support")
        if metrics.max_similarity >= 0.70 or metrics.best_rank <= 10:
            return ReviewGroup(3, "maybe_3_high_similarity_or_rank")
        return ReviewGroup(4, "maybe_4_low_priority_manual_review")

    if decision.review_decision == "accept":
        return ReviewGroup(5, "accepted_explicit_ai_signal")
    if decision.review_decision == "too_broad":
        return ReviewGroup(6, "rejected_too_broad")
    return ReviewGroup(7, "rejected_low_evidence_or_noise")


def sort_key(row: dict[str, str]) -> tuple[int, int, float, int, str]:
    return (
        to_int(row.get("review_priority", "")),
        -to_int(row.get("seed_count", "")),
        -to_float(row.get("max_similarity", "")),
        to_int(row.get("best_rank", "")),
        row.get("candidate_term", ""),
    )


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def screen_rows(rows: list[dict[str, str]], args: argparse.Namespace) -> list[dict[str, str]]:
    screened: list[dict[str, str]] = []
    for row in rows:
        metrics = metrics_from_row(row)
        decision = decide(metrics, args)
        group = review_group(metrics, decision)
        updated = dict(row)
        updated["review_decision"] = decision.review_decision
        updated["include_v2"] = decision.include_v2
        existing_notes = (updated.get("review_notes") or "").strip()
        auto_note = (
            f"auto_screen_confidence={decision.confidence}; "
            f"auto_screen_reason={decision.reason}"
        )
        updated["review_notes"] = f"{existing_notes} | {auto_note}" if existing_notes else auto_note
        updated["review_priority"] = str(group.priority)
        updated["suggested_review_group"] = group.label
        updated["auto_screen_confidence"] = decision.confidence
        updated["auto_screen_reason"] = decision.reason
        screened.append(updated)
    return sorted(screened, key=sort_key)


def write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    counts = Counter((row["review_decision"], row["include_v2"]) for row in rows)
    summary_rows = [
        {
            "review_decision": decision,
            "include_v2": include,
            "count": str(count),
        }
        for (decision, include), count in sorted(counts.items())
    ]
    write_csv(path, summary_rows, ["review_decision", "include_v2", "count"])


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    summary_path = Path(args.summary)

    rows = load_rows(input_path)
    screened = screen_rows(rows, args)
    fieldnames = list(rows[0].keys()) + [
        "review_priority",
        "suggested_review_group",
        "auto_screen_confidence",
        "auto_screen_reason",
    ]
    write_csv(output_path, screened, fieldnames)
    write_summary(summary_path, screened)

    counts = Counter(row["review_decision"] for row in screened)
    print(f"screened candidates: {len(screened):,}")
    for decision, count in sorted(counts.items()):
        print(f"{decision}: {count:,}")
    print(f"screened csv: {output_path}")
    print(f"summary csv: {summary_path}")


if __name__ == "__main__":
    main()
