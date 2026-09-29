# Chinese Writing evaluator recall - causes and fix options (2026-09-29)

**Status: reported to the human, no code changed. The human chooses the fix.** Recorded here because
the first investigation was only in a chat and was lost. Rebuilt from the code on `codex/work`,
read-only; the primary cause was re-checked at the cited lines.

Branch `codex/work` @ a40e64b. Read-only investigation; no code changed, no Docker run.
Legend: **[VERIFIED]** = read in code and/or reproduced with a host stdlib script; **[INFERRED]** = plausible from code, not measured against a live model.

## Pipeline (one path only)

`app.py:930 evaluate_with_ai` → system prompt `active_system_prompt()` (zh: `writing_coach/languages/chinese/profile.py:47-87`) + user request `build_writing_evaluator_request` (`writing_coach/writing_evaluator_contract.py:124-283`, language-neutral) + schema (`writing_evaluator_contract.py:286-369`) → `generate_structured(max_output_tokens=2200, temperature=0)` (`app.py:952-961`) → `validate_result` (`app.py:900-914`) → `normalize_writing_evaluation` / `_normalize_errors` (`writing_coach/writing_evaluation.py:38-116, 238-315`).
Detection of Chinese errors is **LLM-only**. There is no deterministic Chinese detector: `heuristic_fallback` runs its three regex checks only `if not is_chinese()` (`app.py:1008-1021`), and only when the provider is unavailable. Categories for zh are `chinese/profile.py:26-45` (word_order, particle, aspect, complement, measure_word, ba/bei, …, other).

## Causes

### 1. Post-filter silently drops any zh finding whose explanation/rule quotes a Chinese character — PRIMARY [VERIFIED]
- `app.py:903-904`: `allow_explanation_cjk = support_language_uses_cjk(support_code)` → **False** for a Vietnamese (or English) support language (`writing_coach/core/support_languages.py:63-67`).
- `writing_evaluation.py:285-286`: `if not explanation_allow_cjk and (contains_cjk(explanation) or contains_cjk(rule)): continue` — the whole error is discarded, not just the text.
- `writing_evaluation.py:12` `_CJK_RE` matches any Han character, so "dùng lượng từ 本 cho sách" or "không dùng 了 sau 过" kills the finding.
- The zh system prompt explicitly **invites** this: `chinese/profile.py:76` "You may include short Chinese examples inside support-language explanations when they are necessary to teach the rule." Explaining a Chinese particle/measure-word/把 error in Vietnamese without writing the character is nearly impossible, so the most teachable zh errors are the ones most likely dropped.
- English target is barely affected (English explanations do not contain Han), so this is a zh-specific recall loss. Same filter also drops zh `strength_evidence` (`writing_evaluation.py:217`) and empties `summary_vi` / `strengths_vi` / `priorities_vi` containing a character (`:82-84`).
- Regression origin: `c71c644` (2026-09-14, "route evaluator explanations through resolved support language") decoupled `allow_explanation_cjk` from `allow_cjk`. Before it, zh ran with `allow_cjk=is_chinese()=True` for explanations too, so these findings survived.
- Tests do not catch it: the zh end-to-end fixture uses ASCII-only Vietnamese explanations (`tests/test_writing_evaluation.py:684-706`); `test_english_language_safety_rejects_unexpected_cjk_learner_explanations` (`:309-323`) asserts the drop as desired for English. No test covers zh target + vi support + Han in the explanation.
- Reproduced on host (stdlib only): 4 zh findings in → 2 out; the `measure_word` finding for `三个书` was dropped solely because its Vietnamese explanation quoted 本/个.

### 2. Dedupe by (category, fragment) + first-occurrence span collapses repeated short Han fragments [VERIFIED mechanism; recall impact INFERRED]
- `writing_evaluation.py:291-294` keys identity on `(category, fragment)`; `_evidence_span` (`:133-137`) uses `str.find`, i.e. the first occurrence.
- Chinese fragments are often 1-2 characters (的, 了, 个) that recur; two distinct mistakes with the same fragment become one, and the survivor may highlight the wrong place. Reproduced: two `的的` redundancy findings → one. English fragments are usually multi-word and rarely collide.

### 3. Prompt policy is internally contradictory and English-centric on recall [VERIFIED text; model effect INFERRED]
- zh system prompt `chinese/profile.py:50`: "Fewer accurate corrections are better than many doubtful ones." The request contract explicitly removed this wording because small models obey it by returning almost nothing (`writing_evaluator_contract.py:205-225`), but the system prompt still says it (English has the same at `english/profile.py:45,67`). The system role usually outweighs the user message.
- The recall instruction names only English error types: "verb-form, agreement, article, tense, word-choice or fixed-expression" (`writing_evaluator_contract.py:220-222`). None of zh's dominant types (measure word, aspect 了/过, 的/地/得, 把/被, complements, wrong homophone character, omission) is named.
- "Every errors item must describe a genuine problem visible in its exact fragment" (`:203`) discourages omission errors (missing 了/的/量词/在), which are frequent in Chinese learner text; the model has to pick a neighbouring span to anchor a missing element and no instruction tells it how.

### 4. Benchmark cannot measure zh recall [VERIFIED]
- `writing_evaluation_benchmark.py:283-291`: recall passes if **any one** required category appears. Each zh OBVIOUS_ERROR case is one short sentence with 1-2 errors (`writing_evaluation_benchmark_fixtures.py:199-245`); no multi-error zh paragraph, no zh+vi support case with Han in explanations. `known_passing_result` (`:350-398`) uses ASCII explanations. So recall regressions like #1 pass the benchmark.
- `scripts/verify_live_writing_evaluator.mjs:448-455` checks explanation script against the support language, i.e. it reinforces the same rule as #1 rather than measuring loss.

### 5. Output budget / caps [INFERRED, language-neutral, lower confidence]
- `max_output_tokens=2200` (`app.py:958`) for 5 scores + summary + strengths + up to 20 errors each with explanation, rule, suggestion, example in Vietnamese (diacritics tokenize expensively). A long zh essay can hit the budget; `MAX_ERROR_ITEMS=20` (`writing_evaluation.py:16`) also truncates. Affects English too; not measured.
- Old low-recall reviews are reused until `EVALUATOR_CONTRACT_VERSION` (`writing_coach/writing_review_identity.py:50`, `writing-evaluation-v2.6`) moves, so any fix must bump it.

Not causes (checked): `insufficient_evidence` keeps errors (`writing_evaluation.py:74-77`, only clears level); the zh minimum is 2 Han (`writing_limits.py:222`); unanchored fragments are kept, not dropped (`:263-277`); `suggestion` CJK is allowed for zh (`allow_cjk=is_chinese()`, `app.py:911`); the new UI does not slice issues (no `issues.slice(0,n)` in `static/orena`).

## Fix options (một dòng mỗi phương án)

1. **Sửa bộ lọc script theo nguyên tắc ngôn ngữ trung lập**: cho phép chữ của *ngôn ngữ đích* xuất hiện trong explanation/mini_rule (allowed scripts = script ngôn ngữ hỗ trợ ∪ script ngôn ngữ đích), chỉ loại khi phần *văn xuôi* không phải ngôn ngữ hỗ trợ — một hợp đồng chung cho mọi cặp ngôn ngữ, không nhánh riêng cho zh — công: nhỏ (1 hàm + tests EN/ZH/JA), rủi ro: thấp (EN-target giữ nguyên hành vi; cần test đối xứng ja-support).
2. **Không vứt cả lỗi khi explanation lẫn script sai**: giữ finding (fragment, suggestion, category) và chỉ bỏ/thay phần giải thích không hợp lệ, giống cách "unanchored" đã tách "đáng tin" khỏi "định vị được" — công: nhỏ, rủi ro: trung bình (có thể hiện lỗi không có giải thích; cần quyết định UI cho trường hợp đó).
3. **Sửa dedupe/span**: định danh theo (category, fragment, suggestion) hoặc vị trí xuất hiện thứ n, và cho evaluator trả `occurrence`/ngữ cảnh để neo đúng chỗ các mảnh Hán ngắn lặp lại — công: trung bình (thêm trường schema tùy chọn trong contract, không đụng schema dữ liệu người học), rủi ro: thấp-trung bình.
4. **Căn chỉnh prompt**: bỏ câu "Fewer accurate corrections…" khỏi system prompt cả EN lẫn ZH, và để mỗi language profile cung cấp danh sách loại lỗi tiêu biểu (+ hướng dẫn neo lỗi thiếu từ) mà request chung chèn vào thay cho danh sách tiếng Anh cố định — công: nhỏ, rủi ro: trung bình (có thể tăng dương tính giả; phải bump EVALUATOR_CONTRACT_VERSION và chạy benchmark).
5. **Benchmark đo recall thật**: thêm ca zh nhiều lỗi (đoạn văn), ca zh+vi có chữ Hán trong giải thích, đổi kiểm tra recall từ "bất kỳ" sang tỉ lệ/tất cả loại bắt buộc, áp dụng đối xứng cho EN — công: trung bình, rủi ro: thấp (chỉ test/fixture; ca live cần Gemini sandbox).
6. **Bộ dò tất định cho tiếng Trung** (lượng từ, 了过 chồng, 的的…) làm lớp bổ sung — công: lớn, rủi ro: cao (vi phạm tinh thần "một contract chung", dễ hardcode, dương tính giả) — không khuyến nghị.
7. **Nâng/giải quyết ngân sách token** (tăng max_output_tokens hoặc phát hiện finish_reason=length rồi báo) — công: nhỏ, rủi ro: thấp-trung bình (chi phí); chỉ làm sau khi đo được là có cắt cụt.

**Khuyến nghị:** Làm (1) trước kèm test hồi quy zh+vi (đây là nguyên nhân chính, đã tái hiện, do c71c644 gây ra), cùng lúc (5) để đo được recall, rồi (4) + bump EVALUATOR_CONTRACT_VERSION; (3) sau đó; bỏ (6).
