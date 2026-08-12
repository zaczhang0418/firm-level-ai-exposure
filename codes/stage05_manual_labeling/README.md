# Stage 05：候选句提取与人工标注

## 目标

使用审核后的 AI 词表 v2，从全量电话会议文本中提取候选句，并完成人工标注，为 Stage 06 的句子分类器提供训练和验证数据。

```text
Stage 01 标准化句子
+ Stage 02 AI 词表 v2
-> Stage 05 AI 候选句
-> 人工标注
-> Stage 06 分类器
```

## 当前进度

更新日期：2026-08-12

- [x] 完成 AI 词表 v2 审核
- [x] 完成 2001—2024 年候选句提取
- [x] 生成 Round 1 的 1,000 条标注样本
- [x] 完成前 520 条人工标注
- [ ] 完成剩余 480 条人工标注
- [ ] 整理 Stage 06 训练与验证数据

当前标注统计：

| 项目 | 数量 |
|---|---:|
| Round 1 总样本 | 1,000 |
| 已标注 | 520 |
| 正例（`ai_label=1`） | 447 |
| 负例（`ai_label=0`） | 73 |
| 待标注 | 480 |

各抽样类型进度：

| 抽样类型 | 已标注 / 总数 |
|---|---:|
| `random` | 220 / 400 |
| `likely_ai` | 200 / 400 |
| `hard_case` | 100 / 200 |

已完成 `R01-0001` 至 `R01-0520`，下一条为 `R01-0521`。

## 输入与输出

输入：

```text
codes/stage01_xml_standardization/outputs/by_year/*/transcript_sentences.csv
codes/stage02_ai_seed_lexicon/ai_seed_lexicon_v2.csv
```

候选句输出：

```text
codes/stage05_manual_labeling/outputs/ai_candidate_sentences_v2.csv
codes/stage05_manual_labeling/outputs/ai_candidate_summary_by_document_v2.csv
```

人工标注文件：

```text
codes/stage05_manual_labeling/outputs/labeling_batches/round01_ai_labeling_sample.csv
codes/stage05_manual_labeling/outputs/labeling_batches/round01_sampling_summary.csv
```

完整候选句约 265,605 条。不要直接在完整候选句文件中进行人工标注，应始终使用 `labeling_batches` 中的小批次文件。

## Round 1 抽样结构

Round 1 共 1,000 条：

- `random`：400 条。用于估计候选池的真实准确率。
- `likely_ai`：400 条。命中强 AI 词，用于补充正例。
- `hard_case`：200 条。容易产生误判的边界样本，用于补充难负例。

`sample_type` 只表示样本为什么被抽中，不是人工标签。三类样本都必须独立判断 `ai_label`。

## 标注规则

核心标签：

- `ai_label=1`：句子实质讨论 AI 技术、产品、投入、能力、人员或业务应用。
- `ai_label=0`：关键词误伤、泛科技表述、公司或产品名称、普通自动化、金融术语或其他非 AI 内容。

需要填写的字段：

| 字段 | 说明 |
|---|---|
| `ai_label` | `1` 或 `0` |
| `confidence` | `high`、`medium` 或 `low` |
| `false_positive` | 负例的误判类型；正例填 `not_applicable` |
| `needs_review` | 需要复核填 `1`，否则填 `0` |
| `notes` | 必要时记录简短理由 |

常用负例类型：

```text
standalone_ai_noise
generic_technology
automation_without_ai
company_or_product_name
financial_or_index_term
boilerplate
ambiguous
```

判断时重点阅读：`terms`、`matched_text`、`sentence`、`prev_sentence`、`next_sentence` 和 `context_window`。

## 标注命令

查看总体进度：

```bash
python codes/stage05_manual_labeling/labeling_workflow.py status
```

查看下一条未标注样本：

```bash
python codes/stage05_manual_labeling/labeling_workflow.py show --next
```

写入一条标签：

```bash
python codes/stage05_manual_labeling/labeling_workflow.py label R01-0521 \
  --ai-label 1 \
  --confidence high \
  --false-positive not_applicable \
  --needs-review 0 \
  --notes "简短标注理由"
```

如需在写回前生成备份，可增加 `--backup`。

## 下一步

1. 从 `R01-0521` 继续标注，完成 Round 1 剩余 480 条。
2. 检查低置信度和 `needs_review=1` 的样本。
3. 将已确认标签整理为：

   ```text
   codes/stage05_manual_labeling/outputs/labeled_ai_sentences_v2.csv
   ```

4. 将 `ai_label` 映射为 Stage 06 使用的 `label_ai_relevant`。
5. 进入 Stage 06，训练并评估句子分类器。

Stage 05 的职责是构造可审计的人工标注数据，不直接计算最终 AI exposure。
