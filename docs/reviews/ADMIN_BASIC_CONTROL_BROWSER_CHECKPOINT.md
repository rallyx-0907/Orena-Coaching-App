# Admin control-center reconciliation — 2026-10-03

MILESTONE=ADMIN_BASIC_CONTROL_CENTER
STATUS=REVIEWABLE (bounded reconciliation; remaining acceptance below)
COMMIT=2931823dca94cf5b9a7885a2dcf1b4292872c869; independent review covered this implementation delta from baseline 7df94493eef4326d04d3ba1a70b99f1d7b91be57.
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/admin/overview
HOW_TO_REACH_IT=Authorized operator → Profile → Admin; root Admin opens Overview.
EN_PARITY=Real Listening word lookup returns Vietnamese meaning for “pyramids”.
ZH_PARITY=Real Chinese Listening lookup returns Vietnamese meaning for 新.
CROSS_CAPABILITY_STATUS=Existing content/import/lifecycle APIs preserved; supported text capability routing active on this sandbox. Speech capability routing remains reserved/unavailable.

## Preserved implementation

The completed admin/control-center provider credential feature remains the same:
Fernet encryption, write-only entry, connection tests, masked credential state,
removal, Admin authorization, same-origin credential mutation and non-secret audit.
Existing provider/model selection, content lifecycle, Reading jobs/retry, EPUB and
vocabulary imports were reused. Accepted Books, Progress and S2/S6 were not rebuilt.
No real credential was newly entered, removed or printed during this checkpoint.

## Changes and runtime evidence

- Overview, Users/account details and Operations/workers/polling/errors now use
  existing guarded APIs in the pinned Admin shell. All six primary areas are reachable.
- Imports and media detail poll actual preparation stage and outcome; processing
  has a shared progress bar, unknown duration is indeterminate. Catalogue status
  and transcript availability remain separate, including published/archived items.
- Cloud credentials require an HTTPS provider endpoint. Credential-free local
  Ollama HTTP is retained. Browser-to-Admin uses loopback :8021, not remote cloud HTTP.
- Missing sandbox AI_PROVIDER_SECRETS_KEY was provisioning, not absent feature.
  No encrypted provider records existed before provisioning. A new master key is
  in an ignored, ACL-protected `.env.orena-next-verify-secrets` file (never committed).
  Web recreation retained its environment, PostgreSQL and shared durable media mount.
- Existing reviewed migration initialized seven missing text configurations,
  preserving Writing. `validate_ai_runtime_activation.py` static8 PASS.
  AI_RUNTIME_MODE=capability is enabled only on :8021; public/production unchanged.
  Stopped rollback containers remain `orena-next-verify-web-before-admin-provision`
  and `orena-next-verify-web-before-capability-activation`. No persistent volume deleted.
- Config API now reports actual routing policy instead of hardcoded legacy false.
- Real Gemini request failed with seed and succeeded with the otherwise identical
  request without it. Gemini/DeepSeek adapters omit seed at request construction;
  OpenAI retains it. No additional retry/failover was introduced.

## Actual browser journeys

Brave, desktop viewport 1910px, approved `/next` UI:

1. Overview: active/new accounts, 13 published content records, domain activity,
   actual attention issues. Dictionary issue opens its capability editor.
2. Users: masked account list, Chinese language filter, account detail with EN/ZH
   support profiles and actual record counts. Learner-authored content is not exposed.
3. Operations: PostgreSQL, credential store configured, capability routing, actual
   service engines/models, Reading queue counts, recent AI events. The telemetry
   label explicitly describes a recorded sample, not a made-up 24-hour total.
4. AI dictionary: primary connection probe succeeds (934ms). Model picker changed
   from gemini-3.5-flash-lite to gemini-2.5-flash-lite; Save and reload preserved it.
   Actual EN learner request telemetry used the newly saved model. That provider
   request failed and the UI truthfully displayed unavailable meaning. Original
   model was restored through Save; EN “pyramids” then displayed “các kim tự tháp”.
5. Chinese Listening lookup on the existing account-scoped video displayed real VI
   meaning after the adapter correction. Account target language restored to English.
6. Admin Media URL importer: the user-reported B0p5SdkBydU previewed, imported and
   automatically moved from visible processing/progress to Needs review / Transcript
   ready. Open reached the real detail with 75 segments, 320.5s, English and unknown
   rights. It remains invisible to learners; no rights clearance was fabricated.
   The held import success count was corrected separately from publication state.

Screenshots: [Overview](evidence/admin-basic/overview-desktop.png),
[Operations](evidence/admin-basic/operations-desktop.png),
[capability](evidence/admin-basic/capability-live.png),
[Users ZH filter](evidence/admin-basic/users-filter-zh.png),
[EN lookup](evidence/admin-basic/en-lookup-restored.png),
[media processing](evidence/admin-basic/media-import-processing.png),
[media review result](evidence/admin-basic/media-import-review.png).

## Local validation and review

- Python: 278 passed, two inherited FastAPI deprecation warnings, isolated SQLite
  test backend in ephemeral application image. Runtime remains PostgreSQL.
  Tests: AI credentials/control plane and complete Admin authorization matrix.
- Admin control rendering, Admin screen/areas, media publication, copy EN/VI/ZH,
  browser ESM graph (332 modules): PASS locally. No CI PASS claim.
- Ruff 0.16.10 reports inherited UP035/UP042 in untouched platform.py lines;
  those baseline style issues were not changed to broaden this product slice.
- Independent reviewer `/root/review_media_basic` reviewed the working delta:
  APPROVE, including Gemini/DeepSeek request handling. No human product approval.

## Remaining acceptance and truthful limits

- Live asynchronous Admin import refresh through preparation and rights review is
  verified above. Existing S6 rights/publish/EN/ZH opening/archive evidence remains valid.
- Mobile verification of these new control pages is not claimed: the browser
  viewport override returned without changing actual width (still 1910px).
  Temporary overrides were reset; no desktop image is presented as mobile evidence.
- New credential entry requires operator handoff under the browser credential
  policy; the previously verified encrypted flow is preserved, not reclassified as missing.
- Speech ASR/pronunciation/Speaking routing is reserved; these cannot be represented
  as working capability pickers. Current service configuration is reported separately.
- Practice generation and canonical Grammar content administration need their
  supported runtimes. They are remaining basic app capability gaps, not reasons
  to rebuild functional Admin areas.

Deferred hardening: credential rotation/disaster recovery drills, rare provider
edge cases, full process heartbeat/restart controls, advanced observability,
performance and deeper visual fidelity. Production/public activation remains gated.
