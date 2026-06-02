# He Transcript Exposure Methodology Notes

对象：`程序包/Replication_package_labor_shortage_to_dataverse`

用途：这个文档不是为了复现 He 的经济学回归，而是为了拆解并借鉴 He 如何把 conference call transcript 转化为 firm-level topic exposure。我们要学习的是他的文本度量工程，不是他的 labor shortage 实证模型。

## 1. 核心结论

He 的思路可以概括成一句话：

> 先用主题词把 transcript 中可能相关的句子抽出来，再用 FinBERT 判断这些候选句是否真正属于目标主题，最后把目标句子数量除以 transcript 总句子数，聚合成 firm-level exposure。

对我们来说：

```text
labor shortage exposure
→ 替换为
AI exposure
```

可借的是方法论：

```text
transcript
→ sentence-level table
→ keyword/seed candidate sentences
→ classifier
→ topic-related sentence count
→ transcript / firm-quarter / firm-year exposure
```

不能直接借的是主题内容：

```text
labor words
labor shortage labels
labor shortage fine-tuned FinBERT
LS_EXPOSURE
```

这些都要替换成 AI 主题。

## 2. He 的 Exposure 构建逻辑

He 的包里真正和文本 exposure 构建有关的核心文件是：

| 文件或目录 | 方法论作用 |
|---|---|
| `Data input/total_labor_sentences.csv` | 已经从 transcript 中抽出的 labor-related candidate sentences |
| `FinBert-LS model application.ipynb` | 用 fine-tuned FinBERT 判断 candidate sentence 是否 labor-shortage-related |
| `Data input/sentence_id_CEO_talks/` | 管理层陈述部分的句子编号，用来计算 denominator |
| `Data input/sentence_id_Q&A_section/` | Q&A 部分的句子编号，用来计算 denominator |
| `Data input/transcript_level_labor_shortage_sentences.csv` | transcript-level 的目标句子数和总句子数 |
| `Data input/transcript_gvkey_quarter_labor_shortage_exposure.dta` | transcript-firm-quarter 层 exposure |
| `Data input/gvkey_year_labor_shortage_exposure.dta` | firm-year 层 exposure |

He 的经济学回归、表格复现、CRSP/Compustat/BLS/BEA 数据不属于我们要借鉴的文本 exposure 构建方法。

## 3. He 方法的四层结构

### Layer 1. Transcript 句子化

He 最终使用的是 sentence-level 数据，而不是整篇 transcript。

核心思想：

```text
one transcript
→ many sentences
→ each sentence has sentence_id and document_id
```

He 包里没有完整展示 XML/raw transcript 到 sentence table 的 parser，但后续文件说明他至少做了两件事：

1. 把 transcript 拆成 management/presentation section；
2. 把 transcript 拆成 Q&A section。

对应文件：

```text
Data input/sentence_id_CEO_talks/
Data input/sentence_id_Q&A_section/
```

每个文件保存该 firm/transcript 下的句子编号，例如：

```text
000001004_0
000001004_1
000001004_2
```

这说明 He 的 denominator 不是词数，而是句子数。

### Layer 2. 主题词抽取候选句

He 不是直接把所有 transcript sentences 都丢给 FinBERT，而是先得到一个更窄的 candidate sentence pool。

在 labor shortage 版本里，这个候选池是：

```text
Data input/total_labor_sentences.csv
```

重要字段：

| 字段 | 含义 |
|---|---|
| `labor_sentence` | 被 labor 相关词命中的句子 |
| `labor_words` | 命中的 labor 相关词 |
| `labor_sentence_id` | 句子编号 |
| `transcript_id` | transcript 标识 |
| `gvkey` | 公司标识 |
| `document_id` | 文档标识 |
| `cyearq` / `cqtr` | 年度季度信息 |

方法论含义：

```text
seed / dictionary / keyword
→ broad candidate sentences
```

这一步的作用是提高效率，也减少 FinBERT 需要处理的句子范围。

对我们来说，这一步要替换为：

```text
AI seed lexicon
→ AI candidate sentences
```

### Layer 3. FinBERT 二次识别

He 的关键不是简单关键词计数，而是：

```text
keyword candidate sentence
→ fine-tuned FinBERT
→ whether this sentence truly describes labor shortage
```

在 notebook 里，逻辑是：

```python
lsbert = BertForSequenceClassification.from_pretrained(
    "Fine-tuned Finbert Model - Labor Shortage",
    num_labels=2
)

tokenizer = BertTokenizer.from_pretrained("Raw Finbert Model")

nlp = pipeline(
    "text-classification",
    model=lsbert,
    tokenizer=tokenizer,
    truncation=True,
    batch_size=64,
    max_length=128
)
```

然后对 `labor_sentence` 做分类：

```text
LABEL_1 = labor-shortage-related
LABEL_0 = not labor-shortage-related
```

方法论含义：

```text
关键词负责“召回”
FinBERT 负责“精确识别”
```

这点非常重要。He 的 exposure 不是粗糙的 keyword exposure，而是 classifier-filtered exposure。

### Layer 4. Exposure 聚合

FinBERT 识别出真正相关的句子后，He 计算每篇 transcript 的目标句子数：

```text
num_ls_sentences
```

再结合 transcript 总句子数：

```text
number_of_sentences_mgmt
number_of_sentences_qa
```

形成 transcript-level 数据：

```text
document_id
number_of_sentences_mgmt
number_of_sentences_qa
num_ls_sentences
```

核心 exposure 可理解为：

```text
LS_EXPOSURE = num_ls_sentences / total_sentences
```

其中：

```text
total_sentences = number_of_sentences_mgmt + number_of_sentences_qa
```

然后再把 transcript-level exposure 合并到公司、季度、年度层面：

```text
transcript-level
→ firm-quarter
→ firm-year
```

## 4. He 方法的本质

He 的方法不是“找几个关键词然后数次数”，而是一个两阶段文本识别框架：

```text
Stage 1: keyword / seed matching
         broad recall

Stage 2: FinBERT classification
         topic-specific precision

Stage 3: sentence-count aggregation
         interpretable exposure measure
```

这套方法的优点：

1. exposure 是句子级别的，解释性强；
2. keyword 只做候选集，不直接决定最终 exposure；
3. FinBERT 用来区分“提到劳动”与“真正讨论劳动力短缺”；
4. denominator 是 transcript 总句子数，可以比较不同公司、不同长度的 call；
5. 可以自然聚合到 call-level、firm-quarter、firm-year。

对我们的启发：

```text
提到 AI
不等于
真正具有 AI exposure
```

所以我们也需要先抽 AI candidate sentences，再判断这些句子是否真的表示公司面对、使用、投资、销售、依赖或受影响于 AI。

## 5. 从 Labor Shortage 替换到 AI Exposure

我们要做的是同构替换：

| He labor shortage pipeline | 我们的 AI exposure pipeline |
|---|---|
| labor seed words | AI seed lexicon |
| labor-related candidate sentences | AI candidate sentences |
| labor shortage classifier | AI-related classifier |
| `num_ls_sentences` | `num_ai_sentences` |
| `LS_EXPOSURE` | `AI_EXPOSURE` |
| labor shortage firm-year exposure | AI firm-year exposure |

建议变量结构：

```text
sentence-level:
document_id
company_name
ticker
call_date
section
speaker
sentence_id
sentence
matched_ai_terms
ai_label
ai_score

transcript-level:
document_id
company_name
ticker
call_date
number_of_sentences_mgmt
number_of_sentences_qa
num_ai_sentences
AI_EXPOSURE

firm-quarter:
firm_id / ticker / gvkey
year
quarter
AI_EXPOSURE

firm-year:
firm_id / ticker / gvkey
year
AI_EXPOSURE
```

## 6. Word2Vec 在我们项目中的位置

He 当前留下来的包里没有完整展示 Word2Vec 扩词代码；但从方法论上，Word2Vec 适合放在 seed lexicon 和 candidate extraction 之间。

它的角色不是最终识别器，而是扩词工具：

```text
literature-based AI seed terms
→ Word2Vec nearest neighbors in conference call corpus
→ manual screening
→ expanded AI lexicon
```

推荐顺序：

1. 先从文献中整理 AI seed lexicon v1；
2. 用 v1 在 transcript 中抽一批 AI candidate sentences；
3. 用全部 transcript 或干净 corpus 训练 Word2Vec；
4. 查看 seed terms 的近邻词；
5. 人工筛选，得到 AI seed lexicon v2；
6. 用 v2 重新抽 candidate sentences；
7. 再进入 FinBERT/classifier。

注意：Word2Vec 扩出来的词不能直接全部用。它会给出很多“语境相近但主题不精确”的词，比如泛化技术词、业务词、行业词。必须人工筛。

## 7. 我们自己的 XML 输入层

老师给的数据是 XML：

```text
Data/Data_Conference call transcripts/YYYY/*.xml
```

样本 XML 里能直接抽到：

| 信息 | XML 位置 |
|---|---|
| document id | `<Event Id="...">` |
| headline | `<Headline><![CDATA[...]]></Headline>` |
| raw transcript body | `<Body><![CDATA[...]]></Body>` |
| company name | `<companyName>...</companyName>` |
| ticker | `<companyTicker>...</companyTicker>` |
| call date | `<startDate>...</startDate>` |
| presentation / Q&A | `Body` 文本内部标题 |

因此我们的第一步必须是：

```text
XML
→ metadata + raw body
→ section splitting
→ sentence-level table
```

He 包不能直接接 XML，因为它的文本识别入口已经是处理好的 `total_labor_sentences.csv`。

## 8. 当前推荐工作流

### Step 1. XML parser

先写：

```text
ai_exposure_pipeline/01_parse_xml.py
```

目标：拿 5 到 20 个 XML 跑出 sentence-level sample。

输出字段：

```text
document_id
company_name
ticker
call_date
section
speaker
sentence_id
sentence
```

### Step 2. Literature-based AI seed lexicon

读 AI exposure、AI firm、AI innovation、AI labor、AI finance 相关文献，整理 `ai_seed_lexicon_v1.csv`。

建议分组：

```text
core_ai:
artificial intelligence, machine learning, deep learning, neural network

gen_ai:
generative AI, large language model, LLM, ChatGPT, foundation model

automation_ai:
algorithm, predictive analytics, computer vision, natural language processing

business_use:
AI platform, recommendation engine, automated decision, data-driven model
```

### Step 3. Candidate sentence extraction

用 AI seed lexicon 从所有 sentence 中抽候选句。

这一步对应 He 的：

```text
Data input/total_labor_sentences.csv
```

我们的输出可以叫：

```text
outputs/ai_candidate_sentences.csv
```

### Step 4. Word2Vec expansion

用 transcript corpus 训练 Word2Vec，围绕 seed terms 找近邻词，人工筛选后生成：

```text
config/ai_seed_lexicon_v2.csv
```

### Step 5. Manual labeling

从 AI candidate sentences 抽样，标注：

```text
1 = truly AI-related
0 = false positive / generic technology / non-AI usage
```

这一步是训练或验证 classifier 的基础。

### Step 6. FinBERT / classifier

遵循 He 的工程模板：

```text
candidate sentences
→ classifier
→ sentence-level label and score
→ count AI-related sentences
```

但模型要换成 AI classifier。He 的 labor-shortage fine-tuned model 不能直接用于 AI。

### Step 7. Aggregation

先做 transcript-level：

```text
AI_EXPOSURE = num_ai_sentences / total_sentences
```

再聚合到：

```text
firm-quarter
firm-year
```

建议保留多个 exposure 版本：

```text
AI_EXPOSURE_ALL
AI_EXPOSURE_MGMT
AI_EXPOSURE_QA
AI_EXPOSURE_CORE_AI
AI_EXPOSURE_GENAI
```

### Step 8. Validation

最后再做验证：

1. 人工抽样检查 false positives / false negatives；
2. 看 AI exposure 的时间趋势；
3. 看行业分布是否合理；
4. 与 AI patent、AI hiring、AI beta、AI narrative 等外部指标比较；
5. 比较 management section 和 Q&A section 的差异。

## 9. 每次开工提示

当前最重要的不是跑回归，也不是马上训练 FinBERT，而是按顺序搭建文本 pipeline：

```text
XML parser
→ sentence table
→ AI seed lexicon
→ AI candidate sentences
→ Word2Vec expansion
→ manual labels
→ AI classifier
→ AI exposure aggregation
```

最优先任务：

```text
ai_exposure_pipeline/01_parse_xml.py
```

先保证我们能从 XML 稳定得到 sentence-level data。后面所有 seed、Word2Vec、FinBERT 和 exposure 聚合都依赖这一步。
