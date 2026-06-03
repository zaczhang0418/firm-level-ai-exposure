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
codes/stage01_xml_standardization/outputs/transcript_sentences.csv
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
source_csv
matched_terms
matched_concept_groups
matched_priorities
matched_term_count
total_match_count
```

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
