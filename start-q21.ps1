param([ValidateRange(1,65535)][int]$Port = 5273, [ValidateRange(1,65535)][int]$GatewayPort = 5274)
& (Join-Path $PSScriptRoot 'start-flagship.ps1') @PSBoundParameters
