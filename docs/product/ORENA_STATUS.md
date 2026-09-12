# Orena product status

Branch: `codex/work`

CURRENT_MILESTONE: ORENA_WEB_GOLDEN_STAR_V1

STATUS: IMPLEMENTING

The three findings from the earlier capability-direction review are closed in
`docs/project/GOLDEN_STAR_COMPLETION.md`. Golden Star remains IMPLEMENTING.
The current human ruling assigns architecture and shared contracts to Codex,
feature implementation to Opus; see `ORENA_REFERENCE_ARCHITECTURE.md` and the
current handoff. Encounter word exploration was completed by Opus; see its
recorded evidence in the completion ledger. The principal backbone now has
dedicated account/profile, commerce, Collection, execution and Growth contracts;
integration packages are in ORENA_BACKBONE_INTEGRATION_GATES.md under docs/project.
These contracts do not claim deployed sync, billing, achievements or product approval.
The earlier execution evidence below is historical, not a fresh full-suite,
browser or live-provider claim from the architectural handoff.

The human-authorized D-046 reset supersedes the discarded experience mission.
Discovery, intentional Practice, continuation, imported content and recalled
language converge on a new encounter product layer. Synchronized Follow is a
required capability. No human approval of the new implementation is claimed.

WEB_URL: http://localhost:8011/#/

WEB_ROUTE: /#/

HOW_TO_REACH_IT: Internal local review runtime; normal account/profile bootstrap.

The new web product renders from static/orena and templates/orena. The old
static/becoming learner product and seven obsolete product specifications have
been removed. The foundation slice is now functionally coherent end to end and
ready for human review; no human approval is claimed.

Verified by browser acceptance against a real server, at 1440 / 800 / 390 px, in
light and dark, in English and Chinese: every route renders with no horizontal
overflow, no text below its WCAG AA contrast threshold and no pointer target
under 24px. Follow keeps original text, contextual Pinyin and support meaning
synchronized and shows the current line at rest. The canonical deep journey runs
end to end - a media encounter, Follow, Dictation with comparison and durable
evidence, "look closer" on the line just practised, keeping that phrase, and the
hand-off into Recall - and the thread shelf then offers all three archetypes
back. Learner-imported media reaches every Practice intent beside the curated
catalog. Authored grammar notes join the canonical catalog by stable Concept ID
and are labelled as generated. Listening evidence is not overwritten when the
stored record cannot be read first. Local suites sit at 787 passed / 20 failed,
the 20 being the inherited baseline; the rich provider paths now have
deterministic provider-injected coverage of their grounding rules.
Microphone-dependent paths were not executed. This is execution evidence, not
milestone acceptance.

Learning workspace: consuming and producing have different shapes. Following a
voice is content; reconstructing a line is work, so when a practice opens the
encounter re-composes - source on one side, work on the other, both in the
first viewport, each scrolling on its own. Narrow, the source becomes a compact
sticky strip and the work is brought to the learner rather than left below a
screenful of media.

One-frame learning loop (D-051, `DESIGN_CONTRACT.md`): on a 1440 desktop the
activity and its immediate result now share the first viewport in Writing
(draft beside its review), Speaking (situation and take beside what was heard,
evidence and coaching - other starting points moved below) and Dictation
(source beside the work; the comparison arrives inside the practice panel, no
page scroll). At 800 and 390 the same rooms take the activity, then the result
the learner is placed at the start of, below the sticky header, with a way
back. Activity rooms open compactly without artwork; the way back to Practice
sits above the heading instead of repeating the room name under it. Optional
notes - draft kept on this device, what the task field is for, where a
recording lives, what a comparison does not measure, possible mishearing - are
now symbols whose words appear on hover, focus or tap; instructions and the
consent statement before a recording is sent stay as text. Browser-verified in
the running sandbox: Writing against local Ollama (two real reviews), Speaking
with a fake microphone and an injected transcript fixture (placement, not
recognition quality), Dictation with real comparison, all four themes, EN and
ZH, 1440 / 800 / 390 without horizontal overflow.

Phone learning space (D-052): below 900px the header compacts from 131px to
57px while the learner scrolls into a room and returns on a deliberate scroll
up, near the top or when opening the destinations; sticky source strips and
result frames sit below it at its current height. At 390px the Writing editor
grows from 112px to about 310px with the whole activity and its action still in
the first screen, and a Writing or Speaking result frame now runs from 65px to
the bottom of the screen. Listening shows the voice as an 80px strip (was 174px)
and puts the transcript directly under the spoken line and its meaning, so the
current line, its meaning and several transcript lines share one screen;
transcript rows are 61px (were 85px). Reading, Grammar, Speaking, Recall and
feedback are set denser without falling below readable size, and every phone
control keeps a 44px target. Verified in the running sandbox at 390 and 800 in
EN and ZH and in Night Ink; Writing through two real local-Ollama reviews.
The same rules now reach the remaining rooms: Shadowing and Speaking inside a
lesson fit one phone screen under the voice strip; Reading comprehension has
44px choices lighter than their question and its score lands below the header;
a conversation opens without artwork with the reply box in the first screen,
and a partner's reply arrives in view with the box to answer it; Discover, My
content and Collection keep their artwork but a two-line heading, compact rows
and one row of lenses. On a desktop, Follow puts the spoken line and the
transcript beside the video, so the line, its meaning and "look at the words"
with its guide are in the first screen from 1024x640 up.

The approved red-panda library is in the product. Fifty-two approved assets
existed and four were reachable, one of them doing duty as both the arrival and
the empty state; thirty are now addressed by what a moment means - discovery,
reading, listening, conversation, writing, remembering, completion, empty - so
each experience looks like itself without any surface knowing a file path.
Artwork is framed at its own measured ratio and never repainted to match a
theme; the three scenes carrying printed caption strips are framed to the art
above them.

Dictation's hint is the shape of the line, present from arrival and following
what the learner types: word boundaries, each word's length, and a mark for
every character still to find. Each character supplied correctly appears the
moment it is supplied, wherever it sits in the word, and a word fully right is
simply the word. Alignment runs at word level and then character level inside a
matched word, so an insertion or deletion early in the line does not shift the
anchors after it. Nothing is shown that the learner did not produce, and the
deeper level opens at most one unfound character per word and never its last,
so a hint cannot become the reveal.

Shared foundation: tinted panels carry their own ink in both themes, work that
leaves the device reports through one primitive whose retries are always wired,
disabled controls are inert, and the companion scene is framed by the artwork's
own ratio. `docs/product/ORENA_WEB_EXTENSION_GUIDE.md` records what a new
surface inherits and the checks it owes before it is called done.

Learning capabilities now built on that foundation:

- **Pure Listening** is a complete experience, not a corridor to an exercise.
  Follow opens no practice panel; asking what a line means pauses the voice and
  says so, so understanding never costs the learner their place; reaching the
  end is recognised - not scored, opening nothing - and offers hearing it again
  or reading it through; and the transcript can show the meaning of every line
  from the translations the lesson already ships. It tracks the spoken word
  where an asset ships word timing and falls back to the segment where it does
  not. A spoken segment reads as one block - when it was said, the line, then
  what it means underneath - so following a line and understanding it are one
  act rather than two columns to reconcile, and the active line highlights
  whole. Support text ships in its own writing system: Vietnamese with its
  diacritics, held by the catalog contract. Dictation, Shadowing and Speaking
  remain optional deeper paths.
- **Dictation** offers a live character mask: the line takes shape from the
  learner's own correct characters, and the hint ladder never completes a word
  for them.
- **Reading** carries a published library beside generated passages and the
  learner's own text. A text becomes published only with cleared rights, an
  evidence URL, a verification date and a record of what was changed - the
  admission rule matters more than the two seed texts behind it. Comprehension
  is optional and pure reading is valid, so a text without questions says so
  both in the list and when opened, and no questions are invented to make every
  text look alike.
- **Reading** is a real experience with its own intention. A learner asks for a
  passage by form and subject; it arrives in the same encounter as every other
  text, with highlight-to-explain, keeping into the collection, and an optional
  comprehension check whose every answer names the words in the passage that
  settle it and marks them there. It reuses the existing reading service rather
  than a Reading-only engine, and labels a built-in passage as built-in. The
  readable contract now states what a text must carry, including author,
  licence and source in the same shape media uses, so books, public-domain
  works and articles can be added with an adapter rather than a redesign.
- **Writing** shows the full review the evaluator returns - weighted
  dimensions, CEFR, strengths quoted from the learner, issues with the reason
  and the rule - and never strikes through words the learner did not write.
  The final evidence boundary also drops strengths that do not quote the exact
  submitted text and drops incomplete corrections rather than presenting a
  label without an explanation or reusable rule. Every canonical English and
  Chinese feedback category has a learner-readable label in either interface
  language.
  Revising is where writing is learned, so a new version is compared with the
  last: which problems are gone, which are still there, which arrived, which
  were reworked, and which dimensions moved. The learner can say what they are
  writing - a lab report, a message to a landlord - so domain choices are not
  marked as mistakes. Register exploration puts one meaning across
  conversational, professional, formal, academic and technical with the signals
  that place each and when each is the wrong choice; it is a comparison, not a
  rewrite button, and no version is presented as the correct one.
- **Speaking** can now be an exchange rather than a single take. A
  conversation runs over the same recorder and coaching the room already uses;
  the partner is explicitly simulated, never claims to have heard a voice, and
  never corrects - so each of the learner's own turns carries the question
  "how did that land?", answered by the shared coaching surface. Partner turns
  do not, because coaching is about the learner's words.
- **Speaking** is also its own single-take experience: a situation or the
  learner's own prompt, a take, the words recognition returned, evidence,
  guidance, another try. What
  was measured and what is coaching are separate panels making separate claims;
  coaching reads the transcript and says so, never claiming to have heard the
  voice. Free expression reports alignment as not applicable, because there was
  no line to match.
- **Grammar** teaches each pattern against the thing it is not. Beside the
  pattern sits what a learner actually writes instead, struck through, with the
  problem named in the shared judgement vocabulary and the reason authored in
  every support language - so "not possible in this language" means the same
  here as in a writing review. Every example can ask its own question, carrying
  the pattern as the context it sits in.
- **Vocabulary** is practised rather than reread: a kept word asks about itself
  using the sentence it was saved from, so the answer is about how the word
  worked there rather than a dictionary entry.
- **One contextual explanation system** serves reading, listening, writing,
  speaking, grammar and vocabulary, naming which of six things is wrong rather
  than saying "wrong" and answering follow-ups without losing the selection.
  Every capability reaches it with the learner's own wording and the context it
  sat in, and a deeper question keeps that context however long the learner
  keeps asking.
- **What Orena remembers** is no longer an anonymous card. A phrase kept
  anywhere records where the learner met it, a human name for that place, the
  sentence it sat in and why they kept it - so the collection can say "From
  something you read · The last train home" and lead back to the passage
  itself. This is device memory beside the account's own record of the word
  and its review history; the surface says so rather than implying otherwise.
- **Recall** asks the question the phrase's own history calls for. Something
  met while reading comes back inside its sentence with the phrase withheld;
  something the learner said comes back meaning-first, to be said again;
  language from their own writing comes back as a question about where they
  would use it, with the way into a draft. Nothing invents mastery: seeing a
  card is not recall, and a forgotten word never loses the successes it already
  earned.

Microphone and successful/live-provider paths are unexercised in this runtime
and are not claimed. The EN/ZH Writing 503 path is browser-verified: it keeps
the draft, target and task, distinguishes a retryable interruption, and the
retry resubmits. With no provider configured, review, explanation, registers
and spoken coaching degrade honestly rather than inventing an answer.

Operator note: the Platform Admin web surface has no host template since the
reset removed `templates/index.html`; its API and script remain. Whether Orena
keeps that page, and where, is an open human decision recorded in
`docs/project/CURRENT_HANDOFF.md`.

NEXT_REVIEWABLE_SLICE: Human browser review of the learning capabilities and the shared understanding that connects all of them, Grammar and Vocabulary included. After that review, the open product decisions in `docs/project/CURRENT_HANDOFF.md` - Speaking's cross-turn conversation architecture, Reading library sourcing and rights, Grammar breadth, and the Platform Admin host - need judgement before more capability breadth is added. Native remains frozen.
