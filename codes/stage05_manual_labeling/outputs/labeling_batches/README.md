# Stage 05 标注批次文件说明

这个文件夹存放从 Stage 05 完整候选池中抽出的人工标注小样本。不要直接编辑
`ai_candidate_sentences_v2.csv` 大文件；人工标注应在本文件夹中的 round CSV 上完成。

## 文件

```text
round01_ai_labeling_sample.csv
round01_sampling_summary.csv
```

`round01_ai_labeling_sample.csv` 是第一轮 1,000 句标注样本。  
`round01_sampling_summary.csv` 记录每类样本抽了多少行，以及抽样框里各类候选句数量。

Round 1 的 1,000 句切分如下：

```text
random: 400
  2001-2015: 100
  2016-2020: 100
  2021-2022: 100
  2023-2024: 100

likely_ai: 400
  2001-2015: 100
  2016-2020: 100
  2021-2022: 100
  2023-2024: 100

hard_case: 200
  standalone_ai: 100
  weak_or_noisy_terms: 100
```

`sample_type` 只表示抽样来源，不表示最终标签。所有行都需要人工填写
`ai_label`。`likely_ai` 也可能是 false positive，`hard_case` 也可能是真正的
AI 表述。

## 标注列

这些列放在 CSV 最左边，人工标注时主要填写它们：

| Column | Meaning |
|---|---|
| `id` | 本轮标注行号，稳定定位每一句 |
| `round` | 标注轮次，例如 `round01` |
| `sample_type` | 抽样类型：`random`、`likely_ai`、`hard_case` |
| `period_or_case` | 年份层或难例类型 |
| `why_sampled` | 为什么这句话被抽入样本 |
| `ai_label` | 人工标注核心列：`1` 为真正 AI 表述，`0` 为非 AI 表述，拿不准可先留空 |
| `confidence` | `high` / `medium` / `low` |
| `false_positive` | 若标为 `0`，记录误伤类型 |
| `needs_review` | `1` 表示需要复核，`0` 表示不需要 |
| `notes` | 简短备注 |

建议的 `false_positive`：

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

## 阅读列

这些列用于判断句子含义：

| Column | Meaning |
|---|---|
| `year` / `quarter` | 电话会年份和季度 |
| `company` / `ticker` | 公司名称和 ticker |
| `section` | transcript 区段 |
| `speaker` | 说话人 |
| `terms` | 命中的 AI 词表项 |
| `matched_text` | 原文中被命中的文本 |
| `concept_group` | 命中词所属概念组 |
| `sentence` | 需要标注的目标句 |
| `prev_sentence` | 上一句上下文 |
| `next_sentence` | 下一句上下文 |
| `context_window` | 上一句、目标句、下一句拼接文本 |

通常先看 `sentence`。如果判断不清，再看 `prev_sentence`、
`next_sentence` 或 `context_window`。

## 对话式标注

推荐让 Codex 每次提取一条未标注样本，在对话中展示成更容易阅读的格式，
再由人工给出最终判断。这样不需要在 CSV 里来回横向滚动，也能避免写错行。

查看进度：

```powershell
python .\codes\stage05_manual_labeling\labeling_workflow.py status
```

展示下一条未标注样本：

```powershell
python .\codes\stage05_manual_labeling\labeling_workflow.py show --next
```

写回标签：

```powershell
python .\codes\stage05_manual_labeling\labeling_workflow.py label R01-0001 `
  --ai-label 1 `
  --confidence high `
  --false-positive not_applicable `
  --needs-review 0 `
  --notes "Substantive use of machine learning/autonomous coding in operations."
```

对话中人工可以使用简写：

```text
1 high
0 generic_technology: 只是泛科技/数字化表述
review: 上下文不足，需要复核
```

Codex 会把简写规范化写入本 round CSV 的 `ai_label`、`confidence`、
`false_positive`、`needs_review` 和 `notes`。脚本每次写回前会自动生成
同目录备份文件。

## 追溯列

这些列一般不需要人工修改，用于回连完整候选池：

| Column | Meaning |
|---|---|
| `candidate_id` | Stage 05 候选句唯一 ID |
| `document_id` | transcript/document ID |
| `event_id` | event ID |
| `sentence_id` | 句子 ID |
| `source_csv` | 来源句子 CSV |
| `xml_path` | 来源 XML |
| `term_count` | 不同命中词数量 |
| `match_count` | 总命中次数 |

## 抽样类型

`sample_type` 有三种：

```text
random:
  分层随机样本，用来估计候选池整体质量。

likely_ai:
  强 AI 词命中的样本，用来补足正例。

hard_case:
  容易误伤或边界模糊的样本，用来训练模型学会排除假阳性。
```

`period_or_case` 的含义取决于 `sample_type`：

```text
如果 sample_type = random 或 likely_ai：
  period_or_case 是年份层。
  例如 2016-2020 表示这句话来自 2016 到 2020 年电话会的候选句。

如果 sample_type = hard_case：
  period_or_case 是难例类型。
  例如 standalone_ai 表示这句话只命中了单独的 "AI"。
  例如 weak_or_noisy_terms 表示这句话命中了 automation、analytics、
  digital 等更容易误伤的泛科技词。
```

## 判断原则

`ai_label = 1`：

```text
句子实质性讨论 AI 技术、AI 产品、AI 能力、AI 投资、AI 应用、
AI 相关运营使用、AI workforce 或 AI 对公司业务的影响。
```

`ai_label = 0`：

```text
只是关键词误伤、泛科技/数字化表述、非 AI 的 automation/analytics、
公司名或产品名噪声、金融/index/ticker 噪声、boilerplate，或语义上不构成 AI exposure。
```

## 标注完成后

标注完成的 round CSV 是可审计原始批次。进入 Stage 06 FinBERT / classifier
训练前，应整理为：

```text
codes/stage05_manual_labeling/outputs/labeled_ai_sentences_v2.csv
```

Stage 06 使用的核心标签名是 `label_ai_relevant`。整理时将本文件中的
`ai_label` 映射过去：

```text
ai_label = 1 -> label_ai_relevant = 1
ai_label = 0 -> label_ai_relevant = 0
blank/uncertain -> 不进入训练集，或进入复核队列
```

建议保留 `confidence`、`false_positive`、`needs_review`、`notes`、
`sample_type`、`period_or_case` 和追溯 ID，方便后续检查模型在 random、
likely_ai、hard_case 三类样本上的表现。
