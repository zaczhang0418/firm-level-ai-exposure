# Stage 00: Project Scoping

This stage records the overall project design.

The key methodological decision is:

```text
We are not replicating He's economic regressions.
We are borrowing He's transcript-based topic exposure construction logic.
```

He's exposure construction logic is:

```text
conference call transcript
-> sentence-level text
-> topic keyword candidate sentences
-> FinBERT topic classifier
-> topic-related sentence count
-> sentence-share exposure
-> firm-quarter / firm-year aggregation
```

Our replacement is:

```text
labor shortage exposure
-> AI exposure
```

Project notes live mainly in:

```text
docs/he_replication_package_audit.md
```

