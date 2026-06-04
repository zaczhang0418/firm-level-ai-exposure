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
stage04_word2vec_expansion
```

Stage 03 v1 candidate extraction has been completed for 2001-2024. The next goal
is to train Word2Vec on the full Stage 01 sentence corpus, use the Stage 02 v1
AI lexicon as seed terms, and produce candidate expansion terms for a reviewed
AI lexicon v2.

## End-to-End Methodology

This project follows the He-style text exposure pipeline:

```text
keyword / seed matching
-> candidate sentence pool
-> classifier filtering
-> sentence-count exposure aggregation
```

The important point is that keyword hits are not the final exposure measure.
Seed terms are used for broad recall; FinBERT/classifier filtering is used for
precision.

### Stage 01: XML Standardization

Raw and irregular XML conference call transcripts are converted into stable,
database-linkable sentence CSVs.

Input:

```text
Data_Conference call transcripts/YYYY/*.xml
```

Output:

```text
codes/stage01_xml_standardization/outputs/by_year/YYYY/transcript_sentences.csv
```

Each sentence has stable identifiers and transcript metadata, including:

```text
document_id
event_id
company_name
ticker
call_date
section
speaker
sentence_id
sentence
```

Stage 01 provides the denominator for exposure aggregation: total transcript
sentence counts.

### Stage 02: Literature-Based AI Lexicon v1

AI frontier and related academic literature are used to create the first AI seed
lexicon:

```text
codes/stage02_ai_seed_lexicon/ai_seed_lexicon_v1.csv
```

This lexicon contains specific AI expressions such as:

```text
artificial intelligence
machine learning
generative AI
large language model
ChatGPT
NLP
robotics
```

The v1 lexicon is an evidence-backed starting point, not the final dictionary.

### Stage 03: Candidate Sentence Extraction v1

The v1 lexicon is mechanically matched against all Stage 01 sentences. This is
similar to a strict, reproducible Ctrl+F over the standardized sentence tables.

Input:

```text
Stage 01 transcript_sentences.csv files
+ Stage 02 ai_seed_lexicon_v1.csv
```

Output:

```text
codes/stage03_candidate_sentence_extraction/outputs/ai_candidate_sentences.csv
codes/stage03_candidate_sentence_extraction/outputs/ai_candidate_summary_by_document.csv
```

The output is a 2001-2024 pool of sentences that matched v1 AI seed terms, with
document identifiers, sentence identifiers, matched terms, match spans, and
context fields.

This v1 candidate pool is a baseline and diagnostic output. It helps us inspect
false positives, year-by-year patterns, and whether the v1 lexicon is too broad
or too narrow. It is not the final AI exposure.

The v1 candidate file does not have to become the final FinBERT input. Its
main downstream uses are:

```text
1. baseline coverage: how many sentences does the literature-only lexicon find?
2. error diagnosis: which seed terms create obvious false positives?
3. v2 comparison: after Word2Vec expansion, which sentences are newly added?
4. fallback option: if v2 adds mostly noise, keep v1 as the official candidate pool.
```

In the preferred workflow, FinBERT is trained and applied on the reviewed v2
candidate pool, not mechanically on v1. The v1 output is kept so we can justify
what Word2Vec changed and whether the expansion improved recall without adding
too much noise.

### Stage 04: Word2Vec Lexicon Expansion

Word2Vec is trained on text, not on the dictionary.

Training input:

```text
all Stage 01 transcript sentences
```

Query input:

```text
Stage 02 v1 AI seed terms
```

The trained Word2Vec model learns conference-call-specific word contexts. We
then query nearest neighbors around v1 AI seed terms to find possible missing AI
expressions.

Expected outputs:

```text
trained_word2vec.model
seed_term_neighbors.csv
expanded_ai_terms_candidates.csv
stage04_diagnostics.csv
```

Word2Vec is an unsupervised expansion tool. It improves recall by suggesting
terms that v1 may have missed. It does not decide whether a sentence is truly
AI-related.

### Stage 05: Lexicon Review And Sentence Labeling

Stage 05 has two related but separate review tasks.

First, review Word2Vec-suggested expansion terms:

```text
Word2Vec suggested terms
-> manual screening
-> ai_seed_lexicon_v2.csv
```

Second, rerun Stage 03 with the reviewed v2 lexicon:

```text
Stage 01 all sentences
+ ai_seed_lexicon_v2.csv
-> ai_candidate_sentences_v2.csv
```

Then sample from the v2 candidate sentence pool and label whether each sampled
sentence is truly AI-related:

```text
label_ai_relevant = 1 / 0
```

Term review serves lexicon recall. Sentence labeling serves classifier training
and validation.

### Stage 06: AI Sentence Classification

FinBERT or another sentence classifier is trained on labeled v2 candidate
sentences.

Training input:

```text
labeled candidate sentences
```

Application input:

```text
ai_candidate_sentences_v2.csv
```

Expected output:

```text
ai_classified_sentences_v2.csv
```

The classifier adds fields such as:

```text
ai_label
ai_score
```

FinBERT is supervised. It learns from sentence labels and decides whether each
candidate sentence is truly AI-related. It improves precision by filtering false
positive keyword matches.

### Stage 07: Exposure Aggregation

Final exposure is based on classifier-confirmed AI sentences, not raw keyword
matches.

Numerator:

```text
number of candidate sentences with ai_label = 1 for a transcript
```

Denominator:

```text
total Stage 01 sentences for that transcript
```

Core measure:

```text
AI_EXPOSURE = confirmed_ai_sentences / total_transcript_sentences
```

Then transcript-level exposure is aggregated to:

```text
firm-quarter
firm-year
```

## Word2Vec vs FinBERT

| Model | Training data | Labels needed? | Main role |
|---|---|---|---|
| Word2Vec | Full transcript text corpus | No | Suggest lexicon expansion terms and improve recall |
| FinBERT/classifier | Labeled candidate sentences | Yes | Filter candidate sentences and improve precision |

In short:

```text
Word2Vec helps us avoid missing AI language.
FinBERT helps us avoid counting false positives.
```

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
