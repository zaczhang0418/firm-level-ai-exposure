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
