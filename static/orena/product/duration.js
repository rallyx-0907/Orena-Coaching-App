/* A length of time as the pinned design renders it on a card/segment badge: "M:SS", minutes
   unpadded, seconds always two digits (orena-script.js's own `fmt` - `Math.floor(t/60)+":"+
   pad(t%60,2)`, confirmed against the design's "1:18" video-card example). Never invented (0
   renders "0:00" - a genuine zero, not an absent field; a caller with no duration_ms at all
   should not call this and should omit the badge instead, rule 40).

   D-091 first moved this from ui/content.js on the assumption the old UI wanted the identical
   string. It does not: the old UI's own gate (scripts/test_orena_library.mjs) fixes its minutes
   at two digits ("00:46"), a different, deliberate contract for that design generation. Restored
   ui/content.js's own local copy of the old formula rather than reconciling the two into one -
   this module now carries only the new learner UI's format, for screens/discover/model.js
   (and later new-UI screens with the same duration pill). */
export const duration = (ms) => {
  const seconds = Math.round((Number(ms) || 0) / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
};
