param([switch]$NoRebuild)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskRom = Join-Path $taskRoot 'build\barba.nes'
if (!$NoRebuild) {
    & python (Join-Path $PSScriptRoot 'build.py')
    if ($LASTEXITCODE -ne 0) { throw 'ROM build failed; Mesen was not opened.' }
}
if (!(Test-Path -LiteralPath $taskRom)) { throw "ROM missing: $taskRom" }
& python (Join-Path $PSScriptRoot 'prepare_player.py')
if ($LASTEXITCODE -ne 0) { throw 'Mesen setup failed.' }
$taskMesen = Join-Path $taskRoot '.tools\mesen-play\Mesen.exe'
Start-Process -FilePath $taskMesen -ArgumentList ('"' + $taskRom + '"') -WorkingDirectory (Split-Path -Parent $taskMesen) -WindowStyle Normal
Write-Output 'Opened Barba Edition in Mesen. Arrows: move; X: jump; Z: flame; Enter: Start; Left Shift: Select.'
