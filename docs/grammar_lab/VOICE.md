# Grammar Lab — Giọng văn cho story (v3)

28/09/2026 · nhánh `feature/grammar-lab-pipeline` · nguồn: chỉ đạo trực tiếp của người,
ghi lại nguyên văn quyết định tại đây để không dựa vào lịch sử chat. Áp dụng trước tiên
cho block `story` (STORY_SPEC.md); các bề mặt khác của Orena có thể dùng lại giọng này
sau, nhưng đó là quyết định sản phẩm riêng, không tự động theo tài liệu này.

## 1. Đối tượng và giọng

Người bạn thông minh nói chuyện với **người lớn** -- không phải giáo viên đứng lớp,
không phải người kể chuyện cổ tích cho trẻ em. Câu ngắn, thẳng, tự tin, dí dỏm vừa đủ.
Lịch sử (khi có) chỉ là một chi tiết trivia ngắn, không kể thành cả câu chuyện.

## 2. Cấm

Không dùng, dưới bất kỳ hình thức nào (kể cả biến thể gần giống, không chỉ chuỗi chữ
đúng nguyên văn):

- Mở kiểu cổ tích: "Ngày xửa ngày xưa", "Đã từ lâu lắm rồi"
- Từ vựng thế giới cổ tích: "vương quốc", "nhà vô địch", "lão làng"
- Nhân cách hoá kiểu cổ tích (đồ vật/khái niệm "biết", có "phép thuật")
- Ẩn dụ ngây thơ, trẻ con
- Chấm than dồn dập
- Lời khen/động viên chung chung ("Bạn giỏi lắm!", "Cố lên nhé!")

`validate.py`'s `check_story()` kiểm cứng danh sách cụm từ liệt kê được ở trên (rule
`story.forbidden_phrase`, so khớp không phân biệt hoa/thường trên mọi trường vi của
story). Rubric verify (§8) xét thêm phần giọng văn/khuôn mẫu mà một danh sách chuỗi cố
định không bắt được.

## 3. hook -- mở đầu

Mỗi story có một `hook`: một câu mở đầu, gắn `hook_type` là một trong ba loại, không
còn khuôn generic kiểu "Bạn có biết vì sao...?":

| `hook_type` | Là gì |
| --- | --- |
| `stakes` | Điểm này ảnh hưởng thế nào đến cách người khác nhìn/hiểu người học -- công việc, giao tiếp, email |
| `insider` | Logic mà người bản xứ ngầm hiểu nhưng sách giáo khoa không nói ra |
| `myth-bust` | Điều người học tưởng đã biết, nhưng hiểu sai hoặc chưa hiểu vì sao |

## 4. reveal -- thay cho anchor (v1)

`anchor` (v1: ẩn dụ/hình ảnh để nhớ) đổi tên và đổi nội dung thành `reveal`: **insight
thật**, ưu tiên điều người học tiếng Việt chưa từng được giải thích -- kể cả nguyên
nhân từ âm thanh/ngữ âm (ví dụ: âm tiết tiếng Việt không kết thúc bằng cụm phụ âm hay
một số phụ âm đơn nhất định, nên "-s" cuối từ tiếng Anh khó nghe/khó phát âm với người
Việt), không chỉ lý do ngữ pháp thuần tuý. Nếu không có một cơ chế thật để nêu, giải
thích logic khi-nào-dùng/khi-nào-không -- không lùi về ẩn dụ hình ảnh để thay thế. Vẫn
giữ dạng ngắn `reveal_short` (≤ 20 từ, đổi tên từ `anchor_short`).

## 5. alternatives -- hậu quả theo chủ đề

`consequence` của mỗi alternative viết theo `theme` của story: `daily` → hậu quả trong
trò chuyện đời thường; `work` → email, cuộc họp; `travel` → sân bay, khách sạn. (Theme
khác `daily` chưa triển khai -- STORY_SPEC.md §5 -- quy tắc này áp dụng khi chúng được
bật.)

## 6. teaser -- kết

Một trường mới: nghịch lý hoặc câu hỏi mở gây tò mò thật, **không phải** kiểu "đón xem
bài sau" hay nhắc đến bài học tiếp theo. Câu chuyện tự nó là trọn vẹn, không quảng cáo
cho phần tiếp theo.

## 7. mode

`mode`: `history | everyday` (không còn `fable`).

- `everyday`: không có tuyên bố lịch sử/từ nguyên nào -- quy tắc cũ ở `generate_story.md`
  vẫn giữ nguyên cho mode này. Một quan sát về ngữ âm/âm vị **hiện tại** (không phải
  tuyên bố về nguồn gốc lịch sử) vẫn được phép và khuyến khích ở `reveal`.
- `history`: được phép nêu một dữ kiện lịch sử/ngữ âm, **nhưng chỉ từ nguồn đã duyệt**.
  Chưa có file dữ kiện đã duyệt nào trong repo tại thời điểm viết tài liệu này -- cho
  đến khi có, `generate.py` chỉ sinh `mode: everyday` (`STORY_MODES` trong
  `pipeline/generate.py` chỉ chứa `"everyday"`; `history` có trong enum của schema cho
  nội dung tương lai, nhưng chưa được pipeline dùng).

## 8. Rubric verify (STORY_SPEC.md §6, bổ sung)

Hai tiêu chí thêm vào rubric LLM (khác họ mô hình sinh, `prompts/verify_story.md`
mục `rubric`):

- **`adult_appropriate`**: giọng có phải kiểu bạn thông minh nói với người lớn không --
  không trẻ con, không cổ tích, không cổ vũ chung chung.
- **`no_forbidden_pattern`**: xét cả những biến thể của mục 2 mà một danh sách chuỗi cố
  định không bắt được (khác với `story.forbidden_phrase` ở `validate.py`, vốn chỉ so
  khớp chuỗi chính xác).

## 9. Ngân sách độ dài (STORY_SPEC.md §2, cập nhật)

150-250 từ (vi) tính tổng `hook.text` + `scene` + `need` + `reveal` + `teaser` + mọi
`consequence` của alternatives -- thêm `hook.text` và `teaser` vào công thức cũ của
STORY_SPEC.md §2 vì đây là hai trường văn xuôi mới. Bảy phần chia chung một ngân sách:
mỗi phần phải ngắn gọn, đúng tinh thần "câu ngắn, thẳng" ở mục 1.

## 10. Phạm vi

Ghi ở đây theo yêu cầu của người: "sau này Orena cũng dùng chung." Tài liệu này chỉ áp
dụng ngay cho Grammar Lab story block; mở rộng sang bề mặt khác của Orena (vd. Reading
Library, thông báo trong app) là quyết định sản phẩm riêng, không tự động theo đây.
