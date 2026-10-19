/* A content level, as the learner reads it (PRE-204, owner decision of 2026-10-18): a level the catalogue only
   estimated ("deterministic-estimate", no reviewed level) carries the same short "est." qualifier the app already
   uses for an estimated word timing (compare, listening); a reviewed level reads plain. No new visual. */
import { shellCopy } from '../copy/shell.js';

export const ESTIMATED_SOURCE = 'deterministic-estimate';

/* The media payloads name the source (`level_source`); an item that sends only an estimate (no `level`) is one too. */
export function levelIsEstimated(item) {
  if (!item) return false;
  if (item.level_source === ESTIMATED_SOURCE) return true;
  return !item.level && Boolean(item.estimated_level);
}

export function levelWithQualifier(level, estimated) {
  const text = String(level || '');
  return text && estimated ? `${text} · ${shellCopy('levelEstimated')}` : text;
}

/* One call for a card or a meta line: the item's level, qualified when the item says it is only an estimate. */
export function itemLevelLabel(item) {
  return levelWithQualifier(item?.level || '', levelIsEstimated(item));
}
