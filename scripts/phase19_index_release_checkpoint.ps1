param(
    [string]$Workspace = "C:\Users\krist\Desktop\unified_pool_service_platform_build",
    [string]$CheckpointPath = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

$ExtractorDir = Join-Path $Workspace "start_here_extractor_m1_completion"
$BackupDir = Join-Path $Workspace "backups"

if (!(Test-Path -LiteralPath $ExtractorDir)) {
    throw "Extractor repo not found: $ExtractorDir"
}

if ([string]::IsNullOrWhiteSpace($CheckpointPath)) {
    $latest = Get-ChildItem -LiteralPath $BackupDir -Filter "phase19_release_checkpoint_*.json" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (!$latest) {
        throw "No phase19_release_checkpoint_*.json found in $BackupDir. Run the platform Step 15 export first."
    }

    $CheckpointPath = $latest.FullName
}

if (!(Test-Path -LiteralPath $CheckpointPath)) {
    throw "Checkpoint JSON not found: $CheckpointPath"
}

if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutDir = Join-Path $BackupDir "phase19_extractor_evidence_$stamp"
}

Set-Location $ExtractorDir

$env:PYTHONPATH = Join-Path $ExtractorDir "src"

$Py = "py"
$Args = @("-3", "-m", "start_here_extractor.phase19_evidence", "--checkpoint", $CheckpointPath, "--out-dir", $OutDir)

Write-Host "Extractor repo: $ExtractorDir"
Write-Host "Checkpoint:    $CheckpointPath"
Write-Host "Output dir:    $OutDir"
Write-Host ""

& $Py @Args

if ($LASTEXITCODE -ne 0) {
    throw "Evidence indexing failed."
}

Write-Host ""
Write-Host "Evidence pack:"
Get-ChildItem -LiteralPath $OutDir -File | Select-Object Name, Length, LastWriteTime
