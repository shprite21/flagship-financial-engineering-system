param([int]$Port=5273,[int]$GatewayPort=5274)
$ErrorActionPreference='Stop'
$previousGpu=$env:Q_GPU_PYTHON
$previousIndia=$env:Q_INDIA_DATA
try {
    if (-not $env:Q_GPU_PYTHON) {
        $candidatePython=Join-Path $env:USERPROFILE 'gpu-training\.venv\Scripts\python.exe'
        if (Test-Path -LiteralPath $candidatePython) { $env:Q_GPU_PYTHON=$candidatePython }
    }
    $env:Q_INDIA_DATA=Join-Path $PSScriptRoot '.data\india'
    & (Join-Path $PSScriptRoot 'start-q21.ps1') -Port $Port -GatewayPort $GatewayPort
} finally {
    $env:Q_GPU_PYTHON=$previousGpu
    $env:Q_INDIA_DATA=$previousIndia
}
