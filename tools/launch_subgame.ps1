param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dk', 'duck', 'feud', 'waldo', 'wheel')]
    [string]$Game,
    [ValidateSet('176', 'mmc3')]
    [string]$Mapper = '176',
    [switch]$NoRebuild,
    [switch]$PrepareOnly
)

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot

$playDir = if ($Mapper -eq 'mmc3') { Join-Path $taskRoot "play\compat\nes" } else { Join-Path $taskRoot "play\nes" }
$romStem = if ($Mapper -eq 'mmc3') { "$Game-compat" } else { "$Game" }
if ($NoRebuild) {
    $pattern = '^' + [regex]::Escape($romStem) + '-b(\d+)$'
    $numbered = Get-ChildItem -LiteralPath $playDir -Filter "$romStem-b*.nes" -ErrorAction SilentlyContinue |
        Where-Object { $_.BaseName -match $pattern } |
        Sort-Object { [int][regex]::Match($_.BaseName, $pattern).Groups[1].Value } |
        Select-Object -Last 1
    $playRom = if ($numbered) { $numbered.FullName } else { Join-Path $playDir "$romStem.nes" }
} else {
    $playRom = Join-Path $playDir "$romStem.nes"
}
if ($Mapper -eq 'mmc3') {
    if (!$NoRebuild) {
        & python (Join-Path $PSScriptRoot 'build_mmc3.py') --game $Game --out-dir $playDir
        if ($LASTEXITCODE -ne 0) { throw "MMC3 subgame build failed for $Game; Mesen was not opened." }
    }
    if (!(Test-Path -LiteralPath $playRom)) { throw "ROM missing: $playRom" }
} else {

    switch ($Game) {
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
}

$taskMesen = (& python (Join-Path $PSScriptRoot 'prepare_player.py')) | Select-Object -Last 1
if ($LASTEXITCODE -ne 0) { throw 'Mesen setup failed.' }

if ($PrepareOnly) {
    Write-Output "Prepared $playRom without opening Mesen."
    return
}

Start-Process -FilePath $taskMesen -ArgumentList ('"' + $playRom + '"') -WorkingDirectory (Split-Path -Parent $taskMesen) -WindowStyle Normal
