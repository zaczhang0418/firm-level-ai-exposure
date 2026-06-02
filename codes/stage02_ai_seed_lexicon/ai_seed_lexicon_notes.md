# AI Seed Lexicon Notes

## Purpose

The v1 seed lexicon is designed for broad recall, not final classification.

The downstream logic should be:

```text
seed lexicon
-> candidate AI sentences
-> Word2Vec / manual expansion
-> labeled examples
-> classifier filtering
-> AI exposure
```

## Inclusion Logic

Terms are included when they satisfy at least one of the following:

1. They are canonical AI concepts in the academic literature, such as `artificial intelligence`, `machine learning`, or `deep learning`.
2. They identify major modern AI categories, especially generative AI and LLMs.
3. They name AI subfields or methods, such as NLP, computer vision, or reinforcement learning.
4. They name business applications that are commonly AI-related, such as recommendation engines, automated underwriting, or fraud detection models.
5. They are useful high-recall terms that will later be filtered by the classifier.

## Exclusion Logic

Some technology words are deliberately excluded from v1 even though they are AI-adjacent:

```text
data
digital
cloud
software
technology
platform
```

These terms are too broad as standalone seeds. They would produce many false positive candidate sentences and dilute the classifier training sample.

## Reference-Grounded Source IDs

Each seed term should cite explicit source IDs from:

```text
reference_sources.csv
```

For example:

```text
AI01 = Babina et al. 2024 JFE
AI05 = Eisfeldt and Schubert 2024
AI06 = Eisfeldt et al. 2023
AI07 = Jha et al. 2024a
```

The goal is not to summarize each paper's method. The goal is to record how the AI literature talks about AI, GenAI, machine learning, LLMs, and related applications.

## Priority Source Buckets

The current seed list is motivated by local AI-focused references, especially papers on:

1. AI and firm growth/product innovation.
2. AI investments and workforce composition.
3. Generative AI and firm value.
4. ChatGPT and corporate policies.
5. AI as prediction technology.
6. Automated underwriting and machine decision systems.
7. NLP/financial text methods.

The `reference_ids` column identifies which papers support each expression. More precise page references can be added later if needed.

## Frequency Evidence Columns

The lexicon includes three evidence columns:

```text
reference_count
total_hit_count
reference_hit_counts
```

Interpretation:

1. `reference_count`: how many distinct AI references contain the expression.
2. `total_hit_count`: how many times the expression was detected across those references.
3. `reference_hit_counts`: per-reference counts, such as `AI01:150;AI02:71`.

These counts are generated from:

```text
outputs/literature_discovered_terms.csv
```

using:

```text
enrich_seed_with_reference_counts.py
```

The counts provide evidence, not automatic inclusion. A phrase can be frequent but still too broad for seed matching.

## PDF Term Scan

The helper script:

```text
discover_terms_from_references.py
```

uses `pypdf` to extract candidate AI expressions from priority AI PDFs. The output is:

```text
outputs/literature_discovered_terms.csv
```

This discovery step is an aid, not a substitute for judgment. A term can appear in a paper and still be too broad for v1 inclusion, such as:

```text
automation
recommendation
algorithmic
```

## Next Stage Link

Stage 03 will read:

```text
codes/stage02_ai_seed_lexicon/ai_seed_lexicon_v1.csv
```

and match rows where:

```text
include = 1
```

against:

```text
codes/stage01_xml_standardization/outputs/by_year/YYYY/transcript_sentences.csv
```

to create:

```text
ai_candidate_sentences.csv
```
