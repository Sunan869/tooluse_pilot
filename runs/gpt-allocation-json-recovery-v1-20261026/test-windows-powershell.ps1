$ErrorActionPreference = 'Stop'
$project = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$source = Join-Path $project 'runs\gpt-allocation-v1-20261026-170534-5aa7539d\case-0'
$nativePath = Join-Path $source 'runs\file_workspaces\07530c32-37c9-4f5f-9424-709f9eb6a6c8\run_result.json'
$native = [IO.File]::ReadAllText($nativePath,[Text.Encoding]::UTF8)
$bad = [IO.File]::ReadAllText((Join-Path $source 'result.json'),[Text.Encoding]::UTF8)
$predicted = [Text.Encoding]::GetEncoding(936).GetString([Text.Encoding]::UTF8.GetBytes($native))
if ($predicted.Trim().Replace("`r`n","`n") -cne $bad.Trim().Replace("`r`n","`n")) { throw 'Corruption reproduction mismatch' }
$rejected = $false
try { $bad | ConvertFrom-Json | Out-Null } catch { $rejected = $true }
if (-not $rejected) { throw 'Expected historical malformed JSON rejection' }
$encodingBefore = [Console]::OutputEncoding.CodePage
$fixed = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'utf8-writer-regression.json'),[Text.Encoding]::UTF8) | ConvertFrom-Json
$original = $native | ConvertFrom-Json
if ($fixed.usage_db -cne $original.usage_db -or $fixed.state -ne 'finished' -or -not $fixed.score.success -or $fixed.requests -ne 10) { throw 'UTF8 file round-trip mismatch' }
if ($encodingBefore -ne [Console]::OutputEncoding.CodePage) { throw 'Global encoding changed' }
$tokens=$null; $errors=$null
$script = Join-Path $project 'runs\allocation-batch-v1-20261026\run-gpt-batch.ps1'
[System.Management.Automation.Language.Parser]::ParseFile($script,[ref]$tokens,[ref]$errors) | Out-Null
if ($errors.Count -gt 0) { throw ($errors | Out-String) }
$result = 'PASS: exact CP936 corruption reproduced; old JSON rejected; Python UTF8 output parsed with intact path; script syntax valid; console encoding unchanged; zero API calls. PS=' + $PSVersionTable.PSVersion.ToString()
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'WINDOWS-PS-TEST.txt'),$result,[Text.Encoding]::UTF8)
Write-Output $result
