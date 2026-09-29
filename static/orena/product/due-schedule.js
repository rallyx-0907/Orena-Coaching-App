/* When a saved item next comes due, from its own real review schedule - never a guess. Shared by
   every screen that shows a saved word's due line against the same `dueToday`/`dueInDays` copy
   pair (`screens/word/copy.js`, `screens/review/copy.js`, `screens/quick-sheet/copy.js`):
   `dueInDays` needs `t.plural()`, since the real day count can be exactly 1 ("Review in 1 day",
   not "Review in 1 days").

   Moved out of `screens/word/model.js` (2026-09-29, overlays fix pass): `screens/quick-sheet/
   model.js` had grown a byte-for-byte copy of the same function, and the two had already drifted
   (quick-sheet's caller read the flat, non-pluralised key its own copy table declared). One
   function, one place, both screens import it - rule 40 (never invent a due date) and the D-079
   plural convention now have exactly one implementation to keep correct. */
export function dueInfo(item, now = Date.now()) {
  const raw = String(item?.next_review_at ?? '').trim();
  if (!item || !raw) return null;
  const at = Date.parse(raw);
  if (!Number.isFinite(at)) return null;
  const days = Math.ceil((at - now) / 86400000);
  if (item.due || days <= 0) return { key: 'dueToday' };
  return { key: 'dueInDays', n: Math.max(1, days) };
}
