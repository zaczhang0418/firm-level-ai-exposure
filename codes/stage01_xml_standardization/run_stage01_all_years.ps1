param(
    [int]$StartYear = 2001,
    [int]$EndYear = 2024
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$LogDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "stage01_full_run_$Timestamp.log"

Set-Location $RepoRoot

"Stage 01 full run started at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Tee-Object -FilePath $LogPath
"Repo root: $RepoRoot" | Tee-Object -FilePath $LogPath -Append
"Years: $StartYear-$EndYear" | Tee-Object -FilePath $LogPath -Append

foreach ($Year in $StartYear..$EndYear) {
    $OutputDir = "codes\stage01_xml_standardization\outputs\by_year\$Year"
    "" | Tee-Object -FilePath $LogPath -Append
    "===== Stage 01 year $Year started at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =====" | Tee-Object -FilePath $LogPath -Append

    python codes\stage01_xml_standardization\parse_xml.py --year $Year --limit 0 --output-dir $OutputDir 2>&1 |
        Tee-Object -FilePath $LogPath -Append

    if ($LASTEXITCODE -ne 0) {
        "Year $Year failed with exit code $LASTEXITCODE at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" |
            Tee-Object -FilePath $LogPath -Append
        exit $LASTEXITCODE
    }

    "===== Stage 01 year $Year finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =====" | Tee-Object -FilePath $LogPath -Append
}

"" | Tee-Object -FilePath $LogPath -Append
"Stage 01 full run completed at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Tee-Object -FilePath $LogPath -Append
