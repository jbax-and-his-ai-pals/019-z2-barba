param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dk', 'duck', 'f13', 'feud', 'mm2', 'mtpo', 'smb', 'waldo', 'wheel', 'zelda')]
    [string]$Game,
    [switch]$NoRebuild,
    [switch]$PrepareOnly
)

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$playDir = Join-Path $taskRoot "play\standalone"
$playRom = Join-Path $playDir "$Game-barba.nes"

switch ($Game) {
    'f13' {
        $buildScript = Join-Path $PSScriptRoot 'f13_build.py'
        $builtRom = Join-Path $taskRoot 'build\f13_barba.nes'
    }
    'waldo' {
        $buildScript = Join-Path $PSScriptRoot 'build_waldo.py'
        $builtRom = Join-Path $taskRoot 'build\waldo_barba.nes'
    }
    default {
        $buildScript = Join-Path $PSScriptRoot "pack_$Game.py"
        $builtRom = Join-Path $taskRoot "build\subgames\$Game.nes"
    }
}

if (!$NoRebuild) {
    & python $buildScript
    if ($LASTEXITCODE -ne 0) { throw "Subgame build failed for $Game; Mesen was not opened." }
}

if (!(Test-Path -LiteralPath $builtRom)) { throw "ROM missing: $builtRom" }
New-Item -ItemType Directory -Force -Path $playDir | Out-Null
Copy-Item -LiteralPath $builtRom -Destination $playRom -Force

$taskMesen = (& python (Join-Path $PSScriptRoot 'prepare_player.py')) | Select-Object -Last 1
if ($LASTEXITCODE -ne 0) { throw 'Mesen setup failed.' }

if ($PrepareOnly) {
    Write-Output "Prepared $playRom without opening Mesen."
    return
}

Start-Process -FilePath $taskMesen -ArgumentList ('"' + $playRom + '"') -WorkingDirectory (Split-Path -Parent $taskMesen) -WindowStyle Normal
