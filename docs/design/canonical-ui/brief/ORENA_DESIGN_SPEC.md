# ORENA — DESIGN & INTERACTION SPEC
## Product template, screens, functions and interaction flows

**Purpose:** Đây là tài liệu tự đủ để một design agent chưa từng biết Orena có thể thiết kế lại toàn bộ sản phẩm từ đầu.  
**Scope:** Learner app + Admin appendix.  
**Focus:** cấu trúc sản phẩm, màn hình, chức năng, vùng UI, hành động, gesture, trạng thái và luồng thao tác.

---

# 0. PRODUCT MODEL

Orena được tổ chức quanh 6 primary learner destinations:

1. **Today** — Những gì đáng chú ý và đáng làm hôm nay.
2. **Discover** — Tự tìm nội dung, chủ đề hoặc nguồn học.
3. **Orena** — Orena Agent: trợ lý trung tâm hiểu context học tập và giúp người học tìm, hiểu, chọn và đi tới hành động phù hợp.
4. **Practice Hub** — Chủ động luyện kỹ năng và quay lại các task đang làm dở.
5. **My Library** — Những gì người học đã lưu, đã gặp, cần ôn hoặc muốn quay lại.
6. **Progress** — Nơi người học thường xuyên quay lại để thấy mình đang tiến bộ ra sao, duy trì động lực và biết nên tập trung vào đâu tiếp theo.

Các surface quan trọng nhưng không chiếm primary navigation:

- **Profile / Settings** — tài khoản và preference.
- **Search** — global action.
- **Reading / Listening / Speaking / Writing / Grammar** — experience/workspace được mở từ các destination phù hợp.

Reading, Listening, Speaking, Writing không phải bốn app con độc lập. Chúng là các experience nối với cùng một learner memory, evidence và Orena Agent.

**Continue không phải destination.** Mọi task chưa hoàn thành xuất hiện trong **Practice Hub → In Progress** và có thể được mở lại đúng trạng thái trước đó.

---

# 1. PRIMARY NAVIGATION

## Desktop

Persistent primary rail:

- Today
- Discover
- Orena
- Practice Hub
- My Library
- Progress

Orena có visual identity nổi bật như Orena Agent, nhưng Progress vẫn là một destination ngang cấp vì đây là màn learner có lý do quay lại thường xuyên.

Bottom/account area:

- avatar
- Profile
- Settings
- Admin entry if authorized

## Mobile

Persistent bottom destinations:

- Today
- Discover
- Practice
- Library
- Progress

`Practice` là short label của **Practice Hub**.  
`Library` là short label của **My Library**.

### Orena on mobile

Orena là **central persistent agent action** gắn với navigation shell, không bị giấu trong More/Profile.

Recommended pattern:

- một Orena button nổi/nhô lên ở trung tâm bottom navigation; hoặc
- một central action có visual weight khác với 5 destination tabs.

Tap Orena → mở Orena Agent full destination.

Cách này giữ đủ 6 primary destinations mà không ép sáu label ngang nhau trong 360–390px.

Profile mở từ avatar/account control, không chiếm một primary tab.

## Related entry points

Progress vẫn có thể được mở thêm từ:

- Today progress/evidence preview;
- Practice results;
- My Library;
- Profile;
- Orena when the learner asks about progress.

Nhưng các entry này chỉ là shortcut. Progress vẫn có destination riêng trong primary navigation.

## Search

Search là global action, không phải destination riêng.

Có thể mở từ:

- global top utility;
- Discover;
- My Library;
- keyboard shortcut trên desktop.

---

## 1.1 TEMPLATE REFERENCE MAP

Các sản phẩm dưới đây chỉ là reference cho **information hierarchy, behavior và interaction pattern**. Tất cả surface vẫn thuộc cùng một Orena product system.

| Orena surface | Behavioral references |
|---|---|
| Today | Mindvalley, Spotify, Headway |
| Discover | Spotify, Netflix, YouTube |
| Orena | Mindvalley EVE, ChatGPT |
| Practice Hub | Brilliant, Elevate, Duolingo |
| My Library | Spotify Library, Readwise, Kindle |
| Reading | Readwise Reader, Kindle |
| Listening | Spotify, Audible |
| Speaking | ELSA, Speak |
| Writing | Grammarly, DeepL Write |
| Progress | Duolingo, Elevate, Strava-style progress motivation patterns |
| Profile | Duolingo, Strava, Mindvalley |

Shared-product rule:

- shell/navigation;
- typography hierarchy;
- spacing;
- component language;
- states;
- sheets;
- feedback behavior;
- interaction vocabulary

remain consistent across Orena.

A practical target is roughly **80% shared Orena system + 20% workspace-specific adaptation**.

---

# 2. CORE PRODUCT RELATIONSHIP

```text
TODAY
  ├─ personalized recommendations
  ├─ review reminder
  ├─ small progress/evidence signal
  └─ entry to relevant destination

DISCOVER
  ├─ READ
  ├─ LISTEN / WATCH
  ├─ COLLECTIONS
  ├─ SEARCH
  └─ IMPORT

ORENA
  ↔ learner context
  ↔ content discovery
  ↔ explanations
  ↔ recommendations
  ↔ navigation/actions
  ↔ Reading / Listening / Speaking / Writing / Vocabulary context

PRACTICE HUB
  ├─ IN PROGRESS
  ├─ SPEAK
  ├─ WRITE
  └─ FOCUSED PRACTICE

MY LIBRARY
  ├─ SAVED CONTENT
  ├─ SAVED LANGUAGE
  ├─ COLLECTIONS
  ├─ DUE REVIEW
  ├─ RECALL / TRANSFER
  └─ RECENTLY ENCOUNTERED

PROGRESS
  ├─ OVERVIEW
  ├─ TRENDS
  ├─ KNOWING → USING
  ├─ EVIDENCE
  ├─ RANK
  └─ HISTORY

READ / LISTEN
  ↓
ENCOUNTER USEFUL LANGUAGE
  ↓
SAVE TO MY LIBRARY
  ↓
RECALL
  ↓
USE
  ↓
TRANSFER
  ↓
AUTOMATICITY
  ↓
PROGRESS EVIDENCE
```

Reading và Listening chủ yếu là **content-first**.

Speaking và Writing chủ yếu là **production-first**.

Vocabulary, Grammar, saved phrases và Recall tạo thành **learner memory layer**, chủ yếu được truy cập từ My Library và Practice Hub.

Progress là **evidence + motivation layer** và là một primary destination.

Orena Agent cắt ngang toàn bộ hệ thống: người học có thể vào Orena trực tiếp hoặc gọi Orena từ context đang học.

---

# 3. LEARNING EVIDENCE MODEL

Orena theo dõi 5 mức:

## Recognition

Người học nhìn/nghe thấy và nhận ra.

## Recall

Không thấy đáp án nhưng tự nhớ ra.

## Use

Tự dùng đúng trong câu hoặc thông điệp.

## Transfer

Dùng đúng sau khi đổi context.

## Automaticity

Phản ứng đủ nhanh để sử dụng tự nhiên hơn.

UI không bắt buộc hiển thị 5 thanh %.

Có thể hiển thị trạng thái dạng:

- Recognized
- Recalled
- Used
- New context
- Fast recall

Status:

- completed;
- partial;
- not tested.

---

# 4. LANGUAGE LAYERS

Mọi UI copy thuộc một trong 3 lớp:

## Interface language

Navigation, button, system label.

Ví dụ:

- Today
- Save
- Continue
- Retry

## Support language

Explanation, hint, translation, coaching, feedback.

## Target language

Nội dung người học đang học.

Ví dụ:

- bài đọc;
- transcript;
- model sentence;
- vocabulary;
- learner response.

Ba lớp này độc lập.

---

# 5. GLOBAL APP SHELL

## Desktop top bar

Có thể chứa:

- page context;
- global search;
- target language indicator;
- notifications nếu có;
- avatar.

## Mobile top bar

Tối giản:

- page title/context;
- search khi cần;
- avatar.

## Focus workspace

Các màn học sâu:

- Reader
- Listening Workspace
- Dictation
- Speaking recorder
- Writing editor

sẽ giảm chrome.

Chỉ giữ:

- Back
- current source/task
- task-specific controls

Bottom nav có thể ẩn trong focus workspace.

---

# 6. GLOBAL INTERACTION OBJECTS

## Quick Sheet

Dùng để xem nghĩa/giải thích mà không rời context.

### Word mode

- word
- pronunciation / Pinyin
- POS
- contextual meaning
- source sentence
- Save
- Why here?
- deeper explanation

### Sentence mode

- selected sentence
- translation
- structure
- important vocabulary
- explanation
- Save
- Ask deeper

### Desktop

Side panel hoặc large contextual panel.

### Mobile

Bottom sheet.

### Behavior

- tap word → open
- select sentence → open
- close → return exact position
- current media timestamp / reader scroll position preserved

---

## Contextual Bottom Sheet

Dùng cho:

- word;
- sentence;
- grammar;
- issue detail;
- filters;
- quick settings.

Gestures:

- drag up to expand;
- swipe down to dismiss.

---

## Save

Can save:

- word;
- phrase;
- sentence;
- highlight;
- content.

Save updates instantly.

Fail → revert + local error.

---

## Focus Mode

Shared high-attention mode for Reader, Dictation, Speaking recording, Writing editor and focused Grammar practice.

Behavior:

- reduce navigation/chrome;
- keep the current task and local controls;
- opening/closing a contextual panel must not reset the task;
- exiting Focus Mode returns to the exact previous state.

---

## WHY / HOW

A reusable contextual interaction for source text, learner text and feedback.

### WHY

Explains why a word, sentence, correction or pattern matters in this exact context.

Possible content:

- concise reason;
- meaning difference;
- grammar reason;
- naturalness/register reason;
- contrast.

### HOW

Explains how to improve or reuse it.

Possible content:

- preferred wording;
- reusable pattern;
- contrast;
- another example;
- Practice This.

Entry points include Reading, Listening transcript, Writing findings, Speaking feedback and Grammar.

---

## Word-role / POS Lens

Optional semantic highlighting layer across:

- Reading;
- Listening transcript;
- Writing;
- explanations.

Possible groups:

- noun;
- verb;
- modifier;
- connector;
- pronoun/reference;
- number/quantity;
- language-specific roles.

Interaction:

- toggle on/off;
- tap/hover token → role explanation;
- preference can persist.

Chinese segmentation must be language-aware.

---

## Pinyin / Pronunciation Assistance

Relevant Chinese surfaces can support:

- Off;
- On;
- Auto / Adaptive;
- Reveal on demand.

Pinyin stays visually attached to the Hanzi it explains.

Dictation may show a reading directly under individual characters when that mode enables it.

---

## Notifications

Can notify for:

- completed Writing analysis/review;
- saved learner work;
- due Review;
- finished media/transcript preparation;
- system/account events.

Tap → exact related result/screen.

---

# 6A. DISTINCTIVE CAPABILITY INVENTORY

The new design must explicitly support the following non-basic Orena capabilities, not merely generic Reading / Listening / Speaking / Writing screens.

## Shared

- one floating Quick Sheet for words and sentences;
- first-layer short gloss, deeper explanation only on request;
- Ask More / follow-up from contextual explanation;
- WHY / HOW;
- optional word-role/POS highlighting;
- Pinyin controls;
- source-preserving back behavior;
- Global Search;
- Saved;
- History;
- Import;
- Focus Mode;
- truthful loading/error/unavailable/offline states.

## Reading

- book/detail/reader flow;
- persistent reading position;
- word lookup;
- paragraph/sentence meaning;
- bilingual/support layer;
- Pinyin;
- reading-aid toggles;
- notes attached to source context;
- saved quote/highlight;
- source-aware summary;
- comprehension with passage evidence;
- whole-text Discussion thread;
- Write Response from source;
- saved vocabulary/grammar from the passage.

## Listening / Dictation

- real media library/import;
- synced timestamped transcript;
- line tap seeks/plays that exact line;
- current segment highlight;
- current spoken-word highlight when real word timing exists;
- translation/support meaning;
- Pinyin;
- selected-line Deep Practice;
- Dictation;
- progressive hint masking;
- hint usage reflected in evidence;
- Chinese per-character reading in Dictation where enabled;
- Shadowing from the same media asset;
- sticky/compact playback while transcript scrolls;
- transcript/subtitle preparation states;
- distinction between source captions and generated transcript;
- Vocabulary Focus from the selected segment.

## Speaking / Pronunciation

- scripted pronunciation assessment;
- model audio;
- learner recording/playback;
- ASR transcript;
- word/character-level pronunciation detail;
- accuracy / fluency / completeness / tone evidence where supported;
- Compare With Model chart;
- model-vs-learner waveform/timing;
- word alignment;
- Chinese tone contour when real provider data exists;
- stress/rhythm representation when supported;
- alternating Model / Mine playback;
- slower playback;
- recent attempts;
- best attempt;
- attempt history/evidence;
- Shadowing with timing/lag feedback;
- Free Talk;
- Conversation with coaching separate from partner dialogue;
- phrase rehearsal from the learner's own response;
- mic permission / blocked / low-volume / noisy / offline / provider-unavailable states.

## Writing

- draft in progress;
- multiple entry modes;
- autosave/save state;
- prompt + level + register;
- inline findings anchored to exact learner spans;
- WHY / HOW on a selected finding;
- Review tied to learner evidence;
- Keep / Unkeep a useful review;
- revision history;
- revision compare;
- desktop draft + feedback;
- mobile Draft / Review pair;
- recent drafts;
- inspiration prompt bank/rail;
- targeted writing drills from recurring learner issues;
- Respond to Content linked to its source.

## Vocabulary / Review

- compact Daily Feed;
- card flip/reveal;
- saved vocabulary library;
- collections;
- collection detail;
- rich Word Detail;
- Deep Word;
- per-word audio;
- audio/source attribution in detail where required;
- Context Clips with several real occurrences;
- source encounters;
- learner's own usage;
- Chinese stroke surface where supported;
- due state;
- SRS/Active Recall;
- multiple review prompt modes;
- three-grade review result;
- review settings;
- source-aware Recall;
- mastery/evidence state.

## Grammar

- curriculum/library;
- concept detail;
- formula / word order;
- visual transformation;
- timeline/aspect representation where useful;
- contrast between similar structures;
- common mistakes;
- Try It Yourself;
- Quick Quiz;
- lesson path;
- recommended next concept;
- contextual entry from Reading/Listening/Writing.

## Progress / Profile

- Progress overview;
- Trends;
- skill-level evidence;
- evidence drilldown;
- real rank/frame;
- profile settings;
- language settings;
- plan/usage;
- History.

These capabilities may be reorganized under Today / Discover / Orena / Practice Hub / My Library / Progress, while Progress remains a secondary evidence surface. The new design must provide a clear place and interaction path for every capability.

---

# 7. TODAY

Today là personalized entrance của learner.

Today không phải catalogue, không phải full Progress dashboard và không chứa Continue/In Progress.

## Screen T1 — Today

### Purpose

Trong vài giây, user phải hiểu:

- hôm nay có gì đáng chú ý;
- hệ thống đang gợi ý điều gì;
- có review nào đến hạn;
- có nội dung hoặc practice nào phù hợp với trạng thái gần đây;
- tiến trình gần đây có tín hiệu nào đáng xem.

### Structure

#### A. Compact learner context

- target language;
- current level/rank compact if useful;
- search;
- avatar.

#### B. Recommended for Today

Một số ít đề xuất có lý do rõ ràng.

Examples:

- “Luyện 3 cụm bạn đã nhớ nhưng chưa tự dùng”
- “Thử một tình huống nói 2 phút”
- “Nghe một đoạn B1 liên quan chủ đề bạn vừa đọc”
- “Ôn lại cấu trúc bạn lặp lỗi hai lần gần đây”

Tap → destination/workspace tương ứng.

#### C. For You

Curated mixed rail có thể gồm:

- article;
- book;
- video/audio;
- speaking scenario;
- writing prompt;
- vocabulary collection.

Today chỉ show một tập nhỏ được chọn cho learner.

#### D. Review reminder

Nếu có due items:

`8 mục cần ôn`

Tap → **My Library → Due Review**.

#### E. Small evidence / progress signal

Một vùng nhỏ dùng evidence thật, ví dụ:

- recall đang cải thiện;
- một lỗi lặp lại đang giảm;
- recent speaking/writing evidence;
- rank milestone gần nhất.

Tap → Progress.

#### F. Discover entry

Một số highlight ngắn:

- Read
- Listen / Watch
- Collections

See all → Discover.

#### G. Practice entry

Shortcut tới:

- Speak
- Write
- Focused Practice

See all → Practice Hub.

### Gestures

- vertical scroll;
- horizontal swipe trên content rails;
- next card partially visible;
- card tap opens destination directly.

---

# 8. DISCOVER

Discover trả lời:

> “Tôi muốn tìm thứ gì đó để học từ nó.”

Không phải technical library.

## Screen D1 — Discover

### Main tabs / scopes

- All
- Read
- Listen / Watch
- Collections
- Imported

### Top actions

- Search
- Import

### Content types

#### Read

- Books
- Stories
- Articles
- News
- Essays
- Dialogues
- Excerpts
- Imported text

#### Listen / Watch

- Video
- Podcast
- Interview
- Dialogue
- Audio
- Imported media

#### Collections

- Vocabulary collections
- curated learning packs

### Filters

- level
- topic
- duration
- source
- content type
- started / not started

### Card fields

- artwork
- title
- source/author
- level
- duration if applicable
- progress if started

---

## Screen D2 — Filter Sheet

- multi-select filters
- Apply
- Clear
- close

---

## Screen D3 — Search

Global search can also open here.

Search across:

- words
- content
- media
- books
- collections
- saved items
- imported content

Result grouping depends on query type.

---

# 8A. ORENA AGENT

Orena là primary destination ở giữa navigation và đồng thời là contextual assistant có thể được gọi từ các workspace khác.

Orena không phải chỉ là một chatbox. Nó là lớp điều phối giữa learner context, content, practice, review và progress.

## Screen OA1 — Orena Home

### Purpose

Cho learner một nơi để nói bằng ngôn ngữ tự nhiên về việc học và đi thẳng tới hành động phù hợp.

Orena có thể hỗ trợ các intent như:

- “Tôi nên học gì hôm nay?”
- “Tìm cho tôi một video B1 về engineering.”
- “Giải thích lỗi này.”
- “Cho tôi luyện lại phần tôi đang yếu.”
- “Tại sao câu này dùng từ này?”
- “Tôi đang tiến bộ thế nào?”
- “Mở lại bài tôi vừa luyện.”
- “Cho tôi một bài nói ngắn 5 phút.”

### Main structure

#### A. Conversation / command thread

Hiển thị:

- learner message;
- Orena response;
- source/context cards when relevant;
- action cards/buttons when Orena có thể đưa user tới một feature cụ thể.

#### B. Composer

Supports:

- text input;
- voice input where available;
- attach current learning context automatically when invoked from another workspace.

#### C. Suggested starters

Short suggestions based on learner state.

Examples:

- What should I practice?
- Explain my recent mistake
- Find something to listen to
- Review weak vocabulary
- Show my progress

#### D. Action result

Orena response có thể đưa ra action rõ ràng:

- Open content;
- Start Practice;
- Open My Library item;
- Open Progress evidence;
- return to exact source;
- open Quick Sheet/deep explanation where supported.

Orena chỉ hiển thị action mà sản phẩm thực sự hỗ trợ.

---

## Screen OA2 — Contextual Orena

Orena có thể được gọi trong:

- Reading;
- Listening;
- Speaking;
- Writing;
- Vocabulary;
- Grammar;
- Progress.

Khi mở từ context, request phải mang theo đối tượng đang được xem.

Examples:

### Reading

Selected sentence + source context:

> “Tại sao tác giả dùng thì này?”

### Listening

Selected transcript segment:

> “Cụm này nghe tự nhiên ở tình huống nào?”

### Speaking

Pronunciation issue / learner phrase:

> “Tôi đang sai ở đâu?”

### Writing

Selected finding:

> “Tại sao câu này unnatural?”

### Vocabulary

Current word:

> “Cho tôi ví dụ khác nhưng khó hơn.”

### Progress

Trend/evidence:

> “Tại sao hệ thống nói tôi yếu ở phần này?”

### Behavior

- opens as contextual panel/sheet or transitions to full Orena with context preserved;
- closing returns to exact source state;
- thread keeps the context label visible;
- learner can continue asking follow-up questions.

---

## Screen OA3 — Orena Action Handoff

When Orena proposes an action, the handoff object should show:

- destination/task;
- short reason;
- expected duration if known;
- primary action.

Examples:

`Practice 3 weak phrases · ~3 min`

`Open “The Last Question” · Reading`

`Try Situation Reaction · Work / B1`

Tap → destination.

Back → Orena thread with prior context preserved.

---

## Screen OA4 — Orena Source / Evidence Cards

When Orena grounds an explanation or recommendation in learner data/content, it can render compact cards for:

- source article/book;
- transcript segment;
- saved word;
- previous Writing finding;
- Speaking attempt;
- Progress evidence.

Tap card → exact original object.

---

# 9. IMPORT

Import belongs to Discover.

## Screen I1 — Import Type

Options:

- Text
- URL / Media
- File if supported

---

## Screen I2 — Text Import

Fields:

- paste text
- optional title
- detected language
- preview

Flow:

`Paste → Preview → Import → Processing → Reader`

---

## Screen I3 — Media Import

Fields:

- URL/file
- metadata preview
- thumbnail
- detected language
- transcript availability

Flow:

`Input → Preview → Process → Listening Workspace`

---

## Screen I4 — Processing

Possible stages:

- fetching
- transcript preparing
- translation preparing
- content ready

No fake percentage without real progress data.

---

## Screen I5 — Error

- what failed
- Retry
- Edit input

Preserve entered data.

---

# 10. READING EXPERIENCE

Reading is entered mainly from Discover.

## Screen R1 — Reading Browse

Scoped Discover view for readable content.

Top:

- Search
- Import Text
- Filters

Content:

- books
- stories
- articles
- news
- dialogues
- essays
- excerpts
- imports

---

## Screen R2 — Book / Content Detail

### Header

- cover
- title
- author/source
- level
- progress
- Start / Open / Continue reading

“Continue” here means a CTA inside this specific content detail, not a Continue destination.

### Below

- description
- chapter list
- saved words from source
- related content

### Chapter row

- title
- status
- progress
- optional length estimate

Tap → Reader.

---

## Screen R3 — Reader

### Desktop

Optional left:

- TOC / chapter list

Center:

- reading content

Optional right:

- contextual panel

### Top bar

- Back
- title
- chapter
- progress
- Pinyin toggle
- support/bilingual toggle
- text settings
- reading-aids control

### Reading aids

User-controlled layers can include:

- Vocabulary lens;
- Meaning;
- Translation;
- Pinyin;
- Pronunciation;
- Grammar lens;
- Word-role / POS lens.

### Body

Target language primary.

Support layer secondary.

### Notes / Highlights

Learner can attach:

- factual note;
- reflection;
- question;
- saved quote/highlight.

Opening one later returns to the exact source location.

### Summary

Can open without replacing the text.

Possible source:

- source-provided;
- deterministic;
- generated on request.

Generated summaries are labeled as generated.

### Reading insights

Only real source-linked evidence, for example:

- comprehension completed;
- words saved;
- notes/highlights created;
- questions completed.

### Context actions

- Save content
- Listen if audio exists
- Check understanding
- Discuss
- Write response
- Next chapter

---

## Reader interaction — Tap word

`Tap word → Word Quick Sheet`

Contents:

- word
- pronunciation
- POS
- contextual meaning
- source sentence
- Save
- deeper explanation

---

## Reader interaction — Select sentence

`Select sentence → Sentence Quick Sheet`

Actions:

- Translate
- Explain
- Grammar
- Save
- Ask deeper

---

## Screen R4 — Check Understanding

Question types:

- factual
- inference
- meaning
- intent

Flow:

`Question → Answer → Result → Evidence from text`

No question available → unavailable state.

---

## Screen R5 — Discussion

Persistent discussion about current text.

User can ask:

- what does this mean?
- why did author say this?
- grammar question
- interpretation
- content question

Thread remains tied to source.

---

## Screen R6 — Reading Transfer

New active-use function.

### Paraphrase

`Diễn đạt lại ý này bằng cách của bạn.`

### Inference

`Người viết đang ngụ ý điều gì?`

### Context Shift

`Nếu câu này được nói với quản lý thay vì bạn thân, nó sẽ thay đổi như thế nào?`

Input:

- text
- voice optional

Result:

- meaning preserved?
- missing important idea?
- one useful improvement
- Retry / Finish

---

## Screen R7 — Reading Complete

Show:

- completed section/chapter
- saved items
- comprehension if used
- one next action

Actions:

- Next chapter
- Review saved words
- Back to Discover

---

# 11. LISTENING / MEDIA EXPERIENCE

Listening is content-first and entered mainly from Discover.

## Screen LS1 — Listening Browse

Content:

- video
- podcast
- dialogue
- interview
- audio lesson
- imports

Card:

- thumbnail
- title
- source
- duration
- level
- progress

---

## Screen LS2 — Listening Workspace

### Listening modes

#### Follow

- transcript follows playback;
- current segment updates automatically;
- intended for listen-and-read.

#### Active

- learner manually selects a segment;
- playback updates must not destroy learner input;
- used for Dictation and focused listening.

#### Shadowing

- reuses the same media/segment;
- opens the Shadowing workflow.

### Desktop

Media + synced transcript.

### Mobile

Compact/sticky player + transcript.

A mini-player can remain reachable while transcript scrolls.

### Controls

- play/pause
- seek
- speed
- replay current line
- previous/next line
- captions
- support translation
- Pinyin
- auto-scroll

### Transcript

When real timing exists:

- current segment gets a broad highlight;
- current spoken word gets a stronger highlight;
- word timing must not be fabricated from segment timing.

Transcript can show:

- original transcript;
- support-language meaning/translation;
- Pinyin for Chinese;
- segment timestamps.

Tap line:

- seek;
- play that exact segment;
- select;
- line actions.

Tap word:

- pause;
- Quick Sheet.

Close → return to the same timestamp.

### Selected segment panel

Show:

- original text;
- Pinyin / pronunciation aid;
- contextual meaning;
- Play Segment;
- Explain;
- Vocabulary Focus;
- Deep Practice.

### Transcript provenance / preparation

States can include:

- source captions available;
- transcript preparing;
- generated transcript ready;
- translation preparing;
- translation ready;
- degraded/unavailable;
- retry.

Generated transcript is not presented as official source captions.

### Vocabulary Focus

Contextual terms from current segment:

- word;
- pronunciation/Pinyin;
- concise meaning;
- audio;
- Save.

---

## Screen LS3 — Line Actions

Actions:

- Replay
- Meaning
- Save Phrase
- Dictation
- Shadowing
- Read / Pronunciation
- Grammar
- React / Reuse

---

## Screen LS4 — Understand

Short comprehension checkpoint.

Question asks:

- meaning
- intent
- inference
- relation

Input:

- quick choice
- short free response

---

## Screen LS5 — Dictation

Flow:

`Play → Type → Hint optional → Check → Compare → Retry / Next`

UI:

- segment index
- replay
- input
- hint
- check
- previous/next

Result:

- learner input
- source transcript
- mismatch highlight
- important mismatch explanation

### Hint behavior

Hints are progressive.

A hint may reveal:

- length/shape;
- partial word/character information;
- selected missing positions.

A wrong word is not fully exposed merely because the learner asks for a hint.

The checked attempt can visibly carry a “used hint” state so later evidence distinguishes assisted from unassisted recall.

### Chinese reading support

When enabled:

- reading/Pinyin can appear directly under individual characters;
- Hanzi remains primary.

Mobile:

- input always reachable
- keyboard must not hide Check

---

## Screen LS6 — Shadowing

Flow:

`Model → Countdown → Speak with model → Result → Retry`

Show:

- segment
- speed
- timing
- lag if available
- pronunciation issue if available

---

## Screen LS7 — React / Reuse

New function.

### Step 1 — Listen

Audio first.

### Step 2 — Understand

Short meaning/intent question.

### Step 3 — Reveal

Show transcript and highlight useful phrase.

### Step 4 — New Context

Example:

Source:

`I figured you were tied up.`

New context:

`Bạn nhắn cho bạn mình nhưng họ không trả lời. Bạn đoán họ đang bận. Hãy nói một câu.`

Input:

- microphone
- text fallback

### Step 5 — Result

- intent achieved?
- phrase used if target phrase is required
- one natural alternative
- Retry
- New context
- Finish

Alternative valid wording can be accepted when exact phrase is not required.

---

## Screen LS8 — End of Media

Show:

- media completed
- useful items saved
- practice completed
- next recommendation

Actions:

- Replay
- Next
- Review saved phrases
- Discover

---

# 12. PRACTICE HUB

Practice Hub answers:

> “Tôi muốn luyện.”

This is also the only place where **Continue / In Progress** is treated as a dedicated section.

There is no standalone Continue screen.

---

## Screen PH1 — Practice Hub

### Section A — In Progress

Only show if something is unfinished.

Possible items:

- Speaking session
- Writing draft
- Dictation
- Shadowing
- Reading practice
- Listening React
- Conversation
- Recall/Transfer session
- Grammar practice

Each card/row:

- task type
- source or scenario
- current progress
- last active time
- Continue

Tap → exact task state.

If none → section disappears.

### Section B — Speak

- Situation Reaction
- Conversation
- Free Talk
- Pronunciation
- Shadowing
- Timed Reaction
- Mock Interview
- Sound/Tone Practice

### Section C — Write

- Free Writing
- Prompt
- Your Topic
- Respond to Content
- Context Rewrite
- Timed Writing

### Section D — Focused Practice

- Dictation
- Grammar
- Pronunciation/Tone
- Retell
- targeted practice from learner errors

### Section E — Recommended Practice

Personalized based on:

- recent errors
- due recall
- weak evidence stage
- recent content
- available time

---

# 13. SPEAKING

Speaking lives primarily under Practice Hub.

## Screen SP1 — Speaking Modes

Cards:

- Scripted Pronunciation
- Shadowing
- Situation Reaction
- Free Talk
- Conversation
- Retell
- Sound/Tone
- Mock Interview

Each card:

- title
- short description
- approximate duration
- level if relevant

---

## Screen SP2 — Scripted Pronunciation

Main:

- target sentence
- Pinyin/pronunciation support
- model audio
- record button

Flow:

`Listen → Record → Process → Result`

---

## Screen SP3 — Pronunciation Result

Show only evaluation signals that actually exist.

Possible metrics:

- overall interpretation;
- pronunciation accuracy;
- fluency;
- completeness;
- word/character evidence;
- tones if supported.

ASR transcript/content match is a separate signal and is not presented as a pronunciation score.

Tap word/character → detail.

Actions:

- Model
- My attempt if available
- Compare
- Attempt History
- Retry
- Next

### Phrase rehearsal

From an issue or learner phrase:

`learner phrase → issue → better alternative → rehearse`

Learner can replay the model and immediately record the corrected phrase again.

---

## Screen SP4 — Token Detail

- word/character
- expected reading
- learner issue
- pronunciation/tone detail
- model playback
- practice token

---

## Screen SP5 — Compare With Model

This is a distinctive visual analysis screen, not only a score panel.

### Main comparison chart

Where real data exists, align or overlay:

- model timeline;
- learner timeline;
- waveform;
- word/character alignment;
- pause/timing difference;
- Chinese tone contour;
- stress/rhythm representation for other languages.

The chart should make it possible to see **where** the learner diverges from the model.

### Token alignment

Tap a word/character:

- jump to that time range;
- play Model segment;
- play Learner segment;
- open pronunciation detail.

### Playback controls

- Model;
- Mine;
- Alternate Model ↔ Mine;
- slower speed;
- replay selected range;
- Retry.

### Attempt selector

Show:

- recent attempts;
- best attempt;
- current attempt.

Selecting an attempt updates the chart without leaving the screen.

---

## Screen SP5A — Attempt History

Purpose:

Review speaking attempts and improvement over time.

Each attempt can show:

- date/time;
- result summary;
- pronunciation/fluency evidence where available;
- current/best attempt marker.

Tap attempt:

- open Compare With Model using that attempt;
- optionally compare two recent attempts when supported.

Raw audio availability follows actual storage/privacy behavior; transcript/normalized assessment/evidence may remain available independently.

---

## Screen SP6 — Shadowing

Flow:

`Model → Countdown → simultaneous speak → analysis → retry`

Show:

- sentence
- model speed
- countdown
- timing
- lag
- one key issue
- live recording/timer state

If speaker bleed is likely, the UI can suggest headphones.

Result can offer:

- Model playback;
- Mine playback;
- phrase rehearsal;
- Retry.

---

## Screen SP7 — Free Talk Setup

Inputs:

- topic
- duration
- optional useful phrases

CTA:

Start Speaking.

---

## Screen SP8 — Free Talk Recording

- topic
- timer
- mic state
- finish

Minimal chrome.

---

## Screen SP9 — Free Talk Result

- transcript
- short summary
- strengths
- max 3 important fixes
- speaking dimensions if real
- one sentence to retry

---

## Screen SP10 — Conversation Setup

Choose:

- scenario
- partner role
- difficulty

Examples:

- restaurant
- colleague
- hotel
- doctor
- interview

---

## Screen SP11 — Conversation

Partner turn:

- text
- optional audio

Learner turn:

- record
- optional text fallback

Partner replies naturally.

Correction is not injected into every turn.

Optional:

`How did that land?`

Tap → coaching sheet.

---

## Screen SP12 — Conversation Coaching

For one learner turn:

- what worked
- one issue
- more natural alternative
- deeper grammar/pronunciation actions

Close → continue conversation.

---

## Screen SP13 — Situation Reaction

New function.

Prompt:

`Bạn cần dời lịch hẹn sang chiều mai.`

No model sentence.

UI:

- scenario
- context
- microphone
- optional countdown

Flow:

`Scenario → Speak → Result`

Result:

- intent achieved?
- clarity
- one useful improvement
- natural alternative

CTA:

`Try another context`

---

## Screen SP14 — Context Variant

Same communication intent, changed context.

Examples:

- friend → manager
- casual → formal
- hotel → doctor
- today → next week

Previous answer hidden by default.

User responds again.

Creates Transfer evidence.

---

## Screen SP15 — Production Under Pressure

New function.

Prompt:

`Bạn đến họp trễ 5 phút. Xin lỗi và giải thích.`

Measure:

- reaction time
- start delay
- intent
- semantic adequacy

Feedback:

1. communication worked?
2. one improvement
3. retry

---

## Screen SP16 — Speaking Summary

- tasks completed
- key improvement
- evidence created
- suggested next action

---

## Speaking States

### Mic Permission
- explanation
- Allow

### Mic Blocked
- Retry
- settings guidance
- text fallback if valid

### Not Heard
- low input state
- Try Again

### Noisy
- warning
- retry

### Processing
- result pending

### Provider Unavailable
- no fake score
- retry assessment
- continue without score when possible

### Offline
- clarify whether recording is local/pending

---

# 14. WRITING

Writing lives primarily under Practice Hub.

## Screen W1 — Writing Modes

- Continue Draft if unfinished
- Free Writing
- Prompt
- Your Topic
- Respond to Content
- Context Rewrite
- Timed Writing

“Continue Draft” is local to Writing/Practice Hub, not a global destination.

### Recent drafts

Quick list/rail for:

- unfinished drafts;
- recently reviewed drafts;
- kept reviews.

### Inspiration prompts

Optional prompt bank/rail.

Tap prompt → setup/editor with prompt prefilled.

---

## Screen W2 — Prompt Setup

- prompt
- level
- target length
- audience/register

CTA: Write

---

## Screen W3 — Your Topic

- own topic
- optional tone
- target length
- goal

---

## Screen W4 — Editor

Main:

- prompt/context
- large editor
- word/character count
- save state
- Review
- current revision/version state

Autosave where supported.

### Word-role lens

Optional highlighting for:

- nouns;
- verbs;
- modifiers;
- connectors;
- language-specific roles.

Tap highlighted role → brief role explanation.

### Inline findings

When review data exists, exact learner spans can be marked inside the draft.

Tap a marked span → matching finding detail.

Actual error/feedback state visually outranks the optional POS lens.

---

## Screen W5 — Review

### Desktop

Draft + review.

### Mobile

Draft/Review switch or sequential.

Review:

1. overall human-readable interpretation
2. strengths grounded in exact text
3. up to 3 priority issues
4. other issues collapsed
5. supporting dimensions where available
6. next action

Possible supporting dimensions:

- Grammar
- Vocabulary
- Coherence
- Task Achievement
- Naturalness
- estimated writing range/benchmark where real

---

## Screen W6 — Issue Detail

- original
- suggestion
- WHY
- HOW
- reusable rule
- contrast
- example
- related grammar
- Ask deeper
- Practice This
- Save concept
- Apply

Apply must require user action.

---

## Screen W7 — Revision

User edits.

Submit for review again.

---

## Screen W8 — Compare Versions

### Desktop

Revision comparison can occupy the full workspace.

A three-column layout can be used:

1. earlier version;
2. change/evidence legend;
3. revised version.

### Mobile

Use sequential/tabbed versions rather than squeezing three columns.

Show:

- fixed;
- still present;
- new;
- reworked;
- changed sentence spans;
- trustworthy dimension/range movement where available.

### Version history

Accessible from Writing context/menu.

Learner can reopen earlier versions and their associated reviews.

---

## Screen W8A — Kept Review / Saved Review

A learner can keep a useful review for later reading.

Actions:

- Keep Review;
- Unkeep;
- Open Draft;
- Open Revision.

Kept reviews retain their link to the exact writing version.

---

## Screen W8B — Targeted Writing Drill

Short practice generated from a verified Writing issue.

Examples:

- tense consistency;
- article use;
- sentence linking;
- stronger introduction;
- Chinese aspect;
- Chinese word order.

Flow:

`Finding → Practice This → short drill → result → return to draft/review or finish`

---

## Screen W9 — Respond to Content

Entered from Reading or Listening.

Source context remains visible/accessible.

Prompt can ask:

- opinion
- summary
- reaction
- continuation

---

## Screen W10 — Context Rewrite

New function.

Core message:

`Tôi không tham gia được.`

Context A:

`nhắn bạn thân`

Context B:

`email quản lý`

Context C:

`trả lời lời mời trang trọng`

Result:

- intent preserved?
- register fit
- politeness
- clarity
- one language fix

Actions:

- Next Context
- Retry
- Finish

---

## Screen W11 — Timed Writing

New function.

Examples:

- reply to a message
- decline schedule
- ask clarification
- explain delay

UI:

- prompt
- timer/window
- input
- Submit

Result:

1. communication worked?
2. register fit?
3. one important fix

---

# 15. MY LIBRARY

My Library trả lời:

> “Những gì thuộc về quá trình học của tôi đang ở đâu?”

Đây là nơi gom những thứ learner đã lưu, đã gặp, đang sở hữu trong learning history và cần quay lại.

Review là một chức năng bên trong My Library, không phải primary destination riêng.

## Screen ML1 — My Library

### Section A — Saved Content

Có thể gồm:

- saved books;
- saved articles;
- saved video/audio;
- imported content;
- content in progress where it belongs to the learner's collection.

Card/row:

- artwork;
- title;
- type;
- source;
- progress;
- Open.

### Section B — Saved Language

- Words
- Phrases
- Highlights
- Saved grammar/concepts where supported

Tap → detail/source.

### Section C — Collections

- vocabulary collections;
- learner-created/curated collections where supported.

### Section D — Due Review

Compact summary:

- due vocabulary;
- due phrases;
- grammar recall;
- source-aware recall.

CTA:

**Start Review**

→ Review Session.

### Section E — Recently Encountered

Items from:

- recent Reading;
- recent Listening;
- recent Speaking/Writing corrections;
- recent saved concepts.

### Section F — Active Use

Items ready for:

- Recall;
- Use;
- Context Transfer;
- Timed Recall.

### Section G — Library utilities

- Search;
- Filter;
- Sort;
- History shortcut;
- Open Progress shortcut when contextually useful.

---

# 16. SAVED LANGUAGE / VOCABULARY

## Screen V1 — Saved Language Library

Tabs/scopes:

- Words
- Phrases
- Highlights
- Collections

Search/filter:

- due
- source
- mastery stage
- collection
- recently encountered

---

## Screen V2 — Vocabulary Daily Feed

Small set of cards.

Card front:

- target word;
- pronunciation;
- visual/artwork.

Reveal / flip:

- concise meaning;
- example/context;
- Save;
- audio.

Gestures:

- tap/flip to reveal;
- horizontal swipe;
- next card partly visible.

---

## Screen V3 — Collections

Card:

- artwork
- title
- level
- word count
- progress

---

## Screen V4 — Collection Detail

- cover
- title
- progress
- Start Review
- word preview
- Show All

---

## Screen V5 — Word Detail

- word
- pronunciation/Pinyin
- meanings by POS
- examples
- collocations
- source encounters
- related expressions
- mastery evidence

### Audio

Per-word audio control.

Where the audio source requires attribution, credit/source detail is accessible here without cluttering Review cards.

### Source encounters

Show where the learner actually met the word:

- Reading;
- Listening;
- own Writing/Speaking where available.

Tap encounter → return to source context.

Actions:

- audio
- Save/Unsave
- Review
- Context Clips
- Deep Word

---

## Screen V6 — Deep Word

- core mental model
- distinctions
- contrasts
- common mistakes
- natural patterns
- learner usage
- grammar connection

---

## Screen V7 — Context Clips

Occurrences across sources.

Each:

- source
- speaker
- target line
- replay
- surrounding context
- Open Source

---

## Screen V8 — Chinese Strokes

When supported.

- character
- stroke order
- animation/steps
- replay

---

# 17. REVIEW SESSION

## Screen RV2 — Review Front

Review can switch among several prompt modes:

- target → meaning;
- meaning → target;
- audio → word;
- sentence/context cloze;
- source-aware cue.

Actions:

- Reveal;
- Hint;
- audio where relevant.

### Review settings

Accessible before or during a session.

Possible controls:

- enabled review modes;
- session length;
- audio autoplay;
- Pinyin display;
- input mode where relevant.

Scheduler mathematics remain hidden from the learner.

---

## Screen RV3 — Revealed

Show:

- answer
- source context

Grades:

- Quên
- Chưa chắc
- Nhớ rồi

Tap → next.

---

## Screen RV4 — Source-Aware Recall

### From Reading

- sentence cloze
- retrieve phrase

### From Listening

- audio cue
- retrieve phrase

### From Speaking

- situation cue
- say expression again

### From Writing

- previous correction
- produce corrected use

---

# 18. CONTEXT TRANSFER

Context Transfer is part of My Library / Review flow, not a separate top-level destination.

## Screen RV5 — Context Transfer

Example saved item:

`hesitate`

Prompt:

`Mô tả một lần bạn do dự trước khi đưa ra quyết định.`

Do not show target word.

Input:

- Speak
- Type

Result:

- failed recall
- recalled but incorrect use
- correct use
- successful transfer

Actions:

- suggestion
- retry
- new context
- finish

---

# 19. TIMED RECALL / AUTOMATICITY

## Screen RV6 — Timed Recall

Prompt appears.

System records:

- time to start
- response
- result

Feedback:

- retrieved quickly
- retrieved slowly
- not recalled

Can offer retry.

---

# 20. GRAMMAR

Grammar is accessible from My Library/Review and contextual sheets, and also from Practice Hub → Focused Practice.

## Screen G1 — Grammar Library / Concepts

Groups by:

- current level
- recent errors
- saved concepts
- recommended

---

## Screen G2 — Grammar Concept

Sections:

1. concept
2. meaning/function
3. pattern/form
4. when to use
5. when not to use where relevant
6. contrast
7. common mistakes
8. examples
9. mini practice
10. recall / personal production where available

### Visual teaching objects

Depending on concept:

- formula/pattern block;
- word-order rail;
- sentence construction;
- transformation view;
- timeline/aspect view;
- contrast pair;
- semantic role highlighting.

Chinese grammar uses Chinese-specific structures rather than an English grammar layout translated into Chinese.

### Lesson path

Can show:

- previous concept;
- current concept;
- next concept;
- completion state.

---

## Screen G3 — Contrast

Compare confusing alternatives.

- A
- B
- when A
- when B
- examples
- quick practice

---

## Screen G4 — Mini Production

Prompt asks learner to produce one sentence.

Result:

- concept used correctly?
- one correction
- example

Can create Use/Transfer evidence.

---

# 21. PROGRESS

Progress là một **primary learner destination**.

Đây không chỉ là analytics. Nó phải là nơi learner muốn quay lại thường xuyên để:

- thấy bằng chứng mình đang tiến bộ;
- nhận ra kỹ năng nào đang tốt lên;
- nhìn thấy chuỗi thay đổi theo thời gian;
- có động lực tiếp tục;
- biết điểm yếu nào đáng luyện tiếp;
- xem rank/milestone như một lớp động lực, không thay thế bằng chứng học thật.

Ngoài primary navigation, Progress còn có shortcut từ Today, Practice results, My Library, Profile và Orena.

Progress answers:

- what improved?
- what can I really use?
- what keeps failing?
- what should I practice next?

---

## Screen P1 — Progress Overview

### Purpose

Trong một glance, learner phải cảm nhận được:

- “Tôi đã đi được bao xa?”
- “Tôi đang tốt lên ở đâu?”
- “Có điều gì đáng tự hào?”
- “Tôi nên làm gì tiếp?”

### Top progress story

Một vùng nổi bật nhưng không phải KPI wall.

Can show a small number of real signals such as:

- current rank / milestone;
- recent improvement;
- weekly/monthly learning continuity;
- one strongest growth area;
- one next focus.

### Skill progress

Readable skill-level view:

- Reading;
- Listening;
- Speaking;
- Writing;
- Vocabulary / Recall.

Tap skill → evidence/trend detail.

### Knowing → Using

Compact progression:

- Recognized;
- Recalled;
- Used;
- Transferred;
- Fast Retrieval.

### Motivation layer

Can include when real:

- streak;
- milestone reached;
- rank progression;
- personal best;
- “X weeks stronger than previous period”;
- completed learning goal.

These are supporting motivation signals, not substitutes for proficiency evidence.

### Next action

One or a few evidence-based actions:

- Practice this;
- Review weak items;
- Continue a skill focus;
- try a harder/new context.

### Other trustworthy blocks may include

- study time;
- vocabulary;
- recall;
- reading comprehension;
- listening;
- speaking;
- writing;
- rank;
- recent activity.

---

## Screen P2 — Trends

Examples:

- improving
- recurring error
- pronunciation issue
- grammar pattern
- listening difficulty

Each trend:

- description
- evidence count/timeframe
- View Evidence
- Practice This

---

## Screen P3 — Knowing → Using

Show:

- Recognized
- Recalled
- Used
- Transferred
- Fast Retrieval

Only based on real evidence.

Tap → drilldown.

---

## Screen P4 — Evidence Drilldown

Each evidence item:

- date
- source
- learner response
- result
- context

Tap → original source/attempt if available.

---

## Screen P5 — Rank

- current level
- current frame
- sub-level/gems
- progress to next milestone
- milestones

Rank is motivation, not proficiency proof.

---

# 22. HISTORY

History is accessed from Progress, My Library or Profile.

## Screen HS1 — History

Grouped by day.

Possible items:

- Reading
- Listening
- Dictation
- Speaking attempt
- pronunciation comparison
- Writing
- kept Writing review
- revision
- Review
- Transfer

Tap → evidence/detail/source.

---

# 23. PROFILE

## Screen PF1 — Profile

- avatar
- name
- target language
- goal
- rank/frame
- plan
- compact progress context

Actions:

- Settings
- History
- Privacy
- Plan / Usage
- Admin if authorized

---

# 24. SETTINGS

## Screen ST1 — Languages

- Target Language
- Interface Language
- Support Language
- Pinyin/transcription preferences

---

## Screen ST2 — Learning Preferences

- text size
- transcript behavior
- autoplay
- pronunciation assistance
- Pinyin visibility
- other learner settings

---

## Screen ST3 — Privacy

Relevant controls/info for:

- microphone
- learner audio
- history
- account data

---

## Screen ST4 — Plan / Usage

- plan
- quota
- limits
- subscription controls if supported

---

# 25. OPEN RESPONSE RESULT

Shared result model used by:

- Reading Transfer
- Listening React
- Speaking Situation Reaction
- Production Under Pressure
- Writing Context Rewrite
- Timed Writing
- Vocabulary Context Transfer

## Layer 1 — Communication

- Worked
- Partly worked
- Try again

## Layer 2 — One important improvement

Short actionable feedback.

## Layer 3 — Optional detail

- grammar
- naturalness
- register
- pronunciation
- vocabulary

## Layer 4 — Next action

- Retry
- New Context
- Continue
- Finish

Exact sentence matching is not required unless task explicitly tests one target expression.

---

# 26. GLOBAL GESTURES

## Tap

- open
- select
- toggle
- play
- open sheet

## Long press

Optional quick action.

Never essential-only.

## Horizontal swipe

- Today rails
- Discover rails
- Vocabulary feed
- Context clips

Must coexist with vertical scroll.

## Swipe down

Dismiss bottom sheet.

## Drag

- sheet expansion
- seek bar
- waveform/timeline

## Text selection

Reader:

- phrase/sentence actions

Writing:

- contextual explanation if implemented

## Recording gesture

Must be consistent per mode.

Possible:

- tap to start / tap to stop
- hold to record in quick conversation turns

Recording state must always be obvious.

---

# 27. MOBILE BEHAVIOR

## Main destinations

Use bottom navigation.

## Focus workspace

Hide/compact bottom navigation.

## Quick Sheet

Bottom sheet.

## Player

Can become sticky compact player while transcript scrolls.

## Keyboard

Must not hide:

- text input
- Check
- Submit
- Review

## Result

When async result arrives:

- bring result into view automatically.

## Safe area

Respect device safe area.

---

# 28. DESKTOP BEHAVIOR

Use width for context.

Good split views:

- Reader + Quick Sheet
- Media + Transcript
- Writing + Review
- Speaking Model + Result
- Progress + evidence

Panels collapsible.

---

# 29. COMPLETE DESTINATION MAP

```text
TODAY
├─ Recommended for Today
├─ For You
├─ Review Reminder
├─ Small Progress / Evidence Signal
├─ Discover Entry
└─ Practice Entry

DISCOVER
├─ Read
│  ├─ Books
│  ├─ Stories
│  ├─ Articles
│  ├─ News
│  └─ Imported Text
├─ Listen / Watch
│  ├─ Video
│  ├─ Podcast
│  ├─ Audio
│  ├─ Dialogue
│  └─ Imported Media
├─ Collections
├─ Search
└─ Import

ORENA
├─ Ask / Talk
├─ Personalized Recommendation
├─ Find Content
├─ Explain Context
├─ Explain Error
├─ Navigate / Start Action
├─ Source / Evidence Cards
└─ Contextual Orena from learning workspaces

PRACTICE HUB
├─ In Progress
├─ Speak
│  ├─ Pronunciation
│  ├─ Shadowing
│  ├─ Situation Reaction
│  ├─ Timed Reaction
│  ├─ Free Talk
│  ├─ Conversation
│  └─ Interview / Retell / Tone
├─ Write
│  ├─ Free Writing
│  ├─ Prompt
│  ├─ Own Topic
│  ├─ Respond to Content
│  ├─ Context Rewrite
│  └─ Timed Writing
└─ Focused Practice
   ├─ Dictation
   ├─ Grammar
   ├─ Pronunciation
   └─ Targeted Practice

MY LIBRARY
├─ Saved Content
├─ Saved Language
│  ├─ Words
│  ├─ Phrases
│  ├─ Highlights
│  └─ Grammar / Concepts
├─ Collections
├─ Due Review
├─ Recently Encountered
├─ Recall
├─ Context Transfer
├─ Timed Recall
└─ History shortcut

PROGRESS
├─ Overview
├─ Trends
├─ Knowing → Using
├─ Evidence
├─ Rank
└─ History

SECONDARY
└─ Profile / Settings
```

---

# 30. END-TO-END FLOWS

## Flow A — Find something to read

```text
Today
→ Discover
→ Read
→ Book/Article
→ Reader
```

---

## Flow B — Read and inspect a word

```text
Reader
→ Tap Word
→ Quick Sheet
→ Save
→ Close
→ Continue Reading
```

---

## Flow C — Listen naturally

```text
Discover
→ Listen/Watch
→ Media
→ Play
→ Synced Transcript
```

No forced exercise.

---

## Flow D — Listening to active use

```text
Media
→ Select Line
→ React
→ Understand
→ Reveal
→ New Context
→ Respond
→ Result
→ Back to Media
```

---

## Flow E — Resume unfinished practice

```text
Practice Hub
→ In Progress
→ Select unfinished task
→ exact previous state
```

There is no separate Continue destination.

---

## Flow F — Speaking situation

```text
Practice Hub
→ Speak
→ Situation Reaction
→ Speak
→ Feedback
→ New Context
→ Speak Again
→ Finish
```

---

## Flow G — Writing revision

```text
Practice Hub
→ Write
→ Prompt
→ Editor
→ Review
→ Issue
→ Revise
→ Compare
→ Finish
```

---

## Flow H — Save → Recall → Transfer

```text
Reading/Listening
→ Save Word/Phrase
→ My Library
→ Due Review / Recall
→ Recall
→ Context Transfer
→ Timed Recall later
→ Progress evidence
```

---

## Flow I — Repeated error

```text
Speaking/Writing
→ recurring issue
→ Progress Trend
→ Practice This
→ Practice targeted task
→ New Evidence
```

---

# 31. COMPONENT INVENTORY

Design should include reusable:

1. App Rail
2. Bottom Nav
3. Top Bar
4. Search
5. Filter Chips
6. Content Card
7. Media Card
8. Recommendation Card
9. Practice Card
10. In Progress Row
11. Review Due Row
12. Quick Sheet
13. Bottom Sheet
14. Side Panel
15. Audio/Video Player
16. Transcript Line
17. Word Token
18. Sentence Selection
19. Recorder
20. Recording State
21. Waveform
22. Scenario Card
23. Timer
24. Feedback Card
25. Issue Card
26. Evidence Row
27. Review Grade Controls
28. Revision Diff
29. Collection Card
30. Rank Frame
31. Learner Card
32. Empty
33. Error
34. Unavailable
35. Offline
36. Processing
37. Toast
38. Dialog
39. Word-role / POS Toggle + Legend
40. WHY / HOW Action
41. Spoken-word Highlight
42. Selected Transcript Segment Panel
43. Transcript Preparation State
44. Model-vs-Learner Waveform/Timing Chart
45. Tone Contour Chart
46. Attempt Selector / Attempt History Row
47. Inline Writing Finding Marker
48. Kept Review Row
49. Reading Note / Highlight Marker
50. Grammar Pattern / Word-order Rail

---

# 32. SCREEN CHECKLIST

## Today

- T1 Today
- recommendation state
- review reminder state
- new learner state
- desktop
- mobile

## Discover

- D1 Discover
- Read browse
- Listen/Watch browse
- Collections
- Search
- Filter
- Import
- Processing
- Error

## Reading

- R1 Browse
- R2 Detail
- R3 Reader
- Reading aids state
- Notes / Highlights state
- Summary state
- Word Quick Sheet
- Sentence Quick Sheet
- R4 Comprehension
- R5 Discussion
- R6 Transfer
- R7 Complete

## Listening

- LS1 Browse
- LS2 Workspace
- transcript preparation/provenance state
- selected-segment panel
- spoken-word highlight state
- LS3 Line Actions
- LS4 Understand
- LS5 Dictation
- Dictation Result
- LS6 Shadowing
- LS7 React
- LS8 End

## Orena

- OA1 Orena Home
- OA2 Contextual Orena
- OA3 Action Handoff
- OA4 Source / Evidence Cards

## Practice Hub

- PH1 Practice Hub
- In Progress section
- Speak section
- Write section
- Focused Practice
- Recommendations

## Speaking

- SP1 Modes
- SP2 Scripted
- SP3 Result
- SP4 Token Detail
- SP5 Compare With Model chart
- SP5A Attempt History
- SP6 Shadowing
- SP7 Free Talk Setup
- SP8 Recording
- SP9 Result
- SP10 Conversation Setup
- SP11 Conversation
- SP12 Coaching
- SP13 Situation Reaction
- SP14 Variant
- SP15 Timed Reaction
- SP16 Summary
- permission/error/offline states

## Writing

- W1 Modes
- W2 Prompt
- W3 Own Topic
- W4 Editor
- W5 Review
- W6 Issue
- W7 Revision
- W8 Compare
- W8A Kept Review
- W8B Targeted Writing Drill
- W9 Respond to Content
- W10 Context Rewrite
- W11 Timed Writing

## My Library

- ML1 My Library
- Saved Content
- Saved Language
- Collections
- Due Review
- Recently Encountered
- Active Use

## Review Session

- RV2 Review Front
- Saved Language
- Due
- Collections
- Recently Encountered
- RV2 Review Front
- RV3 Revealed
- RV4 Source-Aware Recall
- RV5 Context Transfer
- RV6 Timed Recall

## Vocabulary

- Daily Feed
- Saved Library
- Collections
- Collection Detail
- Word Detail
- Deep Word
- Context Clips
- Chinese Strokes

## Grammar

- Library
- Concept
- Contrast
- Mini Production

## Progress

- P1 Overview
- P2 Trends
- P3 Knowing→Using
- P4 Evidence
- P5 Rank
- History

## Profile

- PF1 Profile
- ST1 Languages
- ST2 Preferences
- ST3 Privacy
- ST4 Plan/Usage

---

# 32A. CURRENT UI CAPABILITY AUDIT RESULT

The feature inventory above has been reconciled against the current/recent Orena learner UI descriptions and repository-derived function records.

Distinctive capabilities that were easy to miss in an ordinary “four skills” redesign and are now explicitly represented include:

- Quick Sheet short-gloss → deeper explanation;
- Ask More / WHY / HOW;
- word-role/POS lens;
- Reading notes/highlights/summary;
- spoken-word transcript highlighting;
- source-caption vs generated-transcript states;
- selected-line Deep Practice;
- Dictation progressive hints and per-character Chinese reading;
- pronunciation assessment separated from ASR/content match;
- model-vs-learner waveform/timing comparison;
- word alignment;
- Chinese tone contour;
- recent/best speaking attempts;
- speaking attempt history;
- phrase rehearsal;
- Writing inline findings;
- kept Writing reviews;
- revision history and full compare;
- targeted writing drills;
- vocabulary card flip;
- audio attribution in Word Detail;
- Context Clips;
- multiple Review modes/settings;
- grammar word-order/transformation/timeline teaching objects;
- learner evidence drilldown.

The top-level learner information architecture is:

`Today → Discover → Orena → Practice Hub → My Library → Progress`

Progress is a first-class evidence + motivation destination. Unfinished work remains an **In Progress** section inside Practice Hub, not a standalone destination.

---

# 33. PLATFORM ADMIN

Platform Admin là khu vận hành riêng, chỉ tài khoản có quyền Admin mới nhìn thấy.

Admin không dùng navigation learner. Khi vào Admin, người dùng chuyển sang một shell quản trị riêng.

## 33.1 Admin primary navigation

Top-level:

1. Overview
2. AI & Models
3. Users
4. Content
5. Imports
6. Operations

Các chức năng quản trị Reading và Practice Generator nằm bên trong các khu vực trên, không tạo thêm một app Admin thứ hai.

---

# 34. ADMIN SHELL

## Screen A0 — Admin Shell

### Desktop

Persistent left rail hoặc top-level navigation chứa:

- Overview
- AI & Models
- Users
- Content
- Imports
- Operations

Top utility:

- environment/runtime indicator nếu cần
- global admin search khi có
- current admin account
- Back to learner app

### Mobile

- compact header
- navigation drawer hoặc horizontal section switcher
- tables chuyển thành rows/cards
- detail mở full-screen

### Common interaction

List → click row → detail/drawer/page.

Advanced technical detail được mở theo nhu cầu, không tràn vào list.

---

# 35. ADMIN OVERVIEW

## Screen A1 — Overview

### Purpose

Cho Admin nhìn nhanh:

- hệ thống đang ổn không;
- khu vực nào cần xử lý;
- content nào đang chờ;
- AI/provider có vấn đề không;
- jobs/workers có lỗi không.

### Summary metrics

Chỉ hiển thị khi có dữ liệu thật:

- Total users
- Active learners
- New users
- Published content
- Content waiting for review
- Failed imports/jobs
- AI health
- Worker health

### Needs Attention

Đây là phần quan trọng nhất.

Mỗi row:

- problem
- severity/status
- affected area
- time
- action/link

Examples:

- provider test failed
- 12 Reading items need review
- 4 import jobs failed
- worker heartbeat stale
- source polling failed

Tap row → đúng màn xử lý.

### Charts / summaries

Có thể gồm:

- registrations trend
- active learners trend
- activity by learning domain
- content by type
- content by language
- AI success/failure trend
- import/job status distribution

### States

- loading
- no data
- partial unavailable
- service degraded

Overview không chứa raw logs.

---

# 36. AI & MODELS

## Screen A2 — AI & Models Home

### Purpose

Quản lý:

- provider
- credential state
- available models
- capability routing
- fallback
- health
- tests

### Provider section

Mỗi provider row/card:

- provider name
- Configured / Not configured
- connection state
- model count
- last test
- health

Actions:

- Configure
- Update credential
- Remove credential
- Test Provider
- Open Detail

Credential sau khi save không hiển thị lại raw secret.

---

## Screen A3 — Provider Configure

Fields tùy provider:

- provider/base URL
- credential/API key
- optional endpoint/options
- default model if relevant

Actions:

- Save
- Test Connection
- Cancel

### Credential behavior

Existing credential:

- show “Configured”
- do not show secret value
- Update replaces secret
- Remove requires confirmation

---

## Screen A4 — Provider Detail

Show:

- provider status
- supported/available models
- last test
- latency
- recent success/failure
- last error
- usage if telemetry exists

Actions:

- Test
- Update Credential
- Return to routing

---

## Screen A5 — Capability Routing

Each capability row:

- capability
- enabled/disabled
- provider
- primary model
- fallback/standby model if supported
- health
- recent failures

Example capabilities:

- Translation
- Dictionary
- Writing Evaluation
- Reading Analysis
- Topic Classification
- Level Estimation
- Learning Target Extraction
- Adaptation
- Question Generation
- Speaking/feedback capabilities when routed through AI

Actions:

- select provider
- select model
- set fallback
- enable/disable
- Test
- Save

### Test result

Show:

- success/failure
- latency
- tested provider/model
- short output or validation result where useful
- request/error detail expandable

Configured, Operational and Healthy are visually distinct states.

---

# 37. USERS

## Screen A6 — Users List

### Purpose

Find and inspect accounts.

### Columns / row data

- Name
- masked email
- Role
- Target language(s)
- Joined
- Last active
- Status
- Plan if relevant

### Filters

- Search
- Role
- Language
- Activity/status
- Plan if supported

Tap row → User Detail.

---

## Screen A7 — User Detail

### Summary

- account identity
- role
- account status
- plan
- language profiles
- last activity
- usage summary

### Learning summary

Only aggregate/relevant data:

- major learning activity
- current target language
- recent usage
- progress/evidence summary when administratively appropriate

Do not expose private learner-authored content unnecessarily.

### Admin actions

Only actions supported by system, e.g.:

- role/access controls
- account status
- plan/status inspection

Dangerous changes require confirmation.

---

# 38. CONTENT

## Screen A8 — Content Home

### Purpose

One administration library for all content.

### Sub-navigation

- All
- Books
- Media
- Vocabulary
- Reading
- Practice Generator

### Shared controls

- Search
- filter
- status
- language
- rights where applicable
- sort

Rows open domain-specific detail.

---

# 39. CONTENT — BOOKS

## Screen A9 — Books List

Fields:

- cover
- title
- author
- language
- chapter count
- word count
- status

Actions:

- Preview
- Archive
- domain actions that actually exist

Tap → Book Detail/Preview.

---

## Screen A10 — Book Preview / Detail

Show:

- cover
- metadata
- chapters
- source/import info
- status
- learner availability

Actions reflect actual supported backend behavior.

---

# 40. CONTENT — MEDIA

## Screen A11 — Media List

Fields:

- thumbnail
- title
- provider/source
- language
- duration
- transcript state
- level/topic if available
- status

Actions:

- Preview
- Reprocess
- inspect transcript/source state

---

## Screen A12 — Media Detail

Show:

- metadata
- source
- thumbnail/player preview
- transcript state
- processing state
- language
- level/topic
- import/reprocess history where relevant

Actions:

- Preview learner view
- Reprocess
- open related job

---

# 41. CONTENT — VOCABULARY

## Screen A13 — Vocabulary Collections

Fields:

- collection name
- language
- framework
- level
- topic
- item count
- rights
- status

Actions:

- Preview
- Review
- Publish when supported
- Archive

Pending review must be obvious.

---

## Screen A14 — Vocabulary Collection Detail

Show:

- collection metadata
- cover/art
- items
- source/provenance
- rights
- status
- learner preview

Actions:

- inspect item
- edit supported metadata
- review/publish/archive according to backend

---

# 42. CONTENT — READING

Reading Content Engine has its own sub-navigation inside Content.

## Reading sub-navigation

- Overview
- Review Queue
- Published
- Rejected
- Archived
- Sources

Primary action:

**+ Add Content**

---

## Screen A15 — Reading Overview

### Purpose

Quick operational view of Reading corpus.

Show:

- Published
- Needs Review
- Processing
- Rejected
- Archived
- Failed jobs
- Active sources
- Source errors

Quick actions:

- Add Content
- Review Queue
- Sources
- View Jobs

---

## Screen A16 — Reading Review Queue

### List fields

- Title
- Source
- Topic
- Estimated level
- Reading time
- Learning target count
- Rights state
- warnings
- status

### Actions

- Preview
- Review
- Publish
- Reject

Tap Review → Reading Review Detail.

List should be easy to scan; full article body is not shown here.

---

## Screen A17 — Reading Review Detail

This is the main editorial/review workspace.

### Desktop layout

Prefer split or tabbed comparison:

**Processed Article | Original Source**

### Processed Article section

- title
- body
- topic
- estimated level
- reviewed/overridden level
- reading time
- source attribution

### Learning Targets section

Each target:

- word/phrase
- type
- context
- meaning
- approve/remove
- reorder

Admin can:

- add target
- remove target
- reorder
- edit allowed target fields

### Original Source section

Read-only:

- original title
- author
- source URL
- publication date
- original content
- rights information

### Processing Evidence

Collapsed by default.

Show:

- detected language
- estimated level
- topic
- duplicate result
- suggested targets
- warnings
- adapted/not adapted
- processor/model version

No hidden reasoning/chain-of-thought display.

### Rights control

Tri-state selector:

- Unknown
- Allow
- Deny

Rights state is always visible in review.

### Actions

- Edit title
- Edit topic
- Override level
- edit allowed article fields
- Publish
- Reject
- Archive

Reject opens reason dialog.

Archive opens confirmation.

After action, return to queue or next item.

---

## Screen A18 — Published Reading

Fields:

- Title
- Level
- Topic
- Source
- Published date
- activity/usage if available

Actions:

- Preview
- Edit metadata
- Unpublish
- Archive

Unpublish is not delete.

---

## Screen A19 — Rejected Reading

Fields:

- Title
- Source
- Reject reason
- Rejected at
- Rejected by

Actions:

- Preview
- Restore to Review
- Archive

---

## Screen A20 — Archived Reading

Fields:

- Title
- Former status
- Source
- Archived at
- reason

Actions:

- Preview
- Restore where supported

---

# 43. ADD READING CONTENT

## Screen A21 — Add Content

Entry from Reading.

Choose:

- URL
- Text
- File

---

## A21A — URL

Fields:

- URL
- Language optional/auto
- Source optional
- Rights

Submit:

`Add to processing queue`

---

## A21B — Text

Fields:

- Title
- Body
- Language
- Source name
- Source URL optional
- Rights

---

## A21C — File

Fields:

- File
- Language
- Source
- Rights

### After submit

Show:

- Queued
- Processing
- Ready for Review
- Failed

The form does not stay blocked until processing ends.

Offer:

- View Job
- Add Another
- Close

---

# 44. READING SOURCES

## Screen A22 — Sources List

Fields:

- Source name
- type
- language
- topics
- rights state
- automation allowed
- status
- last checked
- last success
- last error

Actions:

- View
- Add
- Approve
- Activate
- Pause
- Block
- Archive

---

## Screen A23 — Source Detail

Show:

- source identity
- base URL
- source type
- languages
- topic hints
- rights / attribution policy
- polling policy
- checkpoint
- last success
- last error
- imported count
- published count
- rejected count

Where supported/future-enabled:

- Test Source
- Run Now
- Enable/Disable Polling
- Poll interval

Source errors link to related jobs/events.

---

# 45. PRACTICE GENERATOR / EXERCISE FACTORY

Practice Generator nằm bên trong Content.

Mục tiêu của khu vực này là để Admin tạo nhiều bài luyện có chất lượng mà **không cần tự thiết kế rubric, semantic rules hoặc cấu trúc sư phạm**.

Admin chỉ mô tả mục tiêu ở mức sản phẩm. Hệ thống chịu trách nhiệm sinh:

- learner-facing prompt;
- context variants;
- expected communication intent;
- accepted answer space;
- semantic requirements;
- scoring rubric;
- level-appropriate wording;
- feedback rules;
- transfer variants;
- timed variants khi phù hợp.

Các chi tiết nội bộ trên không phải form bắt buộc cho Admin.

---

## Screen A24 — Practice Generator Home

### Purpose

Cho Admin chọn cách tạo bài luyện.

### Primary actions

#### Generate from Learning Goal

Dùng khi Admin muốn tạo một nhóm bài theo mục tiêu giao tiếp.

Ví dụ:

- xin đổi lịch;
- xin lỗi;
- hỏi thông tin;
- từ chối lịch sự;
- yêu cầu giúp đỡ;
- bày tỏ không chắc chắn;
- đưa ra đề nghị.

#### Generate from Content

Dùng khi muốn biến một Reading/Listening item có sẵn thành practice.

Ví dụ từ một video:

- comprehension;
- useful phrase reuse;
- speaking situation;
- vocabulary transfer;
- dictation/shadowing candidate.

#### Existing Generated Sets

Xem các batch đã tạo:

- Draft
- Reviewing
- Published
- Archived

### Summary rows/cards

Mỗi generated set có:

- name / source;
- target language;
- skill;
- level;
- learning goal;
- number of exercises;
- status;
- created/updated.

Actions:

- Open
- Generate New
- Duplicate Set when useful

---

## Screen A25 — Generate Practice Setup

Admin chỉ chọn các đầu vào dễ hiểu.

### Mode A — From Learning Goal

Fields:

- Target language
- Skill:
  - Speaking
  - Writing
  - Listening
  - Reading
  - Vocabulary / Recall
- Level
- Learning goal / communication goal
- Context/domain:
  - Everyday
  - Work
  - Travel
  - Study
  - Social
  - Other
- Number of exercises
- Optional focus:
  - target word/phrase
  - grammar concept
  - pronunciation/tone target
  - none

Example:

```text
Language: English
Skill: Speaking
Level: B1
Goal: Reschedule an appointment
Context: Work
Quantity: 20
```

Admin does not enter scoring weights or semantic slots.

### Mode B — From Existing Content

Select:

- source content;
- target language;
- learner level;
- which practice types to generate.

Possible practice types:

- comprehension;
- vocabulary recall;
- phrase reuse;
- Context Transfer;
- Speaking Situation;
- Dictation;
- Shadowing;
- short Writing response.

System extracts useful targets from the source.

### Primary action

**Generate Samples**

After tap:

`Generating → Sample Review`

---

## System-generated internals

These are generated automatically and normally hidden from Admin:

- communication intent representation;
- required semantic elements;
- accepted answer variants;
- semantic matching rules;
- scoring rubric;
- feedback rubric;
- difficulty transformation;
- context variation rules;
- transfer target;
- automaticity/timing rules.

If debugging is required, an expandable **Generation Details** panel may expose a readable summary, but Admin does not have to author it.

---

## Screen A26 — Generated Sample Review

### Purpose

Admin judges whether the generated practice feels useful and appropriate.

Admin reviews examples, not the underlying pedagogy engine.

### Batch summary

Show:

- Language
- Skill
- Level
- Goal
- Context
- Number generated

### Each sample

Show learner-facing information first:

- task prompt;
- scenario/context;
- input mode:
  - speak
  - write
  - listen
  - choose/short answer
- expected learner action;
- optional example of one valid response.

Optional collapsed system summary:

- what the task is trying to test;
- why it matches the selected level;
- what counts as a successful response.

Do not show scoring formulas by default.

### Admin actions per sample

- Accept
- Regenerate
- Edit wording
- Flag as bad
- Exclude

### Batch actions

- Accept All Remaining
- Generate More
- Regenerate Flagged
- Back to Setup
- Continue to Publish

The user should be able to judge the batch using normal language, without linguistic terminology.

---

## Screen A27 — Generated Set Review / Publish

### Purpose

Final check before exercises become available to learner-facing practice.

### Show

- generated set name;
- source or learning goal;
- language;
- level;
- skill;
- number accepted;
- number excluded;
- flagged items;
- sample preview;
- generation version/time.

### Quality warnings

System can surface simple warnings such as:

- duplicate prompts;
- difficulty may be above selected level;
- too little variation;
- source phrase not present;
- ambiguous learner instruction.

Warnings should be written in plain language.

### Actions

- Review Flagged
- Generate Replacement
- Publish Set
- Keep as Draft
- Archive

### Publish behavior

Publishing makes the accepted exercises available to Practice/Review generation.

Admin does not have to configure individual scoring rubrics before publishing.

---

## 45.1 Example — Generate Speaking Practice

Admin input:

```text
Language: English
Skill: Speaking
Level: B1
Goal: Reschedule
Context: Everyday / Work
Quantity: 20
```

System may generate:

```text
You have a meeting at 3 PM but something urgent came up.
Ask to move it to tomorrow morning.
```

```text
Call a clinic and ask to move your appointment to next week.
```

```text
A friend wants to meet tonight, but you cannot.
Suggest another day.
```

The system internally prepares valid response criteria and feedback behavior.

Admin only reviews whether the situations and wording make sense.

---

## 45.2 Example — Generate From Listening Content

Admin opens a media item containing:

`I figured you were tied up.`

Choose:

- Generate Practice
- Level B1
- types:
  - comprehension
  - phrase reuse
  - speaking situation
  - vocabulary transfer

System proposes samples such as:

### Comprehension

`Why didn't the speaker stay?`

### Reuse

`Your friend did not answer. You think they were busy. Respond naturally.`

### Situation Reaction

`You stopped by a colleague's desk but they were in a meeting. Explain why you left.`

### Vocabulary Transfer

A later prompt that requires retrieval without showing the original phrase.

Admin can Accept / Regenerate / Edit wording.

---

## 45.3 Relationship to learner UI

Practice Generator is an Admin production tool.

Learners never see:

- generator configuration;
- rubric generation;
- internal semantic elements;
- model/provider details.

Learners only see the final practice task inside:

- Practice;
- Review;
- Reading/Listening follow-up;
- Context Transfer;
- Situation Reaction;
- Timed Production.

---

# 46. IMPORTS

Imports is one operational history across content domains.

## Screen A28 — Imports Home

Filters/sub-scopes:

- All
- Books
- Media
- Vocabulary
- Reading Jobs
- Failed
- History

Each row:

- type
- source/input
- created
- stage
- status
- result

Status examples:

- Queued
- Running
- Success
- Duplicate
- Partial
- Failed

Tap → Job Detail.

---

## Screen A29 — Reading Job Detail

Show:

- Job ID
- input type
- source
- created
- current stage
- attempts
- status

Timeline may include:

- Fetching
- Normalizing
- Deduplicating
- Analyzing
- Building Candidate

Result links:

- source item
- review candidate/article

If failed:

- error category
- short error
- retry eligibility

Actions:

- Retry
- Open Result
- Open Source

No raw stack trace by default.

---

## Screen A30 — Import History

Fields:

- domain
- source
- result
- started
- completed
- status

Filters:

- domain
- status
- date
- source

---

# 47. OPERATIONS

Operations is for system health, not content editing.

Sub-areas:

- Runtime
- Workers
- Source Polling
- Errors / Slow Operations

---

## Screen A31 — Runtime

Show:

- app version
- persistence backend
- schema state
- AI runtime mode
- environment/runtime facts

Never expose secrets.

---

## Screen A32 — Workers

### Worker list/status

- worker identity
- state
- concurrency
- heartbeat
- running jobs
- failed jobs
- last success
- last failure

### Queue summary

- queue depth
- waiting
- running
- failed

Actions only when supported:

- Retry failed
- Run pending work
- Open job

Do not invent Start/Stop if backend does not expose it.

---

## Screen A33 — Source Polling

Show when capability exists:

- active sources
- due sources
- last poll
- failures
- next poll

Tap source → Source Detail.

---

## Screen A34 — Errors / Slow Operations

Actionable events only.

Possible rows:

- AI failure
- import failure
- worker failure
- source failure
- slow operation

Fields:

- type
- affected capability
- time
- short message
- request/job ID
- status

Tap → detail drawer.

This is not a raw log viewer.

---

# 48. ADMIN COMMON STATES

Every Admin list/detail supports relevant states:

## Loading

Skeleton/table placeholder.

## Empty

Explains:

- what is empty
- why
- next admin action

## Error

Show:

- short error
- Retry
- request ID when useful

## Unavailable

Example:

- provider not configured
- telemetry not collected
- worker feature absent

## Running / Pending

For:

- provider test
- import job
- reprocess
- generation

## Success

Use toast/banner and update row state.

---

# 49. ADMIN COMMON INTERACTIONS

## Table/list row

Tap/click → detail.

## Filters

Desktop:

- inline chips/controls.

Mobile:

- filter sheet.

## Bulk selection

Use only where operations are safe and meaningful.

## Dangerous actions

Examples:

- Remove credential
- Reject
- Archive
- Unpublish
- Block source
- Archive generated set

Require confirmation when action is destructive or hard to reverse.

## Status changes

Row updates after action.

## Drawer

Useful for quick inspection without leaving list.

## Full detail

Use when workflow requires editing/review.

---

# 50. ADMIN MOBILE

Admin mobile only needs to remain fully usable.

### Lists

Table → compact card/row.

### Detail

Desktop split view → stacked full-screen detail.

### Review Detail

Tabs:

- Article
- Source
- Targets
- Evidence

### Actions

Primary action may use sticky bottom action bar.

### Navigation

Admin sections accessible through drawer/compact nav.

No horizontal page zoom required.

---

# 51. ADMIN FLOW MAP

```text
ADMIN ENTRY
→ OVERVIEW

OVERVIEW
├─ Needs Attention → exact problem area
├─ AI issue → AI & Models
├─ content waiting → Content / Review Queue
├─ failed import → Imports / Job
└─ worker issue → Operations

AI & MODELS
├─ Provider
│  ├─ Configure
│  ├─ Test
│  └─ Detail
└─ Capability Route
   ├─ Change Provider/Model
   ├─ Test
   └─ Save

USERS
→ User List
→ User Detail

CONTENT
├─ Books
├─ Media
├─ Vocabulary
├─ Reading
│  ├─ Overview
│  ├─ Review Queue
│  │  └─ Review Detail
│  │     ├─ Publish
│  │     ├─ Reject
│  │     └─ Archive
│  ├─ Published
│  ├─ Rejected
│  ├─ Archived
│  ├─ Sources
│  │  └─ Source Detail
│  └─ Add Content
└─ Practice Templates
   ├─ Template List
   ├─ Template Editor
   ├─ Generate Samples
   └─ Publish Version

IMPORTS
→ Jobs
→ Job Detail
→ Retry / Open Result

OPERATIONS
├─ Runtime
├─ Workers
├─ Source Polling
└─ Errors / Slow Operations
```

---

# 52. ADMIN SCREEN CHECKLIST

A design must include at least:

## Shell
- A0 Admin Shell desktop
- A0 Admin Shell mobile

## Overview
- A1 Overview
- Needs Attention state

## AI & Models
- A2 AI & Models
- A3 Provider Configure
- A4 Provider Detail
- A5 Capability Routing
- Test running/success/failure

## Users
- A6 Users List
- A7 User Detail

## Content
- A8 Content Home
- A9 Books
- A10 Book Detail
- A11 Media
- A12 Media Detail
- A13 Vocabulary
- A14 Vocabulary Detail

## Reading
- A15 Reading Overview
- A16 Review Queue
- A17 Review Detail
- A18 Published
- A19 Rejected
- A20 Archived
- A21 Add Content
- A22 Sources
- A23 Source Detail

## Practice Generator
- A24 Generator Home
- A25 Generate Practice Setup
- A26 Generated Sample Review
- A27 Generated Set Review / Publish

## Imports
- A28 Imports
- A29 Job Detail
- A30 History

## Operations
- A31 Runtime
- A32 Workers
- A33 Source Polling
- A34 Errors/Slow Operations

## States
- Loading
- Empty
- Error
- Unavailable
- Running
- Success
- confirmation dialog
- mobile row/detail behavior

---

# 53. FINAL MENTAL MODEL

```text
LEARNER APP

TODAY
= personalized starting point
+ what matters today
+ small reminders and evidence

DISCOVER
= browse and find content worth reading/listening to

ORENA
= contextual learning agent
+ understand learner context
+ find
+ explain
+ recommend
+ route to action

PRACTICE HUB
= actively train a skill
+ resume unfinished practice

MY LIBRARY
= saved content and saved language
+ collections
+ due review
+ recall
+ use
+ transfer
+ timed retrieval

PROGRESS
= evidence + motivation destination
+ what is improving
+ what still needs work
+ milestones/rank
+ reason to keep learning

PROFILE
= account, languages, preferences and plan


PLATFORM ADMIN

OVERVIEW
= what needs operator attention

AI & MODELS
= provider/model/capability routing

USERS
= account and learner administration

CONTENT
= books/media/vocabulary/reading/practice generation

IMPORTS
= ingestion and processing jobs

OPERATIONS
= runtime/workers/queues/errors
```

Reading and Listening create encounters and saved learning objects.

Speaking and Writing create production evidence.

My Library stores what belongs to the learner and contains the Review / Recall / Transfer loop.

Practice Hub is where the learner intentionally trains and where unfinished tasks are resumed.

Orena Agent can be entered directly or called from a learning context and should return the learner to the exact source/task when closed.

Progress observes evidence across the whole system and occupies its own primary navigation destination because learners should be able to revisit it frequently for feedback and motivation.

There is no standalone Continue destination.
