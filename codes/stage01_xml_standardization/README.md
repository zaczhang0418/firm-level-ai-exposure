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

Initial test command:

```bash
python3 codes/stage01_xml_standardization/parse_xml.py --year 2013 --limit 5
```

