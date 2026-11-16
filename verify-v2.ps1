param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
$pythonRuntime = Join-Path $repoRoot 'apps\engine\.venv\Scripts\python.exe'
$nodeRuntime = (Get-Command node -CommandType Application -ErrorAction Stop).Source
$verificationDir = Join-Path $repoRoot 'outputs\verification'
$verificationTemp = Join-Path $verificationDir 'temp'
New-Item -ItemType Directory -Path $verificationTemp -Force | Out-Null
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$env:TEMP = $verificationTemp
$env:TMP = $verificationTemp
function Assert-Check([string]$name) {
    if ($LASTEXITCODE -ne 0) { throw "$name failed with exit code $LASTEXITCODE" }
}
try {
    Push-Location -LiteralPath (Join-Path $repoRoot 'apps\engine')
    try {
        $freshBase = Join-Path $verificationTemp ([guid]::NewGuid().ToString('N'))
        & $pythonRuntime -m pytest -o 'addopts=-p no:cacheprovider --import-mode=importlib --ignore=evidence_tests/test_app.py' --basetemp $freshBase "--junitxml=$verificationDir\python.xml"
        Assert-Check 'Python tests'
    } finally { Pop-Location }
    Push-Location -LiteralPath (Join-Path $repoRoot 'apps\web')
    try {
        $webTests = @(Get-ChildItem -LiteralPath tests -Filter '*.test.mjs' | Sort-Object Name | ForEach-Object FullName)
        & $nodeRuntime --test @webTests
        Assert-Check 'Web tests'
        $gatewayTests = @(Get-ChildItem -LiteralPath '..\gateway\tests' -Filter '*.test.mjs' | Sort-Object Name | ForEach-Object FullName)
        & $nodeRuntime --test @gatewayTests
        Assert-Check 'Gateway tests'
        & $nodeRuntime node_modules/typescript/bin/tsc --noEmit --incremental false
        Assert-Check 'TypeScript'
        if (-not $SkipBuild) {
            & $nodeRuntime node_modules/vinext/dist/cli.js build
            Assert-Check 'Production build'
        }
    } finally { Pop-Location }
} finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
}
Write-Output 'Requested verification checks passed.'

