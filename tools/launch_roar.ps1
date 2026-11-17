param([switch]$PrepareOnly, [switch]$TestPack)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskRom = Join-Path $taskRoot 'build\barba.nes'
if (!(Test-Path -LiteralPath $taskRom)) {
    throw 'Run python tools/build.py first; see docs/BUILD.md.'
}
if ($TestPack) {
    & python (Join-Path $PSScriptRoot 'prepare_test_player.py') --set core --rom $taskRom
    if ($LASTEXITCODE -ne 0) { throw 'Roar checkpoint setup failed.' }
    $taskManifest = Get-Content -Raw -LiteralPath (Join-Path $taskRoot 'build\test-pack\current.json') | ConvertFrom-Json
    $taskRom = $taskManifest.rom
    $taskMesen = Join-Path $taskRoot 'build\mesen-scenarios\roar\core\Mesen.exe'
} else {
    & python (Join-Path $PSScriptRoot 'prepare_player.py')
    if ($LASTEXITCODE -ne 0) { throw 'Mesen setup failed.' }
    $taskMesen = Join-Path $taskRoot '.tools\mesen-play\Mesen.exe'
}
if ($PrepareOnly) { Write-Output "Ready: $taskRom"; return }
Start-Process -FilePath $taskMesen -ArgumentList ('"' + $taskRom + '"') -WorkingDirectory (Split-Path -Parent $taskMesen) -WindowStyle Normal
Write-Output 'Normal Barba build with sampled audio. Stay on the title: roar starts after about 1.3 seconds and repeats about every 4.3 seconds.'
Write-Output 'Game Over follows the original Ganon laugh descent one octave up, without alternating pitch.'
if ($TestPack) { Write-Output 'F2: combat / fireball SFX without attack roars, plus hurt grunt. F6: Lava Link, retaining his Link hurt sound. F9: before Palace 6 boss / gem victory roar.' }
