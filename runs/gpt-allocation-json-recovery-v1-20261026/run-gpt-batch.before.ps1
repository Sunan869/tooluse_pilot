param([int[]]$Cases = @(0))
$ErrorActionPreference = 'Stop'
$batch = $PSScriptRoot
$project = Split-Path (Split-Path $batch -Parent) -Parent
$config = Join-Path $project 'gateway.models.json'
$cfg = Get-Content -LiteralPath $config -Raw -Encoding UTF8 | ConvertFrom-Json
if ($cfg.models.gpt.model -ne 'gpt-6-astra') { throw 'GPT model mapping changed; inspect the existing config before running.' }
if (-not $env:MODEL_BASE_URL -or -not $env:MODEL_API_KEY) { throw 'Set your existing MODEL_BASE_URL and MODEL_API_KEY in this terminal first. Do not share the key.' }
if ($Cases.Count -gt 2 -or @($Cases | Select-Object -Unique).Count -ne $Cases.Count) { throw 'Select each case at most once.' }
foreach ($case in $Cases) { if ($case -notin @(0,1)) { throw 'Cases must be 0 and/or 1.' } }
$out = Join-Path $project ('runs\gpt-allocation-v1-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $out -ErrorAction Stop | Out-Null
$oldPath = $env:PYTHONPATH
$oldEncoding = $env:PYTHONIOENCODING
$oldBytecode = $env:PYTHONDONTWRITEBYTECODE
$env:PYTHONPATH = Join-Path $batch 'code'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
try {
    foreach ($case in $Cases) {
        $destination = Join-Path $out "case-$case"
        New-Item -ItemType Directory -Path $destination -ErrorAction Stop | Out-Null
        Push-Location $destination
        try {
            $candidate = Join-Path $batch "candidates\case-$case\candidate.json"
            $raw = & python -m tooluse_pilot.cli run-candidate $candidate --config $config --model gpt --db (Join-Path $destination 'usage.sqlite') --max-requests 25 --max-tools 80 2> (Join-Path $destination 'stderr.log')
            $exitCode = $LASTEXITCODE
            $text = $raw -join "`n"
            $text | Set-Content -LiteralPath (Join-Path $destination 'result.json') -Encoding UTF8
            if ($exitCode -ne 0) { throw "Runner failed; preserve $destination" }
            $result = $text | ConvertFrom-Json
            $artifact = [IO.Path]::GetFullPath((Join-Path $destination $result.artifact_dir))
            $artifact | Set-Content (Join-Path $destination 'artifact-path.txt') -Encoding UTF8
            $result | Select-Object model,state,requests,tool_calls,invalid_tool_actions
            $result.score | ConvertTo-Json -Depth 10
            Write-Host "Artifact: $artifact"
            if ($result.state -eq 'api_error') { throw 'Transport/API error: stop batch; do not count as model failure.' }
        } finally { Pop-Location }
    }
} finally {
    $env:PYTHONPATH = $oldPath
    $env:PYTHONIOENCODING = $oldEncoding
    $env:PYTHONDONTWRITEBYTECODE = $oldBytecode
    Write-Host "Results: $out"
}
