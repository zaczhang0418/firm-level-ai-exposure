# Stage 03: AI Candidate Sentence Extraction

This stage connects the standardized conference call sentences from Stage 01 with the literature-backed AI seed lexicon from Stage 02.

## Goal

Stage 03 creates a high-recall pool of AI candidate sentences:

```text
Stage 01 transcript_sentences.csv
+ Stage 02 ai_seed_lexicon_v1.csv
-> AI candidate sentences
```

This is not the final AI exposure measure. It is the candidate extraction layer before Word2Vec expansion, manual review, and FinBERT/classifier filtering.

## Input

Sentence table from Stage 01:

```text
codes/stage01_xml_standardization/outputs/by_year
```

The `--sentences` argument can be:

```text
a single transcript_sentences.csv
a directory containing sentence CSV files
a glob pattern such as outputs/*/transcript_sentences.csv
```

Expected columns:

```text
document_id
event_id
company_name
ticker
call_date
call_year
call_quarter
reported_year
reported_quarter
section
speaker
sentence_id
sentence
xml_path
```

Seed lexicon from Stage 02:

```text
codes/stage02_ai_seed_lexicon/ai_seed_lexicon_v1.csv
```

Only rows with `include=1` are used. Rows with `priority=review` are excluded by default unless `--include-review` is passed.

## Output

Candidate sentence file:

```text
codes/stage03_candidate_sentence_extraction/outputs/ai_candidate_sentences.csv
```

Columns:

```text
document_id
event_id
company_name
ticker
call_date
call_year
call_quarter
reported_year
reported_quarter
section
speaker
sentence_id
sentence
xml_path
candidate_id
source_csv
training_text
previous_sentence
next_sentence
context_window
matched_terms
matched_texts
match_spans
matched_concept_groups
matched_priorities
matched_term_count
total_match_count
label_ai_relevant
label_source
label_notes
```

Downstream-oriented fields:

| Column | Purpose |
|---|---|
| `candidate_id` | Stable row identifier for manual labels and classifier training joins |
| `training_text` | Whitespace-normalized candidate sentence for FinBERT or other text classifiers |
| `previous_sentence` / `next_sentence` | Same-document neighboring sentences for context-aware review |
| `context_window` | Previous/current/next sentence joined by `[SEP]`, useful for classifier experiments |
| `matched_texts` | Exact text spans found in the sentence, preserving original casing |
| `match_spans` | Character offsets for each seed hit as `term:start-end` |
| `label_ai_relevant` | Empty placeholder for manual binary labels before classifier training |
| `label_source` | Empty placeholder for annotator/model/provenance notes |
| `label_notes` | Empty placeholder for reviewer comments |
 
For Word2Vec expansion, use the candidate rows plus `matched_terms`,
`matched_concept_groups`, and `context_window` to inspect nearby terminology.
For FinBERT/classifier training, use `candidate_id`, `training_text`, preserved
metadata, matching evidence, and the label placeholder columns.

Document-level summary:

```text
codes/stage03_candidate_sentence_extraction/outputs/ai_candidate_summary_by_document.csv
```

This summary preserves identifiers and reports:

```text
document_id
event_id
company_name
ticker
call_date
call_year
call_quarter
reported_year
reported_quarter
source_csv
total_sentences
candidate_sentences
candidate_sentence_share
total_seed_matches
matched_terms
matched_concept_groups
```

## Run

Default command:

```bash
python3 codes/stage03_candidate_sentence_extraction/extract_ai_candidate_sentences.py
```

By default, this scans every yearly Stage 01 sentence file under:

```text
codes/stage01_xml_standardization/outputs/by_year/*/transcript_sentences.csv
```

The script prints progress as it loads each yearly CSV and every 10,000 scanned
sentence rows. To change the reporting frequency:

```bash
python3 codes/stage03_candidate_sentence_extraction/extract_ai_candidate_sentences.py \
  --progress-every 50000
```

## Parallel Yearly Run And Resume

For the full 2001-2024 sample on Windows, prefer the yearly parallel runner:

```powershell
powershell -ExecutionPolicy Bypass -File .\codes\stage03_candidate_sentence_extraction\run_stage03_by_year_parallel.ps1 `
  -StartYear 2001 `
  -EndYear 2024 `
  -MaxJobs 4 `
  -ProgressEvery 10000
```

This runs each year independently and writes:

```text
codes/stage03_candidate_sentence_extraction/outputs/by_year_parts/
codes/stage03_candidate_sentence_extraction/outputs/logs/
```

Each completed year gets a `.done` marker. If the run is interrupted, run the
same command again; completed years are skipped and unfinished years are rerun.
At the end, yearly candidate and summary files are merged into:

```text
codes/stage03_candidate_sentence_extraction/outputs/ai_candidate_sentences.csv
codes/stage03_candidate_sentence_extraction/outputs/ai_candidate_summary_by_document.csv
```

On another machine, point the script to the full Stage 01 output:

```bash
python3 codes/stage03_candidate_sentence_extraction/extract_ai_candidate_sentences.py \
  --sentences /path/to/transcript_sentences.csv \
  --lexicon codes/stage02_ai_seed_lexicon/ai_seed_lexicon_v1.csv \
  --output /path/to/ai_candidate_sentences.csv \
  --summary-output /path/to/ai_candidate_summary_by_document.csv
```

If Stage 01 produced one sentence file per year, pass the parent directory:

```bash
python3 codes/stage03_candidate_sentence_extraction/extract_ai_candidate_sentences.py \
  --sentences /path/to/stage01_outputs_by_year \
  --output /path/to/ai_candidate_sentences.csv \
  --summary-output /path/to/ai_candidate_summary_by_document.csv
```

Small test run:

```bash
python3 codes/stage03_candidate_sentence_extraction/extract_ai_candidate_sentences.py \
  --sentences codes/stage03_candidate_sentence_extraction/tests/fixtures/sample_transcript_sentences.csv \
  --output codes/stage03_candidate_sentence_extraction/outputs/test_ai_candidate_sentences.csv \
  --summary-output codes/stage03_candidate_sentence_extraction/outputs/test_ai_candidate_summary_by_document.csv
```

## Matching Logic

The script uses case-insensitive regex matching.

For `phrase` and `word_boundary`, terms are matched with alphanumeric boundaries, so `AI` does not match inside unrelated longer strings. Multi-word terms tolerate flexible whitespace.

By default, if a sentence matches both standalone `AI` and a longer AI expression, the output drops standalone `AI` for that sentence. This keeps evidence cleaner while preserving high recall.

Use this option if you want to keep standalone `AI` even when longer expressions match:

```bash
--keep-generic-ai-with-longer-match
```

## He Methodology Connection

This stage mirrors the first text-identification layer in He's labor-shortage pipeline:

```text
topic seed terms
-> broad candidate sentences
-> downstream classifier / exposure aggregation
```

For our project, the topic is AI rather than labor shortage. The seed lexicon is evidence-backed by AI references, and the candidate sentences preserve transcript metadata for later firm-quarter and firm-year aggregation.
