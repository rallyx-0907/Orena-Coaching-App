from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json

from writing_coach.core.language_registry import all_languages
from writing_coach.languages.grammar_registry import (
    all_grammar_providers,
    grammar_provider_codes,
)

enabled_grammar = {
    item.code
    for item in all_languages()
    if item.enabled and "grammar" in item.capabilities
}
providers = set(grammar_provider_codes())

if enabled_grammar != providers:
    raise SystemExit(
        "GRAMMAR_PROVIDER_COVERAGE_FAIL enabled="
        + repr(sorted(enabled_grammar))
        + " providers="
        + repr(sorted(providers))
    )

runtime = (ROOT / "writing_coach/languages/runtime.py").read_text(encoding="utf-8")
for forbidden in (
    "CHINESE_GRAMMAR_COURSE",
    "ENGLISH_GRAMMAR_COURSE",
    "CHINESE_GRAMMAR_KNOWLEDGE_BY_ID",
    "ENGLISH_GRAMMAR_KNOWLEDGE_BY_ID",
):
    if forbidden in runtime:
        raise SystemExit(f"GRAMMAR_RUNTIME_BINARY_BRANCH_FAIL {forbidden}")

print("M4_GRAMMAR_UNIVERSAL_ARCHITECTURE_AUDIT=PASS")
print("CURRENT_GRAMMAR_LANGUAGES=" + ",".join(sorted(providers)))

for provider in all_grammar_providers():
    knowledge_path = (
        ROOT
        / "writing_coach/languages"
        / provider.module_name
        / "grammar_knowledge.json"
    )
    knowledge = json.loads(knowledge_path.read_text(encoding="utf-8"))
    curated = sum(
        1 for item in knowledge
        if item.get("source", {}).get("content_status") == "curated"
    )
    lessons = sum(1 for item in provider.course if item.get("kind") == "lesson")
    print(
        f"{provider.code}: total={len(provider.course)} lessons={lessons} "
        f"curated={curated} pending={len(provider.course)-curated}"
    )

print("FUTURE_LANGUAGE_FRONTEND_CLONE_REQUIRED=NO")
print("VISUAL_QA=RECHECK_REQUIRED")
