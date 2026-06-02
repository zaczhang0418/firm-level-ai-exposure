# Stage 01: XML Standardization

This stage converts raw conference call XML files into standardized CSV tables.

## Goal

The goal is to create transcript and sentence tables that can be linked later to:

```text
ticker
company_name
call_date
reported_year / reported_quarter
gvkey
firm-year
firm-quarter
```

At this stage, we are not detecting AI yet. We are building the text and identifier foundation.

## Input

Raw XML files:

```text
Data/Data_Conference call transcripts/YYYY/*.xml
```

Each XML generally contains:

```text
Event Id
Headline
Body
eventTitle
companyName
companyTicker
startDate
```

## Outputs

Expected metadata output:

```text
outputs/transcript_metadata.csv
```

One row per XML transcript.

Expected fields:

```text
document_id
event_id
company_name
ticker
call_date
call_year
call_quarter
reported_year
reported_quarter
event_title
headline
xml_path
```

Expected sentence output:

```text
outputs/transcript_sentences.csv
```

One row per transcript sentence.

Expected fields:

```text
document_id
event_id
company_name
ticker
call_date
call_year
call_quarter
reported_year
reported_quarter
section
speaker
sentence_id
sentence
xml_path
```

## He Logic To Follow

He's denominator is sentence count, not word count. Therefore, this stage must preserve:

```text
document_id
sentence_id
section
sentence
```

We should distinguish:

```text
presentation / management section
Q&A section
```

This allows later exposure measures such as:

```text
AI_EXPOSURE_ALL
AI_EXPOSURE_MGMT
AI_EXPOSURE_QA
```

## Current Script

```text
parse_xml.py
```

## What This Stage Does

This stage follows the text-standardization layer implied by He's labor-shortage pipeline:

```text
raw transcript
-> document_id
-> section-aware sentence_id
-> sentence-level table
-> denominator for exposure
```

He's later exposure logic depends on knowing:

```text
which transcript a sentence came from
which section it belongs to
how many total sentences the transcript has
```

Therefore, Stage 01 creates the infrastructure for later AI exposure:

```text
XML
-> transcript metadata table
-> sentence-level table
```

## Implementation Details

`parse_xml.py` currently:

1. Finds XML files by year or across all years;
2. Extracts metadata from XML tags:
   - `Event Id`
   - `Headline`
   - `Body`
   - `eventTitle`
   - `companyName`
   - `companyTicker`
   - `startDate`
3. Parses `call_date`, `call_year`, and `call_quarter`;
4. Attempts to parse `reported_year` and `reported_quarter` from transcript title/headline/body;
5. Splits body text into:
   - `presentation`
   - `qa`
   - fallback `transcript` for older files without clear section headings;
6. Parses speaker turns using transcript speaker markers such as `[1]`, `[2]`;
7. Splits speaker turns into sentences;
8. Writes CSV outputs using streaming writers, so full-year runs do not hold all sentences in memory.

## Sentence ID Logic

Sentence IDs are built as:

```text
document_id_section_00001
```

Example:

```text
12251699_presentation_00001
12251699_qa_00164
```

This is intentionally close to He's logic:

```text
document_id + sentence index
```

but we also include section information to make later management/Q&A exposure easier.

## Commands

Small test:

```bash
python3 codes/stage01_xml_standardization/parse_xml.py --year 2013 --limit 5
```

Full single-year run:

```bash
python3 codes/stage01_xml_standardization/parse_xml.py \
  --year 2001 \
  --limit 0 \
  --output-dir codes/stage01_xml_standardization/outputs/by_year/2001
```

Full all-year run:

```bash
python3 codes/stage01_xml_standardization/parse_xml.py --limit 0
```

For production work, prefer the single-year command above and run it year by year. A single all-year output can become very large and harder to inspect.

For large all-year runs, use a stronger machine and keep raw XML at:

```text
Data/Data_Conference call transcripts/
```

## Recommended Output Layout

For 2001-2024 production runs, the recommended structure is:

```text
codes/stage01_xml_standardization/outputs/
  by_year/
    2001/
      transcript_metadata.csv
      transcript_sentences.csv
    2002/
      transcript_metadata.csv
      transcript_sentences.csv
    ...
    2024/
      transcript_metadata.csv
      transcript_sentences.csv
```

So the production output is not just 24 CSV files. It is better to think of it as 24 yearly batches, and each yearly batch has two core CSV files:

```text
transcript_metadata.csv
transcript_sentences.csv
```

That means 48 core CSV files for 2001-2024.

Reason:

1. `transcript_metadata.csv` is one row per XML/call and is used for identifier checking.
2. `transcript_sentences.csv` is one row per sentence and is used for candidate extraction and exposure construction.
3. Keeping years separate makes large runs easier to inspect, rerun, and move across machines.

After all yearly outputs pass quality checks, a later helper script can combine them into all-year files if needed:

```text
outputs/all_years/transcript_metadata_all.csv
outputs/all_years/transcript_sentences_all.csv
```

## Current Test Results

The script has been tested on:

```text
2013 sample: 5 XML files -> 5 metadata rows, 4,130 sentence rows
2001 full year: 421 XML files -> 421 metadata rows, 182,533 sentence rows
```

The 2001 sample confirms the fallback section behavior for older transcript formats that use `Transcript` rather than clear `Presentation` / `Questions and Answers` headings.

## Section Fallback Rule

Some early transcript files do not have clean `Presentation` and `Questions and Answers` headings. For example, some 2001 files use only:

```text
Transcript
```

In those cases, the parser does not drop the text. It keeps all parsed sentences and assigns:

```text
section = transcript
```

This is intentional. It preserves the denominator and keeps the text available for later AI candidate extraction. It also makes these older-format files auditable: later we can decide whether to improve Q&A detection for them or keep them as a single transcript section.

## Known Limitations

1. Sentence splitting is rule-based and may not match NLP libraries perfectly.
2. Older transcripts without explicit Q&A headings are currently marked as `transcript`.
3. `reported_year` / `reported_quarter` may be missing for calls whose title does not contain a clear `Q# YYYY` pattern.
4. `gvkey` is not assigned in this stage. This stage preserves `document_id`, `ticker`, `company_name`, and date fields so later linking is possible.
