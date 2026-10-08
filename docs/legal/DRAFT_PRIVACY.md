> **DRAFT — not legal advice — requires the human's approval and, ideally, a lawyer's review before publication.**

# Orena — Privacy Policy (DRAFT)

Chinese (中文) version: [DECISION: Chinese version waits for approval of the English and Vietnamese text.]
Last updated: [DATE]. Version: draft 0.1 (2026-10-04).

---

## Note to counsel (strip before publishing)

To check with counsel, not claimed as done:

- Decree 13/2023/ND-CP on personal data protection: consent wording, the processing impact assessment dossier, notification to the competent authority, data subject rights and response times, and rules on transferring data abroad (Orena's AI providers process data outside Vietnam, probably).
- Law on Consumer Rights Protection 2023: consumer information and data rules.
- E-commerce rules (Decree 52/2013/ND-CP, as amended): privacy disclosures for e-commerce sites.
- Whether voice recordings, and learners under 16, need special handling.
- Whether other laws apply (for example if learners in the EU, UK, China or elsewhere use Orena). This draft does not claim compliance with any law.

Facts below were checked against the repository on 2026-10-04. Where the repository cannot prove something, it is marked [DECISION].

---

# English

## 1. Who is responsible
[OPERATOR], [ADDRESS], decides how your data is used ("we"). Contact: [EMAIL]. [DECISION: name a data protection contact or officer, if required.]

## 2. The short version
- You sign in with Google. We keep what you learn and write so Orena can continue where you stopped.
- Some features send your text or voice to AI providers to get an answer.
- We do not sell your data. [DECISION: confirm.]
- Your Orena coach's notes about you stay on your device.
- Today there is no self-service button to delete your account or export all your data. Write to [EMAIL]. [DECISION: confirm the process and response time.]

## 3. What we collect
**From Google sign-in:** your Google account identifier, email address (we require it to be verified), name and profile picture.

**What you create and do in Orena (stored in your account):**
- Writing: drafts, revisions, review history and the mistakes found.
- Conversations and discussions about texts.
- Notes, highlights and annotations.
- Saved words, vocabulary decks, review settings and progress.
- Reading, listening, shadowing and speaking records: progress, attempts and results. Reading and speaking also keep results the AI or speech provider returned (for example scores).
- Grammar progress.
- Where you stopped (continuation / place) and your library.
- Private texts you import, and a record of where your content came from.
- Settings: learning language, interface language, level, weekly goal, review settings.
- Your plan and subscription state, and usage counts used for plan limits.

**Technical data:** a session cookie (section 8), and activity records kept for security and operations (for example admin audit entries and per-turn records of the Orena coach, section 6).

**Voice recordings:** by default a recording exists only during your session and is gone afterwards. If you turn on "Keep recent recordings", up to five recordings per line are kept on your own device. We do not save recordings on our servers. [DECISION: re-confirm before publishing, since a server library is a possible future feature and would need this page updated first.]

We do not collect: payment card numbers (the payment provider does, section 7).

## 4. Why we use it
- To run Orena: sign you in, save your work, show your progress, give feedback.
- To run AI features for you (section 5).
- To keep Orena safe and working, and to limit misuse.
- To manage plans, usage limits and payments.
- To understand cost and quality of AI features, without identifying you in most cases (section 6).
- To follow the law.
[DECISION: legal bases / consent mechanism required by Decree 13/2023, for counsel to set.]

## 5. AI providers: what is sent
To produce AI results, Orena sends data to the provider that is switched on. The repository supports these:
| Provider | Used for | What is sent |
|---|---|---|
| Google Gemini API | writing feedback, translation, coach replies and other text features | your text and the instructions needed for the task |
| Groq (Whisper) | speech recognition (turning your voice into text) | your audio, or a link to it |
| Microsoft Azure Speech | pronunciation scoring | your audio and the reference text |
| Ollama (self-hosted, our own computer) | text features during development and, if configured, in service | your text; it does not go to a third-party company |
[DECISION: which providers are active in production, and in which region, as they can be switched by the operator. Remove rows that are not used.]

Each provider processes your data under its own terms and privacy policy. [DECISION: add links, and check each provider's retention and training settings before saying anything about them; the repository does not prove them.] We send what is needed for the task and do not send your name or email in the request. [DECISION: verify this statement against the code before publishing; it has not been verified here.]

## 6. Telemetry and records about AI use
- **AI call telemetry** is anonymous by design: for each AI call we keep technical facts (feature, provider, model, success or failure, time taken, size or audio length, cost estimate). It is not linked to your account.
- **Orena coach turns** are different: each turn creates a record linked to your account (`agent.turn`), with technical data about the turn. These records are kept for 90 days and then deleted automatically. [DECISION: the automatic deletion is built but off by default until it is switched on; confirm it is on before publishing this sentence.]
- **Planned cost record per account:** to understand and limit AI cost per learner, we plan to keep a record with your account ID, the feature used, the cost and the time. It will be kept 13 months and then deleted automatically (human decision of 2026-10-04). [DECISION: this is not built yet; publish this paragraph only when the feature goes live, or word it as "will".]

## 7. Who else sees your data
- **AI providers** (section 5).
- **Google** for sign-in. Interface fonts are loaded from Google Fonts, so your browser contacts Google when you open Orena. [DECISION: keep, or host fonts ourselves.]
- **Payment providers** when payments launch: a Vietnamese gateway ([GATEWAY NAME]) for QR bank transfer and e-wallets, and a merchant of record ([MERCHANT OF RECORD]) for international cards. They handle your payment details; we receive the result of the payment and your plan state. [DECISION: complete once providers are chosen.]
- **Hosting and infrastructure providers:** [DECISION: name the host, region and any CDN or tunnel provider.]
- **Authorities**, when the law requires.
We do not sell your data and do not share it for advertising. [DECISION: confirm.]

## 8. Cookies and similar
- One session cookie, `writing_coach_session`, signed with a secret, keeps you signed in. It is set `SameSite=Lax`, and marked secure (HTTPS only) when Orena runs in secure mode. It is not used for advertising.
- Your browser or device also stores local data Orena needs (for example your Orena conversation, coach notes, interface settings, and optionally recent recordings). You can clear it in your browser.
- We do not use advertising cookies. [DECISION: confirm; add analytics disclosure if any analytics tool is added.]

## 9. Notes the Orena coach keeps about you
The coach may propose short notes (for example your goals or preferences) that you stated directly; it should not record emotions, personal circumstances or health. Notes and the conversation history are stored on your device, not on our servers. You can see and delete coach notes in your preferences. Clearing your browser data also removes them. [DECISION: this describes the current design (AGENT_CONTRACT); update if conversation history moves to the account.]

## 10. How long we keep data
- Account data: until you delete your account, unless the law requires us to keep some of it.
- Account deletion is permanent. A deleted account is never restored, not by support, not from a backup, and signing up again creates a brand-new account with none of your old data.
- Backups and logs: kept for [DECISION: retention period; repository records no value].
- `agent.turn` records: 90 days. Per-account cost record: 13 months (planned).
- Payment and tax records: [DECISION: period required by Vietnamese accounting and tax law, to confirm with counsel].

## 11. Your choices and rights
You can ask to access, correct, delete, restrict or object to our use of your data, to withdraw consent, and to receive a copy. [DECISION: status today: the repository has a permanent-deletion policy and enumeration of what to delete, but no self-service deletion or full export feature yet; describe the email process and response time you commit to, and update when features ship.] Write to [EMAIL]. You may also complain to the competent authority in your country.

## 12. Security
We use signed sessions, HTTPS in production and access control for administrators. No system is perfectly secure. [DECISION: add breach-notification commitment per Decree 13/2023, with counsel.]

## 13. Children
Orena is not meant for children under [DECISION: age]. [DECISION: parental consent process if minors are allowed.]

## 14. International transfers
Our AI, hosting and payment providers may process data outside Vietnam. [DECISION: wording and any filing required for cross-border transfer, with counsel.]

## 15. Changes
We will update this page and tell you in the app or by email [DECISION: notice period] before important changes.

## 16. Contact
[OPERATOR], [ADDRESS], [EMAIL].

---

# Tiếng Việt

*Bản dịch dự thảo. Bản tiếng Trung chờ phê duyệt.*

## 1. Ai chịu trách nhiệm
[OPERATOR], [ADDRESS], quyết định cách dữ liệu của bạn được sử dụng ("chúng tôi"). Liên hệ: [EMAIL]. [DECISION: người phụ trách bảo vệ dữ liệu, nếu bắt buộc.]

## 2. Tóm tắt
- Bạn đăng nhập bằng Google. Chúng tôi lưu những gì bạn học và viết để Orena tiếp tục từ chỗ bạn dừng.
- Một số tính năng gửi văn bản hoặc giọng nói của bạn tới nhà cung cấp AI để có câu trả lời.
- Chúng tôi không bán dữ liệu của bạn. [DECISION: xác nhận.]
- Ghi chú của huấn luyện viên Orena về bạn nằm trên thiết bị của bạn.
- Hiện chưa có nút tự xoá tài khoản hoặc xuất toàn bộ dữ liệu. Hãy viết tới [EMAIL]. [DECISION: xác nhận quy trình và thời gian phản hồi.]

## 3. Chúng tôi thu thập gì
**Từ đăng nhập Google:** mã định danh tài khoản Google, email (phải được xác minh), tên và ảnh đại diện.

**Những gì bạn tạo và làm trong Orena (lưu trong tài khoản):**
- Viết: bản nháp, các lần sửa, lịch sử nhận xét và lỗi đã phát hiện.
- Hội thoại và thảo luận về văn bản.
- Ghi chú, đánh dấu và chú thích.
- Từ đã lưu, bộ từ vựng, cài đặt ôn tập và tiến độ.
- Bản ghi đọc, nghe, nhại theo (shadowing) và nói: tiến độ, lần thử và kết quả. Đọc và nói cũng lưu kết quả do AI hoặc nhà cung cấp giọng nói trả về (ví dụ điểm).
- Tiến độ ngữ pháp.
- Chỗ bạn dừng và thư viện của bạn.
- Văn bản riêng bạn nhập, và ghi nhận nguồn gốc nội dung.
- Cài đặt: ngôn ngữ học, ngôn ngữ giao diện, trình độ, mục tiêu tuần, cài đặt ôn tập.
- Gói và trạng thái đăng ký, số lượt dùng để áp hạn mức.

**Dữ liệu kỹ thuật:** cookie phiên (mục 8), và bản ghi hoạt động phục vụ an ninh và vận hành (ví dụ nhật ký quản trị và bản ghi từng lượt của huấn luyện viên Orena, mục 6).

**Bản ghi âm giọng nói:** mặc định bản ghi chỉ tồn tại trong phiên và mất sau đó. Nếu bạn bật "Giữ các bản ghi gần đây", tối đa năm bản ghi mỗi dòng được giữ trên thiết bị của bạn. Chúng tôi không lưu bản ghi âm trên máy chủ. [DECISION: xác nhận lại trước khi công bố.]

Chúng tôi không thu thập: số thẻ thanh toán (nhà cung cấp thanh toán thu thập, mục 7).

## 4. Vì sao chúng tôi dùng
- Vận hành Orena: đăng nhập, lưu bài, hiển thị tiến độ, đưa phản hồi.
- Chạy tính năng AI cho bạn (mục 5).
- Giữ Orena an toàn, hoạt động tốt và hạn chế lạm dụng.
- Quản lý gói, hạn mức và thanh toán.
- Hiểu chi phí và chất lượng tính năng AI, thường không định danh bạn (mục 6).
- Tuân thủ pháp luật.
[DECISION: cơ sở pháp lý / cơ chế đồng ý theo Nghị định 13/2023, do luật sư thiết lập.]

## 5. Nhà cung cấp AI: gửi gì
Để tạo kết quả AI, Orena gửi dữ liệu tới nhà cung cấp đang bật. Mã nguồn hỗ trợ:
| Nhà cung cấp | Dùng cho | Dữ liệu gửi |
|---|---|---|
| Google Gemini API | nhận xét bài viết, dịch, lời huấn luyện viên, các tính năng văn bản | văn bản của bạn và chỉ dẫn cho tác vụ |
| Groq (Whisper) | nhận dạng giọng nói (chuyển giọng nói thành chữ) | âm thanh của bạn, hoặc liên kết tới nó |
| Microsoft Azure Speech | chấm phát âm | âm thanh của bạn và văn bản mẫu |
| Ollama (tự lưu trữ, máy của chúng tôi) | tính năng văn bản khi phát triển và, nếu cấu hình, khi vận hành | văn bản của bạn; không gửi tới công ty bên thứ ba |
[DECISION: nhà cung cấp nào đang bật trên bản chính thức, ở khu vực nào; xoá các dòng không dùng.]

Mỗi nhà cung cấp xử lý dữ liệu theo điều khoản và chính sách riêng. [DECISION: thêm liên kết; kiểm tra chính sách lưu giữ và huấn luyện của từng nhà cung cấp trước khi nêu.] Chúng tôi gửi những gì cần cho tác vụ và không gửi tên hay email của bạn trong yêu cầu. [DECISION: kiểm chứng với mã nguồn trước khi công bố; chưa được kiểm chứng.]

## 6. Số liệu và bản ghi về việc dùng AI
- **Số liệu cuộc gọi AI** ẩn danh theo thiết kế: mỗi cuộc gọi AI ghi các thông tin kỹ thuật (tính năng, nhà cung cấp, mô hình, thành công hay lỗi, thời gian, kích thước hoặc độ dài âm thanh, ước tính chi phí). Không gắn với tài khoản của bạn.
- **Lượt của huấn luyện viên Orena** thì khác: mỗi lượt tạo một bản ghi gắn với tài khoản (`agent.turn`), chứa dữ liệu kỹ thuật về lượt đó. Giữ 90 ngày rồi tự động xoá. [DECISION: tính năng xoá tự động đã có nhưng tắt mặc định; xác nhận đã bật trước khi công bố.]
- **Bản ghi chi phí theo tài khoản (dự kiến):** để hiểu và giới hạn chi phí AI theo người học, chúng tôi dự kiến lưu bản ghi gồm mã tài khoản, tính năng đã dùng, chi phí và thời gian. Giữ 13 tháng rồi tự động xoá (quyết định ngày 04/10/2026). [DECISION: chưa xây dựng; chỉ công bố đoạn này khi tính năng hoạt động, hoặc dùng "sẽ".]

## 7. Ai khác thấy dữ liệu của bạn
- **Nhà cung cấp AI** (mục 5).
- **Google** cho đăng nhập. Phông chữ giao diện tải từ Google Fonts nên trình duyệt của bạn liên hệ Google khi mở Orena. [DECISION: giữ, hoặc tự lưu phông chữ.]
- **Nhà cung cấp thanh toán** khi ra mắt: cổng trong nước ([GATEWAY NAME]) cho chuyển khoản QR và ví điện tử, và đơn vị bán hàng chính thức ([MERCHANT OF RECORD]) cho thẻ quốc tế. Họ xử lý thông tin thanh toán; chúng tôi nhận kết quả thanh toán và trạng thái gói. [DECISION: hoàn thiện khi chọn nhà cung cấp.]
- **Nhà cung cấp lưu trữ, hạ tầng:** [DECISION: tên, khu vực, CDN hoặc đường hầm.]
- **Cơ quan nhà nước**, khi pháp luật yêu cầu.
Chúng tôi không bán dữ liệu và không chia sẻ cho quảng cáo. [DECISION: xác nhận.]

## 8. Cookie và tương tự
- Một cookie phiên, `writing_coach_session`, được ký bằng khoá bí mật, giữ bạn đăng nhập. Đặt `SameSite=Lax` và đánh dấu bảo mật (chỉ HTTPS) khi Orena chạy ở chế độ bảo mật. Không dùng cho quảng cáo.
- Trình duyệt hoặc thiết bị cũng lưu dữ liệu cục bộ Orena cần (ví dụ hội thoại Orena, ghi chú huấn luyện viên, cài đặt giao diện, và tuỳ chọn các bản ghi âm gần đây). Bạn có thể xoá trong trình duyệt.
- Chúng tôi không dùng cookie quảng cáo. [DECISION: xác nhận; thêm thông tin nếu dùng công cụ phân tích.]

## 9. Ghi chú huấn luyện viên Orena giữ về bạn
Huấn luyện viên có thể đề xuất ghi chú ngắn (ví dụ mục tiêu, sở thích) mà chính bạn nói ra; không ghi cảm xúc, hoàn cảnh cá nhân hay sức khoẻ. Ghi chú và lịch sử hội thoại lưu trên thiết bị của bạn, không lưu trên máy chủ. Bạn xem và xoá ghi chú trong tuỳ chọn. Xoá dữ liệu trình duyệt cũng xoá chúng. [DECISION: mô tả thiết kế hiện tại; cập nhật nếu lịch sử hội thoại chuyển vào tài khoản.]

## 10. Chúng tôi giữ dữ liệu bao lâu
- Dữ liệu tài khoản: đến khi bạn xoá tài khoản, trừ khi pháp luật buộc giữ một phần.
- Xoá tài khoản là vĩnh viễn. Tài khoản đã xoá không bao giờ được khôi phục, kể cả qua hỗ trợ hay bản sao lưu; đăng ký lại tạo tài khoản hoàn toàn mới, không có dữ liệu cũ.
- Bản sao lưu và nhật ký: giữ [DECISION: thời hạn].
- Bản ghi `agent.turn`: 90 ngày. Bản ghi chi phí theo tài khoản: 13 tháng (dự kiến).
- Hồ sơ thanh toán và thuế: [DECISION: thời hạn theo pháp luật kế toán, thuế Việt Nam, xác nhận với luật sư].

## 11. Lựa chọn và quyền của bạn
Bạn có thể yêu cầu truy cập, chỉnh sửa, xoá, hạn chế hoặc phản đối việc chúng tôi dùng dữ liệu, rút lại đồng ý và nhận bản sao. [DECISION: hiện đã có chính sách xoá vĩnh viễn nhưng chưa có tính năng tự xoá hay xuất dữ liệu đầy đủ; nêu quy trình email và thời gian phản hồi cam kết.] Viết tới [EMAIL]. Bạn cũng có thể khiếu nại tới cơ quan có thẩm quyền.

## 12. Bảo mật
Chúng tôi dùng phiên có chữ ký, HTTPS khi vận hành và kiểm soát truy cập cho quản trị viên. Không hệ thống nào an toàn tuyệt đối. [DECISION: cam kết thông báo vi phạm theo Nghị định 13/2023, cùng luật sư.]

## 13. Trẻ em
Orena không dành cho trẻ dưới [DECISION: độ tuổi]. [DECISION: quy trình đồng ý của cha mẹ nếu cho phép người chưa thành niên.]

## 14. Chuyển dữ liệu ra nước ngoài
Nhà cung cấp AI, lưu trữ và thanh toán có thể xử lý dữ liệu ngoài Việt Nam. [DECISION: cách diễn đạt và hồ sơ cần nộp, cùng luật sư.]

## 15. Thay đổi
Chúng tôi sẽ cập nhật trang này và báo trong ứng dụng hoặc qua email [DECISION: thời hạn báo trước] trước thay đổi quan trọng.

## 16. Liên hệ
[OPERATOR], [ADDRESS], [EMAIL].

---

## Sources in the codebase (internal appendix; strip before publishing)

- Google OAuth sign-in, scopes openid/userinfo.email/userinfo.profile, verified email required, name/email/picture returned: `auth_support.py` (~139-147, ~313, ~368-370).
- Session cookie `writing_coach_session`, `SESSION_SECRET`, `same_site="lax"`, `https_only=COOKIE_SECURE`: `auth_support.py` (~42, ~510-515).
- Tables of what is stored per account (users, user_language_profiles, essays, essay_review_history, essay_revisions, writing_errors, saved_words, grammar_progress, listening_progress, shadowing_progress, speaking_attempts, reading_* attempts and projections, library_items, text_discussions and turns, vocabulary_*, plans, subscriptions, usage_events, audit_logs): `writing_coach/persistence/models.py`.
- Server-side learner records approved: `docs/project/DECISION_LOG.md` D-104 (H-18): drafts, conversations, continuation/place, notes/highlights/annotations, imported private content, provenance. Still deferred there: sync protocol, account-deletion runtime, export format, Orena conversation persistence.
- Deletion policy (permanent, no restore, re-registration is a new incarnation): D-054, D-055 in `DECISION_LOG.md`; no runtime deletion path: `writing_coach/persistence/deletion_enumeration.py` line 3. No self-service account deletion or full export route was found (grep of `@app`/`@router` routes).
- Providers: `writing_coach/ai/providers.py` (ollama, groq, gemini), `writing_coach/ai/azure.py`, `writing_coach/speech_asr.py` (Groq transcriptions: audio bytes or `audio_url`), `writing_coach/speech_pronunciation.py` (Azure Speech endpoint `*.stt.speech.microsoft.com`), `app.py` (~499-532 Groq/Ollama config).
- Audio: default session-only; optional local "Keep recent recordings", max five per line; nothing saved on the server in that phase: `docs/project/DECISION_LOG.md` (decision dated 2026-09-23, around line 2719).
- Coach notes and conversation are device memory; `preferences.agent_memory` lets the learner list and delete them: `docs/project/AGENT_CONTRACT.md` §5.4 (line 206-208) and lines 386-387.
- AI telemetry anonymous by design; only agent turns carry an account: `writing_coach/ai/platform.py` (~910-921 `COST_REPORT_GAPS`), `writing_coach/ai/audio_telemetry.py`.
- `agent.turn` kept 90 days, sweep off unless `AGENT_TURN_RETENTION_SWEEP` is on: `app.py` (~841-853), `writing_coach/agent/retention.py`, `tests/test_agent_retention.py`, `docs/project/AGENT_SPEC.md`.
- Per-account cost record with 13-month retention: human decision of 2026-10-04 as given to the drafter; not found in the repository at drafting time.
- Google Fonts loaded from Google; licences page: `THIRD_PARTY_NOTICES.md`.
- Not found in the repository: hosting provider and region, legal bases, backup retention period, provider-side retention or training settings, whether requests omit name and email.
