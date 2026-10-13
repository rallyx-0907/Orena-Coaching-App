"""Assembles integrations/n8n/orena_vocab_generator.json from integrations/n8n/src/*.js.

    python integrations/n8n/build_workflow.py          # rewrite the workflow JSON
    python integrations/n8n/build_workflow.py --check  # exit 1 if the committed JSON is not what the sources build

The Code-node sources live in src/. Shared libraries are inlined where a source says `// <<LIB:name>>`
(an n8n Code node cannot import a module). The vocabulary schema is NEVER typed here: it is copied verbatim from
docs/vocab/vocab_entry.schema.json into the validator, so the workflow cannot drift from the repo. tests/test_n8n_vocab_workflow.py
and scripts/test_n8n_vocab_workflow.mjs fail when it does.

Node ids and the form's webhook id are uuid5 of the node name: stable across builds, and not any n8n instance's ids.
No credential is referenced: the operator selects credentials in n8n after importing.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = HERE / "src"
OUT = HERE / "orena_vocab_generator.json"
SCHEMA_PATH = ROOT / "docs" / "vocab" / "vocab_entry.schema.json"
NS = uuid.UUID("6f1c2d3e-7a58-4b19-9c0e-0a5e11a0ca7d")  # namespace for this workflow's deterministic ids

LIBS = {"common": "lib_common.js", "validate": "lib_validate.js", "sync": "lib_sync.js", "report": "lib_report.js"}


def schema_text() -> str:
    return SCHEMA_PATH.read_bytes().decode("utf-8").replace("\r\n", "\n")


def lib(name: str) -> str:
    text = (SRC / LIBS[name]).read_text(encoding="utf-8")
    if "// <<SCHEMA>>" in text:
        embedded = (
            "const VOCAB_SCHEMA_TEXT = " + json.dumps(schema_text(), ensure_ascii=False) + ";\n"
            "const VOCAB_SCHEMA = JSON.parse(VOCAB_SCHEMA_TEXT);"
        )
        text = text.replace("// <<SCHEMA>>", embedded)
    return text


def code(filename: str) -> str:
    text = (SRC / filename).read_text(encoding="utf-8")
    for name in LIBS:
        text = text.replace(f"// <<LIB:{name}>>", lib(name))
    return text


def nid(name: str) -> str:
    return str(uuid.uuid5(NS, name))


nodes: list[dict] = []
connections: dict[str, dict] = {}


def add(name, type_, version, position, parameters, **extra):
    node = {"parameters": parameters, "type": type_, "typeVersion": version, "position": position, "id": nid(name), "name": name}
    node.update(extra)
    nodes.append(node)


def code_node(name, source, position, **extra):
    add(name, "n8n-nodes-base.code", 2, position, {"mode": "runOnceForAllItems", "jsCode": code(source)}, **extra)


def if_node(name, left, position):
    add(name, "n8n-nodes-base.if", 2.2, position, {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": nid(name + ":condition"), "leftValue": left,
                "operator": {"type": "boolean", "operation": "true", "singleValue": True},
            }],
            "combinator": "and",
        },
        "options": {},
    })


def connect(src, *targets, output=0):
    outputs = connections.setdefault(src, {"main": []})["main"]
    while len(outputs) <= output:
        outputs.append([])
    outputs[output].extend({"node": t, "type": "main", "index": 0} for t in targets)


def http_enrich(name, url, position):
    add(name, "n8n-nodes-base.httpRequest", 4.2, position, {
        "url": url,
        "options": {
            "response": {"response": {"neverError": True, "responseFormat": "text", "outputPropertyName": "data"}},
            "timeout": 30000,
            "batching": {"batch": {"batchSize": 3, "batchInterval": 1000}},
        },
    }, onError="continueRegularOutput")


def download(name, url_key, fmt, position, **extra):
    add(name, "n8n-nodes-base.httpRequest", 4.2, position, {
        "url": "={{ $('Config').first().json.sources." + url_key + " }}",
        "options": {"response": {"response": {"neverError": True, "responseFormat": fmt, "outputPropertyName": "data"}}, "timeout": 300000},
    }, onError="continueRegularOutput", **extra)


FORM_FIELDS = [
    {"fieldLabel": "Word list", "fieldType": "textarea", "requiredField": True, "placeholder": "resilient — C1\n森林 — HSK4"},
    {"fieldLabel": "Batch title", "fieldType": "text", "placeholder": "HSK5 Batch 01"},
    {"fieldLabel": "Collection ID", "fieldType": "text", "placeholder": "empty = made from the batch title"},
    {"fieldLabel": "Delivery mode", "fieldType": "dropdown", "fieldOptions": {"values": [{"option": "file"}, {"option": "api"}]}},
    {"fieldLabel": "When already stored", "fieldType": "dropdown", "fieldOptions": {"values": [{"option": "skip"}, {"option": "overwrite"}]}},
]

TEST_INPUT = (
    "return [{ json: {\n"
    "  'Word list': 'resilient — C1\\n森林 — HSK4',\n"
    "  'Batch title': 'Test Batch 01',\n"
    "  'Delivery mode': 'file',          // 'file' or 'api'\n"
    "  'When already stored': 'skip',    // 'skip' or 'overwrite' (overwrite is honoured only from this manual path)\n"
    "  _trigger: 'manual',               // marks an operator-run execution; the form never sets it\n"
    "} }];\n"
)

NOTE_MAIN = (
    "## Orena · Vocabulary Generator\n"
    "**word list -> enrich -> card -> strict validation -> local files -> (api mode) preview -> import -> report**\n\n"
    "- **file** (default): writes the ready JSONL, rejected.json, report.json and report.csv to `/files/orena`. No Orena URL or credential. Import the ready file in Orena Admin.\n"
    "- **api**: writes the same files first, then previews and imports. Needs the Orena base URL (Config) and a Header Auth credential on *Orena · Preview* and *Orena · Import*. A malformed, refused or unknown preview blocks the import.\n"
    "- Settings live in the **Config** node. The AI key is a Header Auth credential on *AI · Fill gaps* (optional; AI only fills gaps).\n"
    "- The **Form** is protected with Basic Auth: attach a credential before activating. Overwrite is never honoured from the form.\n\n"
    "Read integrations/n8n/README.md in the Orena repository before first use."
)


def build() -> dict:
    add("Form", "n8n-nodes-base.formTrigger", 2.2, [0, 0], {
        "formTitle": "Orena · Vocabulary Generator",
        "formDescription": "One word per line: word — level [— Vietnamese meaning]. Example: resilient — C1 or 森林 — HSK4. The language is detected from the characters.",
        "formFields": {"values": FORM_FIELDS},
        "authentication": "basicAuth",
        "options": {},
    }, webhookId=nid("Form:webhook"))
    add("Run test", "n8n-nodes-base.manualTrigger", 1, [0, 200], {})
    add("Test input", "n8n-nodes-base.code", 2, [220, 200], {"mode": "runOnceForAllItems", "jsCode": TEST_INPUT})
    code_node("Config", "config.js", [440, 80])
    code_node("Parse words", "parse_words.js", [660, 80])
    if_node("Has Chinese?", "={{ $json.hasZh }}", [880, 80])
    add("Read ZH lookup", "n8n-nodes-base.readWriteFile", 1, [1100, -120],
        {"fileSelector": "={{ $('Config').first().json.zhLookup.path }}", "options": {}},
        executeOnce=True, onError="continueRegularOutput", alwaysOutputData=True)
    if_node("ZH lookup cached?", "={{ !$('Config').first().json.zhLookup.rebuild && !!($binary && $binary.data) }}", [1320, -120])
    download("Download CC-CEDICT", "cedict", "file", [1320, -520], executeOnce=True)
    add("Gunzip CEDICT", "n8n-nodes-base.compression", 1.1, [1540, -520], {"operation": "decompress", "binaryPropertyName": "data", "outputPrefix": "file_"})
    add("CEDICT text", "n8n-nodes-base.extractFromFile", 1, [1760, -520], {"operation": "text", "binaryPropertyName": "file_0", "destinationKey": "data", "options": {}})
    download("Download CVDICT", "cvdict", "text", [1980, -520])
    download("Download Make Me a Hanzi", "makeMeAHanzi", "text", [2200, -520])
    download("Download Unihan", "unihan", "file", [1320, -360])
    add("Unzip Unihan", "n8n-nodes-base.compression", 1.1, [1540, -360], {"operation": "decompress", "binaryPropertyName": "data", "outputPrefix": "file_"})
    code_node("Build ZH lookup", "build_zh_lookup.js", [1760, -360])
    add("To JSON file", "n8n-nodes-base.convertToFile", 1.1, [1980, -360], {"operation": "toJson", "mode": "each", "options": {"fileName": "zh_lookup.json"}})
    add("Save zh_lookup.json", "n8n-nodes-base.readWriteFile", 1, [2200, -360],
        {"operation": "write", "fileName": "={{ $('Config').first().json.zhLookup.path }}", "dataPropertyName": "data", "options": {}})
    add("Parse ZH lookup", "n8n-nodes-base.extractFromFile", 1, [2420, -120], {"operation": "fromJson", "binaryPropertyName": "data", "options": {}}, executeOnce=True)
    code_node("Words", "words.js", [2640, 80])
    http_enrich("Enrich call 1", "={{ $json.url1 }}", [2860, 80])
    http_enrich("Enrich call 2", "={{ $('Words').item.json.url2 }}", [3080, 80])
    code_node("Build records", "build_records.js", [3300, 80])
    code_node("Prepare AI", "prepare_ai.js", [3520, 80])
    if_node("No AI needed?", "={{ $json.noop === true }}", [3740, 80])
    add("AI · Fill gaps", "n8n-nodes-base.httpRequest", 4.2, [3960, 240], {
        "method": "POST",
        "url": "={{ $('Config').first().json.ai.endpoint }}",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify($json.body) }}",
        "options": {
            "response": {"response": {"neverError": True, "responseFormat": "text", "outputPropertyName": "data"}},
            "timeout": 90000,
            "batching": {"batch": {"batchSize": 2, "batchInterval": 1000}},
        },
    }, onError="continueRegularOutput")
    code_node("Validate & group", "validate_group.js", [4180, 80])
    code_node("Build files", "build_files.js", [4400, 80])
    add("Save files", "n8n-nodes-base.readWriteFile", 1, [4620, 80],
        {"operation": "write", "fileName": "={{ $json.path }}", "dataPropertyName": "data", "options": {}},
        onError="continueRegularOutput")
    code_node("Check writes", "check_writes.js", [4840, 80])
    code_node("Prepare sync", "prepare_sync.js", [5060, 80])
    if_node("Nothing to sync?", "={{ $json.noop === true }}", [5280, 80])
    add("Orena · Preview", "n8n-nodes-base.httpRequest", 4.2, [5500, 240], {
        "method": "POST",
        "url": "={{ $json.previewUrl }}",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendBody": True,
        "contentType": "multipart-form-data",
        "bodyParameters": {"parameters": [{"parameterType": "formBinaryData", "name": "files", "inputDataFieldName": "data"}]},
        "options": {"response": {"response": {"neverError": True, "responseFormat": "text", "outputPropertyName": "data", "fullResponse": True}}, "timeout": 120000},
    }, onError="continueRegularOutput")
    code_node("Check preview", "check_preview.js", [5720, 240])
    if_node("Preview passed?", "={{ $json.passed === true }}", [5940, 240])
    add("Orena · Import", "n8n-nodes-base.httpRequest", 4.2, [6160, 120], {
        "method": "POST",
        "url": "={{ $json.importUrl }}",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendBody": True,
        "contentType": "multipart-form-data",
        "bodyParameters": {"parameters": [
            {"parameterType": "formBinaryData", "name": "files", "inputDataFieldName": "data"},
            {"parameterType": "formData", "name": "metadata", "value": "={{ JSON.stringify($json.metadata) }}"},
            {"parameterType": "formData", "name": "mappings", "value": "{}"},
            {"parameterType": "formData", "name": "duplicates", "value": "={{ $json.duplicates }}"},
        ]},
        "options": {"response": {"response": {"neverError": True, "responseFormat": "text", "outputPropertyName": "data", "fullResponse": True}}, "timeout": 300000},
    }, onError="continueRegularOutput")
    code_node("Check import", "check_import.js", [6380, 120])
    code_node("Final report", "final_report.js", [6600, 80])
    add("Save final reports", "n8n-nodes-base.readWriteFile", 1, [6820, 80],
        {"operation": "write", "fileName": "={{ $json.path }}", "dataPropertyName": "data", "options": {}},
        onError="continueRegularOutput")
    code_node("Run summary", "run_summary.js", [7040, 80])
    add("Guide", "n8n-nodes-base.stickyNote", 1, [-20, -620], {"content": NOTE_MAIN, "height": 440, "width": 700})
    add("Chinese dictionary", "n8n-nodes-base.stickyNote", 1, [1300, -680],
        {"content": "### Chinese dictionary\nRuns only when `zh_lookup.json` is not in the output folder yet (or `zhLookup.rebuild` is true). The first run downloads CC-CEDICT, CVDICT, Make Me a Hanzi and Unihan and takes a few minutes. Saving the cache is required on this path.", "height": 160, "width": 940, "color": 7})

    connect("Form", "Config")
    connect("Run test", "Test input")
    connect("Test input", "Config")
    connect("Config", "Parse words")
    connect("Parse words", "Has Chinese?")
    connect("Has Chinese?", "Read ZH lookup", output=0)
    connect("Has Chinese?", "Words", output=1)
    connect("Read ZH lookup", "ZH lookup cached?")
    connect("ZH lookup cached?", "Parse ZH lookup", output=0)
    connect("ZH lookup cached?", "Download CC-CEDICT", output=1)
    for a, b in [("Download CC-CEDICT", "Gunzip CEDICT"), ("Gunzip CEDICT", "CEDICT text"), ("CEDICT text", "Download CVDICT"),
                 ("Download CVDICT", "Download Make Me a Hanzi"), ("Download Make Me a Hanzi", "Download Unihan"),
                 ("Download Unihan", "Unzip Unihan"), ("Unzip Unihan", "Build ZH lookup"), ("Build ZH lookup", "To JSON file"),
                 ("To JSON file", "Save zh_lookup.json"), ("Save zh_lookup.json", "Parse ZH lookup"), ("Parse ZH lookup", "Words"),
                 ("Words", "Enrich call 1"), ("Enrich call 1", "Enrich call 2"), ("Enrich call 2", "Build records"),
                 ("Build records", "Prepare AI"), ("Prepare AI", "No AI needed?")]:
        connect(a, b)
    connect("No AI needed?", "Validate & group", output=0)
    connect("No AI needed?", "AI · Fill gaps", output=1)
    for a, b in [("AI · Fill gaps", "Validate & group"), ("Validate & group", "Build files"), ("Build files", "Save files"),
                 ("Save files", "Check writes"), ("Check writes", "Prepare sync"), ("Prepare sync", "Nothing to sync?")]:
        connect(a, b)
    connect("Nothing to sync?", "Final report", output=0)
    connect("Nothing to sync?", "Orena · Preview", output=1)
    connect("Orena · Preview", "Check preview")
    connect("Check preview", "Preview passed?")
    connect("Preview passed?", "Orena · Import", output=0)
    connect("Preview passed?", "Final report", output=1)
    connect("Orena · Import", "Check import")
    connect("Check import", "Final report")
    connect("Final report", "Save final reports")
    connect("Save final reports", "Run summary")

    return {
        "name": "Orena · Vocabulary Generator",
        "nodes": nodes,
        "pinData": {},
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "meta": {"templateCredsSetupCompleted": False},
        "tags": [],
    }


def render() -> str:
    return json.dumps(build(), ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            sys.stderr.write("integrations/n8n/orena_vocab_generator.json is out of date: run python integrations/n8n/build_workflow.py\n")
            sys.exit(1)
        sys.stdout.write("workflow is up to date\n")
    else:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        sys.stdout.write(f"wrote {OUT.relative_to(ROOT)} ({len(text)} bytes, {len(nodes)} nodes)\n")
