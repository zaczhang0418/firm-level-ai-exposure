#!/usr/bin/env python3
"""Train Word2Vec on Stage 01 transcript sentences and expand the AI lexicon.

Stage 04 goal:
    full Stage 01 sentence corpus + Stage 02 AI seed terms
    -> conference-call-specific Word2Vec model
    -> nearest-neighbor candidate terms for AI lexicon v2 review.

Word2Vec is trained on text, not on the dictionary. The dictionary is used
after training to query neighborhoods around known AI terms.
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import platform
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Iterable

import gensim
import numpy as np
from gensim.models import Phrases, Word2Vec
from gensim.models.callbacks import CallbackAny2Vec
from gensim.models.phrases import Phraser

try:
    import psutil
except ImportError:  # pragma: no cover - optional diagnostics only
    psutil = None

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover - optional progress dependency
    tqdm = None


DEFAULT_SENTENCES = "codes/stage01_xml_standardization/outputs/by_year"
DEFAULT_LEXICON = "codes/stage02_ai_seed_lexicon/ai_seed_lexicon_v1.csv"
DEFAULT_OUTPUT_DIR = "codes/stage04_word2vec_expansion/outputs"

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#]*(?:[-'][A-Za-z0-9+#]+)*")

REQUIRED_LEXICON_COLUMNS = {
    "concept_group",
    "term",
    "priority",
    "include",
}


@dataclass(frozen=True)
class SeedEntry:
    concept_group: str
    term: str
    priority: str
    include: str
    key: str


class SeedPhraseMatcher:
    """Greedily joins known multi-token seed phrases with underscores."""

    def __init__(self, seed_terms: Iterable[str]) -> None:
        phrase_tokens: set[tuple[str, ...]] = set()
        for term in seed_terms:
            tokens = tokenize_basic(term)
            if len(tokens) >= 2:
                phrase_tokens.add(tuple(tokens))

        self.phrase_tokens = phrase_tokens
        self.by_first: dict[str, list[tuple[str, ...]]] = defaultdict(list)
        for phrase in sorted(phrase_tokens, key=len, reverse=True):
            self.by_first[phrase[0]].append(phrase)

    def apply(self, tokens: list[str]) -> list[str]:
        output: list[str] = []
        i = 0
        while i < len(tokens):
            matched: tuple[str, ...] | None = None
            for phrase in self.by_first.get(tokens[i], []):
                j = i + len(phrase)
                if tuple(tokens[i:j]) == phrase:
                    matched = phrase
                    break
            if matched:
                output.append("_".join(matched))
                i += len(matched)
            else:
                output.append(tokens[i])
                i += 1
        return output


class TranscriptSentenceCorpus:
    """Reusable streaming corpus over Stage 01 transcript_sentences.csv files."""

    def __init__(
        self,
        sentence_files: list[Path],
        matcher: SeedPhraseMatcher,
        limit: int | None = None,
        progress_every: int = 0,
        total_sentences: int | None = None,
        progress_bar: bool = True,
        progress_label: str = "stream sentences",
    ) -> None:
        self.sentence_files = sentence_files
        self.matcher = matcher
        self.limit = limit
        self.progress_every = progress_every
        self.total_sentences = total_sentences
        self.progress_bar = progress_bar
        self.progress_label = progress_label

    def set_progress_label(self, label: str) -> None:
        self.progress_label = label

    def __iter__(self) -> Iterable[list[str]]:
        yielded = 0
        bar = None
        if self.progress_bar and tqdm is not None:
            bar = tqdm(
                total=self.total_sentences,
                desc=self.progress_label,
                unit="sent",
                dynamic_ncols=True,
                leave=True,
                file=sys.stdout,
            )
        try:
            for csv_path in self.sentence_files:
                with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    if not reader.fieldnames or "sentence" not in reader.fieldnames:
                        raise ValueError(f"Missing required 'sentence' column in {csv_path}")

                    for row in reader:
                        tokens = self.matcher.apply(tokenize_basic(row.get("sentence", "")))
                        if tokens:
                            yield tokens
                            yielded += 1
                            if bar is not None:
                                bar.update(1)

                        if (
                            bar is None
                            and self.progress_every
                            and yielded % self.progress_every == 0
                        ):
                            print(f"streamed {yielded:,} sentences", flush=True)

                        if self.limit is not None and yielded >= self.limit:
                            return
        finally:
            if bar is not None:
                bar.close()


class PhraseTransformedCorpus:
    """Applies learned bigram/trigram phrasers to a reusable corpus."""

    def __init__(
        self,
        base_corpus: TranscriptSentenceCorpus,
        bigram: Phraser | None,
        trigram: Phraser | None,
    ) -> None:
        self.base_corpus = base_corpus
        self.bigram = bigram
        self.trigram = trigram

    def __iter__(self) -> Iterable[list[str]]:
        for tokens in self.base_corpus:
            if self.bigram is not None:
                tokens = self.bigram[tokens]
            if self.trigram is not None:
                tokens = self.trigram[tokens]
            yield list(tokens)


class ProgressIterable:
    """Adds one tqdm bar around an arbitrary iterable."""

    def __init__(
        self,
        iterable: Iterable[list[str]],
        total: int | None,
        label: str,
        enabled: bool,
    ) -> None:
        self.iterable = iterable
        self.total = total
        self.label = label
        self.enabled = enabled

    def __iter__(self) -> Iterable[list[str]]:
        if not self.enabled or tqdm is None:
            yield from self.iterable
            return

        with tqdm(
            total=self.total,
            desc=self.label,
            unit="sent",
            dynamic_ncols=True,
            leave=True,
            file=sys.stdout,
        ) as bar:
            for item in self.iterable:
                yield item
                bar.update(1)


class EpochProgressCallback(CallbackAny2Vec):
    """Print a compact per-epoch progress line for gensim training."""

    def __init__(self, epochs: int, checkpoint_dir: Path | None = None) -> None:
        self.epochs = epochs
        self.epoch = 0
        self.started = perf_counter()
        self.epoch_started = self.started
        self.checkpoint_dir = checkpoint_dir
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if self.checkpoint_dir is not None:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def on_epoch_begin(self, model: Word2Vec) -> None:
        self.epoch_started = perf_counter()
        print(f"epoch {self.epoch + 1}/{self.epochs} started", flush=True)

    def on_epoch_end(self, model: Word2Vec) -> None:
        self.epoch += 1
        elapsed = perf_counter() - self.epoch_started
        total_elapsed = perf_counter() - self.started
        print(
            f"epoch {self.epoch}/{self.epochs} done "
            f"({elapsed:.1f}s; total {total_elapsed:.1f}s)",
            flush=True,
        )
        if self.checkpoint_dir is not None:
            checkpoint_path = (
                self.checkpoint_dir
                / f"trained_word2vec_{self.run_id}_epoch_{self.epoch:03d}.model"
            )
            latest_path = self.checkpoint_dir / "trained_word2vec_latest.model"
            print(f"saving checkpoint: {checkpoint_path}", flush=True)
            model.save(str(checkpoint_path))
            model.save(str(latest_path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train Stage 04 Word2Vec model and export AI seed nearest neighbors."
    )
    parser.add_argument(
        "--sentences",
        default=DEFAULT_SENTENCES,
        help="Stage 01 transcript_sentences.csv path, directory, or glob pattern.",
    )
    parser.add_argument(
        "--lexicon",
        default=DEFAULT_LEXICON,
        help="Stage 02 ai_seed_lexicon_v1.csv path.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for model, neighbor CSVs, and diagnostics.",
    )
    parser.add_argument(
        "--include-review",
        action="store_true",
        help="Include lexicon rows with priority=review if include=1.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max sentence rows for testing. Omit for the full corpus.",
    )
    parser.add_argument("--vector-size", type=int, default=200)
    parser.add_argument("--window", type=int, default=8)
    parser.add_argument("--min-count", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--sg", type=int, choices=[0, 1], default=1, help="1=skip-gram, 0=CBOW.")
    parser.add_argument("--negative", type=int, default=10)
    parser.add_argument("--sample", type=float, default=1e-4)
    parser.add_argument(
        "--workers",
        type=int,
        default=default_workers(),
        help="Word2Vec worker threads. Defaults to a conservative machine-based value.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--topn", type=int, default=50)
    parser.add_argument(
        "--aggregate-mean-vector-neighbors",
        action="store_true",
        help=(
            "Allow fallback mean-vector query results into expanded candidates. "
            "By default they are kept only in seed_term_neighbors.csv."
        ),
    )
    parser.add_argument(
        "--include-generic-ai-neighbors",
        action="store_true",
        help=(
            "Allow neighbors from the standalone 'AI' seed into expanded candidates. "
            "By default they are kept only in seed_term_neighbors.csv."
        ),
    )
    parser.add_argument("--phrase-min-count", type=int, default=10)
    parser.add_argument("--phrase-threshold", type=float, default=10.0)
    parser.add_argument(
        "--no-statistical-phrases",
        action="store_true",
        help="Disable data-learned bigram/trigram phrasers; seed phrases are still joined.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100000,
        help="Print corpus streaming progress every N yielded sentences. Use 0 to disable.",
    )
    parser.add_argument(
        "--no-progress-bar",
        action="store_true",
        help="Disable tqdm progress bars and use text progress only.",
    )
    parser.add_argument(
        "--count-total-sentences",
        action="store_true",
        help=(
            "Pre-count sentence rows so tqdm can show percentages. "
            "This can be slow for the full 70GB+ corpus, so it is off by default."
        ),
    )
    parser.add_argument(
        "--resume-from-model",
        default=None,
        help=(
            "Optional trained_word2vec checkpoint/model path. If set, the script "
            "loads it and trains for --epochs additional epochs."
        ),
    )
    parser.add_argument(
        "--phrase-model-dir",
        default=None,
        help=(
            "Directory for saved bigram/trigram phrasers. Defaults to "
            "<output-dir>/phrase_models."
        ),
    )
    parser.add_argument(
        "--checkpoint-dir",
        default=None,
        help="Directory for per-epoch model checkpoints. Defaults to <output-dir>/checkpoints.",
    )
    parser.add_argument(
        "--no-epoch-checkpoints",
        action="store_true",
        help="Disable saving a model checkpoint after each training epoch.",
    )
    return parser.parse_args()


def default_workers() -> int:
    cpu_count = os.cpu_count() or 1
    if cpu_count <= 4:
        return max(1, cpu_count - 1)
    return max(1, min(cpu_count - 2, 16))


def tokenize_basic(text: str) -> list[str]:
    tokens = [match.group(0).lower() for match in TOKEN_RE.finditer(text or "")]
    normalized: list[str] = []
    for token in tokens:
        token = token.strip("-'")
        if token:
            normalized.append(token)
    return normalized


def resolve_sentence_files(value: str) -> list[Path]:
    raw = Path(value)
    if any(char in value for char in "*?[]"):
        files = [Path(path) for path in glob.glob(value, recursive=True)]
    elif raw.is_file():
        files = [raw]
    elif raw.is_dir():
        direct = raw / "transcript_sentences.csv"
        if direct.exists():
            files = [direct]
        else:
            files = sorted(raw.glob("**/transcript_sentences.csv"))
    else:
        raise FileNotFoundError(f"Could not resolve sentence input: {value}")

    files = sorted(path for path in files if path.is_file())
    if not files:
        raise FileNotFoundError(f"No transcript_sentences.csv files found under: {value}")
    return files


def count_sentence_rows(
    sentence_files: list[Path],
    limit: int | None,
    progress_bar: bool,
) -> int:
    total = 0
    bar = None
    if progress_bar and tqdm is not None:
        bar = tqdm(
            desc="count sentences",
            unit="sent",
            dynamic_ncols=True,
            leave=True,
            file=sys.stdout,
        )
    else:
        print("counting sentence rows...", flush=True)
    try:
        for csv_path in sentence_files:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for _ in reader:
                    total += 1
                    if bar is not None:
                        bar.update(1)
                    elif total % 100000 == 0:
                        print(f"counted {total:,} sentences", flush=True)
                    if limit is not None and total >= limit:
                        return total
    finally:
        if bar is not None:
            bar.close()
    return total


def load_seed_entries(lexicon_path: Path, include_review: bool) -> list[SeedEntry]:
    entries: list[SeedEntry] = []
    with lexicon_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_LEXICON_COLUMNS - fieldnames
        if missing:
            raise ValueError(f"Missing lexicon columns in {lexicon_path}: {sorted(missing)}")

        for row in reader:
            include = (row.get("include") or "").strip()
            priority = (row.get("priority") or "").strip().lower()
            term = (row.get("term") or "").strip()
            if include != "1" or not term:
                continue
            if priority == "review" and not include_review:
                continue

            basic_tokens = tokenize_basic(term)
            if not basic_tokens:
                continue
            key = "_".join(basic_tokens)
            entries.append(
                SeedEntry(
                    concept_group=(row.get("concept_group") or "").strip(),
                    term=term,
                    priority=priority,
                    include=include,
                    key=key,
                )
            )
    return entries


def build_phrase_models(
    base_corpus: TranscriptSentenceCorpus,
    min_count: int,
    threshold: float,
    disabled: bool,
) -> tuple[Phraser | None, Phraser | None]:
    if disabled:
        return None, None

    original_progress_bar = base_corpus.progress_bar
    base_corpus.progress_bar = False
    print("learning statistical bigram phrases...", flush=True)
    try:
        bigram_model = Phrases(
            ProgressIterable(
                base_corpus,
                total=base_corpus.total_sentences,
                label="learn bigrams",
                enabled=original_progress_bar,
            ),
            min_count=min_count,
            threshold=threshold,
            delimiter="_",
        )
        bigram = Phraser(bigram_model)

        print("learning statistical trigram phrases...", flush=True)
        trigram_model = Phrases(
            ProgressIterable(
                bigram[base_corpus],
                total=base_corpus.total_sentences,
                label="learn trigrams",
                enabled=original_progress_bar,
            ),
            min_count=min_count,
            threshold=threshold,
            delimiter="_",
        )
        trigram = Phraser(trigram_model)
    finally:
        base_corpus.progress_bar = original_progress_bar

    return bigram, trigram


def save_phrase_models(
    phrase_model_dir: Path,
    bigram: Phraser | None,
    trigram: Phraser | None,
) -> None:
    phrase_model_dir.mkdir(parents=True, exist_ok=True)
    if bigram is not None:
        bigram.save(str(phrase_model_dir / "bigram_phraser.pkl"))
    if trigram is not None:
        trigram.save(str(phrase_model_dir / "trigram_phraser.pkl"))


def load_phrase_models(phrase_model_dir: Path) -> tuple[Phraser | None, Phraser | None]:
    bigram_path = phrase_model_dir / "bigram_phraser.pkl"
    trigram_path = phrase_model_dir / "trigram_phraser.pkl"
    bigram = Phraser.load(str(bigram_path)) if bigram_path.exists() else None
    trigram = Phraser.load(str(trigram_path)) if trigram_path.exists() else None
    return bigram, trigram


def train_model(args: argparse.Namespace) -> tuple[Word2Vec, dict[str, str], list[SeedEntry]]:
    sentence_files = resolve_sentence_files(args.sentences)
    seed_entries = load_seed_entries(Path(args.lexicon), args.include_review)
    if not seed_entries:
        raise ValueError("No included seed terms found in the Stage 02 lexicon.")

    output_dir = Path(args.output_dir)
    phrase_model_dir = Path(args.phrase_model_dir) if args.phrase_model_dir else output_dir / "phrase_models"
    checkpoint_dir = Path(args.checkpoint_dir) if args.checkpoint_dir else output_dir / "checkpoints"

    matcher = SeedPhraseMatcher(entry.term for entry in seed_entries)
    progress_bar = not args.no_progress_bar
    if args.limit is not None:
        total_sentences = args.limit
        print(f"sentence row limit for this run: {total_sentences:,}", flush=True)
    elif args.count_total_sentences:
        total_sentences = count_sentence_rows(sentence_files, args.limit, progress_bar)
        print(f"total sentence rows for this run: {total_sentences:,}", flush=True)
    else:
        total_sentences = None
        print(
            "skipping full row pre-count; progress bars will show live counts without percentages",
            flush=True,
        )
    base_corpus = TranscriptSentenceCorpus(
        sentence_files=sentence_files,
        matcher=matcher,
        limit=args.limit,
        progress_every=args.progress_every,
        total_sentences=total_sentences,
        progress_bar=progress_bar,
    )

    started = perf_counter()
    if args.resume_from_model:
        print(f"loading Word2Vec checkpoint: {args.resume_from_model}", flush=True)
        model = Word2Vec.load(str(args.resume_from_model))
        print(f"loading phrase models from: {phrase_model_dir}", flush=True)
        bigram, trigram = load_phrase_models(phrase_model_dir)
        if not args.no_statistical_phrases and (bigram is None or trigram is None):
            raise FileNotFoundError(
                f"Missing saved phrase models in {phrase_model_dir}. "
                "Resume needs the same bigram/trigram phrasers used for the original run."
            )
        model.workers = args.workers
    else:
        bigram, trigram = build_phrase_models(
            base_corpus=base_corpus,
            min_count=args.phrase_min_count,
            threshold=args.phrase_threshold,
            disabled=args.no_statistical_phrases,
        )
        save_phrase_models(phrase_model_dir, bigram, trigram)
        print(f"phrase models saved to: {phrase_model_dir}", flush=True)

        training_corpus = PhraseTransformedCorpus(base_corpus, bigram, trigram)
        model = Word2Vec(
            vector_size=args.vector_size,
            window=args.window,
            min_count=args.min_count,
            workers=args.workers,
            sg=args.sg,
            negative=args.negative,
            sample=args.sample,
            seed=args.seed,
        )

        base_corpus.set_progress_label("build vocab")
        print("building vocabulary...", flush=True)
        model.build_vocab(training_corpus)

    print(
        f"training Word2Vec: examples={model.corpus_count:,}, "
        f"words={model.corpus_total_words:,}, vocab={len(model.wv):,}, "
        f"epochs={args.epochs}, workers={args.workers}",
        flush=True,
    )
    training_corpus = PhraseTransformedCorpus(base_corpus, bigram, trigram)
    base_corpus.set_progress_label("train corpus")
    model.train(
        training_corpus,
        total_examples=model.corpus_count,
        epochs=args.epochs,
        report_delay=30.0,
        callbacks=[
            EpochProgressCallback(
                args.epochs,
                checkpoint_dir=None if args.no_epoch_checkpoints else checkpoint_dir,
            )
        ],
    )

    elapsed = perf_counter() - started
    metrics = diagnostics(args, sentence_files, seed_entries, model, elapsed)
    return model, metrics, seed_entries


def diagnostics(
    args: argparse.Namespace,
    sentence_files: list[Path],
    seed_entries: list[SeedEntry],
    model: Word2Vec,
    elapsed_seconds: float,
) -> dict[str, str]:
    metrics = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "gensim": gensim.__version__,
        "logical_cpu_count": str(os.cpu_count() or ""),
        "recommended_workers": str(default_workers()),
        "workers": str(args.workers),
        "sentence_files": str(len(sentence_files)),
        "sentence_input": args.sentences,
        "lexicon": args.lexicon,
        "included_seed_terms": str(len(seed_entries)),
        "limit": "" if args.limit is None else str(args.limit),
        "vector_size": str(args.vector_size),
        "window": str(args.window),
        "min_count": str(args.min_count),
        "epochs": str(args.epochs),
        "sg": str(args.sg),
        "negative": str(args.negative),
        "sample": str(args.sample),
        "statistical_phrases": str(not args.no_statistical_phrases),
        "phrase_min_count": str(args.phrase_min_count),
        "phrase_threshold": str(args.phrase_threshold),
        "resume_from_model": args.resume_from_model or "",
        "phrase_model_dir": args.phrase_model_dir or str(Path(args.output_dir) / "phrase_models"),
        "checkpoint_dir": args.checkpoint_dir or str(Path(args.output_dir) / "checkpoints"),
        "epoch_checkpoints": str(not args.no_epoch_checkpoints),
        "model_corpus_count": str(model.corpus_count),
        "model_total_words": str(model.corpus_total_words),
        "vocab_size": str(len(model.wv)),
        "elapsed_seconds": f"{elapsed_seconds:.3f}",
    }
    if psutil is not None:
        metrics["physical_cpu_count"] = str(psutil.cpu_count(logical=False) or "")
        metrics["memory_gb"] = f"{psutil.virtual_memory().total / (1024 ** 3):.2f}"
    return metrics


def query_seed_neighbors(
    model: Word2Vec,
    seed_entries: list[SeedEntry],
    topn: int,
    aggregate_mean_vector_neighbors: bool,
    include_generic_ai_neighbors: bool,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    seed_keys = {entry.key for entry in seed_entries}
    seed_terms_normalized = {" ".join(tokenize_basic(entry.term)) for entry in seed_entries}
    aggregate: dict[str, dict[str, object]] = {}
    rows: list[dict[str, str]] = []

    for entry in seed_entries:
        query_key = entry.key
        query_status = "exact_key"
        neighbors: list[tuple[str, float]] = []

        if query_key in model.wv:
            neighbors = model.wv.most_similar(query_key, topn=topn + 10)
        else:
            token_keys = [token for token in query_key.split("_") if token in model.wv]
            if token_keys:
                query_status = "mean_vector"
                vector = np.mean([model.wv[token] for token in token_keys], axis=0)
                neighbors = model.wv.similar_by_vector(vector, topn=topn + len(token_keys) + 10)
            else:
                query_status = "missing"

        rank = 0
        for neighbor, score in neighbors:
            if neighbor == query_key:
                continue
            rank += 1
            if rank > topn:
                break

            neighbor_count = model.wv.get_vecattr(neighbor, "count")
            row = {
                "concept_group": entry.concept_group,
                "seed_term": entry.term,
                "seed_key": query_key,
                "seed_priority": entry.priority,
                "query_status": query_status,
                "neighbor_rank": str(rank),
                "neighbor_token": neighbor,
                "neighbor_term": neighbor.replace("_", " "),
                "similarity": f"{score:.6f}",
                "neighbor_count": str(neighbor_count),
            }
            rows.append(row)

            if query_status != "exact_key" and not aggregate_mean_vector_neighbors:
                continue
            if query_key == "ai" and not include_generic_ai_neighbors:
                continue

            normalized_neighbor = neighbor.replace("_", " ")
            if neighbor in seed_keys or normalized_neighbor in seed_terms_normalized:
                continue

            item = aggregate.setdefault(
                neighbor,
                {
                    "candidate_token": neighbor,
                    "candidate_term": normalized_neighbor,
                    "similarities": [],
                    "seed_terms": set(),
                    "concept_groups": set(),
                    "query_statuses": set(),
                    "neighbor_count": neighbor_count,
                    "best_rank": rank,
                },
            )
            item["similarities"].append(score)
            item["seed_terms"].add(entry.term)
            item["concept_groups"].add(entry.concept_group)
            item["query_statuses"].add(query_status)
            item["best_rank"] = min(int(item["best_rank"]), rank)

    candidate_rows: list[dict[str, str]] = []
    for item in aggregate.values():
        similarities = item["similarities"]
        seed_terms = sorted(item["seed_terms"])
        concept_groups = sorted(item["concept_groups"])
        query_statuses = sorted(item["query_statuses"])
        candidate_rows.append(
            {
                "candidate_term": str(item["candidate_term"]),
                "candidate_token": str(item["candidate_token"]),
                "neighbor_count": str(item["neighbor_count"]),
                "seed_count": str(len(seed_terms)),
                "seed_terms": ";".join(seed_terms),
                "concept_groups": ";".join(concept_groups),
                "query_statuses": ";".join(query_statuses),
                "best_rank": str(item["best_rank"]),
                "max_similarity": f"{max(similarities):.6f}",
                "mean_similarity": f"{float(np.mean(similarities)):.6f}",
                "review_decision": "",
                "include_v2": "",
                "review_notes": "",
            }
        )

    candidate_rows.sort(
        key=lambda row: (
            -int(row["seed_count"]),
            -float(row["max_similarity"]),
            int(row["best_rank"]),
            row["candidate_term"],
        )
    )
    return rows, candidate_rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(
    args: argparse.Namespace,
    model: Word2Vec,
    metrics: dict[str, str],
    seed_entries: list[SeedEntry],
) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / "trained_word2vec.model"
    vectors_path = output_dir / "trained_word2vec_vectors.kv"
    model.save(str(model_path))
    model.wv.save(str(vectors_path))

    neighbor_rows, candidate_rows = query_seed_neighbors(
        model,
        seed_entries,
        args.topn,
        args.aggregate_mean_vector_neighbors,
        args.include_generic_ai_neighbors,
    )
    write_csv(
        output_dir / "seed_term_neighbors.csv",
        neighbor_rows,
        [
            "concept_group",
            "seed_term",
            "seed_key",
            "seed_priority",
            "query_status",
            "neighbor_rank",
            "neighbor_token",
            "neighbor_term",
            "similarity",
            "neighbor_count",
        ],
    )
    write_csv(
        output_dir / "expanded_ai_terms_candidates.csv",
        candidate_rows,
        [
            "candidate_term",
            "candidate_token",
            "neighbor_count",
            "seed_count",
            "seed_terms",
            "concept_groups",
            "query_statuses",
            "best_rank",
            "max_similarity",
            "mean_similarity",
            "review_decision",
            "include_v2",
            "review_notes",
        ],
    )
    write_csv(
        output_dir / "stage04_diagnostics.csv",
        [{"metric": key, "value": value} for key, value in metrics.items()],
        ["metric", "value"],
    )

    print(f"model: {model_path}")
    print(f"vectors: {vectors_path}")
    print(f"neighbors: {output_dir / 'seed_term_neighbors.csv'}")
    print(f"candidate terms: {output_dir / 'expanded_ai_terms_candidates.csv'}")
    print(f"diagnostics: {output_dir / 'stage04_diagnostics.csv'}")


def main() -> None:
    args = parse_args()
    model, metrics, seed_entries = train_model(args)
    write_outputs(args, model, metrics, seed_entries)


if __name__ == "__main__":
    main()
