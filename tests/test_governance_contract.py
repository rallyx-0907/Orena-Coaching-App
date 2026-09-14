from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_FILES = (
    "AGENTS.md",
    "docs/project/PROJECT_MEMORY.md",
    "docs/project/PRODUCT_CONSTITUTION.md",
    "docs/project/CURRENT_PRODUCT_STATE.yaml",
    "docs/project/LEGACY_TOMBSTONES.md",
    "docs/project/CURRENT_HANDOFF.md",
    "docs/project/PRODUCT_MAP.md",
    "docs/project/DESIGN_CONTRACT.md",
    "docs/project/README.md",
    "docs/project/PROJECT_STATE.md",
    "docs/project/ARCHITECTURE_INVARIANTS.md",
    "docs/project/DOMAIN_BOUNDARIES.md",
    "docs/project/ROADMAP.md",
    "docs/project/DECISION_LOG.md",
    "docs/project/REVIEW_POLICY.md",
)


def _markdown_table_row(document: str, key: str) -> tuple[str, ...]:
    """Return a table row by semantic cells, not historical column padding."""

    for line in document.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        if cells and cells[0].casefold() == key.casefold():
            return cells
    raise AssertionError(f"missing Markdown table row: {key}")


def _roadmap_status(document: str, stage: str) -> str:
    row = _markdown_table_row(document, stage)
    assert len(row) == 3, f"unexpected roadmap row for {stage}: {row!r}"
    return row[2]


# R8/R10/R11/R12/R20 release-matrix tests were retired with the removed legacy
# wrappers and frozen-native scope.
# Current Orena capability contracts are covered by the active Node gates; the
# frozen native lane is not a current Python release gate.

def _historical_handoff() -> str:
    """Archived closeout evidence; never the current-session handoff."""

    return (ROOT / "docs/project/archive/HANDOFF_BEFORE_PROJECT_MEMORY.md").read_text(encoding="utf-8")


def test_canonical_governance_context_is_present_and_discoverable() -> None:
    assert all((ROOT / path).is_file() for path in GOVERNANCE_FILES)

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    discoverable_authorities = (
        "docs/project/PROJECT_MEMORY.md",
        "docs/product/ORENA_PRODUCT_CONSTITUTION.md",
        "docs/product/ORENA_CONTENT_ARCHITECTURE.md",
        "docs/project/DESIGN_CONTRACT.md",
        "docs/product/ORENA_WEB_EXTENSION_GUIDE.md",
        "docs/product/ORENA_STATUS.md",
        "docs/project/ARCHITECTURE_INVARIANTS.md",
        "docs/project/CURRENT_HANDOFF.md",
        "docs/project/LEGACY_TOMBSTONES.md",
        "docs/project/DECISION_LOG.md",
        "docs/project/REVIEW_POLICY.md",
    )
    for path in discoverable_authorities:
        assert path in agents

    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    assert "PostgreSQL is the authoritative runtime." in project_state


def test_m16_shared_media_shadowing_governance_closeout_is_truthful() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    combined = "\n".join((project_state, handoff, roadmap)).casefold()

    assert "m1.4 is **closed / approved / merged**" in project_state.casefold()
    assert "m1.5 is **closed / approved / merged**" in project_state.casefold()
    assert "m1.6 shared-media shadowing integration is **closed / approved / merged**" in handoff.casefold()
    assert "m1.5 \u2014 active listening: **closed / merged**" in roadmap.casefold()
    assert "m1.6 \u2014 shadowing integration: **closed / merged**" in roadmap.casefold()
    assert "m1.6 shared-media shadowing integration is **closed / approved / merged**" in project_state.casefold()
    assert _markdown_table_row(project_state, "Listening") == (
        "Listening",
        "DEVELOPMENT",
        "available",
        "available",
        "no",
    )
    assert _markdown_table_row(project_state, "Speaking") == (
        "Speaking",
        "DEVELOPMENT",
        "available",
        "available",
        "no",
    )
    assert "r6 \u2014 speaking core: **complete / local acceptance pass**" in project_state.casefold()
    assert "r6 is **complete / local acceptance pass**" in project_state.casefold()
    assert "r6 is **in progress / internal**" not in project_state.casefold()
    assert "r7 \u2014 speaking evaluation + pronunciation: complete / local acceptance pass" in project_state.casefold()
    assert "audio-free" in project_state.casefold()
    assert "durable attempts, public activation, and broader release work are not part of this slice" not in project_state.casefold()
    assert "authenticated speaking attempts boundary" in handoff.casefold()
    assert "/api/speech/transcribe" in handoff
    assert "groq asr" in project_state.casefold()
    assert "not pronunciation" in project_state.casefold()
    assert _roadmap_status(roadmap, "R6") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "r2 \u2014 ai capability control plane: **human gate / ready, not product-blocking**" in project_state.casefold()
    assert "human-gated" in handoff.casefold()
    assert "r11" in combined and "planned" in combined


def test_r13_local_admin_matrix_is_reproducible_and_runtime_safe() -> None:
    report = (ROOT / "docs/project/R13_LOCAL_ACCEPTANCE_MATRIX.json").read_text(encoding="utf-8")
    runner = (ROOT / "scripts/r13_release_matrix.mjs").read_text(encoding="utf-8")
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    r13_section = roadmap.split("## R13 \u2014 Platform Admin Completion", 1)[1].split("## R14", 1)[0]
    normalized_r13 = " ".join(r13_section.split())
    assert '"matrix": "R13-local-admin-acceptance"' in report
    assert '"r13_local_complete": true' in report
    assert '"learner_runtime_activation": false' in report
    assert '"production_mutation": false' in report
    assert '"scope": "mounted-behavior"' in report
    assert '"scope": "source-and-test-boundary"' in report
    assert '"gate": "credentialed_provider_health"' in report
    assert '"gate": "learner_runtime_activation"' in report
    assert "canonical R13 matrix report is stale" in runner
    assert "test_r13_admin_capability_matrix.mjs" in runner
    assert "config_provenance" in runner
    assert "R13 \u2014 Platform Admin Completion: COMPLETE / LOCAL ACCEPTANCE PASS" in project_state
    assert "R13 local acceptance is now closed" in handoff
    assert _roadmap_status(roadmap, "R13") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "**COMPLETE / LOCAL ACCEPTANCE PASS.**" in r13_section
    assert "capability-centric Platform Admin matrix" in normalized_r13
    assert "scoped saves and explicit click-only health checks" in normalized_r13
    assert "Credentialed provider health validation, production mutation, and runtime activation remain explicit human gates." in normalized_r13
    assert _roadmap_status(roadmap, "R13") == "COMPLETE / LOCAL ACCEPTANCE PASS"


def test_r17_local_foundation_closeout_records_verified_route_boundary() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    route_test = (ROOT / "tests/test_r17_admin_routes.py").read_text(encoding="utf-8")
    activity_contract = (ROOT / "scripts/test_product_activity_contract.mjs").read_text(encoding="utf-8")
    retention_contract = (ROOT / "scripts/test_r17_admin_retention.mjs").read_text(encoding="utf-8")
    readiness_contract = (ROOT / "scripts/test_r17_readiness_contract.mjs").read_text(encoding="utf-8")
    readiness_summary = (ROOT / "scripts/test_r17_readiness_summary.mjs").read_text(encoding="utf-8")
    r17_section = roadmap.split("## R17 \u2014 Product Analytics & Operational Observability", 1)[1].split("## R18", 1)[0]
    normalized_r17 = " ".join(r17_section.split())
    assert "R17 \u2014 Product Analytics & Operational Observability: **COMPLETE / LOCAL" in project_state
    assert "R17 \u2014 Product Analytics & Operational Observability: **IN PROGRESS / LOCAL" not in project_state
    assert "R17 \u2014 Product Analytics & Operational Observability: **IN PROGRESS / LOCAL" not in handoff
    assert "R17 local-foundation closeout:** COMPLETE / LOCAL ACCEPTANCE PASS" in handoff
    assert "tests/test_r17_admin_routes.py" in handoff
    assert "httpx.ASGITransport" in route_test
    assert "/api/admin/product-activity" in route_test and "/api/admin/readiness-summary" in route_test
    assert 'headers={"x-test-admin": "1"}' in route_test
    for sensitive in ("private-user", "private learner text", "private prompt", "private.example"):
        assert sensitive in route_test
    assert _roadmap_status(roadmap, "R17") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "**COMPLETE / LOCAL ACCEPTANCE PASS.**" in r17_section
    assert "authenticated Admin-only product-activity, retention, source-specific funnel" in normalized_r17
    assert "ready, degraded, insufficient, unavailable, and deferred states remain explicit" in normalized_r17
    assert "live PostgreSQL observation remains an explicit human gate." in normalized_r17
    for contract in (activity_contract, retention_contract, readiness_contract, readiness_summary):
        assert "PASS" in contract


def test_r18_reference_data_cache_contract_is_recorded() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    route_test = (ROOT / "tests/test_reference_data_cache.py").read_text(encoding="utf-8")
    assert "R18 \u2014 Mobile/API Readiness: **COMPLETE / LOCAL ACCEPTANCE PASS**" in project_state
    assert "Current Orena program: **R21 Mobile Release Readiness \u2014 HUMAN STORE-RELEASE" in project_state
    assert "R18 \u2014 Mobile/API Readiness: **COMPLETE / LOCAL ACCEPTANCE PASS**" in handoff
    assert "R18 \u2014 Mobile/API Readiness: **IN PROGRESS / LOCAL FOUNDATION**" not in project_state
    assert "R18 \u2014 Mobile/API Readiness: **IN PROGRESS / LOCAL FOUNDATION**" not in handoff
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    r18_section = roadmap.split("## R18 \u2014 Mobile/API Readiness", 1)[1].split("## Multilingual roadmap principle", 1)[0]
    normalized_r18 = " ".join(r18_section.split())
    assert _roadmap_status(roadmap, "R18") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "**COMPLETE / LOCAL ACCEPTANCE PASS.**" in r18_section
    assert "immutable reference-data cache, authenticated session bootstrap, and compact resumable media-status contracts" in normalized_r18
    assert "Mobile-client implementation is intentionally owned by R19\u2013R21 and is an autonomous non-production development lane." in normalized_r18
    assert "Provider activation, production release, store credentials/signing, and deployment remain explicit human gates." in normalized_r18
    assert _roadmap_status(roadmap, "R18") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "R18 local-foundation closeout" in handoff
    assert "R18 immutable reference-data cache contract" in handoff
    for contract in ("source_version", "If-None-Match", "no-store", "ASGITransport"):
        assert contract in route_test or contract in handoff


def test_r18_session_bootstrap_contract_is_recorded() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    auth_source = (ROOT / "auth_support.py").read_text(encoding="utf-8")
    route_test = (ROOT / "tests/test_session_bootstrap.py").read_text(encoding="utf-8")
    assert "authenticated session-bootstrap" in handoff
    assert "R18 authenticated session-bootstrap contract" in handoff
    assert "GET /api/session/bootstrap" in handoff
    assert "/api/session/bootstrap" in auth_source
    assert 'SESSION_BOOTSTRAP_VERSION = "orena.session-bootstrap.v1"' in auth_source
    assert "httpx.ASGITransport" in route_test
    assert 'for language in ("en", "zh")' in route_test
    assert '"detail": "Authentication required"' in route_test


def test_r18_compact_media_status_contract_is_recorded() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    media_source = (ROOT / "writing_coach/media_api.py").read_text(encoding="utf-8")
    api_source = (ROOT / "static/orena/infrastructure/api.js").read_text(encoding="utf-8")
    route_test = (ROOT / "tests/test_media_status_compact.py").read_text(encoding="utf-8")
    accessor_test = (ROOT / "scripts/test_media_status_compact_accessor.mjs").read_text(encoding="utf-8")
    assert "compact media" in handoff
    assert "R18 resumable media-status response shaping" in handoff
    assert "compact: true" in handoff
    assert 'compact: bool = False' in media_source
    assert "resume_handle" in media_source
    assert "media_job_unavailable" in media_source
    assert "mediaImportStatusCompact" in api_source
    assert "JSON.parse(calls[0].options.body)" in accessor_test
    assert "httpx.ASGITransport" in route_test
    for state in ("processing", "ready", "failed"):
        assert f'"{state}"' in route_test


def test_r14_local_operations_foundation_closeout_is_recorded() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    report = (ROOT / "docs/project/R14_LOCAL_ACCEPTANCE_MATRIX.json").read_text(encoding="utf-8")
    runner = (ROOT / "scripts/r14_release_matrix.mjs").read_text(encoding="utf-8")
    telemetry_tests = (ROOT / "tests/test_ai_telemetry.py").read_text(encoding="utf-8")
    control_plane_tests = (ROOT / "tests/test_ai_control_plane.py").read_text(encoding="utf-8")
    r14_section = roadmap.split("## R14 \u2014 AI Usage, Cost, Quota & Provider Operations", 1)[1].split("## R15", 1)[0]
    normalized_r14 = " ".join(r14_section.split())

    state_start = project_state.find("R14 \u2014 AI Usage, Cost, Quota & Provider Operations:")
    assert state_start >= 0
    state_section = project_state[state_start:state_start + 700]
    assert "COMPLETE / LOCAL" in state_section
    assert "ACCEPTANCE PASS" in state_section
    assert "IN PROGRESS / LOCAL FOUNDATION" not in state_section
    assert "R14 \u2014 AI Usage, Cost, Quota & Provider Operations: **COMPLETE / LOCAL ACCEPTANCE PASS**" in handoff
    assert "R14 local-operations closeout" in handoff
    assert _roadmap_status(roadmap, "R14") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "**COMPLETE / LOCAL ACCEPTANCE PASS.**" in r14_section
    assert "sanitized capability/provider telemetry" in normalized_r14
    assert "read-only Admin operations surface" in normalized_r14
    assert "Credentialed validation, production observation, billing/quota enforcement, and runtime activation remain explicit human gates." in normalized_r14
    assert _roadmap_status(roadmap, "R14") == "COMPLETE / LOCAL ACCEPTANCE PASS"

    assert '"matrix": "R14-local-ai-operations-foundation"' in report
    assert '"r14_local_complete": true' in report
    assert '"scope": "mounted-behavior"' in report
    assert '"scope": "source-and-test-boundary"' in report
    for gate in (
        "provider_credentials",
        "billing_or_quota_enforcement",
        "learner_runtime_activation",
        "production_postgresql_observation",
    ):
        assert f'"gate": "{gate}"' in report
    assert "canonical R14 matrix report is stale" in runner
    assert "test_r13_admin_capability_matrix.mjs" in runner
    for contract in (
        "test_success_telemetry_keeps_capability_provider_model_and_reported_usage",
        "test_admin_operations_aggregates_cost_by_catalog_and_trend",
        "test_operations_endpoint_is_read_only_and_aggregates_without_provider_probe",
        "test_live_test_failure_taxonomy_is_distinct_and_sanitized",
    ):
        assert contract in telemetry_tests or contract in control_plane_tests


def test_post_r12_governance_pointer_reconciles_completed_ledger() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")

    assert "Current Orena program: **R21 Mobile Release Readiness \u2014 HUMAN STORE-RELEASE" in project_state
    assert "Current Orena program: R18" not in project_state
    assert "R3 \u2014 Writing Evaluation Completion: **COMPLETE / LOCAL ACCEPTANCE PASS**" in project_state
    normalized_state = " ".join(project_state.split())
    normalized_handoff = " ".join(handoff.split())
    for status in (
        "**R12 \u2014 Retention & Growth: COMPLETE / LOCAL ACCEPTANCE PASS.**",
        "**R13 \u2014 Platform Admin Completion: COMPLETE / LOCAL ACCEPTANCE PASS.**",
        "**R14 \u2014 AI Usage, Cost, Quota & Provider Operations: COMPLETE / LOCAL ACCEPTANCE PASS.**",
        "R15 \u2014 SaaS Plans, Entitlements & Usage Policy: **COMPLETE / LOCAL ACCEPTANCE PASS**.",
        "R16 \u2014 Advanced Learning Intelligence: **COMPLETE / LOCAL ACCEPTANCE PASS** for",
        "R17 \u2014 Product Analytics & Operational Observability: **COMPLETE / LOCAL ACCEPTANCE PASS**.",
        "R18 \u2014 Mobile/API Readiness: **COMPLETE / LOCAL ACCEPTANCE PASS**.",
    ):
        assert status in normalized_state
    for status in (
        "R12 \u2014 Retention & Growth: **COMPLETE / LOCAL ACCEPTANCE PASS**",
        "R13 \u2014 Platform Admin Completion: **COMPLETE / LOCAL ACCEPTANCE PASS**.",
        "R14 \u2014 AI Usage, Cost, Quota & Provider Operations: **COMPLETE / LOCAL ACCEPTANCE PASS**",
        "R15 - SaaS Plans, Entitlements & Usage Policy: **COMPLETE / LOCAL ACCEPTANCE PASS**",
        "R16 \u2014 Advanced Learning Intelligence: **COMPLETE / LOCAL ACCEPTANCE PASS**",
        "R17 \u2014 Product Analytics & Operational Observability: **COMPLETE / LOCAL ACCEPTANCE PASS**",
        "R18 \u2014 Mobile/API Readiness: **COMPLETE / LOCAL ACCEPTANCE PASS**",
    ):
        assert status in normalized_handoff
    assert "Current governance lane (2026-08-30)" in handoff
    # D-036 assigns R19-R21 as autonomous non-production implementation lanes,
    # superseding the earlier "no autonomous implementation owner" pointer.
    assert "R20 \u2014 Mobile Learning Experience Parity: COMPLETE / LOCAL ACCEPTANCE PASS." in normalized_handoff
    assert "the R8/R11 promotion review remains an explicit human governance decision" in normalized_handoff
    assert "R8 public-product-gate owner" not in handoff
    assert "mobile/API-readiness follow-on owner" not in handoff
    assert "R2 capability-activation" in handoff
    assert "R8" in handoff and "R11" in handoff and "human gate" in handoff.casefold()
    assert "**Next handoff:** R21 mobile release-readiness completion" in normalized_handoff
    assert "R8 \u2014 Public Product Gate" in project_state
    assert "R11" in project_state and "human gate" in project_state.casefold()
    assert _roadmap_status(roadmap, "R12") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert _roadmap_status(roadmap, "R13") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert _roadmap_status(roadmap, "R14") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert _roadmap_status(roadmap, "R15") == "COMPLETE / LOCAL ACCEPTANCE PASS"


def test_r15_local_account_state_closeout_is_recorded() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    contract = (ROOT / "scripts/test_r15_account_state.mjs").read_text(encoding="utf-8")
    r15_section = roadmap.split("## R15 \u2014 SaaS Plans, Entitlements & Usage Policy", 1)[1].split("## R16", 1)[0]
    normalized_r15 = " ".join(r15_section.split())

    assert "R15 \u2014 SaaS Plans, Entitlements & Usage Policy: **COMPLETE / LOCAL" in project_state
    assert "R15 - SaaS Plans, Entitlements & Usage Policy: **COMPLETE / LOCAL ACCEPTANCE PASS**" in handoff
    assert "R15 account-state visibility closeout" in handoff
    assert _roadmap_status(roadmap, "R15") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "**COMPLETE / LOCAL ACCEPTANCE PASS.**" in r15_section
    assert "truthful known, unavailable, exhausted, unlimited, inactive, and unknown states" in normalized_r15
    assert "Billing integration, entitlement enforcement, production subscription mutation, and public release remain explicit human gates." in normalized_r15
    for contract_token in (
        "productMe",
        "usage_state",
        "renderAccountState",
        "product_me",
        "product_admin_account",
        "unavailable",
    ):
        assert contract_token in contract


def test_r3_roadmap_status_matches_verified_local_closeout() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    normalized_roadmap = " ".join(roadmap.split())

    assert _roadmap_status(roadmap, "R3") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "**COMPLETE / LOCAL ACCEPTANCE PASS.**" in roadmap
    assert _roadmap_status(roadmap, "R3") != "IN PROGRESS / PRIMARY"
    assert "**IN PROGRESS / PRIMARY.**" not in roadmap
    assert "R3 \u2014 Writing Evaluation Completion: **COMPLETE / LOCAL ACCEPTANCE PASS**" in project_state
    assert "R3 \u2014 Writing Evaluation Completion: **COMPLETE / LOCAL ACCEPTANCE PASS**" in handoff
    assert "R2 \u2014 AI Capability Control Plane: **HUMAN GATE / READY, NOT PRODUCT-BLOCKING**" in project_state
    assert "R8 \u2014 Public Product Gate: Writing + Speaking EN/ZH: **PRE-PUBLIC MATRIX" in handoff
    assert "During the historical R3/R4 primary lane" in roadmap
    assert "While R3/R4 are the primary lane" not in roadmap
    assert "Current R6 ownership and any promotion remain governed" in normalized_roadmap
    assert "human governance decision" in handoff.casefold()
    assert "## Historical execution order" in roadmap
    assert "The historical primary execution from the post-R5 checkpoint was:" in roadmap
    assert "Current ownership and promotion gates are recorded in" in normalized_roadmap
    assert "Primary execution from the post-R5 checkpoint is:" not in roadmap
    assert "while R3/R4 are primary" not in roadmap
    assert "### Historical execution relationship" in roadmap
    assert "The historical primary path was:" in roadmap
    assert "The existing primary path remains:" not in roadmap
    assert "no active autonomous R3/R4 implementation lane" in normalized_roadmap


def test_r4_roadmap_status_matches_verified_learning_loop_closeout() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    normalized_roadmap = " ".join(roadmap.split())
    r4_section = roadmap.split("## R4 \u2014 Writing Learning Loop + Grammar Transfer", 1)[1].split("## R5", 1)[0]

    assert _roadmap_status(roadmap, "R4") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "**COMPLETE / LOCAL ACCEPTANCE PASS.**" in r4_section
    assert "The shared EN/ZH evidence-to-grammar, targeted-practice, revision-lineage, and downstream Review/Journey/Library contracts are locally accepted." in normalized_roadmap
    assert "Public promotion remains governed by R8 and the R2 capability-activation gate." in normalized_roadmap
    assert "**R4 \u2014 Writing Learning Loop + Grammar Transfer: COMPLETE / LOCAL ACCEPTANCE PASS.**" in project_state
    assert "R4 \u2014 Writing Learning Loop + Grammar Transfer: **COMPLETE / LOCAL ACCEPTANCE PASS**" in handoff
    assert "R2 \u2014 AI Capability Control Plane: **HUMAN GATE / READY, NOT PRODUCT-BLOCKING**" in project_state
    assert "R8 \u2014 Public Product Gate: Writing + Speaking EN/ZH: **PRE-PUBLIC MATRIX" in handoff


def test_r6_roadmap_status_matches_verified_speaking_core_closeout() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    normalized_roadmap = " ".join(roadmap.split())
    r6_section = roadmap.split("## R6 \u2014 Speaking Core", 1)[1].split("## R7", 1)[0]

    assert _roadmap_status(roadmap, "R6") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "**COMPLETE / LOCAL ACCEPTANCE PASS.**" in r6_section
    assert "The EN/ZH record-to-transcript-to-feedback boundary is locally accepted." in normalized_roadmap
    assert "pronunciation, fluency, or proficiency scoring" in normalized_roadmap
    assert "those dimensions remain R7 work" in normalized_roadmap
    assert "R2 activation and R8 public promotion remain explicit human gates" in normalized_roadmap
    assert "R6 \u2014 Speaking Core: **COMPLETE / LOCAL ACCEPTANCE PASS**" in project_state
    assert "R6 \u2014 Speaking Core: **COMPLETE / LOCAL ACCEPTANCE PASS**" in handoff
    assert "R7 \u2014 Speaking Evaluation + Pronunciation: **COMPLETE / LOCAL ACCEPTANCE PASS**" in handoff


def test_r7_roadmap_status_matches_verified_speaking_evaluation_closeout() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    normalized_roadmap = " ".join(roadmap.split())
    r7_section = roadmap.split("## R7 \u2014 Speaking Evaluation + Pronunciation Completion", 1)[1].split("## R8", 1)[0]

    assert _roadmap_status(roadmap, "R7") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "**COMPLETE / LOCAL ACCEPTANCE PASS.**" in r7_section
    assert "The EN/ZH evaluator, pronunciation evidence, localized feedback, and durable learner-scoped attempt/history contracts are locally accepted." in normalized_roadmap
    assert "Transcription confidence, pronunciation, fluency, and proficiency remain separate dimensions" in normalized_roadmap
    assert "R2 capability activation and R8 public promotion remain explicit human gates." in normalized_roadmap
    assert "R7 \u2014 Speaking Evaluation + Pronunciation: COMPLETE / LOCAL ACCEPTANCE PASS." in project_state
    assert "R7 \u2014 Speaking Evaluation + Pronunciation: **COMPLETE / LOCAL ACCEPTANCE PASS**" in handoff


def test_r9_roadmap_status_matches_verified_shadowing_closeout() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    normalized_roadmap = " ".join(roadmap.split())
    r9_section = roadmap.split("## R9 \u2014 Speaking Advanced / Shadowing Studio", 1)[1].split("## R10", 1)[0]

    assert _roadmap_status(roadmap, "R9") == "COMPLETE / LOCAL ACCEPTANCE PASS"
    assert "**COMPLETE / LOCAL ACCEPTANCE PASS.**" in r9_section
    assert "The EN/ZH Shadowing Studio flow is locally accepted for canonical shared-media selection, transcript practice, Speaking-feedback continuity, and resumable learner state." in normalized_roadmap
    assert "same Media Learning asset/transcript/translation contracts established by M1" in normalized_roadmap
    assert "Public productization and provider activation remain explicit human gates" in normalized_roadmap
    assert "R9 \u2014 Speaking Advanced / Shadowing Studio: COMPLETE / LOCAL ACCEPTANCE PASS." in project_state
    assert "R9 \u2014 Speaking Advanced / Shadowing Studio: **COMPLETE / LOCAL ACCEPTANCE PASS**" in handoff
    assert "R8 \u2014 Public Product Gate: Writing + Speaking EN/ZH: **PRE-PUBLIC MATRIX" in handoff


def test_r16_local_foundation_closeout_records_complete_evidence_chain() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = _historical_handoff()
    normalized_state = " ".join(project_state.split())
    normalized_handoff = " ".join(handoff.split())

    assert "R16 \u2014 Advanced Learning Intelligence: **COMPLETE / LOCAL ACCEPTANCE PASS** for contextual dictionary lookups in Writing, Review, Reading, and shared Listening/Speaking transcripts" in normalized_state
    assert "the scheduled Library review handoff" in normalized_state
    assert "R16 local-foundation evidence reconciliation" in handoff
    assert "Home presents only a valid due review" in normalized_handoff
    assert "due/due-soon" not in normalized_handoff
    for evidence in (
        "scripts/test_r16_contextual_dictionary.mjs",
        "scripts/run_r16_contextual_dictionary.py",
        "scripts/test_r16_reading_contextual_dictionary.mjs",
        "scripts/test_r16_shared_transcript_contextual_dictionary.mjs",
        "scripts/test_adaptive_difficulty_locale.mjs",
        "scripts/run_r16_adaptive_practice.py",
        "scripts/test_review_cue_locale.mjs",
        "scripts/test_cross_skill_transfer_locale.mjs",
        "scripts/test_home_library_review_handoff.mjs",
    ):
        assert evidence in normalized_handoff
    assert "EN/ZH behavior remains shared through existing contracts" in normalized_handoff
    assert "provider credentials, production activation, and public promotion remain deferred gates" in normalized_handoff
