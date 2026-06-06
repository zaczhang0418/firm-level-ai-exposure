# Stage 04: Word2Vec Lexicon Expansion

This stage trains a conference-call-specific Word2Vec model on the full Stage 01
sentence corpus, then uses the Stage 02 AI seed lexicon v1 to find nearest
neighbor terms for manual review.

Word2Vec is our expansion layer. The He-style exposure pipeline does not require
Word2Vec as the core estimator; it is added here to improve recall before manual
review and classifier filtering.

## Input

Training corpus:

```text
codes/stage01_xml_standardization/outputs/by_year/*/transcript_sentences.csv
```

The model trains on the `sentence` column from all Stage 01 yearly files.

Query lexicon:

```text
codes/stage02_ai_seed_lexicon/ai_seed_lexicon_v1.csv
```

Only rows with `include=1` are used. Rows with `priority=review` are excluded by
default unless `--include-review` is passed.

## Output

Default output directory:

```text
codes/stage04_word2vec_expansion/outputs/
```

Expected files:

```text
trained_word2vec.model
trained_word2vec_vectors.kv
seed_term_neighbors.csv
expanded_ai_terms_candidates.csv
stage04_diagnostics.csv
```

`seed_term_neighbors.csv` keeps seed-by-seed nearest neighbors.  
`expanded_ai_terms_candidates.csv` aggregates unique neighbor terms for manual
screening into the AI lexicon v2. By default, the candidate file only aggregates
neighbors from seed terms that exist as exact model keys. Fallback mean-vector
queries are kept in `seed_term_neighbors.csv` for diagnostics; pass
`--aggregate-mean-vector-neighbors` if you want those included too.

The standalone `AI` seed is also kept out of the aggregated candidate file by
default because it is broad and can produce noisy neighbors. Its neighbors remain
available in `seed_term_neighbors.csv`; pass `--include-generic-ai-neighbors` if
you want to aggregate them.

## Completed Run

The full Stage 04 run completed on 2026-06-06 and produced:

```text
codes/stage04_word2vec_expansion/outputs/trained_word2vec.model
codes/stage04_word2vec_expansion/outputs/trained_word2vec_vectors.kv
codes/stage04_word2vec_expansion/outputs/seed_term_neighbors.csv
codes/stage04_word2vec_expansion/outputs/expanded_ai_terms_candidates.csv
codes/stage04_word2vec_expansion/outputs/stage04_diagnostics.csv
```

Training diagnostics:

```text
sentence files: 24
examples / sentences: 231,581,188
words: 3,983,908,187
vocab size: 777,851
vector size: 200
window: 8
epochs: 8
workers: 16
elapsed time: 128,090.892 seconds, about 35.6 hours
```

Review outputs:

```text
seed_term_neighbors.csv: 3,100 rows across 62 seed terms
expanded_ai_terms_candidates.csv: 772 candidate expansion terms
```

The small CSV review artifacts are suitable for Git. The trained model files and
their `.npy` sidecar files are large local artifacts and should not be committed
without Git LFS or a separate model-storage decision.

## Phrase Handling

The script joins included multi-word seed terms before training. For example:

```text
machine learning -> machine_learning
large language model -> large_language_model
```

It also learns statistical bigrams/trigrams from the transcript corpus unless
`--no-statistical-phrases` is passed.

## Smoke Test

Run a small local benchmark before full training:

```powershell
python .\codes\stage04_word2vec_expansion\smoke_test_word2vec.py `
  --sample-rows 25000 `
  --worker-candidates 1,8,16
```

This writes:

```text
codes/stage04_word2vec_expansion/outputs/smoke_test/smoke_test_summary.csv
```

On this machine the default worker rule is:

```text
workers = min(logical_cpu_count - 2, 16)
```

With 20 logical CPUs, the default is `workers=16`.

## Full Training

Recommended full run:

```powershell
.\codes\stage04_word2vec_expansion\run_stage04_full.ps1 `
  -Workers 16 `
  -VectorSize 200 `
  -Window 8 `
  -MinCount 5 `
  -Epochs 8 `
  -TopN 50
```

Equivalent direct Python command:

```powershell
python .\codes\stage04_word2vec_expansion\train_word2vec.py `
  --workers 16 `
  --vector-size 200 `
  --window 8 `
  --min-count 5 `
  --epochs 8 `
  --topn 50
```

Progress bars are enabled by default when `tqdm` is installed. For the full
corpus, the script does not pre-count all rows, so progress bars show live
sentence counts and speed rather than percentages. Use `--count-total-sentences`
if you want percentages, or `--no-progress-bar` for plain log output.

The script saves a model checkpoint after each epoch by default:

```text
codes/stage04_word2vec_expansion/outputs/checkpoints/trained_word2vec_epoch_001.model
codes/stage04_word2vec_expansion/outputs/checkpoints/trained_word2vec_epoch_002.model
codes/stage04_word2vec_expansion/outputs/checkpoints/trained_word2vec_latest.model
```

It also saves the phrase models needed for resume:

```text
codes/stage04_word2vec_expansion/outputs/phrase_models/
```

### Split Training Across Nights

For a large corpus, train fewer epochs first:

```powershell
.\codes\stage04_word2vec_expansion\run_stage04_full.ps1 `
  -Workers 16 `
  -VectorSize 200 `
  -Window 8 `
  -MinCount 5 `
  -Epochs 2 `
  -TopN 50
```

Then continue the next day from the latest checkpoint:

```powershell
.\codes\stage04_word2vec_expansion\run_stage04_full.ps1 `
  -Workers 16 `
  -VectorSize 200 `
  -Window 8 `
  -MinCount 5 `
  -Epochs 6 `
  -TopN 50 `
  -ResumeFromModel codes/stage04_word2vec_expansion/outputs/checkpoints/trained_word2vec_latest.model
```

When `-ResumeFromModel` is used, `-Epochs` means additional epochs to train.

For a quick code test:

```powershell
python .\codes\stage04_word2vec_expansion\train_word2vec.py `
  --limit 50000 `
  --workers 8 `
  --vector-size 50 `
  --min-count 2 `
  --epochs 1 `
  --topn 10 `
  --output-dir codes/stage04_word2vec_expansion/outputs/test_run
```

Runner version of the same quick test:

```powershell
.\codes\stage04_word2vec_expansion\run_stage04_full.ps1 `
  -Limit 50000 `
  -Workers 8 `
  -VectorSize 50 `
  -MinCount 2 `
  -Epochs 1 `
  -TopN 10 `
  -OutputDir codes/stage04_word2vec_expansion/outputs/test_run
```

## Review Step

Stage 04 does not automatically create the final official dictionary. It creates
candidate expansion terms:

```text
expanded_ai_terms_candidates.csv
```

Manual review should decide whether each `candidate_term` should be added to the
AI lexicon v2. The most important columns are:

| Column | How to use it |
|---|---|
| `candidate_term` | Candidate phrase to review for v2 inclusion |
| `neighbor_count` | Corpus frequency of the candidate term |
| `seed_count` | Number of v1 seed terms that recommended this candidate |
| `seed_terms` | Which v1 seed terms the candidate is close to |
| `concept_groups` | AI concept groups associated with the recommending seeds |
| `max_similarity` | Highest similarity to any recommending seed |
| `mean_similarity` | Average similarity across recommending seeds |
| `review_decision` | Manual decision label |
| `include_v2` | Binary v2 inclusion flag |
| `review_notes` | Short reviewer rationale |

Suggested manual coding values:

```text
review_decision = accept / reject / maybe / duplicate / too_broad
include_v2 = 1 for terms accepted into v2
include_v2 = 0 for terms rejected from v2
```

Use `accept` for clearly AI-related terms or variants, such as `gen ai`,
`genai`, `ai-enabled`, or specific methods such as `recommender systems` when
the project scope should include them. Use `reject` or `too_broad` for terms
that are too general without AI context, such as broad analytics or automation
terms that would likely add many false positives. Use `maybe` for terms that
need sentence-level inspection before inclusion.

Accepted terms then become the reviewed AI lexicon v2:

```text
Stage 02 ai_seed_lexicon_v1.csv
+ accepted Stage 04 expansion terms where include_v2=1
-> ai_seed_lexicon_v2.csv
```

The reviewed v2 lexicon should then be used to rerun Stage 03 against the full
Stage 01 sentence corpus, producing a separate v2 candidate pool rather than
overwriting the v1 baseline.
