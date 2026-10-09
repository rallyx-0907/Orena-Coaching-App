# Google Play Data safety form: answers for Orena (PUB-2, D-161)

Internal. Not published. Each answer matches the public Privacy Policy as revised in D-161
(`docs/legal/public/privacy.en.json`), and points at the evidence. Change the policy and this file together.
Rows that wait on a fact still `null` in `docs/legal/public/facts.json`, or on a human decision, are marked **PENDING**.
Assumption: the Play app is a client for this same web backend (web view, TWA or a thin native shell). If the shipped
build adds a diagnostics or advertising SDK, this file and the policy are wrong until updated (none exists today:
`requirements.txt`, `static/`, `templates/`; `mobile/` is frozen).

## 1. Overview questions

| Console question | Answer | Basis |
| --- | --- | --- |
| Does the app collect or share any of the required user data types? | Yes | sections 3-4 |
| Is all of the user data collected by your app encrypted in transit? | Yes | HTTPS is required in public environments (`core/deployment.py:138-157`), HSTS (`core/http_security.py:61`), Secure session cookie. Policy sect. 9 |
| Do you provide a way for users to request that their data be deleted? | Yes | `/account-deletion` (email from the Google account's email; manual; 30 days at most). In-app per-item deletes exist for essays, saved words, library items, text discussions and imported media. There is no in-app delete-account button |
| Account creation methods | OAuth (Google sign-in). No username/password | `auth_support.py:164-175` |
| Delete-account URL (Play Console "Data deletion" section) | `https://<public host>/account-deletion` | **PENDING**: the public host is not fixed in the repo (docs mention `orena.chillpickle.org`, `PROJECT_STATE.md:228`); the human supplies the URL registered in Play |
| Data deletion URL / request without deleting the account | same page, section 4 (per-item deletes) | |
| Privacy policy URL | `https://<public host>/privacy` | **PENDING** host, as above |
| Independent security review | No | |
| Target audience | 13 and over; not designed for children; not in the Families programme | human decision 2026-10-09 (`facts.json` `min_age` 13; stays 13, not 12). No date of birth is collected and there is no technical age gate in the beta; accounts found to belong to someone under 13 are deleted. Not in the Families programme |
| Ads | No ads, no ad SDK | policy summary; no ad code |
| Data sold | No | policy sect. 6 |

## 2. How sharing is classified

Google's form does not count a transfer to a service provider that processes data on the developer's behalf as
"sharing". Orena's AI and speech providers (section 5) receive the text or audio of a feature only to return the result,
and the public text says exactly that. The rows below therefore answer **Shared: No** for those transfers. This is the
developer's classification, and the human should confirm it: if a provider's terms let it use the data for its own
purposes, the answer for text, audio and messages becomes **Shared: Yes**, and the policy sentence changes with it.
Sign-in with Google, and a learner's own import of a YouTube link, are not sharing for the form either (the learner asks for the transfer).

## 3. Data collected

"Optional" means the learner can use the app without it.

| Play data type | Collected | Shared | Ephemeral | Required / optional | Purposes | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Personal info: Name | Yes (from Google) | No | No | Required (sign-in) | Account management, App functionality | `persistence/auth_repository.py:132-153` |
| Personal info: Email address | Yes | No | No | Required | Account management, App functionality | same; verified email required `auth_support.py:401` |
| Personal info: User IDs (Google account ID, internal ids) | Yes | No | No | Required | Account management, App functionality | same |
| Personal info: Other info (profile picture link) | Yes | No | No | Required | Account management | `users.picture`; not sent to AI (`agent/redaction.py:15-45`) |
| Messages: Other in-app messages (Orena Intelligence conversations, text-discussion questions, feedback text up to 600 characters) | Yes | No (provider processing, section 2) | No | Optional | App functionality | `text_discussion_turns`; `works` with the backbone on; `feedback.py:17` |
| Audio: Voice or sound recordings | Yes (uploaded for transcription and pronunciation scoring) | No (provider processing, section 2) | **Yes**: the server does not store it | Optional (microphone permission, learner taps record) | App functionality | `speech_api.py:428,443`, `speech_pronunciation.py:136-139`, `ai/audio_telemetry.py:1-12`; device-only playback `capabilities/speaking-attempts.js` |
| Audio: Other audio files (learner-imported audio) | Yes, if the learner imports | No | No | Optional | App functionality | `media_library_api.py:293-302`; owner-scoped (D-107). **PENDING**: only if the Play build offers import |
| Photos and videos: Videos (learner-imported video) | Yes, if the learner imports | YouTube link sent to YouTube at the learner's request (not sharing) | No | Optional | App functionality | same. **PENDING**, as above |
| Files and docs (imported books, documents, text) | Yes, if the learner imports | No | No | Optional | App functionality | same; `works` private imports. **PENDING**, as above |
| App activity: App interactions (progress, attempts, scores, review history, plan, usage counts) | Yes | No | No | Required for the features | App functionality, Personalization, Analytics (own aggregated usage counts only) | `models.py` progress tables, `usage_events`, `admin_metrics.py` |
| App activity: Other user-generated content (writing and its evaluations, drafts, notes, highlights, saved words) | Yes | No (provider processing, section 2) | No | Optional | App functionality, Personalization | `essays`, `works`, `saved_words`; ORENA_ACCOUNT_BACKBONE=on on :8000 |
| App activity: Search history / Installed apps / Other actions | No | | | | | |
| App info and performance: Crash logs, Diagnostics, Other performance data | No | | | | | no client SDK. Server-side AI telemetry is not tied to the account and not collected by the app (`ai/audio_telemetry.py:1-12`); the human confirms this reading |
| Device or other IDs | No | | | | | no advertising or device identifier read. The server and its providers see the IP address like any web service (policy sect. 2 "Technical records"); the human confirms whether Play wants that declared |
| Financial info (payments, purchase history, credit score) | No | | | | | billing off: `billing/service.py:44`, `product/api.py:68,82`; policy sect. 2 "Plan and usage" |
| Location, Contacts, Calendar, Health and fitness, Web browsing, SMS, Call log | No | | | | | none found |

## 4. Retention and deletion statements used elsewhere

- Account and learning data kept while the account exists; deletion by email within 30 days at most (`/account-deletion`).
- Orena Intelligence turn records 90 days (`agent/retention.py:21`) and learner feedback 24 months
  (`feedback_retention.py`): **true only when `AGENT_TURN_RETENTION_SWEEP=on` and `FEEDBACK_RETENTION_SWEEP=on`**; they are
  unset on :8000 today, the human decided to turn both on at deploy. AI cost records 13 months
  (`ai/account_costs.py:27`).
- Backups: up to 30 days (`retention.backup_days` = 30), enforced by `python scripts/runtime_backup.py rotate --dir <backup
  dir> --days 30 --apply` (tested; `scripts/test_runtime_backup.py`). **Applying it on the :8000 host, at least daily, is
  part of the human-gated deploy**; until then the statement is not yet true there.

## 5. Internal providers (never named in public text)

Verified by coordinator 2026-10-09 against :8000 (names and booleans only, no key values). Re-verify before release.

| Provider | State on :8000 | What it receives | Code |
| --- | --- | --- | --- |
| Google Gemini API (text) | ACTIVE: writing evaluator/improver/task generator, dictionary, translation, reading generator, text discussion, grammar lessons, Orena Intelligence default (gemini-3.5-flash-lite) | task text (agent context is redacted of name, email, picture, ids) | `ai/providers.py:924-935` |
| Groq (speech-to-text) | ACTIVE: ASR model whisper-large-v3-turbo | learner audio for transcription | `speech_asr.py:276,336` |
| Microsoft Azure Speech | ACTIVE: pronunciation assessment, word text-to-speech | learner audio and reference text; word text | `ai/azure.py:30,48`, `speech_pronunciation.py:375`, `word_audio_azure.py:176` |
| Self-hosted Ollama and local translator | URLs present | text; no third party | `ai/providers.py:237`, `vocabulary_localization.py:430` |
| Google OAuth | ACTIVE | sign-in | `auth_support.py:164-175` |
| Cloudflare tunnel | a cloudflared container runs beside the staging stack: HTTPS proxy/CDN (processor). Public text says "hosting and network providers" | all HTTPS traffic | `compose.yaml` |
| YouTube | on learner import (oEmbed, transcripts, audio download); browser loads the player and thumbnails | the video link; the visitor's IP at the browser | `media_providers/youtube.py:54,287-291`, `media_thumbnail.py:159` |
| dictionaryapi.dev, Wikimedia Commons | server-side English lookup and word-audio lookup; browser loads some Wikimedia media | the word looked up | `app.py:2410`, `word_audio.py:63,222`, `listening_catalog.py:50` |
| OpenAI, DeepSeek, Azure OpenAI | INACTIVE (no keys) | nothing | `ai/providers.py:884-910` |
| Gemini Live voice | INACTIVE (`AGENT_VOICE_ENABLED=false`) | nothing. If it is enabled, live conversation audio goes browser to Google: the policy's "audio ... sent to service providers" covers it, and the Audio row above applies | `ai/live_voice.py`, `agent/voice_session.py` |
| Supadata | key present, `MEDIA_TRANSCRIPT_FALLBACK=none`: INACTIVE | nothing | `media_providers/supadata.py:18` |
| Kokoro TTS | not configured | nothing | |
| Polar, payOS (billing) | INACTIVE (billing not enabled) | nothing | `billing/polar.py:39`, `billing/payos.py:32` |

## 6. Release checklist for this form

1. Set `AGENT_TURN_RETENTION_SWEEP=on` and `FEEDBACK_RETENTION_SWEEP=on` before publishing the policy.
2. Apply backup rotation on the :8000 host (daily `rotate ... --apply`). At deploy run `node
   scripts/build_public_pages.mjs --release --effective-date YYYY-MM-DD` (the date of first public deployment);
   it fails while any fact is unconfirmed or the date is missing.
3. Confirm the classification in section 2 and the two readings flagged in section 3 (diagnostics, IP address).
4. Put the real host into the Play Console privacy-policy and delete-account URLs.
5. An independent architecture review of `docs/project/ACCOUNT_DELETION_RUNBOOK.md` is recorded in Git before the
   first manual deletion.
