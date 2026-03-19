$ErrorActionPreference = 'Stop'
$sentinel = 'C:\Sandbox\Results\job.completed.json'
$started = [DateTimeOffset]::UtcNow.ToString('o')
$exitCode = 0
$status = 'completed'
try {
    Write-Host "No sandbox command configured; writing sentinel only."
} catch {
    $status = 'failed'
    $exitCode = 1
} finally {
    $ended = [DateTimeOffset]::UtcNow.ToString('o')
    $payload = @{
        status = $status
        exit_code = $exitCode
        started_at = $started
        ended_at = $ended
        zip_path = 'mismatch.zip'
    } | ConvertTo-Json -Compress
    Set-Content -Path $sentinel -Value $payload -Encoding UTF8
    if ($exitCode -ne 0) { exit $exitCode }
}
