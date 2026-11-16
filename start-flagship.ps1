param([ValidateRange(1,65535)][int]$Port = 5273, [ValidateRange(1,65535)][int]$GatewayPort = 5274)
$ErrorActionPreference = 'Stop'
if ($Port -eq $GatewayPort) { throw 'Web and gateway ports must differ.' }
# Never reuse an unknown listener: it may own V1's private research store.
foreach ($candidatePort in @($Port, $GatewayPort)) {
  if (Get-NetTCPConnection -LocalPort $candidatePort -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $candidatePort is already in use. Close the existing Flagship process or choose distinct -Port and -GatewayPort values. No existing gateway will be reused."
  }
}
$appPath = Join-Path $PSScriptRoot 'apps\web'
$nodeExecutable = (Get-Command node -CommandType Application -ErrorAction SilentlyContinue).Source
if (-not $nodeExecutable) {
  $bundledNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
  if (Test-Path -LiteralPath $bundledNode -PathType Leaf) {
    $nodeExecutable = $bundledNode
  }
}
if (-not $nodeExecutable) {
  throw 'Install Node.js 24 or newer, reopen PowerShell, then run Flagship again.'
}
$cliPath = Join-Path $appPath 'node_modules\vinext\dist\cli.js'
if (-not (Test-Path -LiteralPath $cliPath)) {
  throw 'Dependencies are missing. Run npm run install:ci in apps/web first.'
}
Push-Location -LiteralPath $appPath
$previousPath = $env:PATH
$previousWebPort = $env:Q21_WEB_PORT
$previousGatewayPort = $env:Q21_GATEWAY_PORT
$previousFlagshipData = $env:Q_FLAGSHIP_DATA
$previousPaperData = $env:Q_PAPER_DATA
$previousEnginePython = $env:Q_ENGINE_PYTHON
$env:PATH = (Split-Path -Parent $nodeExecutable) + [IO.Path]::PathSeparator + $env:PATH
$env:Q21_WEB_PORT = [string]$Port
$env:Q21_GATEWAY_PORT = [string]$GatewayPort
# An inherited V1 data override must never redirect this checkout's writes.
$env:Q_FLAGSHIP_DATA = Join-Path $PSScriptRoot '.data\flagship'
$env:Q_PAPER_DATA = Join-Path $PSScriptRoot '.data\paper'
$env:Q_ENGINE_PYTHON = Join-Path $PSScriptRoot 'apps\engine\.venv\Scripts\python.exe'
$integrationProcess = $null
try {
  $gatewayScript = Join-Path $PSScriptRoot 'apps\gateway\server.mjs'
  $integrationProcess = Start-Process -FilePath $nodeExecutable -ArgumentList @('"' + $gatewayScript + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
  $gatewayReady = $false
  for ($attempt = 0; $attempt -lt 20; $attempt++) {
    if ($integrationProcess.HasExited) { throw 'The Flagship gateway failed to start. No web session was opened.' }
    $listener = Get-NetTCPConnection -LocalPort $GatewayPort -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
      if ($listener.OwningProcess -ne $integrationProcess.Id) { throw 'A different process claimed the gateway port. Refusing to connect.' }
      $gatewayReady = $true
      break
    }
    Start-Sleep -Milliseconds 500
  }
  if (-not $gatewayReady) { throw 'The Flagship gateway did not start within ten seconds.' }
  & $nodeExecutable $cliPath dev --port $Port
}
finally {
  if ($integrationProcess -and -not $integrationProcess.HasExited) { Stop-Process -Id $integrationProcess.Id -ErrorAction SilentlyContinue }
  $env:PATH = $previousPath
  $env:Q21_WEB_PORT = $previousWebPort
  $env:Q21_GATEWAY_PORT = $previousGatewayPort
  $env:Q_FLAGSHIP_DATA = $previousFlagshipData
  $env:Q_PAPER_DATA = $previousPaperData
  $env:Q_ENGINE_PYTHON = $previousEnginePython
  Pop-Location
}
