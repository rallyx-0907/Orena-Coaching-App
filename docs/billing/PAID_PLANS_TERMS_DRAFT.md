# Draft: paid-plan terms and refund policy (English only; for the owner, not published)

**Status: a draft for the owner.** It is not on any public page. The public Terms
(`docs/legal/public/terms.en.json`) currently say:

> "When paid plans launch … We will update these Terms, and tell you the price, renewal, cancellation and refund
> rules, before you are charged anything."

So gate 7b cannot open sales until the owner approves this text and it is added to the public Terms, with a Refund
Policy. The legal pages are **English only** (owner, 2026-10-19): every interface language links to the English page.
The UI lane owns `docs/legal/public/` and its D-entry; this lane supplies the billing facts.

Every sentence below states what the code does today, with its source. A bracketed **[owner]** item is a
policy the code does not settle.

## Draft text

### Paid plans

1. **Plans and prices.** Orena offers Free, Plus and Pro.
   - Plus costs US$9.99 a month or US$79.99 a year.
   - Pro costs US$19.99 a month or US$159.99 a year.
   - Prices are charged in US dollars in every language. The limits of each plan are shown on the Plans page.
   - Voice chat with Orena is included in Plus and Pro only.

   *Source:* D-MON-032, D-MON-034, `writing_coach/product/catalog.py`, and the owner's decision of 2026-10-19 on
   voice chat.
2. **Who charges you.** Payments are processed by Polar (polar.sh), which acts as the merchant of record. Polar charges
   your card, handles taxes and issues your invoices. Orena never receives or stores your card details.

   *Source:* D-MON-032, D-MON-033.
3. **Automatic renewal.** A paid plan renews automatically at the end of each month or year, on the card you
   registered, until you cancel.

   *Source:* D-MON-032.
4. **Cancelling.** You can cancel at any time from Plan & usage. Your plan stays active until the end of the period
   you have paid for, and is not renewed.

   *Source:* readiness items 6 and 8, proven on the sandbox.
5. **Changing plan.**
   - An upgrade applies at once, and you are charged the difference for the rest of the current period.
   - **[owner]** A downgrade made in Polar's customer portal also applies at once. Whether the unused part of the
     higher plan is credited to the next invoice is being checked on the sandbox (subscription D, 2026-10-19).
   - In the app, a downgrade is made by cancelling at the period end.

   *Source:* readiness items 5, 6 and 7.
6. **Failed payment.** If a renewal payment fails, your plan stays active for 2 days after the end of the period you
   paid for, while Polar retries the payment. After that, your account has Free's limits until the payment succeeds.
   If the payment succeeds later, the paid plan returns. If Polar stops retrying, the subscription ends.

   *Source:* D-MON-011 and `writing_coach/product/billing_grace.py`.
   - The grace is counted from `paid_through`.
   - `BILLING_PAST_DUE_GRACE_HOURS` defaults to 48 and can be set from 0 to 336. The published number must equal the
     value set on the host.
   - The run on sandbox subscription F, on 2026-10-19, is still being observed.
   - **[owner]** Before publishing, choose whether to promise that learning data is kept. No billing code deletes
     it, but no billing document promises it either.

### Refund policy

7. **[owner]** The refund rule, for example "no refunds for partial periods, except where the law requires" or "full
   refund within N days of the first charge". The code supports a full or partial refund issued from Polar's
   dashboard.

   *Mechanism, not for publishing:* after a refund, access follows the subscription's state on Polar. The text that
   is published comes from item 9.

   *Source:* readiness item 12.
8. **How to ask for a refund.** Email `orena.support@chillpickle.org` from the address of your Google account.

   *Source:* D-162 (operator and contacts).
9. **[owner]** Whether a refund also ends the plan at once, or only at the period end.

## Before gate 7b opens sales

- The owner approves items 7 and 9, and the data line in item 6, and checks item 5 after the D result.
- The voice-chat decision of 2026-10-19 is recorded as a D-entry.
- The UI lane adds the approved text to the English Terms, and adds the Refund Policy, if separate, to the public
  pages.
- The clickwrap under "Continue with Google" links to them.
