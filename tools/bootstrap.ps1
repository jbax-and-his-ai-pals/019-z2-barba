param([switch]$WithEmulator)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskTools = Join-Path $taskRoot '.tools'
$taskLock = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'toolchain.json') | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $taskTools | Out-Null
$taskNames = @('cc65')
if ($WithEmulator) { $taskNames += 'mesen' }
foreach ($taskName in $taskNames) {
    $taskSpec = $taskLock.$taskName
    $taskArchive = Join-Path $taskTools ($taskName + '.zip')
    if (!(Test-Path -LiteralPath $taskArchive)) {
        & curl.exe -L --fail --max-time 120 $taskSpec.url -o $taskArchive
        if ($LASTEXITCODE -ne 0) { throw "Download failed for $taskName" }
    }
    $taskHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $taskArchive).Hash.ToLowerInvariant()
    if ($taskHash -ne $taskSpec.sha256) {
        throw "Checksum mismatch for $taskName. No files extracted. See docs/BUILD.md."
    }
    $taskDestination = Join-Path $taskTools $taskSpec.folder
    Expand-Archive -LiteralPath $taskArchive -DestinationPath $taskDestination -Force
    Write-Output ("Ready: " + $taskName + ' ' + $taskSpec.version)
}
