param(
    [int]$MaxEpisodes = 5,
    [switch]$SkipLlm,
    [switch]$Mock,
    [switch]$SkipDeploy
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==> [1/3] Running local RSS ingestion (MaxEpisodes=$MaxEpisodes)..." -ForegroundColor Cyan
Set-Location (Join-Path $RootDir "backend")

$IngestArgs = @("ingest_anchor_feed.py", "--max-episodes", $MaxEpisodes)
if ($SkipLlm) { $IngestArgs += "--skip-llm" }
if ($Mock) { $IngestArgs += "--mock" }

python @IngestArgs

Write-Host "==> [2/3] Building Angular SSG static bundle..." -ForegroundColor Cyan
Set-Location (Join-Path $RootDir "frontend")
npm run build

if ($SkipDeploy) {
    Write-Host "==> [3/3] Skipping Firebase deploy (-SkipDeploy set)." -ForegroundColor Yellow
    Write-Host "Static site ready at: $(Join-Path $RootDir 'frontend\dist\frontend\browser')"
    exit 0
}

Write-Host "==> [3/3] Deploying static site to Firebase Hosting..." -ForegroundColor Cyan
Set-Location $RootDir
firebase deploy --only hosting
