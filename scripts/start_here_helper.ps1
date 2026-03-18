param(
  [Parameter(Mandatory = $true)] [string]$ZipPath,
  [ValidateSet("Inspect", "Extract")] [string]$Mode = "Inspect",
  [string]$OutputDir = ".\out",
  [int]$MaxEntries = 10000,
  [long]$MaxMemberBytes = 5242880,
  [double]$MaxRatio = 100.0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-SuspiciousZipMemberName {
  param([string]$Name)
  if ($Name -match "\x00") { return $true }
  if ($Name.StartsWith("/") -or $Name.StartsWith("\\")) { return $true }
  if ($Name -match "^[A-Za-z]:") { return $true }
  if ($Name.StartsWith("//") -or $Name.StartsWith("\\\\")) { return $true }
  $normalized = $Name -replace "\\", "/"
  foreach ($part in $normalized.Split("/")) {
    if ($part -eq "..") { return $true }
  }
  return $false
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
  if ($zip.Entries.Count -gt $MaxEntries) {
    throw "Entry count exceeds cap: $($zip.Entries.Count) > $MaxEntries"
  }

  $candidates = @()
  foreach ($entry in $zip.Entries) {
    if ([string]::IsNullOrWhiteSpace($entry.Name)) { continue }
    $suspicious = Test-SuspiciousZipMemberName -Name $entry.FullName
    $ratio = if ($entry.CompressedLength -gt 0) { [math]::Round($entry.Length / $entry.CompressedLength, 4) } elseif ($entry.Length -gt 0) { [double]::PositiveInfinity } else { 0 }
    [pscustomobject]@{
      Name = $entry.FullName
      Length = $entry.Length
      CompressedLength = $entry.CompressedLength
      Ratio = $ratio
      Suspicious = $suspicious
    } | Format-Table | Out-Host

    $stem = [System.IO.Path]::GetFileNameWithoutExtension($entry.Name).ToLowerInvariant() -replace "[^a-z0-9]", ""
    $ext = [System.IO.Path]::GetExtension($entry.Name).ToLowerInvariant()
    if ($stem -eq "starthere" -and @(".txt", ".md") -contains $ext) {
      $candidates += $entry
    }
  }

  if ($Mode -eq "Extract") {
    if ($candidates.Count -eq 0) { throw "No START HERE candidate found" }
    $preferred = $candidates | Sort-Object @{Expression = { if ($_.Name.ToLowerInvariant().EndsWith('.txt')) { 0 } else { 1 } } }, Name
    $selected = $preferred[0]
    if ((Test-SuspiciousZipMemberName -Name $selected.FullName)) {
      throw "Rejected suspicious member path: $($selected.FullName)"
    }
    if ($selected.Length -gt $MaxMemberBytes) {
      throw "Declared size cap exceeded: $($selected.Length) > $MaxMemberBytes"
    }
    if ($selected.CompressedLength -gt 0) {
      $ratio = $selected.Length / $selected.CompressedLength
      if ($ratio -gt $MaxRatio) { throw "Compression ratio cap exceeded: $ratio > $MaxRatio" }
    }

    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $dest = Join-Path $OutputDir ("start_here" + [System.IO.Path]::GetExtension($selected.Name).ToLowerInvariant())
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($selected, $dest, $true)
    Write-Host "Extracted to $dest"
  }
}
finally {
  $zip.Dispose()
}
