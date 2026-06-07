param(
    [int]$StartYear = 2001,
    [int]$EndYear = 2024,
    [int]$MaxJobs = 4,
    [int]$ProgressEvery = 10000,
    [int]$StatusEverySeconds = 60,
    [switch]$IncludeReview,
    [switch]$KeepGenericAiWithLongerMatch
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$ExtractorScript = Join-Path $RepoRoot "codes\stage03_candidate_sentence_extraction\extract_ai_candidate_sentences.py"
$Lexicon = Join-Path $RepoRoot "codes\stage02_ai_seed_lexicon\ai_seed_lexicon_v2.csv"
$Stage01ByYear = Join-Path $RepoRoot "codes\stage01_xml_standardization\outputs\by_year"
$OutputRoot = Join-Path $RepoRoot "codes\stage05_manual_labeling\outputs"
$PartRoot = Join-Path $OutputRoot "by_year_parts"
$LogRoot = Join-Path $OutputRoot "logs"

New-Item -ItemType Directory -Force -Path $PartRoot | Out-Null
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

$years = $StartYear..$EndYear
$jobs = @()
$jobInfo = @{}
$lastStatusAt = Get-Date

function Wait-ForJobSlot {
    param([int]$Limit)
    while (($script:jobs | Where-Object { $_.State -eq "Running" }).Count -ge $Limit) {
        Start-Sleep -Seconds 2
        Write-RunningStatus
        Receive-CompletedJobs
    }
}

function Write-RunningStatus {
    param([switch]$Force)

    $now = Get-Date
    if (-not $Force -and (($now - $script:lastStatusAt).TotalSeconds -lt $StatusEverySeconds)) {
        return
    }

    $runningJobs = @($script:jobs | Where-Object { $_.State -eq "Running" })
    if ($runningJobs.Count -eq 0) {
        $script:lastStatusAt = $now
        return
    }

    Write-Host ""
    Write-Host "Stage 05 heartbeat at $($now.ToString('yyyy-MM-dd HH:mm:ss'))"
    foreach ($job in $runningJobs) {
        $info = $script:jobInfo[$job.Id]
        if ($null -eq $info) {
            Write-Host "  $($job.Name): running"
            continue
        }

        $elapsed = $now - $info.StartedAt
        $candidateMb = "0.0"
        if (Test-Path $info.CandidateOut) {
            $candidateMb = "{0:N1}" -f ((Get-Item $info.CandidateOut).Length / 1MB)
        }

        $lastLogLine = "log not created yet"
        if (Test-Path $info.LogOut) {
            $tail = Get-Content $info.LogOut -Tail 1 -ErrorAction SilentlyContinue
            if ($tail) {
                $lastLogLine = $tail
            }
        }

        Write-Host (
            "  Year {0}: elapsed={1:hh\:mm\:ss}, candidate_file={2} MB, last_log={3}" -f `
                $info.Year, $elapsed, $candidateMb, $lastLogLine
        )
    }
    Write-Host ""
    $script:lastStatusAt = $now
}

function Receive-CompletedJobs {
    foreach ($job in @($script:jobs | Where-Object { $_.State -ne "Running" })) {
        Receive-Job $job | Write-Host
        if ($job.State -eq "Failed") {
            throw "Stage 05 job failed: $($job.Name)"
        }
        Remove-Job $job
        $script:jobs = @($script:jobs | Where-Object { $_.Id -ne $job.Id })
        $script:jobInfo.Remove($job.Id)
    }
}

foreach ($year in $years) {
    $sentences = Join-Path $Stage01ByYear "$year\transcript_sentences.csv"
    $candidateOut = Join-Path $PartRoot "ai_candidate_sentences_v2_$year.csv"
    $summaryOut = Join-Path $PartRoot "ai_candidate_summary_by_document_v2_$year.csv"
    $doneMarker = Join-Path $PartRoot "ai_candidate_sentences_v2_$year.done"
    $logOut = Join-Path $LogRoot "stage05_v2_$year.log"

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
    Write-Host "Starting Stage 05 v2 extraction for $year"

    $job = Start-Job -Name "stage05_v2_$year" -ScriptBlock {
        param(
            $RepoRoot,
            $ExtractorScript,
            $Lexicon,
            $Sentences,
            $CandidateOut,
            $SummaryOut,
            $DoneMarker,
            $LogOut,
            $ProgressEvery,
            $Year,
            $IncludeReview,
            $KeepGenericAiWithLongerMatch
        )

        Set-Location $RepoRoot

        $argsList = @(
            "-u", $ExtractorScript,
            "--sentences", $Sentences,
            "--lexicon", $Lexicon,
            "--output", $CandidateOut,
            "--summary-output", $SummaryOut,
            "--progress-every", $ProgressEvery
        )

        if ($IncludeReview) {
            $argsList += "--include-review"
        }
        if ($KeepGenericAiWithLongerMatch) {
            $argsList += "--keep-generic-ai-with-longer-match"
        }

        & python @argsList *>&1 | Tee-Object -FilePath $LogOut

        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        New-Item -ItemType File -Force -Path $DoneMarker | Out-Null
        "Completed Stage 05 v2 extraction for $Year"
    } -ArgumentList `
        $RepoRoot, `
        $ExtractorScript, `
        $Lexicon, `
        $sentences, `
        $candidateOut, `
        $summaryOut, `
        $doneMarker, `
        $logOut, `
        $ProgressEvery, `
        $year, `
        $IncludeReview.IsPresent, `
        $KeepGenericAiWithLongerMatch.IsPresent

    $jobs += $job
    $jobInfo[$job.Id] = [pscustomobject]@{
        Year = $year
        StartedAt = Get-Date
        CandidateOut = $candidateOut
        LogOut = $logOut
    }
}

while ($jobs.Count -gt 0) {
    Start-Sleep -Seconds 2
    Write-RunningStatus
    Receive-CompletedJobs
}

$candidateFiles = $years |
    ForEach-Object { Join-Path $PartRoot "ai_candidate_sentences_v2_$_.csv" } |
    Where-Object { Test-Path $_ }

$summaryFiles = $years |
    ForEach-Object { Join-Path $PartRoot "ai_candidate_summary_by_document_v2_$_.csv" } |
    Where-Object { Test-Path $_ }

if ($candidateFiles.Count -eq 0) {
    throw "No yearly Stage 05 v2 candidate files were produced."
}

$finalCandidate = Join-Path $OutputRoot "ai_candidate_sentences_v2.csv"
$finalSummary = Join-Path $OutputRoot "ai_candidate_summary_by_document_v2.csv"

Write-Host "Merging yearly Stage 05 v2 candidate outputs..."
$candidateFiles | ForEach-Object { Import-Csv $_ } |
    Export-Csv $finalCandidate -NoTypeInformation -Encoding UTF8

Write-Host "Merging yearly Stage 05 v2 summary outputs..."
$summaryFiles | ForEach-Object { Import-Csv $_ } |
    Export-Csv $finalSummary -NoTypeInformation -Encoding UTF8

Write-Host "Done."
Write-Host "Candidate output: $finalCandidate"
Write-Host "Summary output: $finalSummary"
