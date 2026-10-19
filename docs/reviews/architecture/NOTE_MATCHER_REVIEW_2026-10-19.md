# Coach-note matcher and the note-change nudge (PR #347, closes #346): independent review (2026-10-19)

- **Reviewer:** Claude (Opus 5.5), independent and read-only, over six rounds.
- **Final round:** `de3c8e2f`, **APPROVE**, with no P0 or P1.
- **The risk (#346):** a message matched to a coach note by rule, but really a learning question, could be answered "which note?". Worse, a compliant model could be told to delete or overwrite a note nobody asked about.

| Round | Outcome | What was fixed |
| --- | --- | --- |
| 1 (`22263de8`) | APPROVE, P1 left open | Stop phrases ("giúp mình", "帮我"…); "lưu ý" and 记录 dropped from the note nouns. |
| 2 (`3bf411a5`) | CHANGES REQUIRED | "quên", 忘 and "forget" alone mean "I forget": a forget needs an imperative or a note noun. |
| 3 (`e0f740dd`) | CHANGES REQUIRED | "I forget" is never an imperative, VI tails are narrowed, more real forget phrasings are covered. |
| 4 (`21930956`) | CHANGES REQUIRED | **Structural safeguard:** the nudge orders a change only when the message names a note (`names_a_note`); otherwise it is conditional. 把…忘了 needs 吧; bare 忘了 at the start no longer counts; the Chinese clause-wide self-forget check. |
| 5 (`65123c2a`) | CHANGES REQUIRED | The answer is replaced only when a note is named, the intent is forget, or a keep was confirmed. `replaces` is filled in only when a note is named or nothing new is asked. 那条 is out. Strong and pronoun self-forgets are split. |
| 6 (`de3c8e2f`) | **APPROVE** | A closing particle must close the verb's own clause. |

**After approval:** P2 "quên … rồi" in one clause also means "I forgot", with a negative test.

**Open, follow-up:** "ghi chú", "note" and 笔记 are also the Reader's annotation words, so a request about a Reader note gets the explicit nudge. Tracked in a new issue.

**Accepted trade:** on an unnamed correction where the model omits `replaces`, the server still fills it in (the plain implicit correction "À không, ví dụ dài hơn…" depends on it), unless the message asks to keep something new.
