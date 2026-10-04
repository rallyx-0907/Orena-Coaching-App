# My Library correction / Speaking continuation ? 2026-10-03

MILESTONE=Library overlap and interaction correction
STATUS=REVIEWABLE
COMMIT=see this checkpoint's Git commit
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/library?tab=language
HOW_TO_REACH_IT=My Library ? Saved content / Saved language

## Change and provenance

Canonical `Orena.dc.html` frame 12 and its libLanguage/onSource handlers own
composition and interaction. Existing Visual Skin EN/ZH semantic tokens remain
the visual treatment; no palette, brand or screen redesign.

Inline title/source/word/meaning spans prevented bounded ellipsis and overflowed
into other cards and actions. They now render as block lines in the same measured
layout. Saved language text is a keyboard-accessible button opening Word Detail;
pronunciation remains a separate action. Tab query survives Back and reload.
Imports subscriptions now return the router's cleanup.

## Browser evidence

Real :8021 account data, without deleting/importing/replacing user records:
- Saved content: all card scroll widths bounded; More opens its own menu, Close
  returns to cards without opening the item.
- Saved language: 24 real rows, including a very long stored definition. Before:
  main scroll width 8740px and no word-open actions. After: 1668px main at 1910px
  viewport, zero overflowing rows, 24 word-open actions.
- beginning ? real Word Detail with meaning/pronunciation/context ? Back returns
  to Saved language. Reload preserves `#/library?tab=language`.
- Actual 390?844 browser override: zero overflowing language rows and content
  cards. Override reset after verification.
- Screenshots: `evidence/library-fix/content.png`, `language.png`,
  `phone-language.png`, `speaking-entry.png`.

EN_PARITY=EN desktop and phone browser verified
ZH_PARITY=language-neutral shared fix; ZH browser not claimed in this batch
CROSS_CAPABILITY_STATUS=Saved word ? Word Detail ? same Library tab verified
TESTS=Local Library/Speak/Compare/Free Talk/Speaking Summary Node gates and 332-module ESM graph PASS; not CI evidence
WHAT_THE_HUMAN_SHOULD_REVIEW=long card titles, long saved meanings, More, word tap and Back; learner collections/decks still truthfully unavailable

## Speaking ? IMPLEMENTING, not complete

Preserved current recorder, source, assessment, comparison and server-backed
history work. Browser confirmed Practice Hub ? Free Talk setup with real saved
words, and Scripted Pronunciation with a real Cosmic Calendar target sentence.
No pronunciation scores displayed before an attempt; Mine disabled without audio.

Speak now leaves the shared delayed loading skeleton to the router; Compare
uses the same loading primitive directly. There is only one loading owner per route. Unreturned Fluency displays an unavailable
dash and is omitted from session facts, never a fabricated measured zero.
Regression test first failed on that zero, then passed after correction.

Live recording/provider/feedback/compare/history acceptance is still open.
Automatic approval review initially rejected Start speaking without specific
microphone authorization. The user subsequently explicitly authorized local
:8021 recording and Azure Speech assessment. The actual Record ? Allow microphone
sheet was exercised; the browser permission request has not yet returned. A
request to the user to accept Brave's native prompt is pending. No score/result
has been fabricated and no synthetic capture substituted.

Independent read-only review found no Library regression. Two Speaking findings
(duplicate loading owner, unavailable metric shown as poor-score track) were
corrected and rechecked; stale comment corrected. Local focused gates and ESM
passed after these deltas. Azure OpenAI operator acceptance, Grammar and
integrated Intelligence remain later basic gaps; no whole-app audit restarted.
