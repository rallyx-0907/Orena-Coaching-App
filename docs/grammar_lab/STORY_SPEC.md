# Grammar Lab — Story block (schema v0.3)

28/09/2026 · nhánh `feature/grammar-lab-pipeline` · nguồn: chỉ đạo trực tiếp của người, ghi lại
nguyên văn quyết định tại đây để không dựa vào lịch sử chat. Không thay đổi phạm vi Grammar Lab:
vẫn chỉ sinh nội dung ngữ pháp và lời giải thích.

## 1. Vị trí trong schema

`story` là một **loại block mới**, đặt cạnh `formula`/`example`/`pitfall`/... — **không thay thế**
các block hiện có. Mỗi điểm ngữ pháp có **một story cho mỗi theme**; theme `daily` **bắt buộc** cho
mọi điểm ở `schema_version: "0.3"` (SPEC §3, `grammar_set.schema.json` `$defs.block_story`, ràng buộc
`contains` ở cấp `grammar_point`). Điểm ở `schema_version: "0.2"` không bị ảnh hưởng — không cần story.

Story là **trung tâm** của một điểm ngữ pháp: một câu chuyện ngắn, sống động, giúp hình dung và nhớ
được khi nào dùng cấu trúc này.

## 2. Các beat (lưu tách riêng — app hiển thị từng beat độc lập)

| Beat | Nội dung | Ứng với luồng R5 |
| --- | --- | --- |
| `scene` | Tình huống đời thường, có nhân vật cụ thể | notice |
| `need` | Vì sao người nói cần cách nói này | understand |
| `form_in_action` | (Các) câu đúng trong tình huống đó | pattern, context |
| `alternatives[]` | Cách nói khác, và điều gì xảy ra sai (hiểu lầm, ngượng, buồn cười) | compare |
| `anchor` | Hình ảnh/ẩn dụ giúp nhớ khi nào dùng và khi nào không | recall |

Mỗi `alternative` có: câu ở ngôn ngữ đích (`sentence`), một hoặc nhiều `error_tags`, và `consequence`
(giải thích đầy đủ điều gì xảy ra sai — dùng để đối chiếu ở bước verify).

**Dạng ngắn** (cho màn hình ôn tập): `anchor_short` (≤ 20 từ) và `short` trong mỗi alternative (một
dòng).

**Độ dài**: 150–250 từ ở locale giải thích (vi trước) — tính tổng `scene` + `need` + `anchor` +
`consequence` của mọi alternative, không tính các dạng ngắn. Câu ở ngôn ngữ đích (`form_in_action`,
`alternatives[].sentence`) viết bằng ngôn ngữ đích, không tính vào 150–250 từ đó.

## 3. Cast nhân vật

Một cast **cố định, dùng chung** cho mọi điểm và mọi ngôn ngữ đích: `cast/cast.yaml`. Mỗi nhân vật có
tên và một dòng mô tả tính cách. Trung lập về văn hoá cho người học Việt Nam, không rập khuôn (không
gán nghề theo giới, không rập khuôn sắc tộc/văn hoá). Mọi story chọn nhân vật **từ cast này**, không
tự bịa nhân vật mới. Thêm nhân vật là sửa `cast/cast.yaml` trực tiếp, không phải việc `generate.py`
tự làm.

## 4. Slot có cấu trúc

`form_in_action` và mỗi `alternatives[]` mang `slots[]`: `{role, value, constraint}` với `role` thuộc
`person | place | action | object`. `value` là đúng từ/cụm từ trong câu đóng vai trò đó; `constraint`
mô tả ràng buộc ngữ pháp mà một giá trị thay thế phải giữ. Mục đích: sau này app có thể kể lại câu
chuyện bằng chính đời sống của người học ở bước transfer. **Điền dữ liệu người học vào slot nằm ngoài
phạm vi của lab** — lab chỉ sinh và lưu cấu trúc.

## 5. Theme

Nhãn `theme` trên story: `daily | travel | work | exam`. `daily` là mặc định và **bắt buộc** cho mọi
điểm; các theme khác đến ở vòng sau (chưa triển khai).

## 6. Verify (thêm cho story, ngoài các kiểm tra đã có)

| Kiểm tra | Cách làm | Gắn cờ khi |
| --- | --- | --- |
| Câu `form_in_action` sạch | Gửi qua engine | Engine bắt bất kỳ lỗi nào |
| Alternative — nếu sai ngữ pháp | Gửi `sentence` qua engine | Engine không bắt đúng `error_tags` đã khai |
| Alternative — nếu đúng ngữ pháp nhưng khác nghĩa | Engine không bắt lỗi → hỏi model blind-solve mô tả câu đó ngụ ý gì | Mô tả không khớp `consequence` đã khai |
| Không có tuyên bố về nguồn gốc lịch sử/từ nguyên | Hỏi model blind-solve | Có tuyên bố loại này |
| Rubric: dễ hình dung, đúng khi-nào-dùng, không dài dòng | Model **khác họ** với model sinh chấm điểm | Điểm thấp |
| Tiếng Trung | — | **Luôn vào hàng đợi duyệt**, bất kể điểm hay đã qua gold set |

Nguyên tắc chung của SPEC vẫn áp dụng: model sinh và model verify phải khác họ; mọi câu chuyện đều là
nguyên bản, không phỏng theo hay dùng lại nội dung của người khác.

## 7. App dùng beat thế nào (không xây ở đây, chỉ để biết beat phải tách được)

Bài học lần đầu; ôn tập; khi mắc lỗi (tra theo `error_tag`); và khi Orena kể theo yêu cầu. Đây là lý
do mỗi beat phải tự đọc được độc lập, không dựa vào các beat khác.

## 8. Lộ trình

1. Xây v0.3 offline (schema, cast, prompt sinh, verify) — test giả, không gọi provider thật.
2. Smoke 1–2 điểm trong sandbox `:8020` với prompt mới, báo chi phí từng provider và dán nguyên
   story để người đọc.
3. Vòng 10 điểm chờ người duyệt riêng.

8 điểm mẫu tiếng Anh còn lại ở `schema_version: "0.2"`, không có story — không nằm trong phạm vi việc
này; nâng cấp toàn bộ danh mục lên v0.3 là quyết định riêng, chưa đặt ra ở đây.
