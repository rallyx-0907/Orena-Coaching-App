param(
    [ValidateSet("all", "en", "zh")]
    [string]$Lang = "all",

    [switch]$AllowPaidCandidates,

    [ValidateRange(0.01, 1000.0)]
    [double]$BudgetUsd = 2.00,

    [ValidateRange(0.001, 1.0)]
    [double]$PerPointCostCeilingUsd = 0.02,

    [ValidateRange(0, 10000)]
    [int]$MaxPoints = 0,

    [ValidateRange(1, 12)]
    [int]$MaxRescueCycles = 6,

    [string]$CodexModel = ""
)

$ErrorActionPreference = "Stop"
$InvariantCulture = [System.Globalization.CultureInfo]::InvariantCulture
$PointIdPattern = '(?:en|zh)\.[a-z0-9_-]+(?:\.[a-z0-9_-]+)*'

function Invoke-Corpus {
    param(
        [string]$Language,
        [string]$PointId = "",
        [switch]$CacheOnly,
        [double]$Ceiling = 0.02
    )

    $args = @(
        "-m", "grammar_lab.pipeline.cli", "generate-corpus",
        "--lang", $Language,
        "--provider", "deepseek",
        "--model", "deepseek-flash",
        "--workers", "1",
        "--max-points", "1",
        "--one-shot"
    )

    if ($PointId) {
        $args += @("--point-ids", $PointId)
    }
    if ($CacheOnly) {
        $args += "--cache-only"
    } else {
        $args += @("--cost-ceiling-usd", $Ceiling.ToString("0.####", $InvariantCulture))
    }

    $lines = & python @args 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($lines | Out-String)
    Write-Host $text
    return [pscustomobject]@{ ExitCode = $exitCode; Text = $text }
}

function Get-OutcomePointId {
    param([string]$Text)

    $m = [regex]::Match($Text, "(?m)^(?:written|error|blocked_metadata)\s+($PointIdPattern)\s+")
    if ($m.Success) { return $m.Groups[1].Value }
    return ""
}

function Get-Spend {
    param([string]$Text)

    $matches = [regex]::Matches($Text, "USD\s+([0-9]+(?:\.[0-9]+)?)\s+spent")
    if ($matches.Count -eq 0) { return 0.0 }
    return [double]::Parse($matches[$matches.Count - 1].Groups[1].Value, $InvariantCulture)
}

function Test-NoCandidates {
    param([string]$Text)
    return $Text -match "generate-corpus:\s+0\s+ready point\(s\) selected"
}

function Test-Written {
    param([string]$Text, [string]$PointId = "")
    if ($PointId) {
        return $Text -match "(?m)^written\s+$([regex]::Escape($PointId))\s+"
    }
    return $Text -match "(?m)^written\s+$PointIdPattern\s+"
}

function Get-ReadyPointIds {
    param([string]$Language)

    $json = & python -m grammar_lab.pipeline.cli corpus-plan --lang $Language --json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "corpus-plan --json failed for $Language."
    }

    $plan = ($json | Out-String) | ConvertFrom-Json
    $report = $plan.languages.PSObject.Properties[$Language].Value
    return @(
        $report.items |
            Where-Object { $_.status -eq "ready" } |
            ForEach-Object { [string]$_.id }
    )
}

function Invoke-Rescue {
    param([string]$PointId)

    $args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\grammar_rescue_agent.ps1",
        "-PointId", $PointId,
        "-MaxCycles", "$MaxRescueCycles"
    )
    if ($CodexModel) {
        $args += @("-CodexModel", $CodexModel)
    }

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # The rescue child may forward native stderr from Codex. On Windows
        # PowerShell 5.1 that is represented as NativeCommandError even when
        # Codex exits successfully, so rely on LASTEXITCODE instead.
        $ErrorActionPreference = "Continue"
        $output = & powershell @args 2>&1
        $exitCode = [int]$LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    $output | ForEach-Object { Write-Host $_ }
    return [int]$exitCode
}

function Assert-CorpusComplete {
    param([string[]]$Languages)

    $scope = if ($Languages.Count -eq 2) { "all" } else { $Languages[0] }
    $json = & python -m grammar_lab.pipeline.cli corpus-plan --lang $scope --json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "corpus-plan --json failed."
    }

    $plan = ($json | Out-String) | ConvertFrom-Json
    $expected = if ($scope -eq "all") { 595 } elseif ($scope -eq "en") { 215 } else { 380 }

    $generated = [int]($plan.counts.generated)
    $ready = [int]($plan.counts.ready)
    $blocked = [int]($plan.counts.blocked_metadata)
    $unreviewed = [int]($plan.counts.generated_unreviewed_metadata)
    $canonical = [int]($plan.canonical_total)

    if (
        $canonical -ne $expected -or
        $generated -ne $expected -or
        $ready -ne 0 -or
        $blocked -ne 0 -or
        $unreviewed -ne 0
    ) {
        throw (
            "Corpus is not complete: canonical=$canonical generated=$generated ready=$ready " +
            "blocked_metadata=$blocked generated_unreviewed_metadata=$unreviewed expected=$expected"
        )
    }

    Write-Host "Corpus completeness assertion passed: $generated/$expected generated; no ready/blocked/unreviewed items."
}


function Invoke-FinalGates {
    param([string[]]$Languages)

    Assert-CorpusComplete -Languages $Languages

    Write-Host ""
    Write-Host "=== FINAL GRAMMAR GATES ==="

    & python -m pytest grammar_lab/tests
    if ($LASTEXITCODE -ne 0) { throw "Full grammar_lab pytest failed." }

    & python -m grammar_lab.pipeline.cli import-canonical --check
    if ($LASTEXITCODE -ne 0) { throw "import-canonical --check failed." }

    & python -m grammar_lab.pipeline.cli sync-metadata --check
    if ($LASTEXITCODE -ne 0) { throw "sync-metadata --check failed." }

    & python -m grammar_lab.pipeline.cli seed-audit --lang all
    if ($LASTEXITCODE -ne 0) { throw "seed-audit --lang all failed." }

    & python -m grammar_lab.pipeline.cli corpus-plan --lang all
    if ($LASTEXITCODE -ne 0) { throw "corpus-plan --lang all failed." }

    foreach ($language in $Languages) {
        & python -m grammar_lab.pipeline.cli validate --lang $language
        if ($LASTEXITCODE -ne 0) { throw "validate --lang $language failed." }
    }

    Write-Host "FINAL GATES GREEN."
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python is not available in PATH."
}
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "codex is not available in PATH."
}

$languages = if ($Lang -eq "all") { @("en", "zh") } else { @($Lang) }
$spent = 0.0
$processed = 0

Write-Host "Orena Grammar Completion Agent"
Write-Host "Languages: $($languages -join ', ')"
Write-Host "Codex: automatic root-cause repair"
Write-Host "Paid candidates allowed: $AllowPaidCandidates"
if ($AllowPaidCandidates) {
    Write-Host "Run budget: USD $BudgetUsd (one-shot candidate per uncached point)"
}
Write-Host "Max points this run: $(if ($MaxPoints -eq 0) { 'unlimited' } else { $MaxPoints })"

foreach ($language in $languages) {
    Write-Host ""
    Write-Host "=============================="
    Write-Host "Completing language: $language"
    Write-Host "=============================="

    while ($true) {
        if ($MaxPoints -gt 0 -and $processed -ge $MaxPoints) {
            Write-Host "MaxPoints reached. Safe to resume with the same command."
            Write-Host "Paid spend this run: USD $($spent.ToString('0.0000'))"
            exit 0
        }

        $readyPointIds = @(Get-ReadyPointIds -Language $language)
        if ($readyPointIds.Count -eq 0) {
            Write-Host "$language has no ready points remaining."
            break
        }

        Write-Host ""
        Write-Host "--- Free cache sweep: $($readyPointIds.Count) ready point(s) ---"
        $uncachedPointIds = [System.Collections.Generic.List[string]]::new()
        $rescuePointIds = [System.Collections.Generic.List[string]]::new()

        foreach ($readyPointId in $readyPointIds) {
            if ($MaxPoints -gt 0 -and $processed -ge $MaxPoints) {
                Write-Host "MaxPoints reached. Safe to resume with the same command."
                Write-Host "Paid spend this run: USD $($spent.ToString('0.0000'))"
                exit 0
            }

            $probe = Invoke-Corpus -Language $language -PointId $readyPointId -CacheOnly
            if (Test-Written -Text $probe.Text -PointId $readyPointId) {
                $processed++
                continue
            }

            $pointId = Get-OutcomePointId -Text $probe.Text
            if (-not $pointId) {
                throw "Could not determine the selected point from generate-corpus output."
            }
            if ($pointId -ne $readyPointId) {
                throw "Cache probe selected unexpected point $pointId while probing $readyPointId."
            }

            if ($probe.Text -match "cache-only mode: no cached completion") {
                $uncachedPointIds.Add($readyPointId)
            } else {
                $rescuePointIds.Add($readyPointId)
            }
        }

        Write-Host "Free cache sweep complete: $($uncachedPointIds.Count) uncached; $($rescuePointIds.Count) cached candidate(s) need rescue."

        foreach ($pointId in $rescuePointIds) {
            Write-Host ""
            Write-Host "--- Codex rescue from cached candidate: $pointId ---"
            $rescueExit = Invoke-Rescue -PointId $pointId
            if ($rescueExit -ne 0) {
                Write-Host "STOP: Codex rescue for $pointId exited with code $rescueExit."
                Write-Host "No additional paid candidate was requested."
                exit $rescueExit
            }
            $processed++
        }

        if ($uncachedPointIds.Count -eq 0) {
            continue
        }

        if (-not $AllowPaidCandidates) {
            Write-Host "STOP: Free cache sweep complete; $($uncachedPointIds.Count) ready point(s) have no cache and paid candidates are disabled."
            Write-Host "Resume with -AllowPaidCandidates -BudgetUsd <amount> only when you want to generate those uncached points."
            exit 20
        }

        foreach ($pointId in $uncachedPointIds) {
            if ($MaxPoints -gt 0 -and $processed -ge $MaxPoints) {
                Write-Host "MaxPoints reached. Safe to resume with the same command."
                Write-Host "Paid spend this run: USD $($spent.ToString('0.0000'))"
                exit 0
            }

            $remaining = $BudgetUsd - $spent
            if ($remaining -lt $PerPointCostCeilingUsd) {
                Write-Host "STOP: remaining run budget USD $($remaining.ToString('0.0000')) is below the per-point ceiling."
                Write-Host "Safe to resume later with a fresh budget."
                exit 21
            }

            Write-Host ""
            Write-Host "--- One authorized one-shot candidate: $pointId ---"
            $paid = Invoke-Corpus -Language $language -PointId $pointId -Ceiling $PerPointCostCeilingUsd
            $pointSpend = Get-Spend -Text $paid.Text
            $spent += $pointSpend
            Write-Host "Cumulative paid spend this run: USD $($spent.ToString('0.0000')) / $($BudgetUsd.ToString('0.00'))"

            if (Test-Written -Text $paid.Text -PointId $pointId) {
                $processed++
                continue
            }

            if ($paid.Text -notmatch "(?m)^error\s+$([regex]::Escape($pointId))\s+") {
                throw "One-shot candidate for $pointId returned an unrecognized result."
            }

            Write-Host ""
            Write-Host "--- Codex rescue: $pointId ---"
            $rescueExit = Invoke-Rescue -PointId $pointId
            if ($rescueExit -ne 0) {
                Write-Host "STOP: Codex rescue for $pointId exited with code $rescueExit."
                Write-Host "No additional paid candidate was requested."
                exit $rescueExit
            }
            $processed++
        }
    }
}

Invoke-FinalGates -Languages $languages

Write-Host ""
Write-Host "========================================"
Write-Host "GRAMMAR GENERATION COMPLETION TARGET MET"
Write-Host "Processed this run: $processed"
Write-Host "Paid spend this run: USD $($spent.ToString('0.0000'))"
Write-Host "All selected languages have ready=0 and final deterministic gates are green."
Write-Host "Human/content approval remains a separate review gate; this script does not falsify approval status."
Write-Host "========================================"
exit 0
