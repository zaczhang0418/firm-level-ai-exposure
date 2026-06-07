# Stage 05: V2 Candidate Sentence Pool and Manual Labeling

Stage 05 starts after the Stage 04 Word2Vec lexicon expansion has been manually
reviewed and merged into the official v2 AI lexicon:

```text
codes/stage02_ai_seed_lexicon/ai_seed_lexicon_v2.csv
```

The goal of this stage is to create the sentence-level dataset that will be
manually labeled and then used for FinBERT / AI-sentence classifier training and
validation.

## Workflow Logic

Stage 05 reuses the Stage 03 candidate-sentence extraction logic. Conceptually,
this is still a reproducible Ctrl+F-style pass over the standardized Stage 01
sentence corpus:

```text
Stage 01 all transcript sentences
+ Stage 02 ai_seed_lexicon_v2.csv
-> exact lexicon matching with Stage 03 extraction logic
-> v2 AI candidate sentence pool
```

The important difference is output ownership. The v1 baseline candidate pool
belongs to Stage 03, but the reviewed v2 candidate pool is a downstream training
artifact and should be stored under Stage 05.

## Inputs

Sentence corpus:

```text
codes/stage01_xml_standardization/outputs/by_year/*/transcript_sentences.csv
```

Reviewed v2 lexicon:

```text
codes/stage02_ai_seed_lexicon/ai_seed_lexicon_v2.csv
```

Only rows with `include=1` are used by the extraction logic.

## Expected Outputs

Recommended Stage 05 output directory:

```text
codes/stage05_manual_labeling/outputs/
```

Recommended v2 candidate sentence artifacts:

```text
codes/stage05_manual_labeling/outputs/ai_candidate_sentences_v2.csv
codes/stage05_manual_labeling/outputs/ai_candidate_summary_by_document_v2.csv
```

If we choose to keep year-partitioned outputs for easier inspection and sampling,
use:

```text
codes/stage05_manual_labeling/outputs/by_year/YYYY/ai_candidate_sentences_v2.csv
codes/stage05_manual_labeling/outputs/by_year/YYYY/ai_candidate_summary_by_document_v2.csv
```

This keeps Stage 03 as the reusable extraction-code stage while making Stage 05
the home for the reviewed v2 candidate sentence pool.

## Run V2 Candidate Extraction

Use the Stage 05 runner to reuse the Stage 03 extraction code with the reviewed
v2 lexicon and Stage 05-owned outputs:

```powershell
powershell -ExecutionPolicy Bypass -File .\codes\stage05_manual_labeling\run_stage05_v2_by_year_parallel.ps1 `
  -StartYear 2001 `
  -EndYear 2024 `
  -MaxJobs 4 `
  -ProgressEvery 50000 `
  -StatusEverySeconds 60
```

The runner writes resumable yearly parts and logs under:

```text
codes/stage05_manual_labeling/outputs/by_year_parts/
codes/stage05_manual_labeling/outputs/logs/
```

When all requested years finish, it merges the yearly files into:

```text
codes/stage05_manual_labeling/outputs/ai_candidate_sentences_v2.csv
codes/stage05_manual_labeling/outputs/ai_candidate_summary_by_document_v2.csv
```

If the run is interrupted, rerun the same command. Completed year files with
their `.done` markers are skipped.

`-StatusEverySeconds` controls the main-window heartbeat. It prints the running
years, elapsed time, current candidate-file size, and the last log line so long
runs are visibly alive even while background jobs are still working.

## Labeling Task

After v2 extraction, sample candidate sentences for human labeling. The core
label is:

```text
label_ai_relevant = 1 / 0
```

Interpretation:

```text
1: the sentence substantively discusses AI adoption, AI technology, AI products,
   AI investment, AI capabilities, AI workforce, or AI-related operational use.

0: the sentence is a false positive, generic technology/digitalization language,
   boilerplate, a named entity/noise hit, or otherwise not substantively AI.
```

The labeled sentence sample becomes the training and validation data for Stage
06 classifier work. Stage 06 should train/apply FinBERT or another sentence
classifier to the full v2 candidate sentence pool, rather than treating raw
lexicon matches as final AI exposure.

## Relationship To Other Stages

```text
Stage 04:
  train Word2Vec
  review expanded terms
  create ai_seed_lexicon_v2.csv

Stage 05:
  reuse Stage 03 matching logic with ai_seed_lexicon_v2.csv
  store v2 candidate sentence pool under stage05_manual_labeling/outputs
  manually label sampled candidate sentences

Stage 06:
  train and apply FinBERT / classifier using Stage 05 labels
```

In short, Stage 05 is not a new lexicon-building stage. It is the bridge from
the reviewed v2 dictionary to the sentence-level labeled data needed for
classifier training.
