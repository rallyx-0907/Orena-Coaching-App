> **DRAFT — not legal advice — requires the human's approval and, ideally, a lawyer's review before publication.**

# Orena — Refund Policy (DRAFT)

Last updated: [DATE]. Version: draft 0.1 (2026-10-04).

**Status: payments are not live yet.** This policy describes the planned model and takes effect when paid plans launch.

---

## Note to counsel (strip before publishing)

To check with counsel, not claimed as done:

- Law on Consumer Rights Protection 2023: consumer rights on digital content and services, return or cancellation rights for distance contracts, and limits on terms that exclude refunds.
- E-commerce rules (Decree 52/2013/ND-CP, as amended): displaying prices, payment, cancellation and refund terms on an e-commerce site.
- Decree 13/2023/ND-CP: payment data handled by the gateway and the merchant of record.
- For international card payments, the merchant of record's own refund rules and who is the legal seller; this policy must not contradict them.
- Tax invoices and refunds (VAT) for Vietnamese buyers.
This draft does not claim compliance with any of these.

---

# English

## 1. Summary
- Orena has a free level and may offer paid plans.
- You can cancel a plan any time. You keep your plan until the end of the period you paid for.
- Refunds are available in the cases below.

## 2. Plans and renewal
- Plans: [DECISION: names, for example Free, Plus, Pro; monthly and yearly options].
- Prices: [AMOUNT] per [PERIOD], shown at purchase with taxes [DECISION: included or excluded].
- Renewal: [DECISION: automatic renewal, or manual one-time purchases per period. For Vietnamese QR bank transfer and e-wallets, automatic charging may not be possible.] If a plan renews, we will remind you [DECISION: [N] days] before it does.
- Price changes: we tell you [DECISION: [N] days] before a new price applies to your next renewal.
- Free trial: [DECISION: whether there is one, and its length].

## 3. Cancelling
- Cancel in Settings, Plan & privacy, or by writing to [EMAIL]. [DECISION: confirm the cancel method that will exist at launch.]
- After cancelling, your plan stays active until the end of the paid period, then returns to the free level. Your account and learning data stay (see the Privacy Policy).
- If a payment fails, we keep your plan for a grace period of [DECISION: [N] days] before it ends.

## 4. When you can get a refund
- **Within [N] days of your first purchase** if you have not used more than [DECISION: usage threshold, for example [AMOUNT] of AI units] of the paid features. [DECISION: window and threshold.]
- **Renewals:** you may ask for a refund within [N] days of a renewal charge if you did not use the paid features. [DECISION.]
- **Charged by mistake or twice:** full refund.
- **Service problem:** if a paid feature is unavailable for [DECISION: duration] because of us, we refund or extend the plan for the affected period.
- **Where the law gives you a right** to cancel or a refund, you keep it. Nothing in this policy reduces it.

## 5. When we usually do not refund
- After the refund window, or after you used the paid features beyond the threshold.
- Partly used periods after you cancel mid-period. [DECISION: prorated refund or none.]
- Because AI feedback is not what you hoped. AI can be wrong; please tell us at [EMAIL] and we will look.
- Bans or closures for breaking the Terms of Use.

## 6. How to ask
Write to [EMAIL] with the account email, the date and the amount. We reply within [DECISION: [N] business days].

## 7. How we pay you back
- Refunds go to the original payment method: bank account or wallet for a purchase through [GATEWAY NAME]; card for a purchase through [MERCHANT OF RECORD].
- Time to arrive: [DECISION: typically [N] business days, depending on your bank or the provider].
- For international card purchases, [MERCHANT OF RECORD] may handle the refund under its own terms.
- Currency and fees: [DECISION: who bears gateway or transfer fees; exchange-rate handling].

## 8. After a refund
The paid plan ends at once, or on [DECISION: date]. Your account stays on the free level.

## 9. Contact
[OPERATOR], [ADDRESS], [EMAIL].

---

---

## Sources in the codebase (internal appendix; strip before publishing)

- Payments are not live; plan, price, grace and meter values are human-gated and not chosen in the repository: `docs/project/ORENA_BACKBONE_INTEGRATION_GATES.md` (lines ~76-100: "No speculative ... commercial price is chosen here"), `docs/project/DECISION_LOG.md` D-054 ("Still the human's: plans, prices, quota or entitlement values, retention durations ... billing").
- Data model for plans, entitlements, subscriptions, usage: `writing_coach/persistence/models.py` (`plans`, `plan_entitlements`, `subscriptions`, `usage_events`); commerce read endpoint behind Settings, Plan & privacy: `static/orena/screens/settings/screen.js` (`GET /api/product/commerce`).
- Duplicate or reversed provider subscription events are handled as canonical state: `ORENA_BACKBONE_INTEGRATION_GATES.md` line 53.
- Gateway (domestic QR bank transfer / e-wallet) and merchant of record (international cards): human instruction, not in the repository (placeholders).
- Not found in the repository: refund windows, trial, grace length, renewal mode, cancel flow.
