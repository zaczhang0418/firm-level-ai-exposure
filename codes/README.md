# Codes Workflow

This folder is the canonical code workspace for the firm-level AI exposure project.

The project is organized by workflow stage, similar to branch names. Each stage has a narrow responsibility and should produce outputs that the next stage can consume.

## Stage Map

| Stage | Folder | Purpose |
|---|---|---|
| Stage 00 | `stage00_project_scoping/` | Project logic, He methodology notes, workflow decisions |
| Stage 01 | `stage01_xml_standardization/` | Convert raw XML transcripts into database-linkable CSV tables |
| Stage 02 | `stage02_ai_seed_lexicon/` | Build literature-based AI seed lexicon |
| Stage 03 | `stage03_candidate_sentence_extraction/` | Extract AI candidate sentences using seed terms |
| Stage 04 | `stage04_word2vec_expansion/` | Expand AI lexicon with Word2Vec and manual screening |
| Stage 05 | `stage05_manual_labeling/` | Create labeled sentence samples for training/validation |
| Stage 06 | `stage06_ai_sentence_classification/` | Apply FinBERT/classifier to AI candidate sentences |
| Stage 07 | `stage07_exposure_aggregation/` | Aggregate sentence predictions into transcript/firm-quarter/firm-year exposure |
| Stage 08 | `stage08_validation/` | Validate exposure quality with manual checks and distribution tests |

## Current Stage

We are currently in:

```text
stage03_candidate_sentence_extraction
```

The goal is to use the Stage 02 AI seed lexicon to extract high-recall AI candidate sentences from the standardized Stage 01 transcript sentence table. This is still not the final AI exposure measure; it prepares the sentence pool for Word2Vec review, manual screening, and classifier filtering.

## Naming Principle

Stage folders use branch-like names:

```text
stage##_short_task_name
```

Examples:

```text
stage01_xml_standardization
stage04_word2vec_expansion
stage07_exposure_aggregation
```

## Data Principle

Raw XML data should not be modified. Each stage should write clean outputs into that stage's `outputs/` folder or a shared output location documented in the stage README.
