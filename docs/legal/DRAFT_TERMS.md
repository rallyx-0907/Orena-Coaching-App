> **DRAFT — not legal advice — requires the human's approval and, ideally, a lawyer's review before publication.**

# Orena — Terms of Use (DRAFT)

Last updated: [DATE]. Version: draft 0.1 (2026-10-04).

---

## Note to counsel (strip before publishing)

Orena is expected to be run by a Vietnam-based operator. To check with counsel, not claimed as done:

- Decree 13/2023/ND-CP (personal data protection) and the Law on Consumer Rights Protection 2023: which terms must be shown, how consent and unfair-term rules apply to a click-through contract, and whether a standard-form contract must be registered or notified.
- E-commerce rules (Decree 52/2013/ND-CP, as amended): whether the operator must notify or register the site and show specific seller information.
- Whether a Vietnam-law governing clause and a court or arbitration forum are valid for consumers outside Vietnam. This draft does not claim Orena complies with any of these.

---

# English

## 1. Who we are
Orena ("Orena", "we", "us") is a language-learning service run by [OPERATOR], [ADDRESS]. Contact: [EMAIL].

## 2. Agreeing to these terms
By signing in or using Orena you agree to these Terms and to the Privacy Policy and Refund Policy. If you do not agree, please do not use Orena.
[DECISION: minimum age and rule for minors, for example 16+, or under 16 with a parent or guardian's consent.]

## 3. Your account
- You sign in with your Google account. We do not ask you to create a separate password.
- Keep your Google account secure. You are responsible for what happens under your account.
- Give us accurate information and use one account per person.

## 4. What Orena offers
Orena helps you learn a language through writing, reading, listening, speaking, vocabulary and grammar practice, and an AI coach. Features may change, be added or be removed. Some features may depend on your plan.

## 5. AI features: please read
- Some features use AI. AI can be wrong. Corrections, scores, translations, pronunciation feedback and coach replies are learning aids, not professional, academic or official assessments.
- Do not rely on Orena for exams, immigration, legal, medical or other high-stakes decisions.
- To produce AI results, your text or audio is sent to third-party providers. See the Privacy Policy.

## 6. Your content
- You keep ownership of what you write, record, import or save ("Your Content").
- You give us permission to store it, process it and show it back to you, and to send it to our AI providers, only to run Orena for you.
- Only add content you have the right to use. Imported private content stays yours; do not import material you are not allowed to copy.
- We do not use Your Content to train our own models. [DECISION: confirm this statement with the operator and with each AI provider's current terms before publishing; the repository does not prove provider-side training settings.]

## 7. Our content and licences
- Orena's software, design, name, logo and the Orena mascot belong to [OPERATOR] or its licensors.
- Orena includes third-party dictionaries, data, fonts and software under open licences (for example CC-CEDICT, Wiktionary-derived data, Unicode Unihan, Lucide icons). Credits are listed in the app, in Settings, Plan & privacy, Licences and data sources. Their own licences, including share-alike terms, continue to apply to that material.
- Reading and listening texts come from sources we have admitted for use, or from you. Each text keeps its own source and rights.

## 8. Acceptable use
Do not: break the law; try to break, overload or scan Orena; share your account; scrape or copy content in bulk; upload content that infringes others' rights or is harmful; use Orena to harass others; try to misuse AI features (for example to make harmful content).

## 9. Plans, payment and free use
- Orena has a free level. Paid plans may be added. Payment is not live yet.
- When live, prices, what each plan includes, renewal and cancellation are described at purchase and in the Refund Policy.
- Payments are planned through a Vietnamese gateway ([GATEWAY NAME]; QR bank transfer or e-wallet) and, for international cards, a merchant of record ([MERCHANT OF RECORD]) who may be the seller of record for those purchases.
- [DECISION: plans, prices, currencies, taxes shown inclusive or exclusive, trial, and usage limits.]

## 10. Ending your use
- You may stop using Orena at any time.
- Account deletion: [DECISION: how a learner requests deletion today. At the time of drafting, the repository records a policy that deletion is permanent and a deleted account is never restored, but no self-service deletion feature exists yet. Say "email [EMAIL]" or "in Settings" only when true.]
- We may suspend or close an account that breaks these Terms or the law, or to protect Orena or other learners. [DECISION: notice period, and appeal path.]

## 11. Availability
Orena is provided "as is" and "as available". We try to keep it running but do not promise it will be uninterrupted or error-free. Features that depend on third-party providers may be unavailable at times.

## 12. Limits of liability
To the extent the law allows, [OPERATOR] is not liable for indirect or consequential loss, or for losses from AI output, third-party services or lost data, and our total liability for a claim is limited to [DECISION: cap, for example the amount you paid in the previous 12 months]. Nothing here limits rights you have under mandatory consumer law, including the Law on Consumer Rights Protection, or liability that cannot be limited by law.

## 13. Changes
We may update these Terms. We will tell you in the app or by email [DECISION: notice period, for example 14 days] before important changes take effect. Continuing to use Orena after that means you accept them.

## 14. Governing law and disputes
These Terms are governed by the laws of [DECISION: Socialist Republic of Vietnam, to confirm with counsel]. Disputes go to [DECISION: court or arbitration centre, location]. Please contact us at [EMAIL] first so we can try to solve it.

## 15. Contact
[OPERATOR], [ADDRESS], [EMAIL].

---

---

## Sources in the codebase (internal appendix; strip before publishing)

- Google sign-in, scopes openid/email/profile, verified email required: `auth_support.py` (lines ~139-147, ~313).
- AI by third parties: `writing_coach/ai/providers.py` (ollama, groq, gemini), `writing_coach/speech_asr.py` (Groq), `writing_coach/speech_pronunciation.py` (Azure Speech).
- Learner-owned records on the server: `docs/project/DECISION_LOG.md` D-104 (H-18).
- Account deletion policy (permanent, never restored) but no runtime: D-054, D-055 in `docs/project/DECISION_LOG.md`; `writing_coach/persistence/deletion_enumeration.py` ("no runtime deletion path exists").
- Licences list and credits page: `THIRD_PARTY_NOTICES.md`, `writing_coach/licences.py`, `GET /api/licences`.
- Plans/subscriptions model exists, payment providers not activated: `writing_coach/persistence/models.py` (plans, plan_entitlements, subscriptions), `docs/project/ORENA_BACKBONE_INTEGRATION_GATES.md`.
- Payment gateway and merchant of record: human instruction, not in the repository (placeholders).
- Not found in the repository: any statement about provider-side model training, minimum age, or governing law.
