param([string]$OutputRoot = '', [switch]$Execute)
$ErrorActionPreference = 'Stop'
if (-not $OutputRoot) { $OutputRoot = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) ('runs\gpt-reliability-v1-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)) }
$oldUtf8=$env:PYTHONUTF8
$oldBytes=$env:PYTHONDONTWRITEBYTECODE
try {
 $env:PYTHONUTF8='1'
 $env:PYTHONDONTWRITEBYTECODE='1'
 $runnerArgs=@((Join-Path $PSScriptRoot 'run_gpt_comparison.py'),'--output-root',$OutputRoot)
 if ($Execute) { $runnerArgs+='--execute' }
 & python @runnerArgs
 if ($LASTEXITCODE -ne 0) { throw 'Stopped; preserve the output directory. Do not restart incomplete cases before inspection.' }
} finally { $env:PYTHONUTF8=$oldUtf8; $env:PYTHONDONTWRITEBYTECODE=$oldBytes }
