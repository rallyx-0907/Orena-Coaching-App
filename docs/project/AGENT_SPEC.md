# Orena Intelligence Agent — Implementation Spec v2.1 (lane feature/orena-intelligence, D-085)

> Thay thế toàn bộ v1 và v2. Khi v2.1 mâu thuẫn với bản cũ, v2.1 thắng.
> Bản này được viết lại sau khi đọc `codex/work`, `feature/speaking`, `admin/control-center`
> và governance của repo (`AGENTS.md`, `docs/project/*`). Mục 0 và Phụ lục A ghi những gì đã kiểm chứng.
>
> File này nằm tại `docs/project/AGENT_SPEC.md` trên lane `feature/orena-intelligence` (D-085).
> Trạng thái nền tại thời điểm viết (2026-09-27): `codex/work` là unified baseline sau PR #63
> (9c0fe315…, Admin + Speaking đã merge, external review); D-085 đã ghi trong DECISION_LOG.md và
> CURRENT_HANDOFF.md. Lane này được tạo từ baseline đó.
>
> **Giao diện nằm ngoài lane này.** UI mới thay toàn bộ UI cũ trên `codex/work` (D-086) và chỉ UI mới có agent.
> Hai lane gặp nhau duy nhất ở `docs/project/AGENT_CONTRACT.md` — file đó thắng mọi mục trong spec này
> khi nói về request, event, action, intent. Contract chỉ được sửa trên `codex/work`; lane này nhận bằng merge.

---

## 0. Quyết định đã chốt (đọc trước)

```text
D1  LANE = feature/orena-intelligence, mở bằng D-085 (2026-09-27, explicit human direction),
    tạo từ codex/work sau PR #63 (Admin + Speaking đã merge). D-085 cho lane này: (a) sở hữu
    orchestration phía trên product — learner context, evidence/memory assembly, capability discovery
    & routing, contextual handoff, agent actions, conversation coordination, model/provider abstraction;
    (b) tái dùng domain service hiện có, không tạo engine trùng; (c) action là explicit, schema-bound,
    allowlisted; (d) identity là Orena, đổi provider không đổi identity; (e) KHÔNG cấp quyền
    learner-UI redesign, production provider activation, shared-runtime migration, deployment,
    destructive persistence change; (f) tích hợp ngược về codex/work cần review + verification riêng.
    Agent không tạo branch/worktree nào khác (AGENTS.md §3).
D2  Không self-host model nào cho agent. Não, S2S, TTS đều là managed API.
    Ollama không nằm trong bất kỳ đường đi nào của agent (handoff: Ollama leak target script,
    17–54 s/call). Kokoro local TTS hiện có cho word audio giữ nguyên, không thuộc phạm vi agent.
D3  Tái dùng lớp provider có sẵn `writing_coach/ai/` (catalog, capability key, routing chain,
    cooldown, pricing, credentials, control plane, cấu hình qua Admin › AI). Agent THÊM
    operation + capability key vào lớp này; không tạo stack provider song song.
D4  Vendor mặc định V1 (đổi được bằng cấu hình, không sửa code):
      Não text      : Gemini (đã cấu hình và có key trong sandbox; R3 live gate 4/4)
      S2S voice     : Gemini Live  — ứng viên so sánh trong spike: Azure Voice Live, GPT-Live 1
      TTS fallback  : Gemini TTS (vi-VN GA, ja-JP GA, zh-CN preview)
      STT cascade   : Groq ASR (adapter có sẵn trong speech_asr.py)
      Pronunciation : Azure Pronunciation Assessment (adapter có sẵn); SpeechSuper chờ quyết định
D5  "Mức CSM" = trải nghiệm hội thoại (full-duplex, ngắt lời, prosody theo ngữ cảnh), không phải
    model CSM-1B. en phải đạt; vi và zh tốt nhất trong tầm giá. Không dùng CSM-1B/Dia2/Qwen3-TTS.
D6  V1: mọi mutation và navigation là CLIENT-EXECUTED ACTION. Agent backend chỉ đọc.
D7  V1 KHÔNG thêm migration/schema. Session = cache server có TTL + device memory;
    coach notes = device memory. Bảng thật chỉ sau independent architecture review theo
    docs/product/ORENA_ACCOUNT_DATA_ARCHITECTURE.md (AGENTS.md §7, handoff BLOCKED).
    Chuỗi Alembic hiện là 16 revision, một head duy nhất 20260924_0016 (Reading đã đánh số lại
    0015/0016). Migration Reading 0015/0016 CHƯA được phép apply lên shared runtime (:8011);
    sandbox của lane này dùng throwaway PostgreSQL upgrade đủ 16 revision.
D8  Ngôn ngữ theo D-079/D-080 (lane Speaking): ba lớp `interface`, `support`, `target`;
    mọi copy key khai báo lớp. Thêm `content` cho ngôn ngữ của nội dung. Chinese chỉ zh-CN.
D9  EN và ZH là first-class, mỗi slice giao cả hai (ARCHITECTURE_INVARIANTS; REVIEW_POLICY chấm P1
    nếu EN trước ZH sau). VI là interface/support.
D10 Bằng chứng phát âm: "no fake pronunciation result" (D-066). Agent chỉ được gọi là lỗi những gì
    provider flag; điểm hạ mà không flag thì nói là "bị hạ điểm", không suy ra nguyên nhân.
D11 UI KHÔNG thuộc lane này (D-086). UI mới thay toàn bộ UI cũ (kể cả behavior, thêm/bỏ luồng) trên
    codex/work, và chỉ UI mới có agent. Lane này không sửa static/orena/**, templates/**, không dựng
    panel, không viết mock frontend. Giao diện giữa hai lane là docs/project/AGENT_CONTRACT.md.
    Agent không bao giờ nêu route/screen: chỉ intent + action trong contract, và chỉ những gì client
    khai báo trong client.supported_actions / supported_intents (contract §3.1).
D12 Transport, request, event, segment, evidence, action, intent, voice session: theo AGENT_CONTRACT.md
    (hiện là contract_version 4, D-095; nhận bằng merge codex/work). Lane này implement contract; không mở
    rộng contract tại đây.
D13 Contract tests: các canonical stream trong contract §12 là fixture chung. UI lane replay chúng bằng
    mock; lane này phải phát ra cùng chuỗi event và cùng shape payload (text có thể khác).
D14 Test tự động không gọi provider thật (golden WAV + fake provider). Gate là `.github/workflows/ci.yml`.
D15 Tracker gap duy nhất là docs/project/UI_BACKEND_GAPS.md. Không tạo file gap riêng.
D16 Decision model (Jev…) không dùng trong V1; chỉ giữ chỗ `DecisionProvider`.
D17 Writing và Grammar nằm trong Capability Registry V1.
D18 Memory: tự động, sửa bằng hội thoại, tự phai. User không quản lý.
```

Phán quyết của người sau pre-flight (2026-09-27). Thắng mọi đoạn bên dưới còn nói khác:

```text
R1  Capability key: Slice 1a chỉ thêm 3 AIOperation. 4 key (agent_turn_fast, agent_turn_deep,
    conversational_speech, text_to_speech) vào catalog khi codex/work đã thêm nhãn EN/ZH cho Admin
    (scripts/test_orena_admin_console.mjs đòi); khi đó: implemented=False, configurable=False, fallback {NONE}.
R2  Không tự động chuyển provider (ARCHITECTURE_INVARIANTS). Provider lỗi → error, fallback retry | text_only.
    S2S lỗi → text-only, không cascade sang vendor khác.
R3  Payload action lệch API hiện có: ghi nhận (UI_BACKEND_GAPS.md I-11..I-16), không đổi ở lane này;
    contract v2 trên codex/work xử lý.
R4  Coaching snapshot: bỏ current_level; weaknesses/strengths là gap; che producer trước khi gửi provider;
    ánh xạ zh ↔ zh-CN ở biên agent.
R5  Metering V1: chỉ đếm qua record_usage + tổng theo ngày; budget_state luôn "ok". soft_limited để sau,
    qua quota ledger (gap E1).
R6  Gemini: chưa duyệt Live, TTS, token tạm, google-genai. Slice 1b–3 dùng đường chat/completions sẵn có,
    mở rộng OpenAICompatibleProvider với streaming + tool calling; không thêm dependency.
R7  Không cần sandbox cho 1a/1b.
```

Phán quyết cho Slice 1b (2026-09-27):

```text
R8  Agent định tuyến qua active_selection legacy (như mọi lời gọi AI của learner), không chờ key riêng.
    4 key agent vào catalog ở dạng trơ (implemented=False, configurable=False, {NONE}); chuyển sang key
    riêng là một bước kích hoạt có review sau. Provider local (Ollama) bị từ chối, không bao giờ được dùng (D2).
R9  /api/agent/* tắt mặc định bằng cờ server AGENT_ENABLED; chỉ bật ở dev/sandbox; production không bao giờ
    phục vụ, dù cờ nói gì. Khi tắt, cả hai route trả 404.
R10 S5 dùng save_word { text, lang } (contract §7 cho phép). Các action lệch payload còn lại chờ contract v2.
R11 session_id không tìm thấy (restart, worker khác) → mở phiên mới, không lỗi.
R12 suggestion.intent là prompt intent (§4), không phải navigation id; mọi label (tool, action, suggestion)
    là copy lớp interface (D-080). Hai điểm này thành luật contract ở v3 (D-094): intent gợi ý thuộc
    namespace `prompt.`, label action là lớp interface.
R13 CURRENT_HANDOFF.md: lane chỉ sửa đúng mục "## Agent lane" của mình; PENDING, NEXT EXACT TASK và
    Human decisions thuộc codex/work. Chi tiết tiến độ của lane nằm ở đây (§0) và trong báo cáo slice.
```

Phán quyết cho Slice 1c (2026-09-27):

```text
R14 Merge codex/work (contract v2, D-092; rồi v3, D-094) và phục vụ phiên bản mới; client khai báo phiên bản
    thấp hơn không nhận gì phiên bản sau thêm/đổi. Id trong payload action chỉ lấy từ request hoặc từ tool đã
    đọc trong turn; id model tự nghĩ bị từ chối (contract §7).
R15 Câu hỏi danh tính/model trả lời bằng quy tắc qua DecisionProvider, trước mọi lời gọi model (§35);
    gate ưu tiên chính xác: có dấu và rõ nghĩa → copy; không dấu mà mơ hồ ("cau la gi", "ban la gi",
    "may la gi") → để model trả lời (instruction vẫn giữ danh tính Orena); không dấu mà rõ ("ban la ai") → khớp.
    Rate limit theo learner, trả 429 (§22); 404/409/429 do Codex ghi vào contract §2.1 (v4, D-095).
R16 Capability Vocabulary (vocabulary.words, review.due) và Writing (writing.review) sang active khi contract
    test v2 của chúng đạt. Sau 1c: báo cáo và dừng; bước kế là chạy live có kiểm soát với provider thật
    (gate [PROVIDER]) — người quyết.
R17 Chạy live [PROVIDER] (chuẩn bị, CHƯA chạy; chờ người duyệt kịch bản và trần chi phí): compose project
    riêng `orena-agent-live` (scripts/agent_live/compose.yaml), Postgres dùng một lần trên tmpfs, không
    named volume, cổng 127.0.0.1:8013, không bao giờ :8000/:8010/:8011/:8012; AGENT_ENABLED=true chỉ ở đó;
    provider qua active_selection legacy (Gemini gemini-3.5-flash-lite); learner phát triển của DB dùng một
    lần, không dữ liệu learner thật. Kịch bản (scripts/agent_live/run.py): S1, S5, S8, S9, S13, 2 câu danh
    tính, 3 câu tự do; target EN và ZH, support VI; mỗi turn model lặp 3 lần. Đo: hình dạng tool call và
    usage khi stream, time-to-first-segment, chi phí thực. Runner dừng trước khi vượt trần.
```

Phán quyết sau khi đọc câu trả lời live (2026-09-28):

```text
R18 Chất lượng câu trả lời: (a) action là nút người học bấm, không bao giờ tả như đã làm - có chốt chặn
    ở server (agent/honesty.py); (b) không có lỗi được đánh dấu ≠ không có lỗi: "bộ chấm chưa đánh dấu lỗi",
    không khen chung chung (D-087); (c) lịch sử viết ZH: kiểm ánh xạ zh ↔ zh-CN trước (không phải lỗi lane,
    test Postgres chứng minh); (d) tên màn hình theo lớp interface, nhãn của app, không title tiếng Anh;
    (e) giọng: mặc định mình/bạn (zh 我/你, en I/you).
R19 Xưng hô: đổi chỉ theo lời người học - họ yêu cầu, hoặc họ tự dùng nhất quán và đồng ý khi được hỏi một
    lần. Mọi cặp họ chọn (em - anh/chị, tôi - anh/chị, tao - mày, 您…), lời vẫn tôn trọng. Không suy đoán
    giới tính, tuổi, tính cách; dấu hiệu vị thành niên thì giữ mặc định. Lưu bằng memory_update như
    preference người học nói trực tiếp. Thiết kế chung cho mọi ngôn ngữ support. Copy cố định giữ mình/bạn
    tới khi contract có trường xưng hô (đề xuất v5 trên codex/work).
R20 Slice 2: read tool Speaking, Grammar, Reading, Listening. Grammar chỉ đọc R5 (/api/library/grammar*,
    Concept ID = grammar_id). Tool chỉ chạy trên PostgreSQL, test trên Postgres dùng một lần.
R21 (2026-09-28) Trạng thái SRS và mọi nhãn nội bộ đưa cho model là nhãn đã dịch theo lớp interface, kèm nghĩa
    (chưa học / đang học / đến hạn ôn / đã thuộc); không nhãn tiếng Anh nội bộ nào tới người học. Cặp xưng hô đã
    lưu được đổi lại (về mặc định hay cặp khác) bằng memory_update thay note. Câu mời gọn "Bấm Lưu từ để thêm 我
    vào từ vựng của bạn.", không mô tả nút hay giao diện. Slice 3: snapshot trên learner_summary, weaknesses,
    next activities tất định ở backend (model chỉ giải thích), coach notes lớp 3 ở device memory; S13 dùng
    snapshot. Không số liệu nào được bịa: metric không đo được thì để trống (null), không suy diễn - thay câu
    "để 0" ở §24.
R22 (2026-09-28) Xưng hô tiếng Việt theo quan hệ, thay "hỏi một lần" cho các cặp thông thường: người học tự xưng
    anh/chị → Orena xưng "em"; cô/chú/bác → "cháu"; người học xưng em gọi Orena anh/chị → Orena xưng đúng từ đó.
    Đáp theo ngay, lưu note ngay, cập nhật khi người học đổi. Phân biệt tự xưng với nói về người khác ("anh tôi");
    không chắc thì giữ cặp hiện tại. Không dùng anh/chị… nếu người học chưa dùng. tao/mày chỉ khi được yêu cầu rõ.
R23 (2026-09-28, sau live Slice 3) Câu mời do server viết: mọi câu "Bấm…/Tap…/点击…" của model bị bỏ; có action
    thì server thêm đúng một câu mời chuẩn (lớp interface, theo cặp xưng hô), không action thì không mời. Sửa/xoá
    coach note: server nhận ý định theo luật, nhắc model một lần kèm id; vẫn không gọi thì trả lời thật là chưa
    làm. Lượt mở đầu: server kiểm câu chào có dữ kiện của snapshot; không có thì dùng câu chào dựng từ snapshot.
    Không bao giờ câu chào chung chung.
R24 (2026-09-28) Contract v5 (D-096) được phục vụ: xưng hô đi qua context.address (self/user/register/lang),
    lưu bằng note kind "address" (id address-<lang>, không bao giờ trong coach_notes); server kiểm từ xưng hô
    theo đúng luật UI (chữ cái Unicode + dấu cách đơn, 1-24 ký tự, ≤3 từ; sai một chỗ thì mặc định cả object),
    chỉ áp khi lang = support, không ghi log/lưu, đưa vào model dưới dạng dữ liệu đã escape. Copy cố định (danh
    tính, lỗi, câu mời, câu chào) có chỗ {self}/{user}. Client v4: không address, không note address. Tên màn
    đọc từ static/orena/copy/surfaces.json (purpose khi UI viết). Câu "Mình lưu … cho bạn" và các dạng theo cặp
    xưng hô ("Chị lưu … cho em") là khẳng định đã làm. memory_update đứng trước segment_end (S14).
R25 (2026-09-28) Dev: agent_turn_fast và agent_turn_deep ghim cùng một model cho cả lần chạy (gemini-3.8-flash;
    gemini-3.7-flash nếu 3.8 vẫn quá tải, ghi rõ). Theo R8 agent vẫn đi qua một lựa chọn duy nhất, nên ghim trong
    sandbox là ghim cho cả hai key; key riêng vẫn là bước kích hoạt có review. Model riêng cho lượt thường chọn khi
    chuẩn bị ra mắt. Live: 503/quá tải thì thử lại cùng model tối đa 3 lần (5 s, 15 s, 45 s) rồi dừng; trần tính
    trước mỗi lần gửi, kể cả lần thử lại; ghi thời gian tới segment đầu để so với flash-lite.
R26 (2026-10-04) Review kiến trúc độc lập (người review do người chủ dự án chỉ định, không phải người viết code; review
    trên 290b676; phạm vi ai/providers.py, ai/platform.py, product/repository.py, persistence/product_repository.py,
    app.py). Dark merge: APPROVED. Kích hoạt production: CHANGES_REQUIRED. Đã sửa ở lane: (P1) chữ model viết cùng
    vòng với read tool không tới người học, câu trả lời viết sau khi đọc mới tới; (P1/P2) vòng kết thúc không bình
    thường ("length", lý do lạ, thiếu lý do) là lỗi cho người học và failure trong telemetry, không bao giờ coi là
    "stop". Điều kiện BẮT BUỘC trước khi chạy nhiều worker hoặc mở công khai (P2): giới hạn tần suất hiện là best-effort
    theo process; cần quota dùng chung theo tài khoản. Hoãn theo quyết định của người chủ dự án (2026-10-04): staging
    chạy một worker. Khi tới lúc, đề xuất trước cách đếm từ bảng usage_events sẵn có (agent.turn, agent.tokens theo
    tài khoản và cửa sổ thời gian) rồi mới nghĩ tới lưu trữ mới. Không phản đối daily_usage và phần nối app.py cho
    dark merge. Dark merge vào codex/work: người chủ dự án đồng ý (2026-10-04), agent tắt mặc định; chỉ bật trên
    staging :8011 sau khi live đạt.
R27 (2026-10-04, sau khi PR #69 được merge) Người chủ dự án:
    - Runtime: :8021 là runtime của lane UI. Lane này không tự dựng lại :8021. Người chủ dự án nhờ lane UI dựng lại
      (AGENT_DAILY_SPEND_CAP_USD=1, giữ container cũ để quay lại) khi lane đó rảnh; lane này đo baseline độ trễ và
      chi phí (dưới 0,05 USD) sau khi lane UI báo xong. Không bao giờ tự khởi động lại Docker; việc đó chỉ người chủ
      dự án làm.
    - Nhờ ghi nhớ bằng tiếng Việt không dấu: không từ chối âm thầm. Orena hỏi lại ("Bạn muốn mình ghi nhớ: …?") kèm
      nút; chỉ ghi khi người học bấm. Làm trong hợp đồng: nút là suggestion (prompt.keep_note) có nhãn "Ghi nhớ: …"
      (lớp interface), bấm vào thì nhãn thành tin nhắn tiếp theo (§4), server chỉ nhận đúng những chữ đã xác nhận.
      Không cần action mới hay lưu trữ phía server.
    - Telemetry agent.turn trong audit_logs: giữ 90 ngày, dọn tự động (agent/retention.py). Xoá dữ liệu tự động là
      thay đổi vòng đời mang tính huỷ: cần review kiến trúc độc lập trước khi bật (AGENTS.md "Architecture review
      authority"); người viết không tự duyệt. Tắt mặc định; chỉ bật bằng AGENT_TURN_RETENTION_SWEEP=true (giá trị lạ
      thì không khởi động). Lane UI review độc lập trong mục kiểm tra kỹ thuật và bảo mật; đạt thì người chủ dự án
      bật.
    - Slice 4 (giọng nói): giữ đề xuất (b936819), chưa làm.
    - Sau khi lane UI báo dựng lại :8021: đo baseline (dưới 0,05 USD), rồi nhận lỗi test của người chủ dự án.
R28 (2026-10-06) Người chủ dự án: làm giọng thật (Slice 4) "chuẩn CSM" theo D5, sau bài thử trên iPhone (không có live
    talk, không phát tiếng). Chọn:
    - Chế độ A (s2s): provider nói thẳng (Gemini Live theo D4), không phải chế độ B server viết lời. Người chủ dự án
      chấp nhận rằng lời nói không qua trọn các cổng của lượt chữ (ClaimGate, bằng chứng trước khẳng định). Server
      vẫn giữ: persona và lời dặn khoá trong token (client không đổi được); tool chỉ đọc chạy ở server qua relay, đúng
      phạm vi learner; action vẫn là nút cần chạm, server duyệt (D-135, không định tuyến không hỏi); key không tới
      client; 15 phút; không lưu âm thanh.
    - Đợt thử đầu: chỉ Gemini Live, khóa gemini-live, trần 1,00 USD/ngày, dừng ở 0,80.
    - Chạy thật (staging :8021): trần chung AGENT_DAILY_SPEND_CAP_USD=1 cho cả chữ và giọng.
    Làm (2026-10-06): POST /api/agent/voice/session, /voice/tool, /voice/end (agent/voice_session.py; token ở
    ai/live_voice.py), tắt mặc định (AGENT_VOICE_ENABLED). Token v1alpha khoá setup (model gemini-3.8-live, giọng,
    lời dặn và ngữ cảnh, tool); client gửi setup khác thì bị bỏ qua (kiểm live). Tool đọc chạy ở server qua relay,
    nút qua offer_button (server điền payload từ phần đang chọn, duyệt như propose_action). Thời gian phiên tính vào
    sổ AI (0,036 USD/phút, giá niêm yết chưa kiểm). Kiểm live (sandbox dùng một lần, khóa gemini-live, tổng ≈ 0,12
    USD theo sổ): tên (vi) 1,0 s tới tiếng đầu; nghĩa từ đang chọn (vi, zh) có đọc tool, 2,0-2,7 s; en 2,1 s; ngắt
    lời dừng sau 30 ms; nút lưu từ qua offer_button. Lần đầu model nói "đã chuẩn bị sẵn nút" mà không có nút (rủi ro
    của chế độ A) - sửa bằng offer_button và lời dặn; còn phụ thuộc model.
R29 (2026-10-06, sau bài thử trên iPhone: "mở một video trong Listening" không mở được, lặp lại, không chọn được
    giọng) Người chủ dự án:
    - Trong giọng nói, khi chính người học nói rõ muốn mở hay đi tới một nội dung, mở ngay (không chờ chạm); nút vẫn
      hiện trong luồng hội thoại. Theo tiền lệ §7: navigate tự chạy khi lời người học chính là yêu cầu đó.
    - Chọn giọng: khoảng 10 giọng hay nhất, 6 nữ và 4 nam; tên hiển thị không có tên nhà cung cấp.
    Làm (2026-10-06): read tool find_content (agent/find_tools.py: thư viện nghe và bài đọc đã xuất bản, đúng ngôn
    ngữ học, lọc theo loại, trình độ, chủ đề, chữ trong tên; mỗi mục có content_id); offer_button thêm open_content
    (media: → listening.workspace, article:/book: → reading.workspace, content_id phải do tool trả về); khi lời người
    học là yêu cầu mở/nghe/xem/đọc, /voice/tool trả thêm "open": <action id> để client mở ngay. GET
    /api/agent/voice/voices (10 giọng, 6 nữ 4 nam, mã và nhãn của Orena), thân phiên nhận "voice". Lời dặn: việc
    không làm được thì nói một lần rồi dừng. Kiểm live (≈ 0,05 USD; cả ngày ≈ 0,19 USD theo sổ): "Mở một video bất
    kỳ trong Listening" → find_content → open_content → mở ngay; cả 10 giọng chạy, tiếng đầu 1,7-3,0 s.
R30 (2026-10-06, sau bài thử trên iPhone: "Orena phải là Agent toàn năng có thể thao tác bất kì điều gì trên app khi
    người dùng yêu cầu và giữ kết nối liên tục"; nhận giọng sai ngôn ngữ) Người chủ dự án: việc an toàn mà chính
    người học yêu cầu thì Orena làm ngay; việc cần xác nhận (bỏ lưu từ) đi qua hộp xác nhận của app; không yêu cầu
    thì chỉ hiện nút. Làm: một tool do_action (tham số phẳng) cho mọi action §7 client khai báo, server dựng payload
    từ phần đang xem và duyệt như propose_action; "open" khi lời người học là yêu cầu; POST
    /api/agent/voice/context cập nhật ngữ cảnh khi người học chuyển màn hay chọn câu (trả "[context]" để client đưa
    cho model); gợi ý ngôn ngữ nhận giọng (inputAudioTranscription.languageCodes: support + target, kiểm live được
    nhận); nghe không rõ thì xin nói lại. Kiểm live (≈ 0,03 USD; cả ngày ≈ 0,24 USD): mở tiến độ, mở luyện nói, bắt
    đầu ôn đều chạy ngay; sau cập nhật ngữ cảnh phát mẫu đúng bài và câu; giọng thật vi và en nhận đúng nguyên câu.
R31 (2026-10-07, sau PR #85) Người chủ dự án tạm gác việc agent ("Tạm thời gác lại cái này"). Ghi lại để làm sau,
    từ bài thử chat chữ: "tôi hỏi 1 nghĩa 1 từ thì agent trả lời nhưng không hiện thị nó 1 cách rõ ràng hay dạng md
    cho đẹp, kèm câu muốn lưu không thì tôi nhắn là Ok lưu thì nó không lưu mà lại gửi lặp lại 'Dựa trên hồ sơ học
    tập của bạn với bài đọc ...'":
    1. Nghĩa của từ trả về chữ phẳng: không tiêu đề từ, không in đậm nghĩa, không danh sách ví dụ (client đã hiển
       thị tập con Markdown §5.1; đây là định dạng của câu trả lời).
    2. "Ok lưu" ngay sau câu hỏi "muốn lưu không" không lưu: cần đường ngắn như "open it" (R30/#85) cho lời đồng ý
       ngắn sau một đề xuất - chạy (open: true) đúng action vừa đề xuất (save_word), không bao giờ quay về tóm tắt
       hồ sơ. Lưu ý: ở chế độ chữ hiện chỉ mở màn chạy ngay; lưu từ chạy ngay cần người chủ dự án mở rộng R30 cho chữ.
    3. Câu mở đầu lặp "Dựa trên hồ sơ học tập của bạn…" xuất hiện khi người học hỏi điều cụ thể.
    Chưa làm gì cho tới khi người chủ dự án mở lại.
```

Tiến độ lane (cập nhật mỗi slice):

```text
Slice 1a  REVIEWABLE, b2fbc2f (2026-09-27). writing_coach/agent/: contract, schemas, locale, events,
          learner_copy, errors, tools, limits, session, provider, fake_provider, capability_registry +
          capabilities/*.json (15, pending), tool_plan (31 tool, 7 gap), decision, context, redaction, voice.
Slice 1b  REVIEWABLE (local, 2026-09-27). /api/agent/turn (SSE) + /api/agent/capabilities sau AGENT_ENABLED;
          turn (vòng tool ≤ 4, reply tools, evidence trước claim, metering agent.turn/agent.tokens);
          OpenAICompatibleProvider.stream_chat + platform.stream_agent_turn (legacy selection, từ chối local);
          read tools get_due_review_summary, get_due_vocabulary, get_current_writing_evaluation (EN, ZH);
          4 key agent trơ; daily_usage cho cả hai store; contract streams S1, S5, S8, S9.
Slice 1c  REVIEWABLE (local, 2026-09-27). 1c-1 4672fdd: contract v2 (orena.home, turn mở đầu
          trigger:"open" = S13, display, payload theo API thật), id chỉ từ lượt đọc, 4 read tool
          get_saved_word_state, get_word_detail, get_writing_feedback_items, get_writing_history_summary
          (EN, ZH), capability vocabulary.words, review.due, writing.review active. v3 ff6d3c8 (merge 05fbaad):
          intent gợi ý prompt.*, label action lớp interface. 1c-2 f36f465: identity.py + RuleDecisionProvider
          trả lời danh tính/model từ copy trước model (EN, VI, ZH); ratelimit.py 12 turn / 60 lượt đọc
          capability mỗi phút mỗi learner, 429 + Retry-After. Review đối kháng 9a0b0df: id gắn với khóa đã
          đọc, lượt mở đầu chỉ khoảng trắng là lỗi, get_word_detail đọc catalogue DB, gate danh tính chính
          xác. Contract streams S1, S5, S8, S9, S13.
Contract v4 merge 0e2b1ee (D-095: §2.1 HTTP status, §4.1 error class; phần xung đột của handoff lấy
          bản codex/work theo R13) và phục vụ v4. Handoff chỉ còn chỗ cho một dòng trỏ về đây (giới hạn 8 KB).
Live      R17 đã chạy 2026-09-28 (duyệt, trần 2,00 USD; sandbox :8015 đã gỡ). Gemini gemini-3.5-flash-lite:
          tool call về nguyên cục (không `index`) kèm extra_content.google.thought_signature, phải gửi lại ở vòng
          sau (3c208af); usage về trên stream khi xin include_usage (giá đã vào pricing.py); request chỉ có
          system bị từ chối nên lượt mở đầu có một user message cố định nêu ngôn ngữ support (5653de1). Đo
          (45 turn đạt): event đầu ≈ 0,01 s; segment đầu trung vị 2,9 s, p90 3,9 s; xong trung vị 3,4 s;
          ≈ 3,9k token vào / 140 ra mỗi turn ≈ 0,0015 USD; tổng thực ≈ 0,09 USD. Lỗi còn lại là HTTP 429
          quota của gói key (≈ 25-30 lượt gọi/phút), không phải lỗi request.
Chất lượng ce89f83, ea1db15 (R18): tên màn hình surface.<id> theo copy của UI mới; ghi chú "bộ chấm chưa
          đánh dấu lỗi" trong kết quả tool viết; khối giọng nói viết bằng chính ngôn ngữ support, đặt sát lời
          người học; ClaimGate stream theo câu, thay câu "đã lưu" bằng lời mời bấm nút khi có action (segment_end
          vẫn đúng bằng các delta). Kiểm live EN/ZH, support VI, trần 0,50 USD (≈ 0,41 USD tính mức xấu nhất).
Xưng hô  55eb880 (R19): address.py, reply tool set_address / offer_address, note address-<support>,
          context.address; chưa kiểm live.
Slice 2  REVIEWABLE (local, 2026-09-28; R20). c5b89c6 Grammar: get_grammar_point, search_grammar_points qua R5;
          1073d33 Speaking (get_pronunciation_history/attempt/word_detail), Listening
          (get_current_listening_context, get_listening_attempt), Reading (get_current_reading_context,
          get_reading_progress). Active: grammar.point, speaking.pronunciation.line, speaking.free_talk,
          listening.dictation, reading.passage. Test Postgres dùng một lần (ORENA_TEST_POSTGRES_URL): mỗi tool
          đọc đúng learner và ngôn ngữ.
Review   01e20f0: review đối kháng (8 lỗi xác nhận, đã sửa): selection gửi dạng chuỗi JSON đã escape; ClaimGate
          bỏ câu Orena tự nhận đã làm ở mọi turn, câu bị động chỉ khi có nút, câu hỏi không bao giờ là claim;
          ngôn ngữ support khác không nhận I/you tiếng Anh; từ chối xưng hô cũng được lưu; từ xưng hô ≤ 3 từ.
Kiểm live 2026-09-28 (trần 0,20 USD, thực ≈ 0,10 USD; sandbox đã gỡ). Sửa từ lần chạy: 30462dc câu mời dựng từ
          action, quy tắc ở mô tả propose_action; 6780fda action không kèm chữ vẫn là câu trả lời, khối giọng nói cho
          phép đổi xưng hô; 869575d vòng im lặng được nhắc một lần; 7e9267e mô tả payload từng action (model đoán
          sai 4 lần); 36b918d ví dụ theo đúng ngôn ngữ và tình huống. Đạt: xưng hô (mặc định, đổi, từ chối được lưu),
          câu mời thay "đã làm" ở vi/en/zh, lịch sử viết ZH. Chưa đạt: hỏi "màn này để làm gì" - model đoán sai
          công dụng vì context chỉ có tên màn; cần mô tả công dụng theo surface (§23 app knowledge).
Sửa R21 161544d: agent/labels.py (SRS, danh mục lỗi hai ngôn ngữ, loại lỗi, lỗi phát âm; LearnerScope mang
          interface), đổi lại xưng hô, câu mời gọn; "Mình lưu … cho bạn" là claim (v5 B1). Flow live mới: decline
          (một cặp qua nhiều lượt, hỏi một lần, từ chối), rechange.
Slice 3  REVIEWABLE (live 2026-10-04, gói trả phí; R21, R23, R26). 03faf0c: coaching.py - build_learning_snapshot (/api/learner-summary
          30 ngày + review due, không current_level, số demo bị loại, null khi không đọc được),
          get_learning_weaknesses (đếm tất định trên bản ghi; ngữ pháp null), get_recommended_next_activities
          (thứ tự backend: từ đến hạn rồi cross-skill cue, kèm id cho navigate); coach notes lớp 3 (remember_note /
          forget_note → memory_update, id của note người học); S13 dựng trên snapshot, không read tool.
          coaching.next_steps active. Test Postgres dùng một lần: snapshot và weaknesses đúng learner, đúng ngôn ngữ.
v5       R24: contract v5 (D-096) - context.address, note kind address, copy có chỗ xưng hô, surfaces.json, S14/S15.
Live     2026-09-28 notes trên gemini-3.8-flash (R25): lưu note đạt; sửa note đạt nhưng chỉ sau lời nhắc của server
          (vòng 1 không gọi tool); xoá chưa kiểm được - 503 "high demand" 3 lần, lần thứ 4 vượt trần đợt 0,15 USD
          (bound 0,0802; chi phí thật 0, gói miễn phí). Tới segment đầu 17,6 s / 19,1 s (flash-lite trước đây: trung vị
          2,96 s trên 82 lượt khác). Lần sau: gemini-3.7-flash.
Live     2026-10-04 notes, coaching, claims trên gemini-3.5-flash-lite, ghim cho cả agent_turn_fast và agent_turn_deep
          (trần 0,30 USD; bound 0,0443; khóa nhịp tim gemini-text): 11/11 lượt trả lời, không lần thử lại, không vòng
          nào kết thúc bất thường (không có lượt Gemini kết thúc stream mà không gửi lý do). Notes đạt cả bốn bước:
          lưu note; sửa thay đúng note (cùng id) và xoá đúng note - cả hai sau lời nhắc của server (vòng 1 không gọi
          tool). Lượt mở đầu nêu dữ kiện từ snapshot ("3 từ đến hạn ôn"); câu mời do server viết, đúng ngôn ngữ, không
          câu nào nói đã làm. Tới segment đầu: trung vị 3,99 s, chậm nhất 5,94 s.
Merge    PR #69 (dark merge, agent tắt mặc định) đã vào codex/work; CI xanh trên 57c4e27 (run 37195960228).
Sau #69  9d1d297..7bfcbbf: F-13 trả lời "màn này để làm gì" từ màn hình, không read tool; timeline một dòng
          agent.turn mỗi lượt cho baseline; gate 3.1-3.5 (kết luận về việc học phải đọc bản ghi; server duyệt mọi lần
          ghi note theo lời người học; đổi ngôn ngữ học bỏ ngữ cảnh cũ; bắt thêm câu "đã làm"); trần chi tiêu theo ngày
          trên sổ AI dùng chung (AGENT_DAILY_SPEND_CAP_USD, đóng khi không đọc được sổ); đề xuất Slice 4 (chưa làm).
R27      Nhờ ghi nhớ không dấu: hỏi lại kèm nút, chỉ ghi khi bấm (notes.py, turn.py; test vi không dấu, xác nhận đúng
          chữ, chữ khác bị từ chối, nhãn theo ngôn ngữ interface). agent.turn giữ 90 ngày, dọn tự động (retention.py;
          test unit và Postgres: chỉ dòng agent.turn cũ bị xoá, dòng audit khác giữ nguyên); tắt mặc định, bật bằng AGENT_TURN_RETENTION_SWEEP sau review độc lập của lane UI.
Merge    PR #70 vào codex/work (27187dd). Lane UI dựng lại :8021 trên 27187dd với AGENT_DAILY_SPEND_CAP_USD=1, giữ
          container cũ (orena-next-verify-web-before-spend-cap).
Baseline 2026-10-04 trên :8021 (trần 0,05 USD; khóa gemini-text; không đổi cấu hình runtime): 10/10 lượt đạt, zh-CN,
          support vi, gemini-3.5-flash-lite qua agent_turn_fast; chi phí thật 0,02716 USD theo sổ AI; không vòng nào
          kết thúc bất thường. Tới chữ đầu tiên người học thấy: trung vị 2,39 s, chậm nhất 5,67 s; provider chiếm 97%
          thời gian phía server. Theo loại lượt (vòng; token vào/ra; tới chữ đầu): screen help 1; 246/57; 1,2 s -
          mở đầu 2; 2135/45; 2,0-2,5 s - hỏi từ (get_word_detail) 2; 7467/79; 2,2-2,3 s - điểm yếu (2 read) 3;
          12863/174; 3,4-3,6 s - bước tiếp theo (get_recommended_next_activities + action) 5; 18178/170; 5,6-5,7 s.
          Thấy khi đo: bước tiếp theo chỉ còn câu mời "Bấm Ôn ngay để bắt đầu ôn." và tốn 5 vòng; screen help đoán sai
          công dụng của vocabulary.my_language vì surfaces.json chưa có purpose (§6.2, chờ IMPLEMENTATION_MAP).
Tiếp      Nhận lỗi test của người chủ dự án (R27); quota dùng chung trước khi chạy nhiều worker (R26); bật dọn
          agent.turn sau review của lane UI; Slice 4 chỉ là đề xuất.
```

---

## 1. Mục tiêu

Xây dựng một AI Assistant riêng cho Orena có khả năng:

- hiểu người dùng đang ở đâu trong app;
- hiểu feature, flow và capability của toàn bộ Orena;
- truy xuất đúng dữ liệu học tập (reading, listening, speaking, writing, vocabulary, grammar);
- giải thích lỗi / tiến độ / nội dung theo bằng chứng thật;
- điều hướng và đề xuất action để frontend thực hiện;
- đóng vai learning coach cá nhân dài hạn;
- trò chuyện bằng giọng nói tự nhiên;
- sau này dùng chung cho web, mobile (đang frozen) và Orena physical assistant/robot.

Không triển khai như một chatbot độc lập chỉ biết trả lời text.

```text
UI mới trên codex/work (D-086) — ngoài lane này
   │  AppContextSnapshot + event stream
   ▼
Orena Intelligence Agent (Agent Core)
   │  AIOperation.AGENT_TURN qua writing_coach/ai (routing, cooldown, pricing, config)
   ├── Agent Tool Gateway (READ_ONLY trong V1) → service hiện có:
   │      learner_summary · writing_evaluation · speech_api/attempts · vocabulary_* ·
   │      grammar_* · reading_* · listening_* · text_discussion · conversation
   ├── Structured Actions → frontend gọi API hiện có
   └── Voice Layer (độc lập với Agent Core)
          ├── ConversationalSpeechSession  (AIOperation.CONVERSATIONAL_SPEECH — S2S)
          ├── SpeechRecognitionProvider    (speech_asr — Groq)
          ├── ReferencePronunciationProvider / word_audio (đã có)
          └── PrerenderedSpeechCache       (AIOperation.TEXT_TO_SPEECH)
```

---

## 2. Cold start và pre-flight (bắt buộc, báo cáo trước khi viết code)

Cold start đúng AGENTS.md §2, không lấy từ tài liệu:

```bash
git branch --show-current
git rev-parse HEAD
git status --short
git log -5 --oneline
```

rồi đọc **canonical sequence trong `docs/project/PROJECT_MEMORY.md`** — và chỉ sequence đó. Sau đó đọc file này.

Pre-flight — trả lời từng câu, không tự quyết:

```text
P1  Xác nhận đang ở feature/orena-intelligence và HEAD chứa D-085 (grep "D-085" docs/project/DECISION_LOG.md
    và CURRENT_HANDOFF.md). Không thấy → lane chưa fast-forward từ codex/work → DỪNG, báo người.
P2  Xác nhận merge PR #63 (9c0fe315) nằm trong ancestry: git merge-base --is-ancestor 9c0fe315 HEAD.
    Có → Slice 1a rồi 1b liên tục trong lane này. Không → DỪNG, báo người.
P3  docs/project/AGENT_CONTRACT.md tồn tại và giống hệt bản trên codex/work
    (git diff origin/codex/work -- docs/project/AGENT_CONTRACT.md phải rỗng)? Ghi contract_version.
    Thiếu hoặc lệch → DỪNG, báo người (contract chỉ vào lane bằng merge codex/work).
P4  alembic heads == 1 và head là 20260924_0016? Liệt kê 3 migration cuối. Khác → báo, không sửa.
P5  writing_coach/ai/capabilities.py: liệt kê AIOperation và capability key hiện có.
    providers.py: provider nào hỗ trợ streaming? tool calling? (v2.1 giả định: chưa có cả hai)
P6  Endpoint hiện có mà client sẽ gọi khi thực thi action contract §7 (save/unsave word, collection, review,
    speech attempts). Chỉ liệt kê để map payload; không đọc/sửa code frontend.
P7  learner_summary_api.py trả gì? Có đủ cho coaching snapshot (mục 24) không? Thiếu gì?
P8  text_discussion.py: cơ chế metering turn (ordinal, không từ chối) — dùng lại cho budget được không?
P9  Gemini: capability key nào đang trỏ gemini trong sandbox? Key có dùng được cho Live API không (câu hỏi cho người)?
P10 Sandbox nào cho lane này (handoff nêu :8011 codex, :8013 speaking)? Chỉ vận hành sandbox được cấp.
```

Không redesign learner screens. Không chạm mobile/. Không chạm Platform Admin ngoài việc thêm capability key.

---

## 3. Nguyên tắc thiết kế bắt buộc

### 3.1 Agent không truy cập database trực tiếp

Không SQL, không ORM tùy ý, không đọc full user record. Mọi truy cập qua tool → service/API hiện có.

### 3.2 Agent backend không mutate dữ liệu học tập trong V1 (D6)

Agent trả structured action; frontend gọi API hiện có bằng session của user. Backend mutation tools chỉ thêm sau V1 cho client không có frontend (robot).

### 3.3 Agent phải context-aware

Request và `context` theo **AGENT_CONTRACT.md §3**: `surface` là surface id (không phải route), `locale` 3 lớp D-079 + `content`, `activity_type` enum, selection, `coach_notes` từ device memory, và `client.supported_actions/intents` là ràng buộc (contract §3.1).

### 3.4 Bằng chứng trước, giải thích sau (D10)

Mọi câu về lỗi của learner phải trace được về một field của evaluation/attempt thật. Không có evidence → nói không có, đề xuất cách lấy (làm lại take, nộp bài), không đoán.

### 3.5 Không model local, không dependency GPU (D2)

---

## 4. Agent roles

### A. App Copilot
Giải thích chức năng, tìm feature, mở đúng screen (action), giải thích dữ liệu đang hiển thị, tìm nội dung, đề xuất action đơn giản.

### B. Learning Coach
Phân tích learning history, lỗi lặp lại (phát âm, ngữ pháp, từ vựng, viết), so sánh kỹ năng, đề xuất activity, xây session, giải thích *theo bằng chứng*, theo dõi dài hạn.

Ví dụ đúng theo D10 — user chọn 是 trong kết quả phát âm, hỏi "Tại sao tôi sai từ này?":

```text
Evidence:   attempt.words["是"].phonemes[0] = {pinyin:"shi", tone:4, score:6, flagged:true}
Trả lời:    "Azure đánh dấu 是 (shì, thanh 4) là phát âm sai, điểm 6/100. Nghe mẫu rồi thử lại nhé."
Không nói:  "Bạn hạ thanh 4 quá sớm" (không có pitch evidence ở backend).
```

Nếu syllable chỉ bị hạ điểm (ví dụ 60–71) mà không flag:

```text
"美 (měi) chỉ đạt 71 điểm, chưa bị đánh dấu sai. Thanh 3 và thanh 2 dễ lẫn — muốn so sánh với mẫu không?"
```

---

## 5. Capability Registry

Path: `writing_coach/agent/capabilities/*.json`. Phục vụ qua `GET /api/agent/capabilities` đúng shape contract §8.

```json
{
  "id": "speaking.pronunciation.line",
  "title": "Say a line and get it assessed",
  "surfaces": ["speaking.workspace", "speaking.word_detail"],
  "status": "active | pending",
  "contexts": ["attempt_id", "content_id", "selected_item"],
  "actions": ["play_model", "play_user", "say_again", "compare_with_model"],
  "languages": ["en", "zh-CN"],
  "evidence_source": "speech.pronunciation",
  "tools": ["get_pronunciation_attempt", "get_pronunciation_word_detail"]
}
```

- Registry **không chứa route**. `surfaces` và `actions` chỉ dùng id có trong contract §6–§7.
- Drift test phía backend: mọi surface/action trong registry có trong contract; mọi `tools[]` có trong tool registry; mọi `evidence_source` thuộc enum contract §5.3.
- Drift phía UI (surface nào UI mới thực sự có) là việc của lane UI (contract §8); backend xử lý qua `client.supported_*`.

---

## 6. Capability domains V1

```text
Home · Library · Reading · Listening (Dictation) · Speaking (workspace, free talk, shadowing)
Writing (workspace, review, revision) · Grammar (catalog, knowledge, learning model)
Vocabulary / My Language · Review · Progress (pending: chưa migrate) · Settings/Preferences
```

Không có tool cho tất cả ngay, nhưng registry phải biết chúng tồn tại.

---

## 7. Tool architecture

```python
class AgentTool:
    name: str
    description: str
    input_schema: dict
    permission: ToolPermission   # READ_ONLY | NAVIGATION | PLAYBACK | USER_MUTATION | HIGH_IMPACT
    backed_by: str               # module/endpoint hiện có, bắt buộc
    languages: tuple[str, ...]   # EN/ZH parity kiểm được (D9)
    execute(authenticated_user, args) -> ToolResult
```

V1 chỉ đăng ký tool `READ_ONLY`; enum đầy đủ để test. Test assert không có tool nào khác được đăng ký.

Giữ chỗ:

```python
class DecisionProvider:  # V1: rule/LLM. Sau V1 có thể là decision model (D16).
    def decide(self, state, questions) -> Decisions: ...
```

---

## 8. V1 tool set (READ_ONLY) — map vào service có sẵn

Bản đồ đã kiểm chứng với code là `writing_coach/agent/tool_plan.py` (2026-09-27): mỗi tool ghi callable có sẵn
(`backed_by`, `composes`, test import từng cái) hoặc là gap. Bảng dưới là tóm tắt; khi lệch, `tool_plan.py` thắng.

| Tool | Backed by (đã kiểm chứng) |
|---|---|
| `get_app_context`, `get_current_selection`, `get_current_learning_activity` | Tier 1 từ request + session (`agent/context.py`) |
| `get_learning_overview`, `get_skill_progress`, `get_recent_learning_activity` | `learner_summary.py` (+ `speaking_progress`). Không dùng `product_activity.py`, `readiness_summary.py`: đó là số liệu gộp chỉ cho admin |
| `get_due_review_summary`, `get_due_vocabulary`, `get_word_detail`, `get_saved_word_state` | `becoming_library.py` (`library_summary`, `list_library_vocabulary` status=due, `saved_vocabulary_state`), card từ `vocabulary_cards.py`. Không dùng `word_detail.py`: mỗi lần gọi đều tới provider |
| `get_pronunciation_attempt`, `get_pronunciation_history` | `PostgresSpecializedLearningRepository.list_speaking_attempt_records` (chỉ đường GET; chưa có get-by-id) |
| `get_pronunciation_word_detail`, `get_tone_analysis` (zh-CN), `get_stress_analysis` (en) | Word detail: evidence đã lưu, "flagged" = `error_type` của provider (D-084). Tone, stress: gap (UI_BACKEND_GAPS I-2, I-3) |
| `get_current_writing_evaluation`, `get_writing_feedback_items`, `get_writing_history_summary` | `learning_repository.get_essay` + `writing_contract.project_review`/`project_issue`; lịch sử: `learner_summary.py` + `writing_analytics.py` |
| `get_grammar_point`, `search_grammar_points`, `get_grammar_mistakes_summary` | `languages/runtime.py` (`active_grammar_by_id`, `active_grammar_course`, knowledge). Mistakes: gap (I-4) |
| `get_current_reading_context`, `get_reading_progress`, `get_reading_mistakes`, `get_word_context_in_reading` | `reading_content_repository`, `reading_library_repository`, `ReadingEvidenceRepository.list_evidence` (không dùng `ability()`: có ghi). `becoming_reading.py` đã bị xoá (D-082). Mistakes, word context: gap (I-5, I-6) |
| `get_current_listening_context`, `get_listening_attempt`, `get_listening_mistakes` | `listening_catalog.py` (curated), `list_listening_progress_records`. Mistakes: gap (I-7) |
| `build_learning_snapshot`, `get_learning_weaknesses`, `get_recommended_next_activities` | `learner_summary.py` + `review_queue`; recommend: `cross_skill_transfer.select_cross_skill_cue` (đang chạy ở `/api/cross-skill-cue`). Weaknesses: gap (I-1) |

Đã có feature gần trùng — agent **gọi**, không làm lại:

```text
"Giải thích văn bản này / hỏi về bài đọc"   → text_discussion.py (D-072.2, đã qua 4 vòng review)
Role-play / luyện hội thoại                  → conversation.py (partner-turn, stateless)
Spoken coaching sau free talk                → luồng Gemini coaching có sẵn của lane Speaking
```

Tool thiếu backend → ghi vào `docs/project/UI_BACKEND_GAPS.md` (D15) trước khi viết service.

Đã chuyển thành ACTION (mục 14, contract §7): `navigate`, `play_model`, `play_user`, `say_again`, `compare_with_model`, `save_word`, `add_word_to_collection`, `start_review`, `start_targeted_drill`, `unsave_word`.

---

## 9. Permissions

Tool backend: chỉ `READ_ONLY`, chạy theo authenticated user (lấy từ request/session, không tin `user_id` do model sinh).

Action (frontend thực thi):

```text
LOW       navigate, play_model, play_user, say_again, compare_with_model, save_word,
          add_word_to_collection, start_review, start_targeted_drill        (contract §7)
CONFIRM   unsave_word                                                   → confirm dialog hiện có
BLOCKED   delete collection, reset progress, clear history, bulk remove, mọi thứ admin → agent không sinh
```

Mức rủi ro gắn với `type` trong registry, không nằm trong prompt.

---

## 10. Context assembly

Tier 1 (always): user ref, `locale` 3 lớp + content, surface/capability/activity_type, selection, coach notes (device memory, vài trăm token, có TTL).
Tier 2 (on demand): evidence cho câu hỏi hiện tại (attempt, evaluation, feedback items…).
Tier 3 (coaching): learning snapshot, recurring mistakes, review load, goals.

System prompt + tool schema ổn định để prompt-cache. `ProviderContextBuilder` (mục 36) scope theo task.

---

## 11. Agent session state (D7 — không migration)

```text
agent_session_id, user_id, current_app_context, last_selected_entity, active_learning_goal,
recent_tool_results (bounded), voice_session_ref, created_at, updated_at
```

- Server: cache có TTL (in-process hoặc Redis nếu đã có trong compose), không bảng mới.
- Client: lịch sử hội thoại hiển thị giữ ở device memory theo pattern "conversations, drafts and continuation are device memory by design" (AGENTS.md §7). Resume qua reload bằng `agent_session_id` còn hạn; hết hạn thì bắt đầu phiên mới, không mất gì vì lớp 2 nằm ở DB.
- Không lưu chain-of-thought. Có thể giữ tool calls, summaries, user-visible messages, resolved entities.

Bảng thật (`agent_session`, `coach_notes`) chỉ được đề xuất bằng proposal theo `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` + independent review, sau khi chuỗi Alembic ổn.

---

## 12. Memory strategy (D18)

Ba lớp. User không phải quản lý gì.

- **Lớp 1 — session:** "từ này", "câu vừa rồi" → snapshot + session state.
- **Lớp 2 — learning history:** DB thật qua tool. 90% cảm giác "agent hiểu mình". Không thay bằng model-generated memory.
- **Lớp 3 — coach notes:** vài fact có cấu trúc về *cách học* (preference, goal, plan) với `weight`, `last_reinforced`, `expires_at`. V1 lưu ở **device memory**, gửi lên trong Tier 1 (bounded, redacted). Quy tắc: V1 chỉ ghi fact user nói trực tiếp; sửa bằng hội thoại ("không, giải thích kỹ hơn"); không củng cố thì tự phai; đã có ở lớp 2 thì không ghi; không suy diễn cảm xúc/hoàn cảnh/sức khỏe. Một mục ẩn trong Preferences → Privacy: "Những gì Orena ghi nhớ về cách bạn học" + xóa (theo pattern preferences hiện có, D-079 "every way into the preferences").

---

## 13. Agent API → AGENT_CONTRACT.md §2–§4, §9

Implement đúng contract. Chi tiết phía backend:

- `POST /api/agent/turn` trả `text/event-stream`, dừng sinh khi client abort.
- `session_id` trỏ tới session cache TTL (mục 11), không bảng mới.
- `tool_call.label` và `error.message` sinh bằng copy có khai báo lớp ngôn ngữ (D-080), không bằng model.
- Voice session (contract §9): cấp ephemeral token qua `writing_coach/ai/credentials.py` + `platform.py`; key không bao giờ xuống client hay vào error.

---

## 14. Actions, segments, evidence → AGENT_CONTRACT.md §5–§7

Phía backend phải bảo đảm:

- Chỉ phát `action.type` thuộc allowlist contract §7 **và** thuộc `client.supported_actions`; `navigate` chỉ với intent thuộc `client.supported_intents`. Không đủ → nói bằng lời, không action.
- `risk` lấy từ bảng contract §7, không từ model.
- Mọi khẳng định lỗi có ít nhất một `evidence` phát trước `segment_end` trích nó (D10).
- `voice_style` thuộc enum contract §5.2; `reference` cho đoạn cần phát âm mẫu.
- `memory_update` chỉ cho fact learner nói trực tiếp (mục 12).

---

## 15. UI → lane codex/work (D-086)

Panel, dispatcher, mapping intent → màn hình, device memory, mock, "Ask Orena", suggested prompts, trạng thái mic/voice: đều thuộc UI mới trên codex/work, dựng theo AGENT_CONTRACT.md. Lane này không làm và không review code UI; chỉ bảo đảm server tuân contract bằng contract tests (mục 28).

---

## 19. Model/provider abstraction (D3, D4)

Thêm vào `writing_coach/ai/capabilities.py`:

```python
class AIOperation(StrEnum):
    ...
    AGENT_TURN            = "agent_turn"             # streaming + native tool calls
    CONVERSATIONAL_SPEECH = "conversational_speech"  # S2S session
    TEXT_TO_SPEECH        = "text_to_speech"         # pre-render
```

Ba operation đã có (Slice 1a). Capability key (cấu hình qua Admin › AI) vào catalog sau khi codex/work thêm nhãn
EN/ZH cho Admin (R1), mỗi key `implemented=False`, `configurable=False`, fallback `{NONE}` cho tới khi được kích hoạt:

```text
agent_turn_fast       provider/model do operator chọn trong Admin › AI (sandbox: gemini)
agent_turn_deep       V1 cấu hình giống agent_turn_fast; không tự rơi về key khác
                      Dev (R25): cả hai key ghim cùng một model cho cả lần chạy - gemini-3.8-flash, hoặc
                      gemini-3.7-flash khi 3.8 quá tải (ghi rõ trong kết quả). Model riêng cho lượt thường chọn khi
                      chuẩn bị ra mắt.
conversational_speech chưa duyệt (R6)
text_to_speech        chưa duyệt (R6)
```

Không có tự động chuyển provider hay key (ARCHITECTURE_INVARIANTS, R2): provider lỗi → turn kết thúc bằng `error`
với `fallback: retry` (text) hoặc `text_only` (voice). Persisted fallback policy chỉ là metadata cho tới khi runtime
activation được review.

`providers.py`: mở rộng `OpenAICompatibleProvider` (chat/completions sẵn có) với streaming và native tool calling;
không thêm dependency, không SDK riêng (R6). `routing.py` (`build_chain`, `run_chain`, cooldown) dùng nguyên.
`pricing.py` thêm giá voice khi voice được duyệt.

Không local model, không fallback local.

---

## 20. Tool execution loop

```text
message (text) | delegation event (voice)
  → resolve app context
  → DecisionProvider (V1 rule/LLM): cần tool? capability nào? identity question? authorization pre-check?
  → permission check (gateway; READ_ONLY)
  → execute tool(s) qua service hiện có
  → generate: segments + actions + suggestions + evidence (stream)
```

Hard limit (config, có test): `max_tool_iterations_per_turn` (4), `max_tool_result_bytes` (8 KB/tool), `turn_timeout_seconds`, `max_input_tokens_per_turn`.

---

## 21. Observability

Mỗi request: `request_id, agent_session_id, capability_key, provider, model, latency_to_first_segment, total_latency, tokens in/cached/out, tool calls + latency, success/failure, cost_estimate` — qua telemetry sẵn có của `ai/platform.py`. Không log secret, không log raw audio.

---

## 22. Safety / authorization / metering

- Tool chạy theo authenticated user. Reject xem dữ liệu user khác, admin routes, ở gateway.
- **Metering V1 (R5)**: mỗi turn được đếm qua `record_usage` (bảng `usage_events` có sẵn, như `text_discussion.py`), không bị từ chối, cộng theo ngày (cần thêm một hàm đọc theo ngày cạnh `monthly_usage`, không migration). `budget_state` luôn `"ok"`. `soft_limited` để sau và đi qua quota ledger (gap E1). Không biến agent thành route enforce entitlement đầu tiên.
- Rate limit theo user/IP ở endpoint agent.
- Provider/credential/billing là human gate (AGENTS.md §10). Agent không cấu hình vendor, không đọc key trực tiếp.

---

## 23. App knowledge

Registry + surface/intent metadata (contract §6) + copy layers + help. V1 lookup deterministic; RAG sau.

---

## 24. Coaching snapshot

Xây trên `learner_summary.py` (+ `review_queue` cho `review_due`, `cross_skill_transfer` cho gợi ý). Không dùng
`readiness_summary`, `product_activity`: số liệu gộp chỉ cho admin. Schema (R4):

```json
{ "target": "zh-CN",
  "skill_summary": { "reading": {}, "listening": {}, "speaking": {}, "writing": {}, "vocabulary": {}, "grammar": {} },
  "review_due": 12, "recent_sessions": [] }
```

- Không có `current_level`: không gộp CEFR, HSK, điểm nghe và phát âm thành một điểm.
- `recent_weaknesses` / `recent_strengths` chưa có backend (UI_BACKEND_GAPS I-1); không có trong snapshot cho tới khi có.
- `skill_summary.vocabulary` là domain `language` của Learner Summary.
- `producer` và mọi định danh bị che trước khi gửi provider (`agent/redaction.py`); `target` là mã contract (`zh-CN`), ánh xạ
  từ `zh` ở biên agent (`agent/locale.py`).

Một metric không có đo lường thì để trống (`null`) và không suy diễn (D-066; R21 thay "để 0"). Số 0 chỉ khi đã
đọc được và thật sự là 0 (ví dụ chưa làm bài đọc nào trong 30 ngày).

---

## 25. Không làm trong V1

```text
autonomous background agent · push notifications · robot hardware · proactive daily coaching
web browsing · admin agent · agent-to-agent · arbitrary browser/code execution
backend mutation tools (D6) · migration/schema (D7) · decision model (D16)
chắt lọc coach notes tự động (mục 12, sau V1) · self-host (D2) · CSM-1B/Dia2/Qwen3-TTS (D5)
mobile/ (frozen) · Platform Admin ngoài capability key
```

Conversational voice là một phần V1, chạy song song (Track 0), không là dependency của Agent Core.

---

## 26. Phase implementation

### Track 0 — Voice spike (người chạy; song song; 3–5 ngày)

```text
Cấu hình:  V1 Gemini Live (key sẵn có — cần người xác nhận dùng được cho Live; gate credential)
           V2 Azure Voice Live tier Standard (cần resource + credential gate)
           V3 GPT-Live 1, delegation=client (cần credential gate)
           V4 cascade (một chế độ để so sánh, không phải fallback — R2): Groq ASR → fake agent → Gemini TTS
Đầu vào:   20 câu coach vi, 10 en, 10 zh (mỗi câu có voice_style) — docs/agent/BAKEOFF_SET.md
Đo:        time-to-first-audio, barge-in, cost/phút từ usage, blind listening 3–5 người Việt
Output:    docs/operations/AGENT_VOICE_SPIKE_<date>.md (theo mẫu SPEAKING_AZURE_E2E_2026-09-23.md:
           không key, không region, không raw JSON, không learner audio) + điền vendor vào 33.2
```

### Slice 1a — Backend cô lập (không chạm file dùng chung)

```text
writing_coach/agent/: schemas (AppContextSnapshot 3 lớp + content, ToolPermission, AgentTool,
event stream contract), tool registry, fake provider, session cache TTL, capability registry loader
(tất cả entry status=pending), DecisionProvider stub, các interface voice (mục 33).
ai/capabilities.py: 3 AIOperation. 4 capability key theo R1 (sau nhãn Admin trên codex/work).
Tests: schema, permission (assert READ_ONLY only), registry loader, session, fake provider.
KHÔNG: đăng ký router vào app.py, sửa app.js/api.js/theme.css/index.html/compose.yaml/ci.yml, migration.
```

### Slice 1b — Vertical slice đầu tiên (tiếp ngay sau 1a REVIEWABLE, cùng lane) — backend only

```text
Đăng ký router agent (1 chỗ trong app.py). POST /api/agent/turn (SSE), GET /api/agent/capabilities
theo contract. 2–3 read tool Vocabulary + Writing, EN và ZH cùng lúc (D9).
Contract tests: server phát đúng chuỗi event S1, S5, S8, S9 (contract §12) với provider fake.
Registry: surface/action id theo contract; drift test backend (mục 5).
KHÔNG: static/orena/**, templates/**, panel, mock frontend, .mjs gate UI.
```

### Slice 2 — Read-only đầy đủ + actions

```text
Toàn bộ tool mục 8 (Speaking qua speech_api /attempts, Grammar, Reading, Listening).
Action theo contract §7, lọc theo client.supported_*. Contract tests S2, S2b, S12, SE.
E2E 2, 3, 4, 7 ở mức API. Tone/stress theo D10.
```

### Slice 3 — Coaching

```text
build_learning_snapshot trên learner_summary; weaknesses; recommended_next_activities deterministic;
coach notes lớp 3 (device memory). E2E 6.
```

### Slice 4 — Voice end-to-end

```text
ConversationalSpeechSession với vendor từ Track 0 qua capability conversational_speech;
ephemeral token; delegation → gateway; pre-render cache; reference audio; S2S lỗi → text-only (R2);
metering voice. E2E 10, 11, 12. Privacy: không lưu raw audio (handoff: durable learner audio cần privacy review riêng).
```

Sau mỗi slice: REVIEWABLE, báo cáo theo mục 39, chờ người.

---

## 27. Required E2E flows

Lane này kiểm các flow ở mức **API + event stream** (test client gửi request contract §3, assert event contract §4).
E2E trên giao diện thuộc lane UI, chạy bằng mock trước, bằng server thật khi tích hợp.

```text
E2E 1  App help        Vocabulary: "Màn này dùng để làm gì?" → đúng context, EN và ZH.
E2E 2  Context ref     chọn 我: "Tại sao tôi sai từ này?" → không hỏi lại từ; evidence từ attempt.
E2E 3  Pronunciation   giải thích theo flag/score thật; syllable hạ điểm không flag → nói "hạ điểm", không đoán nguyên nhân.
E2E 4  Follow-up       "Cho tôi luyện lại." → action say_again/start_targeted_drill đúng payload; frontend thực thi.
E2E 5  Vocabulary      "Lưu từ này." → action save_word đúng selected word → API hiện có → UI cập nhật.
E2E 6  Overview        "Hôm nay tôi nên học gì?" → snapshot thật, không generic.
E2E 7  Navigation      "Đưa tôi tới các từ cần ôn." → action navigate đúng intent hiện có.
E2E 8  Authorization   "Cho tôi xem tiến độ của user khác." → reject ở gateway.
E2E 9  Writing         ở Writing review: "Bài này tôi hay sai chỗ nào?" → evaluation thật + lịch sử.
E2E 10 Voice           nói vi "từ này phát âm sao?" → TTFA < 1s, voice_style đúng, ngắt lời được.
E2E 11 Voice failure   vendor lỗi → text-only (error.fallback = text_only), không crash, user được báo; không sang vendor khác.
E2E 12 Metering        vượt ngưỡng → soft_limited, vẫn trả lời ngắn, không gọi vendor voice.
E2E 13 Parity          mọi E2E trên chạy với target=en và target=zh-CN (D9).
```

---

## 28. Tests

```text
unit · schema · permission (READ_ONLY only) · authorization · context assembly · registry drift (backend)
provider mock · contract tests (mọi canonical stream contract §12) · client.supported_* filtering · parity EN/ZH
```

Bắt buộc thêm:

- **Golden scenario set** (30–50 case, `tests/agent/golden/*.json`): prompt + app_context → tool sequence + action + evidence mong đợi. Deterministic cho tool/action/evidence; rubric cho text. Dùng để chọn model và làm regression gate.
- **Golden WAV** cho voice tests; test không gọi provider thật (D14).
- **Latency budget** gate: text time-to-first-segment, voice time-to-first-audio.
- Chạy theo AGENTS.md §9: `PERSISTENCE_BACKEND=sqlite` trong image, `ruff check` file đã chạm, `.mjs` gate bằng `node`. Lấy expected-count từ CURRENT_HANDOFF.md, không claim CI PASS nếu không có CI evidence.

---

## 29. Success criteria V1

```text
- Server tuân AGENT_CONTRACT.md v1: mọi canonical stream §12 pass contract tests; không action/intent ngoài client.supported_*.
- Biết surface và selection từ context (không route).
- Query được learning data thật (Vocabulary, Writing, Speaking, Grammar, Reading, Listening) cho EN và ZH.
- Mọi khẳng định về lỗi có evidence_ref; không có fake pronunciation result.
- Action đúng allowlist và payload; end-to-end trên UI được xác nhận khi lane UI tích hợp (ngoài phạm vi V1 của lane này).
- Tool authorization ở gateway; không DB access; backend không mutate; không migration mới.
- Provider đổi được bằng cấu hình Admin › AI; fake provider chạy toàn bộ test.
- Voice vi/en/zh qua ConversationalSpeechSession; en đạt D5; vi/zh TTFA < 1s, barge-in, blind listening ≥ 70%.
- Voice lỗi → text-only, không tự chuyển provider (R2); metering đếm được (R5).
- E2E 1–13 pass; existing learner flows không regression; gate CI xanh (có evidence).
```

---

## 30. UX principle

> **Context first, evidence second, answer third, action fourth.**

Không bắt user mô tả lại thứ trên màn hình. Có dữ liệu thì không generic. Có evidence mới gọi là lỗi. Có bước tiếp theo trong Orena thì đưa action. Không spam. Không tự thay đổi dữ liệu học tập.

---

## 31. Future architecture

Web → Agent Core ← Mobile (frozen) / Desktop / Robot. Robot cần backend mutation tools (sau V1, cùng contract action). Agent Core không phụ thuộc component frontend.

---

## 32. Multilingual (D8, D9)

Locale = `interface`, `support`, `target` (D-079) + `content`. Agent Core không hard-code ngôn ngữ. Capability đặc thù ngôn ngữ khai báo trong registry:

```json
{ "id": "speaking.pronunciation.tone",   "languages": ["zh-CN"], "evidence_source": "speech.pronunciation", "linguistic_reason": "…" }
{ "id": "speaking.pronunciation.stress", "languages": ["en"],    "evidence_source": "speech.pronunciation", "linguistic_reason": "…" }
```

Chinese chỉ zh-CN. Japanese chưa khai báo: `ja` là support language nhưng không phải target language trong
`core/language_registry.py`, nên registry (chỉ nhận target language) chưa có entry pitch; khai báo khi `ja` thành target.
Mỗi slice giao EN và ZH cùng lúc.

---

## 33. Conversational Voice Architecture (D4, D5)

```text
Mic ──► Vendor S2S session (WebRTC/WS, ephemeral token) ──► Loa
              │ delegation / tool call
              ▼
        Agent Core ──► Tool Gateway (READ_ONLY) / coach notes / identity policy
              │
              ▼
        event stream → frontend (segments, actions, voice_state, evidence)
```

### 33.1 Abstraction

```python
class ConversationalSpeechSession:      # AIOperation.CONVERSATIONAL_SPEECH
    mode: Literal["s2s", "cascade"]
    def open(self, speaker_profile, locale, instructions, coach_notes, on_delegation) -> SessionHandle: ...
    def push_text_segments(self, segments) -> AsyncIterator[AudioChunk]: ...   # cascade
    def interrupt(self) -> None: ...
    def close(self) -> Usage: ...

class SpeechRecognitionProvider:        # speech_asr.SpeechAsrProvider (Groq) — đã có
class ReferencePronunciationProvider:   # word_audio (Wikimedia/Kokoro) + Azure reference — đã có
class PrerenderedSpeechCache:           # AIOperation.TEXT_TO_SPEECH, cùng voice với S2S
```

### 33.2 Provider routing (điền sau Track 0)

Voice chưa được duyệt (R6). Khi được duyệt, mỗi ngôn ngữ có một đường chính; lỗi thì về text-only, không cascade
sang vendor khác (R2):

| Ngôn ngữ | Conversational (sau Track 0) | Khi lỗi | Reference | Pre-render |
|---|---|---|---|---|
| vi | S2S `{VENDOR}` | text-only | — | TTS cùng vendor/voice |
| en | S2S `{VENDOR}` | text-only | word_audio / Azure en-US | như trên |
| zh | S2S `{VENDOR}` | text-only | word_audio / Azure zh-CN | như trên |

Cascade (Groq ASR → Agent → TTS) là một chế độ server có thể chọn khi mở phiên, không phải đường cứu phiên S2S lỗi.
Đổi vendor = đổi capability key trong Admin › AI, không sửa code.

### 33.3 Session mode theo activity, không theo lượt

```text
coaching / app_help / review        → s2s, instructions bằng support
conversation_practice / role_play   → s2s, instructions bằng target (nội dung lượt lấy từ conversation.py nếu cần)
segment.voice_style == "reference"  → phát bằng reference audio, không bằng giọng hội thoại
```

### 33.4 Voice identity

`speaker_profile` cấp sản phẩm với `vendor_voice_map`; pre-render và S2S cùng vendor voice → một giọng Orena. Không clone giọng người thật không có consent.

### 33.5 Context trong voice

Cap một session (15 phút) → mở session mới, nạp lại lớp 1 + lớp 3. Không gửi audio history sang Agent Core. Không lưu raw audio.

### 33.6 Voice không là dependency của Agent Core.

---

## 34. Speech input

Cascade mode dùng `speech_asr.py` (Groq) như hiện có; s2s mode vendor tự STT. Pronunciation Assessment (Azure) giữ nguyên làm nguồn evidence; SpeechSuper là quyết định của người (báo cáo Azure E2E: tone tiếng Trung flag 2/7).

---

## 35. Product identity

Name: Orena. Role: AI learning assistant and personal coach. Câu hỏi danh tính/model → `DecisionProvider` gate → câu trả lời deterministic; cũng đưa vào instructions của voice session. Không bịa tên model. Provider/model metadata chỉ hiện qua UI từ runtime metadata. Không key/secret trong context hay frontend.

---

## 36. Data boundary

Minimum necessary context. `ProviderContextBuilder`: scope theo task, redact, size limit, log *loại* dữ liệu, policy theo vendor (config, không prompt). Không gửi email/profile/full history. Coach notes không chứa suy diễn cá nhân. Voice: không lưu raw audio.

---

## 37. Voice observability & failover

Trace: `voice_session_id, vendor, mode, language, ttfa, interruptions, text_only_fallbacks, audio_seconds_in/out, cost_estimate, error_class`. Health/cooldown dùng `ai/routing.py` sẵn có. Không tự chuyển vendor (R2): phiên lỗi kết thúc bằng `error{class: voice_unavailable, fallback: text_only}` và hội thoại tiếp tục bằng text.

---

## 38. Implementation order (chốt)

```text
Người   : D-086 + AGENT_CONTRACT.md trên codex/work rồi merge forward vào lane · Gemini Live credential (P9)
          · sandbox port cho lane (P10) · SpeechSuper? — D1 và merge Admin/Speaking đã xong (D-085, PR #63)
UI lane : UI mới trên codex/work, panel + mock theo contract (song song, độc lập)
Track 0 : voice spike (người chạy, song song)
Slice 1a: backend cô lập — có thể bắt đầu ngay sau D1
Slice 1b: vertical slice Vocabulary + Writing — sau merge
Slice 2 : read-only đầy đủ + actions (Speaking, Grammar, Reading, Listening)
Slice 3 : coaching + coach notes (device memory)
Slice 4 : voice end-to-end
```

---

## 39. Instruction cho coding agent

Gửi nguyên đoạn này:

> Cold start per `AGENTS.md` §2: verify live Git state, then read the canonical sequence in `docs/project/PROJECT_MEMORY.md`. Then read `docs/project/AGENT_SPEC.md` (v2.1). Section 0 lists binding decisions; where it conflicts with any older agent spec, v2.1 wins; where it conflicts with repository governance (AGENTS.md, ARCHITECTURE_INVARIANTS.md, DESIGN_CONTRACT.md, REVIEW_POLICY.md), governance wins and you report the conflict as a `MEMORY CONTRADICTION`.
>
> Answer pre-flight P1–P10 (section 2) and stop. You are on lane `feature/orena-intelligence`, opened by D-085; do not create any other branch or worktree. If P1 or P2 fails, stop and report; do not fix Git state yourself. Slice 1a is authorized now; Slice 1b follows in the same lane once 1a is REVIEWABLE. This lane never edits `static/orena/**`, `templates/**` or `docs/project/AGENT_CONTRACT.md`; the contract is authoritative for request, events, actions and intents, and a needed contract change is reported to the human, not made here.
>
> Slice 1a scope: `writing_coach/agent/` only (schemas with the three language layers + content, `ToolPermission` enum, `AgentTool`, tool registry with only `READ_ONLY` tools registrable, event-stream contract, deterministic fake provider, TTL session cache, capability registry loader with every entry `status: pending`, `DecisionProvider` stub, voice interfaces), plus the three `AIOperation` values and four capability keys in `writing_coach/ai/capabilities.py` (definitions only). Tests for all of it, hermetic, never calling a real provider. No router registration in `app.py`, no edits to `static/orena/**`, `compose.yaml`, `.env.example`, `ci.yml`, no migration, no new persistence for learner-owned data (AGENTS.md §7).
>
> Reuse existing services; every tool declares `backed_by`. A tool with no backing service goes into `docs/project/UI_BACKEND_GAPS.md`, not a new file. Providers, credentials and routing go through `writing_coach/ai/*`; never read a provider key directly and never let one appear in an error. Product identity is Orena. No local models, no CUDA/torch dependencies. Do not touch `mobile/` or Platform Admin beyond the capability keys.
>
> Validate per AGENTS.md §9 (sqlite backend in the image, `ruff check` on touched files, node `.mjs` gates). Label runs as local execution; never claim CI PASS without CI evidence.
>
> When Slice 1a is REVIEWABLE, report in the REVIEW_POLICY.md format, plus: files changed; existing services mapped as future tools; gaps recorded; risks; test results with expected-count from CURRENT_HANDOFF.md; proposed Slice 1b list. Update `CURRENT_HANDOFF.md` per PROJECT_MEMORY.md's transaction and run `python scripts/validate_project_memory.py`. Stop and wait for human review. Never merge to main; never declare human approval.

---

## 40. Phụ lục A — Những gì đã kiểm chứng trong repo (2026-09-26)

```text
codex/work
  - Governance: AGENTS.md là router; authority ở docs/project/* và docs/product/*. Cold start = git state + PROJECT_MEMORY canonical sequence.
  - Lane: codex/work = Codex lane, D-066 làm trực tiếp; claude/<task> = Claude lane; hai lane không đọc code nhau.
  - Persistence: PostgreSQL authoritative; learner-owned schema cần independent architecture review; conversations/drafts là device memory by design.
  - writing_coach/ai/: base, capabilities (AIOperation: STRUCTURED_TEXT_GENERATION, DETERMINISTIC, SPEECH_RECOGNITION,
    PRONUNCIATION_EVALUATION, SPEAKING_EVALUATION), config, control_plane, credentials, platform, pricing, providers
    (Ollama; OpenAI-compatible: openai, deepseek, groq, gemini), routing (chain, classify, cooldown). Chưa có streaming/tool-use.
  - Speech: speech_asr.py = Groq adapter; speech_pronunciation.py = Azure adapter; speech_api.py: /status /transcribe /evaluation
    /attempts /pronunciation; speaking_evaluator.py; pinyin_alignment.py. word_audio.py = Wikimedia + Kokoro (KOKORO_TTS_URL).
  - Sẵn có gần trùng agent: conversation.py (partner-turn), text_discussion.py (D-072.2, metering), learner_summary(_api).py,
    readiness_summary, product_activity, cross_skill_transfer, grammar_catalog/knowledge/learning_model, writing_evaluation*.
  - Sandbox: orena-foundation-web:8011; Gemini gemini-3.5-flash-lite đã cấu hình (key trong sandbox env); pytest 2472 passed / 3 skipped / 0 failed
    (verification hợp nhất 2026-09-26, PostgreSQL 16 cách ly, theo CURRENT_HANDOFF.md).
  - Human gates: production/preview, migration apply, provider, credential, OAuth/DNS/Cloudflare, billing, destructive history.

feature/speaking (38 commit / 86 file, REVIEWABLE, sandbox :8013)
  - Speaking workspace/library/free talk/shadowing/compare theo frame D-075; PronunciationResult provider-neutral;
    Azure scripted + unscripted đo thật (docs/operations/SPEAKING_AZURE_E2E_2026-09-23.md): latency 0.45–1.4 s;
    tone tiếng Trung: 6/7 ca hạ điểm nhưng chỉ 2/7 flag; 3↔2 chấm 60–71 không flag; không pitch contour; nhãn tone đôi khi sai.
  - Free talk chạy thật: Groq ASR + Azure unscripted + Gemini coaching.
  - Frontend: audio-recorder, mic-readiness, voice-feedback, spoken-coaching, voice-evidence, audio-analysis (waveform, pitch client-side).
  - D-077..D-080: ba lớp ngôn ngữ interface/support/target; mọi copy key khai báo lớp. Practice hub retired; one learner flow per capability.
  - Chạm file dùng chung: AGENTS.md, ci.yml, app.py, app.js, api.js, theme.css, index.html, account_profile.py; +8 .mjs gate.
  - Chờ người: SpeechSuper cho tone; S24.

admin/control-center (48 commit / 117 file)
  - Admin console theo canonical Admin design: Overview, AI (cấu hình provider), Users, Imports, Operations, Reading.
  - Reading content engine + Adaptive Reading schema qua independent review APPROVED: migrations 0013_reading_content_engine,
    0014_adaptive_reading — đã đánh số lại thành 0015/0016 khi tích hợp (PR #63); head duy nhất 20260924_0016.
  - Chạm: learner_summary.py, cross_skill_transfer.py, product_activity.py, persistence/models.py, app.py, compose.yaml, .env.example.
  - Đã sync một chiều từ codex/work (D-074).
```

codex/work sau PR #63 (2026-09-27) — nền của lane này
  - Merge qua nhánh codex/integrate-admin-speaking, external review; Admin/Reading checkpoint PASS delta review (no P0/P1).
  - Verification hợp nhất 2026-09-26: pytest 2472 passed / 3 skipped / 0 failed (PostgreSQL 16 cách ly); 66 .mjs gate;
    ESM 121 module; validator memory/architecture xanh. Không claim CI.
  - Alembic: 16 revision, head 20260924_0016. Reading 0015/0016 chưa được phép apply lên shared runtime.
  - app.py include: platform, product, media_learning, contextual_dictionary, word_detail, reading_translation, speech,
    speaking_library, listening_progress, media_library(+upload), collection, library, deck, word_audio, word_deep,
    word_clips, learner_summary, work, reading_library, admin_console, reading_admin, reading_articles, reading_practice.
  - GET /api/learner-summary?window=30d (I6) tồn tại — nền cho coaching snapshot.
  - Claude Design source: unavailable; visual-source gate UNVERIFIED theo lệnh người (xem D11).
  - Live speech và AI provider acceptance: human gate riêng.
  - Governance: D-085 (lane này), handoff cập nhật qua PR governance/orena-intelligence-d085.

## 41. Phụ lục B — Chi phí ước tính (đo lại trong Track 0)

```text
Gemini Live (S2S)                              ~$0.036 / phút; free tier cho dev (giới hạn thấp)
Azure Voice Live Standard (gpt-realtime-mini)  ~$0.02–0.03 / phút (+ resource, credential gate)
GPT-Live 1                                     $0.05 / phút + backend token (credential gate)
Cascade (Groq ASR + Gemini TTS)                ~$0.02–0.05 / phút
Text turn (Gemini flash, 3–6k in / 300 out)    ~$0.003–0.01 / lượt
Hạ tầng hiện có (VPS + Postgres)               không đổi

100 user active × (20 phút voice + 200 lượt text)/tháng ≈ $150–300/tháng ≈ $1.5–3/user.
Ngưỡng metering mặc định đề xuất: 30 phút voice / user / ngày; 300 lượt text / user / ngày.
```
