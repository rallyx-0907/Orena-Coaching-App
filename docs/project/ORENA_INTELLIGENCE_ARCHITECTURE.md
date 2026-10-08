# Orena Intelligence — Conversation & Memory Architecture Target

## 1. Mục tiêu

Orena Intelligence phải trở thành một **conversational intelligence layer** xuyên suốt toàn bộ Orena, không phải một chatbot nhỏ gắn bên cạnh từng màn học.

Trải nghiệm nhắn tin phải gần với các chatbot LLM hiện đại như ChatGPT, Gemini hoặc DeepSeek:

- người dùng có thể trò chuyện tự nhiên nhiều lượt;
- có thể hỏi tiếp bằng các câu như “cái đó”, “ý trên”, “từ vừa rồi”, “cho ví dụ khác”;
- có thể paste một đoạn văn rất dài rồi hỏi về nội dung đó;
- có thể chuyển qua lại giữa text và voice trong cùng một conversation;
- không bị mất ngữ cảnh giữa các lượt;
- agent hiểu màn hình và nội dung hiện tại khi điều đó có ích;
- agent có thể dùng Orena tools khi cần;
- càng sử dụng lâu, Orena càng hiểu cách học, preference và những khó khăn lặp lại của người dùng.

Không xây một bản sao đầy đủ của Hermes.

Không thêm một hệ thống orchestration nặng nếu runtime hiện tại đã xử lý được tools, provider, SSE, evidence, authentication và actions.

Target là:

> ChatGPT-like conversation + Orena context + Orena tools + long-term learner memory.

---

# 2. Nguyên tắc kiến trúc

## 2.1 LLM-first, orchestration-thin

Không xây nhiều classifier, intent router và rule trước khi model được nhìn thấy cuộc hội thoại.

Default flow:

```text
User input
    ↓
Conversation Context
    ↓
Relevant Orena Context
    ↓
LLM
    ↓
Answer OR Tool/Action
```

Chỉ dùng deterministic logic cho các trường hợp có side effect hoặc continuation rõ ràng, ví dụ:

```text
Agent:
Bạn muốn lưu "mitigate" không?

User:
ok lưu
```

Nếu có pending action `save_word("mitigate")`, runtime phải xử lý trực tiếp.

Không cần gọi LLM để đoán lại user đang muốn gì.

Nhưng với các câu như:

```text
ý trên là sao?
giải thích dễ hơn
cho thêm ví dụ
không phải cái đó, cái phía trên
tác giả có đúng không?
```

hãy để LLM xử lý bằng conversation context.

---

# 3. Target Architecture

```text
                    ORENA INTELLIGENCE

 TEXT ────────────────┐
                      │
 VOICE → STT ─────────┤
                      │
 PASTE / DOCUMENT ────┤
                      │
 SELECTED CONTENT ────┤
                      ▼

          ┌─────────────────────────┐
          │ Conversation Runtime    │
          │                         │
          │ recent turns            │
          │ rolling summary         │
          │ active topic            │
          │ referents               │
          │ pending interaction     │
          │ active task             │
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │ Context Assembler       │
          │                         │
          │ conversation context    │
          │ current screen          │
          │ selected content        │
          │ relevant learner state  │
          │ relevant memories       │
          └────────────┬────────────┘
                       │
                       ▼
                  ┌─────────┐
                  │   LLM   │
                  └────┬────┘
                       │
            ┌──────────┴──────────┐
            │                     │
          answer               tool/action
            │                     │
            └──────────┬──────────┘
                       ▼
               Unified Response
                       │
              ┌────────┴────────┐
              ▼                 ▼
             TEXT              VOICE
                             TTS output

                       │
                       ▼
          ┌─────────────────────────┐
          │ Memory Distiller        │
          │                         │
          │ keep only useful        │
          │ durable information     │
          └────────────┬────────────┘
                       │
                       ▼
                Long-term Memory
```

---

# 4. Conversation Runtime

Đây là phần ưu tiên số 1.

Runtime hiện tại không được tiếp tục coi mỗi lượt user là một request gần như độc lập.

Mỗi conversation cần có một state riêng.

Target:

```python
ConversationState {
    session_id

    recent_turns
    rolling_summary

    active_topic
    referents

    pending_interaction
    active_task

    created_at
    updated_at
}
```

---

# 5. Recent conversation

Agent phải nhìn thấy conversation gần đây.

Target ban đầu:

```text
10–20 recent turns
+
rolling conversation summary
```

Không gửi toàn bộ conversation vô hạn vào model.

Ví dụ:

```text
Recent turns:
User: mitigate nghĩa là gì?
Assistant: ...
User: cho ví dụ kỹ thuật
Assistant: ...

Summary:
- User đang đọc bài về energy systems.
- User đang hỏi vocabulary.
- Current active word = mitigate.
- User thích giải thích bằng tiếng Việt ngắn gọn.
```

Khi conversation dài:

```text
older turns
    ↓
summarize / compact
    ↓
rolling summary

recent turns
    ↓
keep verbatim
```

---

# 6. Referential context

Runtime phải hỗ trợ các câu tự nhiên như:

```text
từ đó
cái đó
ý trên
câu vừa rồi
đoạn này
nó
cái thứ hai
từ vừa nãy
```

Không hard-code từng phrase.

Giữ một state nhỏ:

```json
{
  "active_topic": {
    "type": "word",
    "value": "mitigate"
  },

  "referents": {
    "current_word": "mitigate",
    "current_sentence": "...",
    "current_paragraph": "..."
  }
}
```

LLM sử dụng referents cùng conversation history để hiểu follow-up.

---

# 7. Pending Interaction

Đây là state deterministic quan trọng nhất.

Không tạo `pendingSaveWord`, `pendingNavigate`, `pendingSomethingElse` riêng lẻ.

Tạo primitive generic:

```python
PendingInteraction {
    id
    kind
    action
    payload
    created_at
    expires_at
    status
}
```

Ví dụ:

```json
{
  "kind": "action_confirmation",

  "action": "save_word",

  "payload": {
    "text": "mitigate",
    "lang": "en"
  },

  "status": "pending"
}
```

Flow:

```text
Assistant:
Bạn muốn lưu từ này không?

pending_interaction =
save_word("mitigate")

User:
ok lưu

→ detect confirmation
→ execute/emit save_word("mitigate")
→ clear pending interaction
→ return success
```

User:

```text
không
```

→ cancel pending interaction.

User:

```text
khoan, từ đó có formal không?
```

→ không execute action.

→ conversation tiếp tục bình thường.

Pending interaction phải hỗ trợ ít nhất:

```text
confirm
cancel
expire
replace
complete
```

---

# 8. Do not route normal language through excessive filters

Không tạo pipeline kiểu:

```text
message
→ language classifier
→ intent classifier
→ screen classifier
→ question classifier
→ learning classifier
→ profile classifier
→ model
```

Target:

```text
message
+ conversation
+ relevant app context
→ model
```

Chỉ intercept trước model khi:

1. pending interaction có thể resolve deterministic;
2. permission/security bắt buộc;
3. input validation kỹ thuật;
4. rate limit;
5. action có side effect cần kiểm soát.

Không dùng rule để thay thế khả năng hiểu ngôn ngữ của LLM.

---

# 9. Message model

Không tiếp tục coi một message chỉ là:

```json
{
  "message": "hello"
}
```

Thiết kế message theo dạng content blocks.

Ví dụ:

```json
{
  "role": "user",

  "content": [
    {
      "type": "text",
      "text": "Giải thích đoạn này"
    },

    {
      "type": "quoted_text",
      "text": "Artificial intelligence has fundamentally..."
    }
  ]
}
```

Target content types:

```text
text
quoted_text
selected_word
selected_sentence
selected_paragraph
image
audio
document
```

Không cần implement tất cả ngay.

Nhưng schema phải cho phép mở rộng mà không phải rewrite protocol.

---

# 10. Long pasted content

Người dùng phải được phép paste paragraph, article hoặc text dài trực tiếp vào chat.

Không ép user:

```text
Import
→ Reading
→ Analyze
→ Ask
```

Nếu input nằm trong model/context limit, xử lý trực tiếp.

Ví dụ:

```text
User:
[paste 2500 words]

"Tác giả đang phản biện điều gì?"
```

Agent phải trả lời trực tiếp.

Nếu content quá lớn:

```text
chunk / compact / attach reference
```

nhưng UX vẫn phải giống một cuộc trò chuyện.

Nếu thấy nội dung phù hợp để tạo Reading content, agent có thể đề nghị:

```text
Tôi có thể lưu nội dung này thành một bài Reading để bạn học tiếp.

[Save to Reading]
```

Đây là optional action.

Không được ép workflow đó trước khi trả lời câu hỏi.

---

# 11. Voice và Text phải dùng cùng một conversation

Voice không được trở thành một agent/runtime khác.

Flow:

```text
Audio
 ↓
STT
 ↓
normal user message
 ↓
same Conversation Runtime
 ↓
same LLM/tools
 ↓
assistant response
 ↓
optional TTS
```

Ví dụ:

```text
VOICE:
"mitigate nghĩa là gì?"

TEXT:
"cho ví dụ kỹ thuật"

VOICE:
"ừ lưu từ đó đi"
```

Cả ba lượt phải thuộc cùng một conversation.

Agent phải hiểu `"từ đó"` là `mitigate`.

---

# 12. Context Assembler

Không dump toàn bộ database, learner profile và history vào mỗi prompt.

Context priority:

```text
1. Current user message

2. Pending interaction

3. Recent conversation

4. Conversation summary

5. Current screen / selected content

6. Relevant learner memory

7. Relevant learner profile

8. Tool/RAG data if required
```

Conversation luôn có priority cao hơn profile.

Bug kiểu:

```text
User:
ok lưu

Agent:
Dựa trên hồ sơ học tập của bạn...
```

không được phép xảy ra.

---

# 13. Current App Context

Agent vẫn phải biết user đang ở đâu trong Orena.

Ví dụ:

```json
{
  "surface": "reading",
  "content_id": "...",
  "selected_word": "mitigate",
  "selected_sentence": "...",
  "current_paragraph": "..."
}
```

Nhưng app context chỉ là context.

Không phải command router.

Ví dụ đang ở Reading nhưng user hỏi:

```text
Docker container khác VM thế nào?
```

Agent vẫn trả lời câu hỏi bình thường.

Không cố biến nó thành câu hỏi Reading.

---

# 14. Tools

Giữ hệ tools hiện tại nếu đã hoạt động tốt.

LLM có thể quyết định:

```text
answer normally
OR
call tool
```

Ví dụ:

```text
"What does mitigate mean?"
```

không cần tool.

```text
"Lưu từ đó."
```

→ `save_word`

```text
"Tôi còn bao nhiêu từ đến hạn?"
```

→ learner-data tool.

```text
"Màn này dùng để làm gì?"
```

→ screen context là đủ, không gọi learner-data tool.

Không gọi tool chỉ vì có tool.

---

# 15. Tool side effects

LLM không được tự tuyên bố action đã thành công.

Flow:

```text
LLM requests action
      ↓
runtime/tool executes
      ↓
tool result
      ↓
assistant confirmation
```

Không:

```text
LLM:
"Đã lưu từ rồi."

nhưng save_word chưa chạy.
```

Mutating actions phải có:

```text
idempotency
success/failure result
clear confirmation
```

Ví dụ user gửi:

```text
ok lưu
ok lưu
```

không được tạo duplicate.

---

# 16. Memory architecture

Memory phải tách khỏi conversation.

Có ba tầng.

## Working Memory

Sống trong conversation:

```text
current topic
current referents
pending action
recent turns
active task
```

---

## Episodic Memory

Những observation hữu ích từ các lần học:

```text
User repeatedly confuses affect/effect.

User struggled with phrasal verbs in this lesson.

User requested technical examples several times.
```

---

## Durable Learner Profile

Những thông tin tương đối ổn định:

```text
English level: B2

Goal: C1

Preferred explanation language: Vietnamese

Preferred verbosity: concise

Prefers practical/technical examples
```

---

# 17. Memory Distiller

Không lưu tất cả conversation thành memory.

Sau conversation hoặc theo interval, một lightweight process đánh giá:

```text
Có thông tin nào đủ hữu ích để dùng lại trong tương lai?
```

Candidate format:

```json
{
  "category": "preference",
  "fact": "User prefers concise explanations in Vietnamese",
  "confidence": 0.94,
  "importance": 0.82
}
```

Trước khi lưu:

```text
deduplicate
contradiction check
update existing memory if needed
```

Ví dụ:

Old:

```text
prefers detailed explanations
```

New repeated evidence:

```text
prefers concise explanations
```

Không lưu hai fact mâu thuẫn mãi mãi.

Update memory hiện tại.

---

# 18. Memory retrieval

Không inject toàn bộ user memory vào prompt.

Retrieve chỉ những memory có liên quan.

Ví dụ user hỏi vocabulary:

```text
Relevant memory:

- prefers Vietnamese explanations
- prefers concise answers
- technical examples work well
```

Không cần inject:

```text
writing history
listening history
30 previous lessons
payment data
all vocabulary
```

---

# 19. Storage tối thiểu

Không cần hệ thống memory nặng trong phase đầu.

Có thể bắt đầu bằng PostgreSQL.

Suggested structures:

```text
conversation_sessions

conversation_turns

user_memories
```

Ví dụ:

```text
conversation_sessions
- id
- user_id
- summary
- active_topic
- referents
- pending_interaction
- created_at
- updated_at
```

```text
conversation_turns
- id
- session_id
- role
- content
- created_at
```

```text
user_memories
- id
- user_id
- category
- fact
- importance
- confidence
- created_at
- updated_at
- last_used_at
- source_session_id
- embedding optional
- metadata
```

Không cần external vector DB ban đầu.

Nếu semantic retrieval trở nên cần thiết, dùng PostgreSQL + pgvector trước.

---

# 20. Response rendering

Agent chat phải đạt baseline của chatbot hiện đại.

Text response hỗ trợ:

```text
Markdown
headings
bold/italic
lists
tables
blockquote
code block
inline code
links
```

Learning-specific response có thể render native component.

Ví dụ vocabulary:

```text
mitigate · verb
/ˈmɪtɪɡeɪt/

giảm nhẹ; làm giảm mức độ nghiêm trọng

Example:
The controller mitigates voltage spikes.

[Save]
```

Nhưng nếu component không khả dụng, Markdown fallback vẫn phải đọc đẹp.

Không phụ thuộc hoàn toàn vào model để tạo UI layout.

---

# 21. Chat UX baseline

Text experience phải hỗ trợ dần:

```text
streaming output
Markdown
copy response
stop generation
retry
edit/resend user message
long text input
paste large content
scroll stability
clear tool states
voice playback
```

Tool execution không được biến giao diện thành control dashboard.

Ví dụ:

```text
Checking your vocabulary...
```

hoặc một subtle status là đủ.

---

# 22. What NOT to build now

Không làm trong phase này:

```text
multi-agent swarm
subagents
Hermes-compatible gateway
skill marketplace
sandbox environment
complex planning engine
separate agent per learning feature
external vector infrastructure
knowledge graph
dozens of intent classifiers
workflow per phrase
```

Chỉ thêm những phần thật sự cần để conversation hoạt động tự nhiên.

---

# 23. Keep existing Orena capabilities

Không rewrite những phần đã tốt nếu không có lý do rõ ràng.

Preserve:

```text
provider abstraction
tool registry
learner-scoped authentication
evidence grounding
SSE streaming
action contract
rate limiting
telemetry
permission boundaries
```

Conversation Kernel phải nằm phía trước/bao quanh runtime hiện tại, không phá các capability trên.

---

# 24. Target runtime flow

Pseudo flow:

```python
async def handle_turn(request):

    session = load_conversation(request.session_id)

    user_message = normalize_message(request)

    resolution = resolve_pending_interaction(
        session.pending_interaction,
        user_message
    )

    if resolution.is_action:
        result = execute_action(resolution.action)

        update_conversation(session, user_message, result)

        return render_action_result(result)

    context = assemble_context(
        user_message=user_message,
        recent_turns=session.recent_turns,
        summary=session.summary,
        referents=session.referents,
        app_context=request.app_context,
        memories=get_relevant_memories(...)
    )

    response = run_llm(
        context=context,
        tools=available_tools
    )

    execute_required_tools(response)

    update_conversation_state(
        session,
        user_message,
        response
    )

    schedule_memory_distillation_if_needed(...)

    return stream_response(response)
```

---

# 25. Example target interaction

### Turn 1

```text
User:
mitigate nghĩa là gì?
```

```text
Orena:

**mitigate** /ˈmɪtɪɡeɪt/ · verb

Làm giảm mức độ nghiêm trọng hoặc tác hại của một thứ gì đó.

Example:
The controller helps mitigate voltage spikes.

Bạn muốn lưu từ này không?

[Save]
```

Runtime:

```text
active_topic = mitigate

pending_interaction =
save_word("mitigate")
```

### Turn 2

```text
User:
cho thêm ví dụ kiểu điện tử
```

Không execute save.

Conversation tiếp tục:

```text
Orena:

The capacitor helps mitigate voltage spikes during switching.

Ở đây **mitigate** = làm giảm mức độ nghiêm trọng của voltage spike.
```

Pending save vẫn có thể tồn tại nếu policy cho phép.

### Turn 3

```text
User:
ừ lưu đi
```

Runtime resolve:

```text
save_word("mitigate")
```

Tool success:

```text
Orena:
Đã lưu **mitigate** ✓
```

### Turn 4

```text
User:
còn từ trước nó là gì ấy?
```

Agent dùng conversation history/referents để hiểu và trả lời.

Không hỏi user nhập lại từ nếu có đủ context.

---

# 26. Long-content example

```text
User:
[pastes 3000-word article]

Tóm lại tác giả phản đối điều gì?
```

Expected:

```text
Agent đọc trực tiếp nội dung được paste.

Không yêu cầu Import Reading.

Không redirect user sang một màn khác.

Không gọi learner profile nếu không cần.

Trả lời dựa trên article.
```

Follow-up:

```text
User:
đoạn thứ 3 lập luận có yếu không?
```

Agent phải hiểu `"đoạn thứ 3"` dựa trên content và conversation trước đó.

---

# 27. Cross-modality example

```text
Voice:
"scarcity nghĩa là gì?"

Orena:
...

Text:
"cho ví dụ với điện"

Orena:
...

Voice:
"ừ lưu cái đó"

→ save_word("scarcity")
```

Cùng session.

Không reset context khi đổi input modality.

---

# 28. Implementation priority

## Phase 1 — Basic Conversation Kernel

Làm trước mọi intelligence feature khác.

Implement:

```text
recent turns
conversation persistence
rolling summary
referents
generic pending interaction
confirmation/cancel resolution
```

Acceptance:

- `"ok lưu"` hoạt động đúng;
- `"cái đó"` hoạt động;
- `"ý trên"` hoạt động;
- `"cho ví dụ nữa"` hoạt động;
- multi-turn conversation không mất context.

---

## Phase 2 — Chat UX

Implement:

```text
proper Markdown rendering
long input
paste large content
stable streaming
copy
retry
stop
edit/resend where appropriate
```

---

## Phase 3 — Unified Text + Voice

Voice transcript trở thành normal conversation turns.

Text và voice share the same session.

---

## Phase 4 — Long-term Memory

Implement:

```text
user_memories
memory distillation
deduplication
contradiction/update
relevant retrieval
```

---

## Phase 5 — Context efficiency

Add:

```text
rolling summarization
token budgeting
relevance scoring
optional pgvector
```

Chỉ sau khi basic conversation đã VERIFIED.

---

# 29. Required tests

Không chỉ test isolated commands.

Phải có conversational E2E.

### Save continuation

```text
User: "abate nghĩa là gì?"
Agent: explains + offers save

User: "ok lưu"

Expected:
- exactly one save_word(abate)
- confirmation shown
- no learner-profile tangent
```

### Cancel

```text
User: "abate nghĩa là gì?"
Agent offers save

User: "không"

Expected:
- no save
- conversation continues normally
```

### Follow-up

```text
User: "mitigate nghĩa là gì?"
User: "cho ví dụ khác"
User: "formal không?"
User: "từ đó lưu đi"

Expected:
save mitigate
```

### Referential context

```text
User: "giải thích câu này"
User: "ý thứ hai là sao?"
User: "cho ví dụ khác về nó"
```

Expected:
all turns resolve correctly.
```

### Long pasted content

```text
User pastes long article.
User asks question.
User asks follow-up without pasting again.
```

Expected:
context remains available.
```

### Cross modality

```text
voice
→ text
→ voice
```

Expected:
same conversation context.
```

### Idempotency

```text
User: "ok lưu"
User accidentally repeats: "ok lưu"
```

Expected:

```text
one saved vocabulary item
no duplicate mutation
```

---

# 30. Definition of Done

Không tuyên bố Orena Intelligence conversation complete chỉ vì unit tests pass.

Phải VERIFIED bằng live product.

Minimum acceptance:

```text
1. 20+ turn conversation không mất topic bất thường.

2. Pronouns/references:
   "nó"
   "cái đó"
   "ý trên"
   "từ vừa rồi"
   hoạt động trong normal usage.

3. Pending actions survive natural follow-up.

4. Text và voice dùng chung context.

5. User có thể paste long-form content rồi hỏi nhiều lượt.

6. Markdown/chat rendering đạt mức chatbot hiện đại cơ bản.

7. Profile/RAG không hijack short conversational continuations.

8. Mutating tools execute exactly once.

9. Long conversations được compact mà vẫn giữ semantic continuity.

10. Memory chỉ được retrieve khi relevant.

11. Agent không claim tool action thành công trước tool result.

12. Existing evidence/auth/tool safety vẫn pass regression.
```

---

# 31. Core product rule

Orena Intelligence không được thiết kế như:

```text
Learning workflow
+
chatbot widget
```

Target là:

```text
                    Orena Intelligence
                            │
           ┌────────────────┼─────────────────┐
           │                │                 │
        Reading         Vocabulary         Speaking
           │                │                 │
           └────────────────┼─────────────────┘
                            │
                    same conversation
                    same memory
                    same intelligence
```

Orena Intelligence là lớp intelligence xuyên suốt product.

---

# 32. Final architectural rule

LLM chịu trách nhiệm cho:

```text
natural language understanding
conversation
reasoning
explanation
follow-up interpretation
tool selection
```

Runtime chịu trách nhiệm cho:

```text
conversation state
context selection
memory
permissions
tool execution
side effects
idempotency
authentication
evidence
persistence
```

Không cố biến runtime thành một LLM bằng rules.

Không để LLM tự giả lập những thứ runtime phải đảm bảo.

Đây là boundary cần giữ trong toàn bộ Orena Intelligence.

---

# Execution instruction

Implement architecture này theo hướng incremental trên runtime hiện tại.

Không rewrite toàn bộ Orena Intelligence.

Trước khi sửa:

1. map current session/context/turn/action flow;
2. xác định phần nào có thể reuse;
3. xác định code đang special-case follow-up;
4. thêm Conversation Kernel ở boundary nhỏ nhất có thể;
5. giữ backward compatibility với contract hiện tại nếu hợp lý;
6. thêm migration/versioning nếu request/session contract thay đổi;
7. thêm conversational E2E trước khi mở rộng feature mới.

Ưu tiên đầu tiên:

> Make Orena a competent continuous chatbot before making it a more sophisticated agent.

Không tiếp tục thêm intelligence feature mới nếu basic multi-turn conversation, contextual references và pending actions chưa VERIFIED.