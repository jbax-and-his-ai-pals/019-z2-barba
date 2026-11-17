param([switch]$NoRebuild, [switch]$TestPack, [switch]$PrepareOnly,
      [ValidateSet('core','palaces','endgame','bosses','world','gem','items','movement','edges')][string]$CheckpointSet = 'core')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskRom = Join-Path $taskRoot 'build\barba.nes'
if (!$NoRebuild) {
    & python (Join-Path $PSScriptRoot 'build.py')
    if ($LASTEXITCODE -ne 0) { throw 'ROM build failed; Mesen was not opened.' }
}
if (!(Test-Path -LiteralPath $taskRom)) { throw "ROM missing: $taskRom" }
if ($TestPack) {
    & python (Join-Path $PSScriptRoot 'prepare_test_player.py') --set $CheckpointSet
    if ($LASTEXITCODE -ne 0) { throw 'Test pack setup failed.' }
    $taskPack = Get-Content -Raw -LiteralPath (Join-Path $taskRoot 'build\test-pack\current.json') | ConvertFrom-Json
    $taskRom = $taskPack.rom
    $taskMesen = Join-Path $taskRoot "build\mesen-scenarios\$CheckpointSet\Mesen.exe"
} else {
    & python (Join-Path $PSScriptRoot 'prepare_player.py')
    if ($LASTEXITCODE -ne 0) { throw 'Mesen setup failed.' }
    $taskMesen = Join-Path $taskRoot '.tools\mesen-play\Mesen.exe'
}
if ($PrepareOnly) { Write-Output 'Prepared without opening or changing a running emulator.'; return }
Start-Process -FilePath $taskMesen -ArgumentList ('"' + $taskRom + '"') -WorkingDirectory (Split-Path -Parent $taskMesen) -WindowStyle Normal
Write-Output 'Opened Barba Edition in Mesen. Arrows: move; X: jump; Z: flame; Enter: Start; Left Shift: Select.'
if ($TestPack) {
    Write-Output "Checkpoint set: $CheckpointSet"
    foreach ($state in $taskPack.states) { Write-Output ("F{0}: {1} - {2}" -f $state.slot,$state.name,$state.instructions) }
}
