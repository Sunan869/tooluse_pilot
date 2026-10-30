param([int[]]$Cases = @(2))
$ErrorActionPreference = 'Stop'
$batch = $PSScriptRoot
$project = Split-Path (Split-Path $batch -Parent) -Parent
$config = Join-Path $project 'gateway.models.json'
$cfg = Get-Content -LiteralPath $config -Raw -Encoding UTF8 | ConvertFrom-Json
if ($cfg.models.gpt.model -ne 'gpt-6-astra') { throw 'GPT model mapping changed; inspect the existing config before running.' }
if (-not $env:MODEL_BASE_URL -or -not $env:MODEL_API_KEY) { throw 'Set your existing MODEL_BASE_URL and MODEL_API_KEY in this terminal first. Do not share the key.' }
if ($Cases.Count -gt 1 -or @($Cases | Select-Object -Unique).Count -ne $Cases.Count) { throw 'Select each case at most once.' }
foreach ($case in $Cases) { if ($case -notin @(2)) { throw 'Only case 2 is available.' } }
$out = Join-Path $project ('runs\gpt-allocation-diamond-v2-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
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
            $resultPath = Join-Path $destination 'result.json'
            & python (Join-Path $batch 'run_to_file.py') --candidate $candidate --config $config --model gpt --out $resultPath --db (Join-Path $destination 'usage.sqlite') --max-requests 25 --max-tools 80 1> (Join-Path $destination 'stdout.log') 2> (Join-Path $destination 'stderr.log')
            $exitCode = $LASTEXITCODE
            if ($exitCode -ne 0) { throw "Runner failed; preserve $destination. Do not retry before inspecting existing artifacts." }
            $text = [IO.File]::ReadAllText($resultPath, [Text.Encoding]::UTF8)
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
