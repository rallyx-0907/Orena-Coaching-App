# Terms insert for paid plans (ready to fill; English only)

**Status: the owner approved the text, which is not published yet** (D-MON-037, 2026-10-19). He approved the
Renewal, Cancelling, Refunds, Asking for a refund, Disputes and "When a paid plan ends" cards word for word. Any
wording change needs a new approval. The downgrade sentence will be approved separately. The text is published only
when sales open.

This file replaces section "3. Plans and payment" of `docs/legal/public/terms.en.json` when gate 7b opens sales.
The facts behind each sentence, with their sources, are in `PAID_PLANS_TERMS_DRAFT.md`.

**The owner's answers (2026-10-19, relayed by Hermes):**
- **A refund ends the plan at once** (D-MON-035): filled in below.
- **Learning data after a paid plan ends is kept for 3 months** (D-MON-035, 10:20): filled in below. The text must not
  suggest that the account is deleted. Free data stays under the Privacy Policy.
- **The refund rule follows Claude's (Anthropic's) model, adapted** (D-MON-036, 10:35): filled in below. The text
  was checked against Polar's buyer terms and refund documentation.
- **A downgrade credits the unused part:** its sentence is added once subscription D shows how Polar applies it.

No placeholder is left. The block stays unpublished until sales open.

## How to apply it (after the owner answers)

1. The UI lane owns `docs/legal/public/`. It pastes the block below as the `"3. Plans and payment"` section and
   sets `effective_date` in `facts.json`.
2. Check before merging:
   - `2 days` equals `BILLING_PAST_DUE_GRACE_HOURS` on the host (48 hours, the default). Change both together.
   - The prices equal the Polar products (gate 7b P1) and the catalogue.
   - The voice minutes equal `VOICE_MINUTES_PER_DAY`, or the stored catalogue (D-237).
3. Rebuild the public pages (`scripts/build_public_pages.mjs`) and run the gate that compares them.
4. Publish **before** `BILLING_NEW_SALES` is opened. The current Terms promise these rules before any charge.

## The block

```json
{
  "h": "3. Plans and payment",
  "blocks": [
    { "p": "Orena has a free plan and two paid plans, Plus and Pro. Plus costs US$9.99 a month or US$79.99 a year. Pro costs US$19.99 a month or US$159.99 a year. Prices are charged in US dollars, whatever language you use Orena in. The usage limits of each plan are shown in the app. Voice chat with Orena is a feature of Plus and Pro, with a daily limit on voice minutes shown in the app; the free plan chats with Orena in text. Speaking practice does not depend on that limit. An administrator may change the plan or limits of an account by hand." },
    {
      "cards": [
        ["Who charges you", "Payments are processed by Polar (polar.sh), the merchant of record. Polar charges your card, handles taxes and issues your invoices. Orena never receives or stores your card details."],
        ["Renewal", "A paid plan renews automatically at the end of each month or year, on the card you registered, until you cancel."],
        ["Cancelling", "You can cancel at any time in the app. Your plan stays active until the end of the period you have paid for and is not renewed."],
        ["Changing plan", "An upgrade applies at once: the unused part of your current plan counts towards the new one, and you are charged the difference for the rest of the current period."],
        ["Failed payment", "If a renewal payment fails, your plan stays active for 2 days after the end of the period you paid for while the payment is retried. After that your account has the free plan's limits until the payment succeeds."],
        ["Refunds", "Payments are non-refundable, except in the cases below or where the law where you live requires a refund. We refund: (a) a duplicate charge, or a charge made in error by a payment fault; (b) a period in which a problem on Orena's side made the paid features unusable for most of that period; (c) if you live in the European Economic Area or the United Kingdom, a refund you ask for within 14 days of the purchase, less the part of the period you have already used; (d) other cases, at Orena's discretion. In these cases we ask Polar, our merchant of record, to refund you. A refunded plan ends at once, and your account returns to the free plan."],
        ["Asking for a refund", "Email orena.support@chillpickle.org from the address of your Google account, with the date of the charge. We check the request against these rules and reply. Refunds are issued through Polar, our merchant of record, to your original payment method where possible. Polar's buyer terms also apply: Polar makes the final refund decision and may refund a payment itself."],
        ["Disputes", "If you have opened a dispute or chargeback with your bank for a payment, we do not process a refund for it until the dispute is closed or withdrawn."],
        ["When a paid plan ends", "When a paid plan is cancelled, expires or is refunded, your account stays open on the free plan. We keep your learning data for 3 months, so you can continue where you left off if you return to a paid plan. After those 3 months, data that only a paid plan provides may be deleted. Your account and the data the free plan covers are kept while your account is active, as described in the Privacy Policy."]
      ]
    }
  ]
}
```

The downgrade sentence is left out until subscription D's result (2026-10-19) shows how Polar credits the unused
part. The owner's rule is that it is credited (D-MON-035). Add the sentence then, worded from the evidence.
