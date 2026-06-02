# Stage 02: AI Seed Lexicon

This stage builds the literature-based AI seed lexicon used to identify broad AI candidate sentences.

The seed lexicon is not the final AI exposure measure. It is the first recall layer:

```text
transcript_sentences.csv
-> AI seed lexicon
-> AI candidate sentences
-> Word2Vec expansion / manual screening
-> classifier filtering
-> AI exposure
```

This follows the He labor-shortage logic:

```text
topic words identify broad candidate sentences
classifier decides which candidate sentences are truly topic-related
```

Current seed file:

```text
ai_seed_lexicon_v1.csv
```

## Current Files

| File | Purpose |
|---|---|
| `ai_seed_lexicon_v1.csv` | Initial literature-based AI seed terms used for candidate sentence extraction |
| `reference_sources.csv` | AI-related reference papers with source IDs such as `AI01` |
| `excluded_or_review_terms.csv` | Terms that are related to technology but too broad or ambiguous for v1 inclusion |
| `ai_seed_lexicon_notes.md` | Methodological notes explaining inclusion/exclusion logic |
| `extract_reference_terms.py` | Scans priority AI PDFs for candidate terminology evidence |
| `discover_terms_from_references.py` | Literature-first extraction of candidate AI expressions from AI-context sentences |
| `enrich_seed_with_reference_counts.py` | Adds reference frequency evidence to the seed lexicon |
| `validate_seed_lexicon.py` | Lightweight validation script for CSV structure and duplicate terms |

## Seed Lexicon Columns

```text
concept_group
term
match_type
priority
include
reference_count
total_hit_count
reference_ids
reference_hit_counts
evidence_terms
notes
```

Column meanings:

| Column | Meaning |
|---|---|
| `concept_group` | The AI concept family, such as `core_ai`, `gen_ai`, `ai_methods`, or `ai_applications` |
| `term` | The phrase or acronym to match in transcript sentences |
| `match_type` | Matching instruction for Stage 03, usually `phrase`, `acronym`, or `word_boundary` |
| `priority` | `high`, `medium`, or `review`; high terms should have relatively low false positives |
| `include` | `1` means use in v1 candidate extraction; `0` means do not use yet |
| `reference_count` | Number of distinct reference papers where the expression appears |
| `total_hit_count` | Total number of detected appearances across reference papers |
| `reference_ids` | Semicolon-separated IDs from `reference_sources.csv` showing which papers support the expression |
| `reference_hit_counts` | Semicolon-separated per-paper counts, such as `AI01:150;AI02:71` |
| `evidence_terms` | The expression found or searched in the reference text |
| `notes` | Short explanation of ambiguity or intended usage |

## Recommended Concept Groups

```text
core_ai
gen_ai
ai_methods
ai_applications
ai_infrastructure
automation_robotics
```

## Validation

Run:

```bash
python3 codes/stage02_ai_seed_lexicon/validate_seed_lexicon.py
```

Expected result:

```text
Seed lexicon validation passed.
```

To discover terminology from local AI PDFs, run:

```bash
.venv/bin/python codes/stage02_ai_seed_lexicon/discover_terms_from_references.py
```

This writes a local, ignored file:

```text
codes/stage02_ai_seed_lexicon/outputs/literature_discovered_terms.csv
```

Use it as evidence support, not as an automatic final lexicon.

To add reference frequency evidence to the lexicon after discovery, run:

```bash
.venv/bin/python codes/stage02_ai_seed_lexicon/enrich_seed_with_reference_counts.py
```

## Important Rule

Do not add broad technology words just because they sound AI-adjacent.

Examples that should remain excluded or under review unless paired with stronger context:

```text
data
digital
cloud
software
technology
platform
```

Those terms may be useful later in contextual rules or Word2Vec review, but they are too noisy as standalone v1 seeds.
