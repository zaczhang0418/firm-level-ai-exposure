# Stage 06: AI Sentence Classification

Stage 06 turns the Stage 05 v2 candidate sentence pool into classifier-filtered
AI sentence predictions. The key principle is:

```text
lexicon matches are candidate sentences, not final AI exposure
```

Final exposure should be based on classifier-confirmed AI sentences.

## Inputs

Full v2 candidate sentence pool from Stage 05:

```text
codes/stage05_manual_labeling/outputs/ai_candidate_sentences_v2.csv
```

Labeled sentence sample from Stage 05:

```text
codes/stage05_manual_labeling/outputs/labeled_ai_sentences_v2.csv
```

Expected core label:

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

## LLM-Assisted Labeling Design

Codex or another LLM agent may be used as an assisted labeling tool before
classifier training. This should be treated as structured pre-labeling, not as
unqualified human ground truth.

Recommended workflow:

```text
human-written codebook / labeling skill
-> Codex-assisted sentence pre-labeling
-> confidence scores and rationales
-> human review of uncertain and high-impact cases
-> gold validation set
-> classifier training and evaluation
```

This mirrors the Stage 04 term-review workflow, but sentence labels require
semantic judgment. The labeling skill/codebook should define positive and
negative cases clearly enough that repeated Codex-assisted passes are
consistent and auditable.

## Recommended Labeling Fields

Keep the original Stage 05 label columns and add audit fields for assisted
labeling:

```text
label_ai_relevant
label_source
label_notes
label_confidence
false_positive_type
review_needed
reviewer_final_label
reviewer_notes
```

Suggested values:

```text
label_source:
  human
  codex_assisted
  adjudicated

label_confidence:
  high
  medium
  low

false_positive_type:
  standalone_ai_noise
  generic_technology
  company_or_product_name
  financial_or_index_term
  boilerplate
  ambiguous
  not_applicable

review_needed:
  1 / 0
```

## Sampling Strategy

Do not train only on a simple random sample. The candidate pool should be
sampled by strata so the classifier sees both easy and difficult examples:

```text
standalone AI only
AI plus longer AI phrase
strong AI terms: machine learning, deep learning, LLM, ChatGPT, GenAI, NLP
broad application terms: automation, fraud detection, recommendation, robotics
recent years: especially 2022-2024
section: presentation vs Q&A
```

Standalone `AI` is expected to create many false positives. It should be
oversampled for labeling so the classifier learns when `AI` is substantive and
when it is noise.

## Gold Validation Set

To protect validation integrity, keep a human-reviewed gold set separate from
the Codex-assisted training labels.

Recommended minimum:

```text
Codex-assisted pre-labels: several thousand candidate sentences
Human-reviewed gold set: at least 500-1,000 sentences
```

The gold set should be stratified and should include difficult cases, especially
standalone `AI` hits and broad application terms. Report agreement between
Codex-assisted labels and human-reviewed labels before using the assisted labels
for training.

## Classifier Output

The Stage 06 classifier should be applied to the full Stage 05 v2 candidate
pool and write:

```text
codes/stage06_ai_sentence_classification/outputs/ai_classified_sentences_v2.csv
```

Expected prediction fields:

```text
ai_label
ai_score
classifier_model
classifier_version
prediction_notes
```

`ai_label = 1` means the classifier predicts the candidate sentence is truly
AI-related. Stage 07 should aggregate only classifier-confirmed AI sentences.

## Methodology Note

This follows the He-style exposure construction logic:

```text
topic keywords
-> candidate sentence pool
-> labeled sample
-> FinBERT / sentence classifier
-> classifier-confirmed topic sentence count
-> sentence-share exposure
```

For this project, the topic is AI. Word2Vec and the v2 lexicon improve recall;
Stage 06 improves precision by filtering false positive keyword matches.
