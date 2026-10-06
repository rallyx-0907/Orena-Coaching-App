from pathlib import Path
from textwrap import dedent


generate_path = Path("grammar_lab/pipeline/generate.py")
text = generate_path.read_text(encoding="utf-8")

anchor = "def normalize_generated_formula_order(data: dict[str, Any], zh: bool) -> dict[str, Any]:\n"
assert anchor in text
helper = dedent(r'''
def normalize_generated_optional_suffix_bindings(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Shorten a proven optional suffix when the next slot realizes that suffix.

    Chinese slots such as ``没(有)`` can surface as either ``没`` or ``没有``.
    When a provider binds the long form ``没有`` to that slot and also binds
    the following verb slot to the overlapping suffix ``有``, assembly cannot
    produce non-overlapping spans. Recover only when the formula itself proves
    the short/long alternation (closed options or one parenthesized suffix),
    and the rewritten bindings have a deterministic ordered surface placement.
    Otherwise leave the candidate unchanged.
    """
    out = copy.deepcopy(data)
    if not zh:
        return out

    form_keys = {"affirmative": "formula", "negative": "negative", "question": "question"}

    def proven_short_form(slot: dict[str, Any], long_surface: str, suffix: str) -> str | None:
        if not suffix or not long_surface.endswith(suffix) or len(long_surface) <= len(suffix):
            return None
        short = long_surface[:-len(suffix)]
        options = {
            target_text(str(option.get("text", "")), True)
            for option in slot.get("options") or []
            if isinstance(option, dict)
        }
        if short in options and long_surface in options:
            return short

        hint = target_text(str(slot.get("text", "")), True)
        match = re.fullmatch(r"(.+?)[(（]([^()（）]+)[)）]", hint)
        if match and match.group(1) == short and match.group(2) == suffix:
            return short
        return None

    for example in out.get("examples", []):
        key = form_keys.get(example.get("form"))
        formula = out.get(key) if key else None
        if not formula:
            continue

        bindings = example.get("bindings") or []
        indexed: dict[int, dict[str, Any]] = {}
        valid = True
        for binding in bindings:
            slot_index = binding.get("slot_index")
            if (
                type(slot_index) is not int
                or not 0 <= slot_index < len(formula)
                or slot_index in indexed
            ):
                valid = False
                break
            indexed[slot_index] = binding
        if not valid:
            continue

        sentence = target_text(str(example.get("text", "")), True)
        for left_index in sorted(indexed):
            right_index = left_index + 1
            if right_index not in indexed:
                continue

            left_binding = indexed[left_index]
            right_binding = indexed[right_index]
            long_surface = target_text(str(left_binding.get("text", "")), True)
            suffix = target_text(str(right_binding.get("text", "")), True)
            short = proven_short_form(formula[left_index], long_surface, suffix)
            if not short or sentence.count(long_surface) != 1:
                continue

            long_start = sentence.find(long_surface)
            suffix_start = long_start + len(short)
            if sentence[suffix_start:suffix_start + len(suffix)] != suffix:
                continue

            proposed = copy.deepcopy(bindings)
            for binding in proposed:
                if binding.get("slot_index") == left_index:
                    binding["text"] = short
                    break

            located = _locate_generated_bindings(sentence, proposed, True)
            if located is None:
                continue
            ordered = [located[index] for index in sorted(located)]
            if any(ordered[i][1] > ordered[i + 1][0] for i in range(len(ordered) - 1)):
                continue
            if (
                located[left_index][0] != long_start
                or located[left_index][1] != suffix_start
                or located[right_index][0] != suffix_start
            ):
                continue

            left_binding["text"] = short

    return out


''').lstrip()
text = text.replace(anchor, helper + anchor, 1)

old = '''def normalize_generated_structure(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Return the exact structural candidate that full assembly validates."""
    out = normalize_generated_common_prefix_options(data, zh)
'''
new = '''def normalize_generated_structure(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Return the exact structural candidate that full assembly validates."""
    out = normalize_generated_optional_suffix_bindings(data, zh)
    out = normalize_generated_common_prefix_options(out, zh)
'''
assert old in text
text = text.replace(old, new, 1)
generate_path.write_text(text, encoding="utf-8")


rescue_path = Path("scripts/grammar_rescue_agent.ps1")
rescue = rescue_path.read_text(encoding="utf-8")

old = '''function Invoke-CodexRepair {
    param(
        [string]$Id,
        [string]$Failure,
        [string]$RequestedModel,
        [string]$PythonExecutable
    )
'''
new = '''function Invoke-CodexRepair {
    param([string]$Id, [string]$Failure, [string]$RequestedModel)
'''
assert old in rescue
rescue = rescue.replace(old, new, 1)

old = '''- Run focused pytest only. Inspect git diff before finishing.
- Use the exact interpreter in `$env:ORENA_PYTHON` for focused tests, for example: `& $env:ORENA_PYTHON -m pytest ...`.
- Do not use `.venv`, `py`, or a bare `python` command inside Codex.
'''
new = '''- Do not run Python or pytest inside Codex; this sandbox may not execute host interpreters.
- The outer wrapper runs the targeted pytest suite after RESCUE_PATCHED.
- Inspect git diff before finishing.
'''
assert old in rescue
rescue = rescue.replace(old, new, 1)

old = '''    Push-Location "grammar_lab"
    $previousErrorActionPreference = $ErrorActionPreference
    $hadOrenaPython = Test-Path Env:ORENA_PYTHON
    $previousOrenaPython = $env:ORENA_PYTHON
    try {
        $env:ORENA_PYTHON = $PythonExecutable
'''
new = '''    Push-Location "grammar_lab"
    $previousErrorActionPreference = $ErrorActionPreference
    try {
'''
assert old in rescue
rescue = rescue.replace(old, new, 1)

old = '''    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        if ($hadOrenaPython) {
            $env:ORENA_PYTHON = $previousOrenaPython
        } else {
            Remove-Item Env:ORENA_PYTHON -ErrorAction SilentlyContinue
        }
        Pop-Location
    }
'''
new = '''    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Pop-Location
    }
'''
assert old in rescue
rescue = rescue.replace(old, new, 1)

old = '''$pythonExecutableLines = & python -c "import sys; print(sys.executable)" 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Could not resolve the Python interpreter executable."
}
$pythonExecutable = (($pythonExecutableLines | Select-Object -First 1).ToString()).Trim()
if (-not $pythonExecutable -or -not (Test-Path -LiteralPath $pythonExecutable)) {
    throw "Resolved Python interpreter does not exist: $pythonExecutable"
}

'''
assert old in rescue
rescue = rescue.replace(old, "", 1)

old = '''    $agent = Invoke-CodexRepair -Id $PointId -Failure $replay.Text -RequestedModel $CodexModel -PythonExecutable $pythonExecutable
'''
new = '''    $agent = Invoke-CodexRepair -Id $PointId -Failure $replay.Text -RequestedModel $CodexModel
'''
assert old in rescue
rescue = rescue.replace(old, new, 1)
rescue_path.write_text(rescue, encoding="utf-8")
