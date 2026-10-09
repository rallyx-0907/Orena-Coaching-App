# Public Privacy and Terms: what changed from the design's text, and why (PUB-2, D-162)

The pinned design's legal text (`Orena-Privacy.dc.html`, `Orena-Terms.dc.html`, revision of 2026-10-09) described
things Orena does not do. The human authorised replacing the WORDS (2026-10-09, D-162); the structure (13 sections,
same headings and order, summary card, contents list, contacts, footer), layout and tone are unchanged. Vietnamese
and English change in parallel; one row covers both. Old text is shortened. Evidence is file:line on this branch.

Source of the new text: `docs/legal/public/*.json` and `facts.json`. Audit: `PUB2_PRIVACY_TRUTH.md` claim ids
(P = Privacy, T = Terms) in the first column.

## Privacy Policy

| Audit | Old (short) | New (short) | Evidence |
| --- | --- | --- | --- |
| P1 | "We don't sell personal data and we don't run ads." | kept | no ad/tracker code (grep of `static/`, `templates/`, `app.py`, `requirements.txt`) |
| P2/P15/P16 | Summary: "Voice recordings are kept only if you turn that option on." Sect. 5: "Keep recordings for playback ... stored in your account" | "Orena's servers do not keep your voice recordings. Any recording kept for playback stays on your own device." Sect. 5: audio is sent for transcription or scoring and not kept by the servers; recordings for playback stay in the browser tab; where Orena lets you keep recent ones, up to five per line stay on the device, never uploaded | `speech_api.py:428,443`, `speech_pronunciation.py:136-139`, `agent/voice_session.py:1-20`, `capabilities/speaking-attempts.js:4-5,82-87`, `screens/attempts/copy.js` (privacyNoteSession/Kept). No UI toggle for keep-recent exists today, so the text does not name one |
| P3/P23 | Summary: "Export or delete all your data at any time in Settings." | "You can ask us to delete your account and data by email: see Delete account." | no export or delete-account route or UI: `screens/settings/model.js` privacyRows; `persistence/incarnation_repository.py:7`; `persistence/deletion_enumeration.py:1-5` |
| P4 | Summary: "AI providers may use your data only to answer your request." | "Some AI and speech features send what you submit or record to service providers that process it for us to return the result." | provider terms are not provable from the repo (human: do not name vendors) |
| P30 | Sect. 1: "web and mobile apps, orena.app" | "the Orena web app, any Orena app that connects to it (e.g. an Android app), the website where this page is published"; operator RallyX, Vietnam | mobile frozen (AGENTS.md 5); `orena.app` has no evidence; human decision on operator |
| P5 | Account: "Display name, email, profile photo and sign-in method (email, Google or Apple)" | Google sign-in only; stores Google account ID, email, name, picture link, interface and learning language, weekly goal, account type, sign-up and last sign-in times; scopes openid, email, profile; no password | `auth_support.py:164-175`, `persistence/auth_repository.py:98-153` |
| P6 | Learning data list | kept, plus listening, speaking, grammar progress and review history | `persistence/models.py` (grammar_progress, listening_progress, shadowing_progress, speaking_attempts) |
| P7 | Content: "writing, answers, notes, questions to Orena Intelligence, books or documents you upload" | writing and its AI evaluations, answers, drafts, notes and highlights, saved conversations and place in a text, text discussions, imported books, documents and media; stored on our servers for signed-in learners | `essays`, `text_discussion_turns` (`models.py`); `ORENA_ACCOUNT_BACKBONE=on` on :8000 (coordinator, 2026-10-09); D-104; `media_library_api.py:293-302` |
| P2 | Voice audio card: "Recordings made when you practise speaking..." | "...sent for processing and is not stored on our servers" | as P2 |
| P8/P11 | Payments card: "plan, transaction history and donations; card numbers handled by our payment partner" | "Plan and usage": payments not live, no card numbers, payment details or transactions; a plan an administrator assigns by hand during the beta records only the plan and its limits | `billing/service.py:44`, `billing/gateway.py:15`, `product/api.py:68,82` (`billing_ready: False`); D-154 |
| P9/P10 | Device card: "device type, OS, browser, language, IP address, access times, crash reports" | servers and hosting/network providers see IP, requests, times and may keep operational logs; account-linked records (Orena Intelligence request time and kind without text; feedback rating, areas, up to 600 characters); AI use and cost counts without content; no advertising, analytics or crash-reporting service | `agent/timeline.py:1-12`, `feedback.py:17`, `ai/audio_telemetry.py:1-12`, `ai/account_costs.py:1-20`; no SDK in `requirements.txt`, `static/`, `templates/` |
| P11 | Use: "Process payments and send receipts and account notices." | "Show your plan and apply its usage limits." | no payment or email-sending code |
| P10 | Use: "improve the product using aggregated statistics" | "using our own aggregated usage counts" | `writing_coach/admin_metrics.py`, `usage_events` |
| P12 | "We send marketing email only with your consent ... unsubscribe link" | "Orena does not send marketing email." | no email/newsletter code |
| P13 | Sect. 4: text/audio sent "to the AI model provider we work with ... never your email or payment details" | any AI feature (feedback, translation, dictionary, discussion, pronunciation) sends the needed text or audio to AI and speech service providers that process it on our behalf; level and target language included; Orena Intelligence requests are stripped of name, email, picture, account IDs | `agent/redaction.py:15-45` (verified for Orena Intelligence only, so the claim is limited to it) |
| P4 | Sect. 4: contracts forbid training and require deletion after a short period | removed; instead: providers may be outside Vietnam, we do not control their systems, do not submit what you do not want processed this way | provider terms unverifiable |
| P14 | "Orena uses the microphone only when you tap record." | kept | `capabilities/mic-readiness.js` |
| P17 | Sharing: processors incl. "payment partners, email delivery and crash reporting" | hosting and network providers, AI and speech providers; Google (sign-in); other services a feature needs, described by function: dictionary and word-pronunciation lookups (the word only), YouTube on import (link sent; browser loads player and thumbnails, IP seen), public media hosts such as Wikimedia for some material (IP seen) | `app.py:2410` (dictionary), `word_audio.py:63,222`, `media_providers/youtube.py:54,287-291`, `media_thumbnail.py:159`, `capabilities/media-player.js:16-22` |
| P18 | "Some processors host servers outside Vietnam" | "Some of these providers host servers..." | kept in substance |
| P19 | Retention: "30 days primary / 90 days backups after deletion; transaction records longer" | account and learning data kept while the account exists; no delete button yet, deletion by email, manual, within 30 days; Orena Intelligence records 90 days, feedback 24 months, AI cost records 13 months; backups up to `backup_days` days (pending); device recordings stay until deleted | `agent/retention.py:21`, `feedback_retention.py:1`, `ai/account_costs.py:27`; `scripts/runtime_backup.py` has no rotation; human decisions |
| P20 | Rights: "View and edit your personal information in Profile." | language and weekly-goal settings editable in the app; name, email, photo come from Google | `persistence/auth_repository.py:34,145-146` |
| P3 | Rights: "Export all of your learning data in a readable file." | "Ask us what personal data we hold about you, by email. There is no self-service export yet." | no export route. This is a commitment the operator must be able to keep |
| P21 | "Delete individual items (voice recordings, question history) or your entire account" | delete items where the app offers it (essays, saved words, library items, text discussions, imported media) or ask us to delete the account | `app.py:3208,2756,4031`, `library_api.py:143`, `deck_api.py:138`, `text_discussion.py:282`, `media_library_api.py:302` |
| P22 | "Withdraw consent ... marketing email" | device data cleared by clearing site data; microphone permission withdrawn in the browser or device | no marketing |
| P23 | "Most of these are available in Settings -> Privacy ... respond within 15 working days" | "For requests the app cannot handle yet, including account deletion, contact us ... we respond within 30 days." | Settings -> Privacy has no such rows; 30 days is the human's deletion commitment, applied to all requests (operator to confirm) |
| P24 | "encrypted in transit and at rest. Internal access limited by role and logged" | "encrypted in transit with HTTPS. Access to administration tools is limited to administrator accounts, and administrator actions are logged" | `core/deployment.py:138-157`, `core/http_security.py:32,61`, `auth_support.py:144-157`; at-rest encryption is not provable |
| P25/P26 | Cookies: "cookies and browser storage ... theme, language and reading position. We use aggregated analytics ..." | one signed session cookie (up to 14 days); local storage for theme and language and, only if kept, recent recordings; pages and fonts served from Orena itself; no analytics or third-party advertising cookies | `auth_support.py:613-618`, `kit/boot.js:18`; fonts self-hosted (D-162) |
| P27/T12 | Children: "Users under 16 need parental consent ..." | "Orena is for people aged 13 and over. Orena does not check your age when you sign in; Google has its own age rules. If we learn an account belongs to someone under 13 we delete it." | no age gate in code (grep birth/age/parental); human decision min age 13 |
| P28 | "notify you in the app or by email at least 14 days before" | "We publish changes on this page. For significant changes, we update this page at least 14 days before they take effect." | no in-app notification system or email sender (`settings/model.js:135-139`) |
| P29 | Contact | kept; adds "Orena is operated by RallyX, Vietnam" | human decision |
| (new) | Google Fonts not disclosed | not needed: fonts are self-hosted | `templates/orena/index.html`, `static/orena/fonts/`, gate section 6 |

## Terms of Service

| Audit | Old (short) | New (short) | Evidence |
| --- | --- | --- | --- |
| T1 | Intro: "when you create an account, learn, buy a plan or support the project" | "...when you create an account and use Orena", operated by RallyX, Vietnam | no purchase or donation flow |
| T2 | Summary: "Paid plans renew automatically; cancel any time in Profile." | "Paid plans are not live yet; during the beta an administrator may assign a plan to an account." | `billing/service.py:44`; D-154 |
| T8 | Summary: "Donations are voluntary and never required" | "You can ask us to delete your account at any time, by email." | Donate not built (PUB-3) |
| T12 | Sect. 1: "Users under 16 need consent from a parent or guardian." | "You must be at least 13 years old to use Orena." | as P27 |
| T5 | Sect. 2: "keeping your password safe", "provide accurate information when you sign up" | "You sign in with a Google account. Keep it secure ..."; plus a pointer to Delete account | no passwords exist (`auth_support.py:164-175`) |
| T1/T2/T3 | Sect. 3: free plan and paid plans "listed on the Pricing page"; prices include taxes; cards: Automatic renewal (7-day reminder), Cancelling in Profile, Refunds (7 days; App Store or Google Play policy), Price changes (30 days) | Orena has a free plan; paid plans are not available and nothing is a charge; limits depend on the plan and are shown in the app; an administrator may change a plan by hand during the beta; cards: "Payments" (not live, no payment details collected) and "When paid plans launch" (terms updated and rules told before any charge) | no renewal, refund, reminder or store-billing code; `product/api.py:68,82`; "Manage plan" inert (UI_BACKEND_GAPS N-31 note) |
| T4 | Sect. 4: donations via the Support Orena page, recognition badge, refund and monthly rules | "Orena does not accept donations yet. If that changes, we will update these Terms first." | Donate page not built (PUB-3, D-160) |
| T8 | Sect. 9: "You can delete your account at any time in Settings." | "You can ask us to delete your account at any time by email ... we process requests by hand within 30 days." | no in-app deletion |
| T9 | Sect. 9: "If a paid account is terminated ... we refund the unused portion." | removed | no paid accounts |
| P28 | Sect. 11: "notify you in the app or by email at least 14 days before" | "publish the update on this page at least 14 days before it takes effect" | no notification or email system |
| P29 | Sect. 13 | kept; adds operator line | human decision |
| T6, T7, T11 | Content licence incl. sending to AI providers; imported material visible only to you; scores are guidance, not IELTS/HSK | kept | `media_library_api.py:293`; D-107 |
| T10 | Sect. 10 liability cap "previous 12 months"; Sect. 12 governing law Vietnam | kept: a legal drafting decision for a lawyer; no entity beyond the operator name is published | not verifiable by code |

## New page

`/account-deletion` (VI and EN): how to ask (email the support address from the Google account's email), what is
deleted (the enumeration in `persistence/deletion_enumeration.py:12-50` plus the tables and stores it misses, see
`docs/project/ACCOUNT_DELETION_RUNBOOK.md`), what is kept (a content-free deletion record, backups until
overwritten, operational logs, data already with service providers, device-local data), processing by hand within
30 days. No commitment beyond the human's decision.

## Later changes (2026-10-09, human decisions on the PR)

- The three pages are static HTML (no script needed; one file per language); layout measured identical to the previous pages.
- Age: Terms 1 and Privacy 11 now also say no date of birth is collected and there is no technical age gate during the beta
  (evidence: no birth/age/parental code; `auth_support.py:164-175`).
- Backups: "up to 30 days" now has a mechanism (`scripts/runtime_backup.py rotate`).

## Facts the text states and who must confirm them

`docs/legal/public/facts.json`: publish date (null in the repository; stamped at deploy with `--release
--effective-date YYYY-MM-DD`, which fails without it). Minimum age 13, Orena Intelligence records 90 days, feedback 24
months and backups 30 days are the human's decisions of 2026-10-09; the retention statements are true only once
`AGENT_TURN_RETENTION_SWEEP` and `FEEDBACK_RETENTION_SWEEP` are ON and backup rotation is applied on the public host.
