# Terms insert for paid plans (ready to fill; English only)

**Status: prepared, not applied.**

This file replaces section "3. Plans and payment" of `docs/legal/public/terms.en.json` when gate 7b opens sales.
The facts behind each sentence, with their sources, are in `PAID_PLANS_TERMS_DRAFT.md`.

Three placeholders wait for the owner, and **no agent fills them**:

| Placeholder | The owner's question | Example answers (not chosen) |
| --- | --- | --- |
| `[REFUND_RULE]` | When is a payment refunded? | "Payments are not refunded for partial periods, except where the law requires it." / "You can ask for a full refund within 14 days of your first payment." |
| `[REFUND_PLAN_EFFECT]` | What happens to the plan after a refund? | "A refunded plan ends at once." / "A refunded plan stays active until the end of the period." |
| `[DATA_RETENTION_AFTER_CANCEL]` | What happens to learning data when a plan ends? | "Your learning data stays in your account on the free plan." |

## How to apply it (after the owner answers)

1. The UI lane owns `docs/legal/public/`. It pastes the block below as the `"3. Plans and payment"` section, fills the
   three placeholders word for word, and sets `effective_date` in `facts.json`.
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
        ["Changing plan", "An upgrade applies at once, and you are charged the difference for the rest of the current period."],
        ["Failed payment", "If a renewal payment fails, your plan stays active for 2 days after the end of the period you paid for while the payment is retried. After that your account has the free plan's limits until the payment succeeds."],
        ["Refunds", "[REFUND_RULE] [REFUND_PLAN_EFFECT] To ask for a refund, email orena.support@chillpickle.org from the address of your Google account."],
        ["When a plan ends", "[DATA_RETENTION_AFTER_CANCEL]"]
      ]
    }
  ]
}
```

The downgrade sentence for Polar's portal is left out until subscription D's result (2026-10-19) shows whether
the unused part is credited. Add it then, worded from the evidence.
