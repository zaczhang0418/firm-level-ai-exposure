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

When the command finishes, it merges all completed yearly files with `.done`
markers into:

```text
codes/stage05_manual_labeling/outputs/ai_candidate_sentences_v2.csv
codes/stage05_manual_labeling/outputs/ai_candidate_summary_by_document_v2.csv
```

If the run is interrupted, rerun the same command. Completed year files with
their `.done` markers are skipped. This means segmented runs still rebuild the
combined output from every completed year, not only the years requested in the
latest command.

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

## 人工标注抽样策略

当前 `ai_candidate_sentences_v2.csv` 是用 AI lexicon v2 从全量
transcript sentences 中筛出的候选句池。它的含义是：

```text
这些句子更可能包含 AI 表述，但不能保证每一句都是真正的 AI 表述。
```

因此，Stage 05 的任务不是直接把所有候选句都当作 AI 句子，而是从候选池中
抽取一部分句子进行人工标注，形成 FinBERT / classifier 的训练和验证数据。
训练好的分类器会在 Stage 06 回到完整的 v2 候选句池上逐句判断：

```text
ai_label = 1: 真正 AI-related
ai_label = 0: 关键词误伤、泛科技表述、公司名/产品名噪声或其他非 AI 表述
```

这与 Harford, He, and Qiu 的 labor-shortage exposure 方法一致：关键词或词表
先负责召回候选句，FinBERT 再负责过滤 false positives。

### 如果随机抽样命中率太低

如果从 `ai_candidate_sentences_v2.csv` 中简单随机抽样后发现
`label_ai_relevant = 1` 的比例太低，不应立刻把更多词加入最终 v2 词表。正例
比例太低首先是训练样本构造问题，而不一定是候选池召回问题。

He 的 labor-shortage 论文中也遇到了类似问题：他们先用较宽的
labor-related 词表构造完整候选池，但随机抽样后 labor-shortage 正例很少。
为了解决训练集类别不平衡，他们又构造了更窄的 labor-shortage-related 词表，
用来额外抽取更可能为 positive 的句子。这个额外词表的主要目的不是直接构造
最终 exposure，而是提高人工标注样本中的 positive 比例，让 FinBERT 有足够
正例可学。

对应到本项目，如果随机样本中真正 AI 表述太少，应优先调整抽样方法：

```text
1. 保留一部分简单随机样本，用于估计候选池的真实 precision。
2. 增加 AI-positive-enriched 样本，用强 AI 词提高正例比例。
3. 增加 hard-negative 样本，让模型学习容易误伤的非 AI 表述。
4. 按年份、section、matched_terms 等维度做分层抽样，避免训练集过窄。
```

可优先用于 positive-enriched sampling 的强 AI 词包括：

```text
artificial intelligence
machine learning
deep learning
generative AI
gen AI
large language model
LLM
ChatGPT
natural language processing
computer vision
AI model
AI platform
AI-powered
```

可优先用于 hard-negative sampling 的高风险误伤类型包括：

```text
standalone "AI"
generic technology / digital / analytics language
automation without AI context
company or product names containing AI-like strings
financial/index/ticker noise
boilerplate language
```

只有当人工检查发现很多明显 AI 句子根本没有进入
`ai_candidate_sentences_v2.csv` 时，才说明 v2 词表召回不足，需要回到词表层面
补词并重新提取候选池。否则，正例率偏低更适合通过 stratified sampling 和
positive-enriched sampling 解决。

### 建议标注规模

He 的 labor-shortage replication package 中，全量 transcript sentences 与
labor-related candidate sentences 的规模大致为：

```text
total transcript sentences: 51,121,611
labor-related candidate sentences: 1,339,370
candidate / total: 2.62%
```

He 最终人工标注 5,000 句用于 FinBERT fine-tuning 和 testing：

```text
labeled / candidate: 5,000 / 1,339,370 = 0.373%
```

本项目当前 Stage 05 的规模为：

```text
total transcript sentences: 231,744,566
AI candidate sentences: 265,605
candidate / total: 0.115%
```

如果机械套用 He 的 `labeled / candidate` 比例，本项目第一轮应标注约：

```text
265,605 * 0.373% ≈ 1,000 sentences
```

因此，建议采用渐进式标注：

```text
Round 1: 1,000 sentences
  目的：估计候选池 precision、观察 positive rate、总结 false positive 类型。

Round 2: 3,000 sentences
  目的：形成初步可训练的 FinBERT / classifier 数据集。

Final target: 3,000-5,000 sentences
  目的：尽量接近 He 的训练样本规模，同时保证正例、负例和难负例都足够。
```

当前已经生成 Round 1 的 1,000 句人工标注样本。第一轮样本不是简单随机
1,000 句，而是训练导向的混合样本池：

```text
400: random
     从完整 Stage 05 AI candidate pool 中按时期分层随机抽取。
     用途：估计候选池真实 precision 和基础 positive rate。

400: likely_ai
     从命中强 AI 词的候选句中按时期分层随机抽取。
     用途：提高训练样本中的正例比例。

200: hard_case
     优先抽取 standalone AI、泛科技、automation、analytics 等容易误伤的句子。
     用途：补足 hard negatives，让 FinBERT 学会过滤 false positives。
```

三类样本的目的不同，后续标注和解释时不要混淆：

```text
stratified random:
  为了代表总体，估计候选池真实质量。

AI-positive-enriched:
  为了补足正例，让 FinBERT 学会 AI 表述长什么样。

hard-negative:
  为了补足难负例，让 FinBERT 学会哪些关键词命中不该算 AI。
```

Round 1 的实际切分如下：

```text
random:
  2001-2015: 100
  2016-2020: 100
  2021-2022: 100
  2023-2024: 100

likely_ai:
  2001-2015: 100
  2016-2020: 100
  2021-2022: 100
  2023-2024: 100

hard_case:
  standalone_ai: 100
  weak_or_noisy_terms: 100
```

这里的时期层是为了覆盖 AI language 随时间变化的情况。`2023-2024` 单独成层，
是因为 generative AI / LLM / ChatGPT 相关表述在这一时期明显增多。
`hard_case` 不按年份分层，而是按误伤机制分层，因为它的目的不是代表总体，
而是让分类器学习边界样本。

具体判断标准：

```text
stratified random:
  按年份/时期、section、matched_terms 等维度分层。
  每个层内部随机抽样。
  目的不是提高正例率，而是观察不同年份和不同命中词下的真实 precision。

AI-positive-enriched:
  优先抽取命中强 AI 词的句子。
  例如 artificial intelligence, machine learning, deep learning,
  generative AI, large language model, LLM, ChatGPT, NLP,
  computer vision, AI-powered, AI model, AI platform。
  目的不是代表总体，而是提高训练样本中的 positive 比例。

hard-negative:
  优先抽取容易被关键词误伤的句子。
  例如 standalone "AI"、generic technology、digital、analytics、
  automation without AI context、company/product name noise、
  ticker/index/noise hits、boilerplate language。
  目的是让模型学习“命中 AI 相关词但不应计入 AI exposure”的边界。
```

注意：这个比例是训练样本构造建议，不是最终 exposure 的加权比例。最终 Stage
06 classifier 仍应应用到完整 `ai_candidate_sentences_v2.csv` 候选池上，再由
Stage 07 使用 classifier-confirmed AI sentences 聚合 exposure。

### 标注批次文件夹

不要直接打开或编辑完整的 `ai_candidate_sentences_v2.csv`。该文件约 386MB，
列也较多，不适合人工标注。人工标注应使用小批次 CSV：

```text
codes/stage05_manual_labeling/outputs/labeling_batches/
```

当前第一轮标注文件：

```text
codes/stage05_manual_labeling/outputs/labeling_batches/round01_ai_labeling_sample.csv
codes/stage05_manual_labeling/outputs/labeling_batches/round01_sampling_summary.csv
```

第一轮样本为 1,000 句：

```text
random: 400
likely_ai: 400
hard_case: 200
duplicate candidate_id: 0
```

`random` 和 `likely_ai` 都按四个时期均分，每层 100 句。`hard_case` 分为
`standalone_ai` 100 句和 `weak_or_noisy_terms` 100 句。完整抽样框和每类抽样
数量记录在：

```text
codes/stage05_manual_labeling/outputs/labeling_batches/round01_sampling_summary.csv
```

注意：`sample_type` 只说明这句话为什么被抽入人工标注样本，不是标签本身。
所有样本都必须人工判断 `ai_label`。尤其是 `likely_ai` 仍可能是 false
positive，`hard_case` 也可能出现真正的 AI 表述。

抽样脚本：

```text
codes/stage05_manual_labeling/create_labeling_sample.py
```

重新生成第一轮样本的命令：

```powershell
python .\codes\stage05_manual_labeling\create_labeling_sample.py `
  --round round01 `
  --stratified-n 400 `
  --positive-n 400 `
  --hard-negative-n 200
```

标注 CSV 的列按“先标注、再阅读、最后追溯 ID”的顺序排列。人工主要填写：

```text
ai_label
confidence
false_positive
needs_review
notes
```

核心阅读列：

```text
terms
matched_text
sentence
prev_sentence
next_sentence
context_window
```

追溯列：

```text
candidate_id
document_id
event_id
sentence_id
source_csv
xml_path
```

`outputs/labeling_batches/README.md` 中有完整列字典和标注规则。

### 对话式标注工作流

Round CSV 可以直接人工编辑，但推荐用 Codex 对话式标注来减少横向滚动和写错行的风险：

```text
Codex 读取下一条未标注样本
-> 展示命中句、前后句、上下文、命中词和追溯 ID
-> Codex 给出初步建议、理由和不确定点
-> 人工回复 1 / 0 / 备注 / 需要复核
-> Codex 写回 round CSV
```

辅助脚本：

```text
codes/stage05_manual_labeling/labeling_workflow.py
```

查看当前进度：

```powershell
python .\codes\stage05_manual_labeling\labeling_workflow.py status
```

展示下一条未标注样本：

```powershell
python .\codes\stage05_manual_labeling\labeling_workflow.py show --next
```

写回一个标签：

```powershell
python .\codes\stage05_manual_labeling\labeling_workflow.py label R01-0001 `
  --ai-label 1 `
  --confidence high `
  --false-positive not_applicable `
  --needs-review 0 `
  --notes "Substantive use of machine learning/autonomous coding in operations."
```

如果标为 `0`，`false_positive` 应优先使用：

```text
standalone_ai_noise
generic_technology
automation_without_ai
company_or_product_name
financial_or_index_term
boilerplate
ambiguous
not_applicable
```

在对话中，人工可以只回复简写，例如：

```text
1 high
0 company_or_product_name: GPT 是公司名，不是 generative pretrained transformer
review: 需要查公司产品背景
```

Codex 再把这些判断规范化写入 `ai_label`、`confidence`、`false_positive`、
`needs_review` 和 `notes`。标注脚本每次写回前会自动备份当前 round CSV。

### 标注完成后的训练样本池

人工标注完成后，Round CSV 仍保留在 `outputs/labeling_batches/` 中，作为可审计
的原始标注批次。提供给 Stage 06 的训练样本池应整理为：

```text
codes/stage05_manual_labeling/outputs/labeled_ai_sentences_v2.csv
```

Stage 06 README 使用的核心训练标签名是：

```text
label_ai_relevant = 1 / 0
```

因此，整理训练样本池时应将 Round CSV 中的 `ai_label` 映射为
`label_ai_relevant`：

```text
ai_label = 1 -> label_ai_relevant = 1
ai_label = 0 -> label_ai_relevant = 0
blank/uncertain -> 不进入训练集，或仅进入 review/adjudication 队列
```

建议保留这些审计字段进入 Stage 06：

```text
id
round
sample_type
period_or_case
confidence
false_positive
needs_review
notes
candidate_id
document_id
sentence_id
terms
matched_text
sentence
prev_sentence
next_sentence
context_window
```

训练和验证拆分时，不要把 `sample_type` 当作 exposure 权重。它可以作为
diagnostic 变量，用来分别报告 random precision、likely-ai positive rate、
hard-case false positive filtering performance。

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
