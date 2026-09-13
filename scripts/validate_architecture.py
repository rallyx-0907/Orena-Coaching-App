from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
index = (ROOT / "templates" / "orena" / "index.html").read_text(encoding="utf-8")
app = (ROOT / "app.py").read_text(encoding="utf-8")
auth = (ROOT / "auth_support.py").read_text(encoding="utf-8")

require(version == "1.4.0", "VERSION must be v1.4.0")
require("COPY writing_coach ./writing_coach" in dockerfile, "Dockerfile must copy writing_coach package")
require('app.mount("/static"' in app, "StaticFiles mount is required")
require("writing_coach.languages.runtime" in app, "Language evaluator runtime must be modular")
require("writing_coach.product.api" in app, "Product API must be installed")
require("Data stays in local SQLite." not in index, "Learner UI must not expose storage implementation")
require("languages.english.grammar_course import" not in app, "English grammar course must not be hardwired in app.py")
require("GRAMMAR_LIBRARY = [" not in app, "Dead embedded GRAMMAR_LIBRARY must not return")
require('translation_vi = excluded.translation_vi,\n              translation_vi' not in app, "Duplicate vocabulary SQL assignment exists")
require("<script>\nconst $=" not in index, "Large inline app JavaScript must stay extracted")
require('/orena-assets/app.js' in index, 'Root must load the Orena product')
require('/orena-assets/world.css' in index, 'Root must load the shared presentation foundation')
require(not (ROOT / 'static/becoming').exists(), 'Retired learner product must stay physically absent')
require('/orena-assets/' in auth, 'New product assets must pass the auth asset boundary')
require("LANGUAGE_CODE_CTX" in auth, "Auth middleware must set language context")
require("resolve_language_db_path" in auth, "Auth must resolve DB by user + language")

sys.path.insert(0, str(ROOT))
from writing_coach.core.language_registry import all_languages

langs = {x.code: x for x in all_languages()}
require("en" in langs and langs["en"].enabled, "English must be enabled")
require("zh" in langs and langs["zh"].enabled, "Chinese must be enabled in v1.1")
from writing_coach.grammar_catalog import GrammarCatalogInvalid, validate_grammar_catalog
from writing_coach.languages.chinese.grammar_course import (
    GRAMMAR_BY_ID as ZH_GRAMMAR_BY_ID,
    GRAMMAR_COURSE as ZH_GRAMMAR,
)
from writing_coach.languages.chinese.profile import PROFILE as ZH_PROFILE

zh = langs.get("zh")
require(zh is not None and all(x in zh.capabilities for x in ("grammar","vocabulary","dictionary","translation","pinyin")), "Chinese library capabilities are incomplete")
try:
    validate_grammar_catalog(ZH_GRAMMAR, ZH_PROFILE.levels, ZH_GRAMMAR_BY_ID)
except GrammarCatalogInvalid as exc:
    errors.append(f"Chinese grammar curriculum is structurally invalid: {exc}")
require(
    {item["level"] for item in ZH_GRAMMAR} == set(ZH_PROFILE.levels),
    "Chinese grammar curriculum must cover every configured HSK level",
)
require(
    all(
        any(item["level"] == level and item.get("kind") == "review" for item in ZH_GRAMMAR)
        and any(item["level"] == level and item.get("kind") == "checkpoint" for item in ZH_GRAMMAR)
        for level in ZH_PROFILE.levels
    ),
    "Chinese grammar curriculum must include review and checkpoint items for every configured HSK level",
)


if errors:
    print("Architecture validation FAILED:")
    for item in errors:
        print(" -", item)
    raise SystemExit(1)

print("Architecture validation OK")
print("Version:", version)
print("Languages:", ", ".join(f"{x.code}:{x.status}" for x in all_languages()))
