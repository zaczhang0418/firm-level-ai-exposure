param(
    [int]$StartYear = 2001,
    [int]$EndYear = 2024,
    [int]$MaxJobs = 4,
    [int]$ProgressEvery = 10000
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Stage03Script = Join-Path $RepoRoot "codes\stage03_candidate_sentence_extraction\extract_ai_candidate_sentences.py"
$Lexicon = Join-Path $RepoRoot "codes\stage02_ai_seed_lexicon\ai_seed_lexicon_v1.csv"
$Stage01ByYear = Join-Path $RepoRoot "codes\stage01_xml_standardization\outputs\by_year"
$OutputRoot = Join-Path $RepoRoot "codes\stage03_candidate_sentence_extraction\outputs"
$PartRoot = Join-Path $OutputRoot "by_year_parts"
$LogRoot = Join-Path $OutputRoot "logs"

New-Item -ItemType Directory -Force -Path $PartRoot | Out-Null
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

$years = $StartYear..$EndYear
$jobs = @()

function Wait-ForJobSlot {
    param([int]$Limit)
    while (($script:jobs | Where-Object { $_.State -eq "Running" }).Count -ge $Limit) {
        Start-Sleep -Seconds 2
        Receive-CompletedJobs
    }
}

function Receive-CompletedJobs {
    foreach ($job in @($script:jobs | Where-Object { $_.State -ne "Running" })) {
        Receive-Job $job | Write-Host
        if ($job.State -eq "Failed") {
            throw "Stage 03 job failed: $($job.Name)"
        }
        Remove-Job $job
        $script:jobs = @($script:jobs | Where-Object { $_.Id -ne $job.Id })
    }
}

foreach ($year in $years) {
    $sentences = Join-Path $Stage01ByYear "$year\transcript_sentences.csv"
    $candidateOut = Join-Path $PartRoot "ai_candidate_sentences_$year.csv"
    $summaryOut = Join-Path $PartRoot "ai_candidate_summary_by_document_$year.csv"
    $doneMarker = Join-Path $PartRoot "ai_candidate_sentences_$year.done"
    $logOut = Join-Path $LogRoot "stage03_$year.log"

    if ((Test-Path $candidateOut) -and (Test-Path $summaryOut) -and (Test-Path $doneMarker)) {
        Write-Host "Skipping $year; completed output already exists."
        continue
    }

    if (-not (Test-Path $sentences)) {
        Write-Host "Skipping $year; missing $sentences"
        continue
    }

    if (Test-Path $doneMarker) {
        Remove-Item $doneMarker
    }

    Wait-ForJobSlot -Limit $MaxJobs
    Write-Host "Starting Stage 03 for $year"

    $jobs += Start-Job -Name "stage03_$year" -ScriptBlock {
        param($RepoRoot, $Stage03Script, $Lexicon, $Sentences, $CandidateOut, $SummaryOut, $DoneMarker, $LogOut, $ProgressEvery, $Year)

        Set-Location $RepoRoot

        & python -u $Stage03Script `
            --sentences $Sentences `
            --lexicon $Lexicon `
            --output $CandidateOut `
            --summary-output $SummaryOut `
            --progress-every $ProgressEvery *>&1 |
            Tee-Object -FilePath $LogOut

        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        New-Item -ItemType File -Force -Path $DoneMarker | Out-Null
        "Completed Stage 03 for $Year"
    } -ArgumentList $RepoRoot, $Stage03Script, $Lexicon, $sentences, $candidateOut, $summaryOut, $doneMarker, $logOut, $ProgressEvery, $year
}

while ($jobs.Count -gt 0) {
    Start-Sleep -Seconds 2
    Receive-CompletedJobs
}

$candidateFiles = $years |
    ForEach-Object { Join-Path $PartRoot "ai_candidate_sentences_$_.csv" } |
    Where-Object { Test-Path $_ }

$summaryFiles = $years |
    ForEach-Object { Join-Path $PartRoot "ai_candidate_summary_by_document_$_.csv" } |
    Where-Object { Test-Path $_ }

if ($candidateFiles.Count -eq 0) {
    throw "No yearly candidate files were produced."
}

$finalCandidate = Join-Path $OutputRoot "ai_candidate_sentences.csv"
$finalSummary = Join-Path $OutputRoot "ai_candidate_summary_by_document.csv"

Write-Host "Merging yearly candidate outputs..."
$candidateFiles | ForEach-Object { Import-Csv $_ } |
    Export-Csv $finalCandidate -NoTypeInformation -Encoding UTF8

Write-Host "Merging yearly summary outputs..."
$summaryFiles | ForEach-Object { Import-Csv $_ } |
    Export-Csv $finalSummary -NoTypeInformation -Encoding UTF8

Write-Host "Done."
Write-Host "Candidate output: $finalCandidate"
Write-Host "Summary output: $finalSummary"
