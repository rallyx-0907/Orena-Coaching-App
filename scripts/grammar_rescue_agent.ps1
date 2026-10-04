param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(en|zh)\.canon\.[a-z0-9]+\.[0-9]{3}$')]
    [string]$PointId,

    [ValidateRange(1, 12)]
    [int]$MaxCycles = 6,

    [ValidateRange(1, 60)]
    [int]$MaxTurns = 24,

    [string]$Model = "",

    [switch]$AllowInitialPaidCandidate,

    [ValidateRange(0.001, 1.0)]
    [double]$CostCeilingUsd = 0.02
)

$ErrorActionPreference = "Stop"

function Invoke-OneShotGeneration {
    param(
        [string]$Id,
        [double]$Ceiling
    )

    $lang = if ($Id.StartsWith("zh.")) { "zh" } else { "en" }
    $args = @(
        "-m", "grammar_lab.pipeline.cli", "generate-corpus",
        "--lang", $lang,
        "--provider", "deepseek",
        "--model", "deepseek-flash",
        "--workers", "1",
        "--point-ids", $Id,
        "--one-shot",
        "--cost-ceiling-usd", "$Ceiling"
    )

    $lines = & python @args 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($lines | Out-String)
    Write-Host $text

    return [pscustomobject]@{
        ExitCode = $exitCode
        Text = $text
    }
}


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

    return [pscustomobject]@{
        ExitCode = $exitCode
        Text = $text
    }
}

function Invoke-TargetedTests {
    $lines = & python -m pytest grammar_lab/tests/test_generate.py grammar_lab/tests/test_llm_client.py -q 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($lines | Out-String)
    Write-Host $text
    return [pscustomobject]@{
        ExitCode = $exitCode
        Text = $text
    }
}

function Invoke-GrammarAgent {
    param(
        [string]$Id,
        [string]$Failure,
        [int]$Turns,
        [string]$RequestedModel
    )

    $prompt = @"
You are the Orena Grammar Rescue Agent working in the current repository.

TARGET POINT
$Id

CURRENT CACHE-ONLY REPLAY FAILURE
$Failure

NON-NEGOTIABLE SAFETY / COST CONTRACT
1. NEVER call DeepSeek, Gemini, Anthropic API, OpenAI API, or any external model/provider from repository code or shell.
2. NEVER run generate-corpus yourself, with or without --cache-only. The outer rescue wrapper owns replay.
3. NEVER delete, invalidate, rewrite, rename, or fabricate LLM cache files.
4. NEVER regenerate an already-paid grammar candidate.
5. NEVER weaken, skip, suppress, special-case around, or delete validator checks merely to make the point pass.
6. NEVER hand-edit the target generated corpus JSON to silence validation.
7. Prefer deterministic normalization/assembly fixes that are generally correct for the failure family.
8. Preserve semantic content. A deterministic fixer must be fail-closed when the transformation is ambiguous.
9. Add regression tests for every new deterministic behavior.
10. Work only under grammar_lab/**. Do not touch application/runtime product code.
11. Do not commit, push, rebase, reset, checkout, stash, or alter git history.
12. Do not install packages or change dependencies.

YOUR JOB
- Reproduce/understand the validator failure from code and local cached candidate evidence.
- Identify the root cause, not just the visible symptom.
- Inspect the relevant cached candidate locally when useful.
- Implement the smallest general deterministic fix in grammar_lab/**.
- Add focused regression tests proving both the successful case and a fail-closed/ambiguous case where appropriate.
- Run only pytest commands needed to validate your change.
- Inspect git diff before finishing.
- If a safe deterministic fix cannot be proven, DO NOT guess. Leave code unchanged (or revert only your own unsafe edit) and report BLOCKED with the exact reason and evidence needed.

IMPORTANT PIPELINE CONTRACT
The outer PowerShell wrapper will replay the same paid candidate with:
  python -m grammar_lab.pipeline.cli generate-corpus ... --one-shot --cache-only
after you exit. Your goal is to make that cached candidate pass truthfully, not to obtain another candidate.

FINISH RESPONSE
Return a concise result beginning with exactly one of:
RESCUE_PATCHED
RESCUE_NO_CHANGE
RESCUE_BLOCKED
Then summarize root cause, files changed, tests run, and any residual risk.
"@

    $allowed = @(
        "Read",
        "Edit",
        "Write",
        "Glob",
        "Grep",
        "Bash(python -m pytest:*)",
        "Bash(git diff:*)",
        "Bash(git status:*)"
    )

    $claudeArgs = @(
        "-p", $prompt,
        "--max-turns", "$Turns",
        "--output-format", "text",
        "--allowedTools"
    ) + $allowed

    if ($RequestedModel) {
        $claudeArgs += @("--model", $RequestedModel)
    }

    & claude @claudeArgs
    return $LASTEXITCODE
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python is not available in PATH."
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    throw "claude is not available in PATH."
}

Write-Host "Grammar rescue agent: $PointId"
Write-Host "Maximum cycles: $MaxCycles"
Write-Host "Claude provider access: BLOCKED (Claude cannot run generate-corpus)."
if ($AllowInitialPaidCandidate) {
    Write-Host "Initial DeepSeek candidate: ALLOWED ONCE by wrapper; one-shot; soft ceiling USD $CostCeilingUsd."
} else {
    Write-Host "Initial DeepSeek candidate: BLOCKED. Cache-only rescue only."
}

function Get-ChangedPaths {
    $paths = @()
    $lines = git status --porcelain=v1
    foreach ($line in $lines) {
        if ($line.Length -lt 4) { continue }
        $path = $line.Substring(3).Trim()
        if ($path -match " -> ") {
            $path = ($path -split " -> ")[-1]
        }
        $paths += $path.Replace("\\", "/")
    }
    return @($paths | Sort-Object -Unique)
}

$baselinePaths = @(Get-ChangedPaths)
$baselineOutsideDiff = (
    (git diff --no-ext-diff --binary -- . ":(exclude)grammar_lab/**" | Out-String) +
    (git diff --cached --no-ext-diff --binary -- . ":(exclude)grammar_lab/**" | Out-String)
)

for ($cycle = 1; $cycle -le $MaxCycles; $cycle++) {
    Write-Host ""
    Write-Host "=== Rescue cycle $cycle/$MaxCycles : cache-only replay ==="

    $replay = Invoke-CacheReplay -Id $PointId

    if ($replay.Text -match "(?m)^written\s+$([regex]::Escape($PointId))\s+cached\s*$") {
        Write-Host "RESCUE COMPLETE: $PointId was written from cache with zero provider spend."
        exit 0
    }

    if ($replay.Text -match "cache-only mode: no cached completion") {
        if (-not $AllowInitialPaidCandidate) {
            Write-Error (
                "No paid cached candidate exists for $PointId. " +
                "Re-run with -AllowInitialPaidCandidate to authorize exactly one one-shot candidate."
            )
            exit 20
        }

        Write-Host ""
        Write-Host "=== Rescue cycle $cycle/$MaxCycles : authorized one-shot paid candidate ==="
        $paid = Invoke-OneShotGeneration -Id $PointId -Ceiling $CostCeilingUsd
        $AllowInitialPaidCandidate = $false

        if ($paid.Text -match "(?m)^written\s+$([regex]::Escape($PointId))") {
            Write-Host "RESCUE COMPLETE: $PointId was written by the single authorized candidate."
            exit 0
        }

        if ($paid.Text -notmatch "(?m)^error\s+$([regex]::Escape($PointId))") {
            Write-Error "Authorized one-shot generation returned an unrecognized result. Stopping fail-closed."
            exit 22
        }

        $replay = $paid
    }

    if ($replay.Text -notmatch "(?m)^error\s+$([regex]::Escape($PointId))") {
        Write-Error "Replay did not return a recognized point error. Stopping fail-closed."
        exit 21
    }

    Write-Host ""
    Write-Host "=== Rescue cycle $cycle/$MaxCycles : Claude code repair ==="
    $agentExit = Invoke-GrammarAgent -Id $PointId -Failure $replay.Text -Turns $MaxTurns -RequestedModel $Model
    if ($agentExit -ne 0) {
        Write-Error "Claude Code exited with code $agentExit."
        exit 30
    }

    $afterPaths = @(Get-ChangedPaths)
    $newPaths = @($afterPaths | Where-Object { $_ -notin $baselinePaths })
    $outOfScope = @($newPaths | Where-Object { $_ -notlike "grammar_lab/*" })
    $afterOutsideDiff = (
        (git diff --no-ext-diff --binary -- . ":(exclude)grammar_lab/**" | Out-String) +
        (git diff --cached --no-ext-diff --binary -- . ":(exclude)grammar_lab/**" | Out-String)
    )
    if ($outOfScope.Count -gt 0 -or $afterOutsideDiff -ne $baselineOutsideDiff) {
        Write-Error (
            "Claude changed content outside grammar_lab/**; stopping before replay. " +
            "Review git diff manually."
        )
        exit 32
    }

    Write-Host ""
    Write-Host "=== Rescue cycle $cycle/$MaxCycles : targeted regression suite ==="
    $tests = Invoke-TargetedTests
    if ($tests.ExitCode -ne 0) {
        Write-Error "Targeted tests failed. Stopping before replay."
        exit 31
    }
}

Write-Error "Rescue stopped after $MaxCycles cycles without a truthful cached write. No provider generation was attempted."
exit 40
