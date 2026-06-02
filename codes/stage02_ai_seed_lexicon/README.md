# Stage 02: AI Seed Lexicon

This stage builds the literature-based AI seed lexicon.

The seed lexicon is used to extract broad AI candidate sentences before Word2Vec expansion and classifier filtering.

Current seed file:

```text
ai_seed_lexicon_v1.csv
```

The file should stay auditable. Each term should include:

```text
concept_group
term
source_note
include
```

Recommended concept groups:

```text
core_ai
gen_ai
automation_ai
business_use
```

