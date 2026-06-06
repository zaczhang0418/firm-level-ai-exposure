#!/usr/bin/env python3
"""Small local benchmark for Stage 04 Word2Vec settings."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from time import perf_counter

from gensim.models import Word2Vec

from train_word2vec import (
    DEFAULT_LEXICON,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SENTENCES,
    SeedPhraseMatcher,
    TranscriptSentenceCorpus,
    default_workers,
    load_seed_entries,
    resolve_sentence_files,
)

try:
    import psutil
except ImportError:  # pragma: no cover - optional diagnostics only
    psutil = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark a tiny Stage 04 Word2Vec run on this machine."
    )
    parser.add_argument("--sentences", default=DEFAULT_SENTENCES)
    parser.add_argument("--lexicon", default=DEFAULT_LEXICON)
    parser.add_argument("--output-dir", default=f"{DEFAULT_OUTPUT_DIR}/smoke_test")
    parser.add_argument("--sample-rows", type=int, default=25000)
    parser.add_argument("--vector-size", type=int, default=50)
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--min-count", type=int, default=2)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument(
        "--worker-candidates",
        default="1,8,16",
        help="Comma-separated worker counts to test.",
    )
    return parser.parse_args()


def benchmark_workers(args: argparse.Namespace) -> list[dict[str, str]]:
    sentence_files = resolve_sentence_files(args.sentences)
    seed_entries = load_seed_entries(Path(args.lexicon), include_review=False)
    matcher = SeedPhraseMatcher(entry.term for entry in seed_entries)
    worker_candidates = sorted(
        {
            max(1, min(int(value.strip()), os.cpu_count() or 1))
            for value in args.worker_candidates.split(",")
            if value.strip()
        }
    )

    rows: list[dict[str, str]] = []
    for workers in worker_candidates:
        corpus = TranscriptSentenceCorpus(
            sentence_files=sentence_files,
            matcher=matcher,
            limit=args.sample_rows,
            progress_every=0,
        )
        model = Word2Vec(
            vector_size=args.vector_size,
            window=args.window,
            min_count=args.min_count,
            workers=workers,
            sg=1,
            negative=5,
            seed=42,
        )
        started = perf_counter()
        model.build_vocab(corpus)
        model.train(corpus, total_examples=model.corpus_count, epochs=args.epochs)
        seconds = perf_counter() - started
        words_per_second = model.corpus_total_words / seconds if seconds else 0.0
        rows.append(
            {
                "workers": str(workers),
                "seconds": f"{seconds:.3f}",
                "sentences": str(model.corpus_count),
                "words": str(model.corpus_total_words),
                "vocab_size": str(len(model.wv)),
                "words_per_second": f"{words_per_second:.1f}",
            }
        )
        print(
            f"workers={workers}: {seconds:.2f}s, "
            f"{words_per_second:,.0f} words/sec, vocab={len(model.wv):,}",
            flush=True,
        )
    return rows


def write_summary(args: argparse.Namespace, rows: list[dict[str, str]]) -> Path:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "smoke_test_summary.csv"
    best = max(rows, key=lambda row: float(row["words_per_second"])) if rows else None

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "workers",
            "seconds",
            "sentences",
            "words",
            "vocab_size",
            "words_per_second",
            "logical_cpu_count",
            "physical_cpu_count",
            "memory_gb",
            "default_recommended_workers",
            "best_smoke_workers",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            enriched = dict(row)
            enriched["logical_cpu_count"] = str(os.cpu_count() or "")
            enriched["physical_cpu_count"] = (
                str(psutil.cpu_count(logical=False) or "") if psutil else ""
            )
            enriched["memory_gb"] = (
                f"{psutil.virtual_memory().total / (1024 ** 3):.2f}" if psutil else ""
            )
            enriched["default_recommended_workers"] = str(default_workers())
            enriched["best_smoke_workers"] = best["workers"] if best else ""
            writer.writerow(enriched)
    return summary_path


def main() -> None:
    args = parse_args()
    print(f"logical CPUs: {os.cpu_count()}")
    if psutil is not None:
        print(f"physical CPUs: {psutil.cpu_count(logical=False)}")
        print(f"memory GB: {psutil.virtual_memory().total / (1024 ** 3):.2f}")
    print(f"default recommended workers: {default_workers()}")
    print(f"sample rows: {args.sample_rows}")

    rows = benchmark_workers(args)
    summary_path = write_summary(args, rows)
    best = max(rows, key=lambda row: float(row["words_per_second"]))
    print(f"best smoke-test workers: {best['workers']}")
    print(f"summary: {summary_path}")


if __name__ == "__main__":
    main()
