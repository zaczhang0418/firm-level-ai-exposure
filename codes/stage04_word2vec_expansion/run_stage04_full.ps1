param(
    [int]$Workers = 16,
    [int]$VectorSize = 200,
    [int]$Window = 8,
    [int]$MinCount = 5,
    [int]$Epochs = 8,
    [int]$TopN = 50,
    [string]$OutputDir = "",
    [string]$ResumeFromModel = "",
    [string]$PhraseModelDir = "",
    [string]$CheckpointDir = "",
    [Nullable[int]]$Limit = $null,
    [switch]$IncludeReview,
    [switch]$AggregateMeanVectorNeighbors,
    [switch]$IncludeGenericAiNeighbors,
    [switch]$NoEpochCheckpoints
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Stage04Script = Join-Path $RepoRoot "codes\stage04_word2vec_expansion\train_word2vec.py"
$Sentences = Join-Path $RepoRoot "codes\stage01_xml_standardization\outputs\by_year"
$Lexicon = Join-Path $RepoRoot "codes\stage02_ai_seed_lexicon\ai_seed_lexicon_v1.csv"
if ($OutputDir -eq "") {
    $OutputDir = Join-Path $RepoRoot "codes\stage04_word2vec_expansion\outputs"
}

Set-Location $RepoRoot

$argsList = @(
    "-u", $Stage04Script,
    "--sentences", $Sentences,
    "--lexicon", $Lexicon,
    "--output-dir", $OutputDir,
    "--workers", $Workers,
    "--vector-size", $VectorSize,
    "--window", $Window,
    "--min-count", $MinCount,
    "--epochs", $Epochs,
    "--topn", $TopN
)

if ($Limit -ne $null) {
    $argsList += @("--limit", $Limit)
}
if ($IncludeReview) {
    $argsList += "--include-review"
}
if ($AggregateMeanVectorNeighbors) {
    $argsList += "--aggregate-mean-vector-neighbors"
}
if ($IncludeGenericAiNeighbors) {
    $argsList += "--include-generic-ai-neighbors"
}
if ($ResumeFromModel -ne "") {
    $argsList += @("--resume-from-model", $ResumeFromModel)
}
if ($PhraseModelDir -ne "") {
    $argsList += @("--phrase-model-dir", $PhraseModelDir)
}
if ($CheckpointDir -ne "") {
    $argsList += @("--checkpoint-dir", $CheckpointDir)
}
if ($NoEpochCheckpoints) {
    $argsList += "--no-epoch-checkpoints"
}

Write-Host "Running Stage 04 Word2Vec training..."
Write-Host "Workers: $Workers"
Write-Host "Output: $OutputDir"

& python @argsList

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Done."
