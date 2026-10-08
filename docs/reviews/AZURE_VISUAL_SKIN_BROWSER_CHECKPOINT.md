# Azure Admin and Visual Skin checkpoint — 2026-10-03

MILESTONE=Azure Admin/runtime and approved Visual Skin integration
STATUS=REVIEWABLE (bounded slice; not Admin basic-complete or public-ready)
COMMIT=7857d4353be106e1ced97de8ea84a27804b1defb
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/admin/ai and #/settings
HOW_TO_REACH_IT=Admin → AI & Models → Azure provider; Profile → Settings → Learning
EN_PARITY=Browser EN form/settings tested
ZH_PARITY=Browser ZH settings, shared palette/runtime contracts; adapter EN/ZH regression passes
CROSS_CAPABILITY_STATUS=Speech feeds existing pronunciation adapter; OpenAI supports existing structured-text routes, not reserved speech routes

## Implemented and browser evidence

Azure Speech and Azure OpenAI reuse the encrypted, write-only Admin credential
flow. Speech validates a regional HTTPS endpoint and tests authentication without
returning the token. OpenAI validates the resource /openai/v1 endpoint and tests
the operator's deployment rather than pretending a resource model catalogue is
a deployment list. Redirects are refused for Azure OpenAI requests.

Stored Speech credentials activate the existing adapter when the runtime mode is
unset/Azure; explicitly disabled modes stay disabled. Request-time resolution
prevents deleted credentials surviving in a startup singleton. Unreadable stored
credentials disable assessment without preventing app startup. Operations refreshes
service state, and removal warns about pronunciation dependency.

On :8021: Admin provider list displayed seven providers; Azure Speech showed its
environment credential, pronunciation dependency, and a real **Test passed**
result (1,056 ms). The initial browser test exposed an environment-key test bug;
the corrected test reuses the current key only with no endpoint override, never
copies it into stored credentials, and never returns it. Azure OpenAI displayed
an honest unconfigured state and reachable endpoint/key/deployment form.

Overview now uses A1's full-width four metrics before its two-column blocks.
Settings displayed Indigo/Orchid/Blue/Rose; rose/light and blue/dark were visibly
checked, Orchid selected, and the palette survived reload. Chinese settings
preserved composition and translated all new controls. Original EN/dark/indigo
preferences were restored. Approved brand assets were not modified.

Screenshots: [Azure OpenAI form](evidence/azure-visual-skin/azure-openai-form.png),
[rose light EN](evidence/azure-visual-skin/rose-light-en.png).

## Design provenance and differences

- Composition: `Orena-Admin.dc.html` A1 Overview and A3 provider configuration;
  `Orena.dc.html` frame 26 Settings, adapting the existing device-preference row
  for the explicitly approved accent selection. No separate palette page.
- Visual treatment: original `Orena Visual Skin EN.html` and `Orena Visual Skin
  ZH.html`, decoded as data and read without executing their scripts. Their
  Board theme/accent mapping owns shared tokens; screen pins own composition.
- ZH treatment: Noto Sans SC UI fallback, Noto Serif SC learning prose, 2.2 line
  height. Admin prose uses Literata/Noto Serif SC instead of Source Serif 4.
- Measured AA deviations remain: darker blue/rose small text and darker action
  fills carrying white labels; existing D-093 fixes remain. Capability colours
  and Intelligence gradient do not follow the selected accent.
- Browser could not open file:// prototype exports under its URL policy. Source
  comparisons were used; no attempt was made to bypass that restriction.
- No complete whole-app fidelity claim. Phone viewport acceptance remains open
  because the browser viewport override previously left actual width at 1910px.

## Validation and review

Local execution: 125 Python tests passed (Azure, credential security, AI control
plane, pronunciation and Admin routes). Admin screen/control, Settings, copy
(45 tables/2587 keys), browser ESM (332 modules), kit token/provenance and AA
(58 existing pairs plus alternative action-fill contrast) gates passed.
No CI PASS claimed.

Independent reviewer `/root/review_media_basic` reviewed this Azure working diff,
including the environment-key test correction, and found no remaining actionable
P1/P2; APPROVE is engineering review, not human product approval. Reviewer did
not run Docker or tests. Implementer ran the checks above.

## Remaining bounded acceptance

Azure OpenAI has no sandbox credential/deployment: no live generation/routing
success claimed. New credential entry belongs to the operator. Live Speech
authentication was tested; no new recorded-audio assessment or paid generation
was performed in this slice. Full pronunciation telemetry in AI operations and
multi-deployment discovery remain later refinements, not invented UI data.
Finish bounded operator acceptance, then return to canonical Grammar/runtime
and integrated Intelligence/Agent under their existing contracts. Preserve
accepted Books/Progress/Listening work; do not restart an app audit.
