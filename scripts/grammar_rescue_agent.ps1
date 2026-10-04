param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(en|zh)\.canon\.[a-z0-9]+\.[0-9]{3}$')]
    [string]$PointId,

    [ValidateRange(1, 12)]
    [int]$MaxCycles = 6,

    [string]$CodexModel = "",

    [switch]$AllowInitialPaidCandidate,

    [ValidateRange(0.001, 1.0)]
    [double]$CostCeilingUsd = 0.02
)

$ErrorActionPreference = "Stop"
$InvariantCulture = [System.Globalization.CultureInfo]::InvariantCulture

function Invoke-CacheReplay {
    param([string]$Id)

    $lang = if ($Id.StartsWith("zh.")) { "zh" } else { "en" }
    $args = @(
        "-m", "grammar_lab.pipeline.cli", "generate-corpus",
        "--lang", $lang,
        "--provider", "deepseek",
        "--model", "deepseek-flash",
        "--workers", "1",
        "--point-ids", $Id,
        "--one-shot",
        "--cache-only"
    )

    $lines = & python @args 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($lines | Out-String)
    Write-Host $text

    return [pscustomobject]@{ ExitCode = $exitCode; Text = $text }
}

function Invoke-OneShotGeneration {
    param([string]$Id, [double]$Ceiling)

    $lang = if ($Id.StartsWith("zh.")) { "zh" } else { "en" }
    $args = @(
        "-m", "grammar_lab.pipeline.cli", "generate-corpus",
        "--lang", $lang,
        "--provider", "deepseek",
        "--model", "deepseek-flash",
        "--workers", "1",
        "--point-ids", $Id,
        "--one-shot",
        "--cost-ceiling-usd", $Ceiling.ToString("0.####", $InvariantCulture)
    )

    $lines = & python @args 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($lines | Out-String)
    Write-Host $text

    return [pscustomobject]@{ ExitCode = $exitCode; Text = $text }
}

function Invoke-TargetedTests {
    $lines = & python -m pytest grammar_lab/tests/test_generate.py grammar_lab/tests/test_llm_client.py -q 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($lines | Out-String)
    Write-Host $text
    return [pscustomobject]@{ ExitCode = $exitCode; Text = $text }
}

function Get-ChangedPaths {
    $paths = @()
    $lines = git status --porcelain=v1
    foreach ($line in $lines) {
        if ($line.Length -lt 4) { continue }
        $path = $line.Substring(3).Trim()
        if ($path -match " -> ") { $path = ($path -split " -> ")[-1] }
        $paths += $path.Replace("\\", "/")
    }
    return @($paths | Sort-Object -Unique)
}

function Get-OutsideGrammarDiff {
    return (
        (git diff --no-ext-diff --binary -- . ":(exclude)grammar_lab/**" | Out-String) +
        (git diff --cached --no-ext-diff --binary -- . ":(exclude)grammar_lab/**" | Out-String)
    )
}

function Invoke-CodexRepair {
    param([string]$Id, [string]$Failure, [string]$RequestedModel)

    $prompt = @"
You are the Orena Grammar Rescue coding agent working in the current repository.

TARGET POINT
$Id

CURRENT CACHE-ONLY REPLAY FAILURE
$Failure

GOAL
Make the already-paid cached candidate validate truthfully. Do not obtain a new candidate.

NON-NEGOTIABLE CONTRACT
- Your Codex project root is already grammar_lab/. Work only inside this workspace.
- Do not run generate-corpus. The outer wrapper owns replay.
- Do not call DeepSeek, Gemini, Anthropic, OpenAI API, curl, wget, Invoke-WebRequest, or any network command.
- Do not delete, invalidate, rewrite, rename, fabricate, or hand-edit LLM cache files.
- Do not hand-edit the generated target corpus JSON merely to silence validation.
- Do not weaken, skip, suppress, delete, or point-special-case validator checks.
- Do not regenerate existing grammar content.
- Do not commit, push, pull, rebase, reset, checkout, stash, or alter git history.
- Do not install packages or change dependencies.
- Prefer the smallest general deterministic normalization/assembly fix.
- A fixer must remain fail-closed when transformation is ambiguous.
- Preserve semantic content.
- Add focused regression tests for the repaired failure family, including an ambiguous/fail-closed case where appropriate.
- Run focused pytest only. Inspect git diff before finishing.
- If a safe deterministic fix cannot be proven, do not guess; report BLOCKED with exact evidence needed.

IMPORTANT
The outer wrapper will run the same paid candidate afterward with --one-shot --cache-only.
Success means that cached candidate becomes written through normal assembly + validators.

Finish with exactly one of:
RESCUE_PATCHED
RESCUE_NO_CHANGE
RESCUE_BLOCKED
Then summarize root cause, files changed, tests run, and residual risk.
"@

    $args = @(
        "-c", 'approval_policy="never"',
        "-c", 'sandbox_mode="workspace-write"',
        "-c", "sandbox_workspace_write.network_access=false",
        "exec"
    )
    if ($RequestedModel) {
        $args += @("--model", $RequestedModel)
    }
    $args += @($prompt)

    Push-Location "grammar_lab"
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5.1 wraps native stderr as NativeCommandError.
        # Codex writes informational banners/progress to stderr, so do not let
        # ErrorActionPreference=Stop turn normal native output into an exception.
        $ErrorActionPreference = "Continue"
        $output = & codex @args 2>&1
        $exitCode = [int]$LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Pop-Location
    }

    $output | ForEach-Object { Write-Host $_ }
    return [int]$exitCode
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python is not available in PATH."
}
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "codex is not available in PATH."
}

$baselinePaths = @(Get-ChangedPaths)
$baselineOutsideDiff = Get-OutsideGrammarDiff

Write-Host "Grammar rescue agent (Codex): $PointId"
Write-Host "Maximum rescue cycles: $MaxCycles"
Write-Host "Codex mode: approval_policy=never, sandbox_mode=workspace-write, project root=grammar_lab"
if ($AllowInitialPaidCandidate) {
    Write-Host "Initial DeepSeek candidate: authorized once; one-shot; soft ceiling USD $CostCeilingUsd"
} else {
    Write-Host "Initial DeepSeek candidate: blocked; cache-only rescue"
}

for ($cycle = 1; $cycle -le $MaxCycles; $cycle++) {
    Write-Host ""
    Write-Host "=== Rescue cycle $cycle/$MaxCycles : cache-only replay ==="
    $replay = Invoke-CacheReplay -Id $PointId

    if ($replay.Text -match "(?m)^written\s+$([regex]::Escape($PointId))\s+cached\s*$") {
        Write-Host "RESCUE COMPLETE: $PointId written from cache with zero provider spend."
        exit 0
    }

    if ($replay.Text -match "cache-only mode: no cached completion") {
        if (-not $AllowInitialPaidCandidate) {
            Write-Error "No paid cached candidate exists. Re-run with -AllowInitialPaidCandidate to authorize exactly one one-shot candidate."
            exit 20
        }

        Write-Host ""
        Write-Host "=== Authorized one-shot paid candidate ==="
        $paid = Invoke-OneShotGeneration -Id $PointId -Ceiling $CostCeilingUsd
        $AllowInitialPaidCandidate = $false

        if ($paid.Text -match "(?m)^written\s+$([regex]::Escape($PointId))") {
            Write-Host "RESCUE COMPLETE: $PointId written by the single authorized candidate."
            exit 0
        }
        if ($paid.Text -notmatch "(?m)^error\s+$([regex]::Escape($PointId))") {
            Write-Error "Authorized one-shot generation returned an unrecognized result."
            exit 22
        }
        $replay = $paid
    }

    if ($replay.Text -notmatch "(?m)^error\s+$([regex]::Escape($PointId))") {
        Write-Error "Replay did not return a recognized point error."
        exit 21
    }

    Write-Host ""
    Write-Host "=== Rescue cycle $cycle/$MaxCycles : Codex root-cause repair ==="
    $agentExit = Invoke-CodexRepair -Id $PointId -Failure $replay.Text -RequestedModel $CodexModel
    if ($agentExit -ne 0) {
        Write-Error "Codex exited with code $agentExit."
        exit 30
    }

    $afterPaths = @(Get-ChangedPaths)
    $newPaths = @($afterPaths | Where-Object { $_ -notin $baselinePaths })
    $outOfScope = @($newPaths | Where-Object { $_ -notlike "grammar_lab/*" })
    $afterOutsideDiff = Get-OutsideGrammarDiff
    if ($outOfScope.Count -gt 0 -or $afterOutsideDiff -ne $baselineOutsideDiff) {
        Write-Error "Codex changed content outside grammar_lab/**. Stopping before replay; inspect git diff."
        exit 32
    }

    Write-Host ""
    Write-Host "=== Targeted regression suite ==="
    $tests = Invoke-TargetedTests
    if ($tests.ExitCode -ne 0) {
        Write-Error "Targeted tests failed. Stopping before replay."
        exit 31
    }
}

Write-Error "Rescue stopped after $MaxCycles cycles without a truthful cached write. No additional provider candidate was generated."
exit 40
