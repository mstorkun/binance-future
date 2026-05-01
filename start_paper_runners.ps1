$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$shouldStartDefault = $true
$shouldStartShadow2h = $true

foreach ($lock in @("paper_runner.lock", "paper_shadow_2h_runner.lock")) {
    $path = Join-Path $repo $lock
    if (Test-Path -LiteralPath $path) {
        try {
            $raw = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
            $pid = [int]$raw.pid
            $running = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if (-not $running) {
                Remove-Item -LiteralPath $path -Force
            } else {
                if ($lock -eq "paper_runner.lock") {
                    $shouldStartDefault = $false
                }
                if ($lock -eq "paper_shadow_2h_runner.lock") {
                    $shouldStartShadow2h = $false
                }
            }
        } catch {
            # The runner may be rewriting the lock file right now. Avoid deleting a
            # locked file; the runner's own lock guard will prevent duplicates.
            if (-not (Get-Process python -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

if ($shouldStartDefault) {
    Start-Process -FilePath python `
        -ArgumentList @("paper_runner.py", "--loop", "--interval-minutes", "60") `
        -WorkingDirectory $repo `
        -RedirectStandardOutput (Join-Path $repo "paper_runner_stdout.log") `
        -RedirectStandardError (Join-Path $repo "paper_runner_stderr.log") `
        -WindowStyle Hidden
}

if ($shouldStartShadow2h) {
    Start-Process -FilePath python `
        -ArgumentList @("paper_runner.py", "--loop", "--interval-minutes", "60", "--tag", "shadow_2h", "--timeframe", "2h", "--scale-lookbacks") `
        -WorkingDirectory $repo `
        -RedirectStandardOutput (Join-Path $repo "paper_shadow_2h_stdout.log") `
        -RedirectStandardError (Join-Path $repo "paper_shadow_2h_stderr.log") `
        -WindowStyle Hidden
}
