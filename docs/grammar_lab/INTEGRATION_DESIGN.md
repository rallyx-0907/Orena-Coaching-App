# Grammar Lab — tích hợp vào Orena (D-105, export package v1)

30/09/2026 · nhánh `feature/grammar-lab-pipeline` · **thay thế bản 28/09** ("bộ đã xuất bản đi cùng mã
nguồn, nạp lúc khởi động"). D-105.4 và D-106 (`docs/project/DECISION_LOG.md` trên `codex/work`) đã bỏ mô hình
đó: nội dung **không** đi cùng mã nguồn. Phía app được đặc tả ở `docs/project/proposals/GRAMMAR_CONTENT_STORE.md`
(rev 2, trên `codex/work`); tài liệu này chỉ đặc tả **phía Grammar Lab** và hợp đồng ở ranh giới. Không có mã
app, DB hay API nào trong nhánh này.

## 1. Luồng duy nhất

```
Grammar Lab ──export-package──▶ gói đã duyệt ──Admin import──▶ phiên bản nội dung bất biến trong DB
   ──Admin accept / rights / publish──▶ /api/grammar/v1/* ──▶ màn Grammar hiện có trên /next
```

- Grammar Lab là **upstream**, nơi duy nhất viết nội dung. Orena không sửa nội dung; sửa = phiên bản mới từ upstream.
- Gói chỉ chứa điểm `status: approved`. Chỉ người đặt `approved`; pipeline và công cụ xuất không bao giờ đặt.
- Import, accept, rights và publish là bốn hành động Admin tách biệt, có audit. Publish là hành động tường minh.
- Quyền (rights) là cổng cứng ở Publish (D-105.5a): chứng nhận theo lô do người ở Admin đưa ra lúc import, **không** do gói
  khai. Gói chỉ ghi chính sách nguồn (`rights` trong manifest).
- Không có `cli publish` chép JSON vào `writing_coach/`, không `index.json` đi cùng mã nguồn, không nạp lúc khởi động.

## 2. Export profile (ranh giới), khác schema nội bộ

Schema nội bộ của Grammar Lab (`schema/grammar_set.schema.json`) là đa phiên bản (v0.2/0.3/0.4), dùng `zh-Hans`, chỉ bắt
`en` khi `approved`, và chứa provenance/review/flags trong điểm. Ranh giới với app là một **profile một phiên bản**,
**suy ra** từ schema nội bộ bằng `pipeline/export_profile.py` và commit ở `schema/export_profile.schema.json`
(`export-profile --write`):

| | Nội bộ Grammar Lab | Export profile 1 (app) |
| --- | --- | --- |
| `target_lang` | `en \| zh-Hans \| ja` | `en \| zh` |
| khoá locale | `vi en zh-Hans ja` | `vi en zh` |
| locale bắt buộc | `vi` luôn; `en` khi approved | **`vi` và `en` trong mọi locale map**, placeholder bị cấm |
| `status` | 5 giá trị | hằng `approved` |
| phiên bản điểm | 0.2 / 0.3 / 0.4 | một hình dạng (khối v0.4); không `blocks`, `title`, `summary` |
| thân điểm | gồm `provenance`, `review`, `flags`, `source_anchors`, `schema_version` | **chỉ nội dung tác giả**: các trường đó không bao giờ xuất hiện |
| đóng | — | `additionalProperties: false` ở mọi object |

- `zh-Hans` ↔ `zh` là **tường minh và có test**: `to_app_point` / `from_app_point` đổi `target_lang` và khoá locale, không
  thêm chữ nào; nội bộ vẫn giữ `zh-Hans`. Ghi chú trôi dạt: hợp đồng đã merge trên `codex/work` nói `zh`; PR #67 (patch,
  chưa merge) và mục 10 của đề xuất store nói `zh-Hans` bên trong nội dung. Profile theo bản đã merge; nếu #67 được merge,
  chỉ đổi `APP_TARGET_LANG`, `APP_LOCALE_KEY` trong `export_profile.py`.
- **Chống trôi dạt**: test và lệnh xuất so `schema/export_profile.schema.json` đã commit với bản suy ra mới nhất từ schema nội
  bộ; lệch thì xuất từ chối (`profile.drift`) cho tới khi sinh lại và review profile.
- `en` không bao giờ được copy từ `vi`: `locale.en_placeholder` chặn một map có `en == vi` mang chữ Latin có dấu. Hai fixture
  UI (`fixtures/ui/`) có placeholder nên **không** vào được gói production.
- Nhãn `function` (`functions.json`) cần `vi` và `en` thật; `zh` có thì mang theo.

## 3. Manifest (`package.json`)

```
export_profile        "grammar-export-profile/1"
profile_schema_hash   sha256 của schema profile đã dùng (canonical JSON)
schema_version        "0.4"  (phiên bản nội dung mà profile suy ra từ)
language              en | zh
set_version           nhãn lô, vd. 2026-10-01.en.A1
source_commit         commit Grammar Lab đã xuất; source_dirty (bool)
exported_at           thời điểm xuất (UTC)
package_hash          mục 5
external_references   id điểm ngoài gói mà điểm trong gói tham chiếu (đã duyệt ở Grammar Lab)
functions             [{id, title:{vi,en,zh?}}]
points                [{id, version, content_hash, level,
                        provenance:{reviewer, reviewed_at, review_seconds, run_id, model, prompt_version,
                                    generated_at, source_refs, source_anchors, r5_source?}}]
r5_map                [{r5_id, point_id|null, disposition, is_primary}]   mục 4
validator             {tool, version, passed, codes}   tự khai, không phải bằng chứng an toàn; app kiểm lại sâu
rights                {source_text_policy: catalogue_codes_only, external_text_included: false,
                       attestation_required_at_import: true, note}
```

Provenance để audit nằm ở manifest, không ở thân điểm. Importer lưu `points[].provenance` cạnh phiên bản và không phục vụ
nó cho người học. `validator` là một lời khai, không ai dựa vào nó để bảo đảm an toàn.

## 4. R5: một id, đúng một thay thế chính (D-106 2, 4)

- Mỗi id R5 có **đúng một** điểm chính (primary) hoặc được `dropped`. `aliases` của điểm chứa id R5 **chỉ ở điểm chính**.
- Mảnh phụ của một phép tách **không** có id đó trong `aliases`; nó ghi quan hệ vào `source_refs.r5_split` (mã nguồn/provenance,
  không phải alias).
- `r5_map` là bảng **tường minh** một dòng cho mỗi (id R5, mảnh); app **không bao giờ suy ra** nó từ `aliases` lúc import:

| `disposition` | Ý nghĩa | Dòng |
| --- | --- | --- |
| `replaced` | một id R5 → một điểm | 1 chính |
| `merged` | nhiều id R5 → một điểm | mỗi id một dòng, cùng điểm, đều chính |
| `split_primary` | id R5 tách thành mảnh; đây là mảnh chính | 1 chính |
| `split_secondary` | mảnh khác của cùng id | ≥ 1, không chính |
| `dropped` | không có thay thế | 1, `point_id: null` |

- `build_r5_map` dựng bảng từ danh mục runtime (`r5` = mọi nguồn R5, `aliases` = id mà điểm là chính); id `dropped` lấy từ
  `r5_conversion_map.tsv` (`action = remove`) qua `--with-dropped`. Gói không được mang nửa phép tách: mọi mảnh của một id R5
  phải cùng gói (`r5_map.incomplete`).
- `validate_r5_map` (xuất và kiểm gói cùng chạy): mỗi id có đúng một chính hoặc một `dropped`; không vừa ánh xạ vừa
  `dropped`; `split_secondary` có `split_primary`; điểm chính liệt id trong `aliases`; mảnh phụ **không** liệt, và có trong
  `source_refs.r5_split`; không id nào ở `aliases` của hai điểm (`aliases.duplicate`); mọi alias có dòng trong `r5_map`.

## 5. Băm JSON chuẩn (quy phạm; importer phải tái tạo y hệt)

**Dạng chuẩn**: các byte UTF-8 của giá trị, tuần tự hoá với khoá đối tượng **sắp theo điểm mã Unicode** ở mọi cấp, dấu phân cách
`,` và `:` (không khoảng trắng), **không thoát ASCII** (`ộ` ghi nguyên, không `ộ`), số nguyên là số nguyên (**số thực ở bất kỳ
đâu là lỗi**, kể cả `1.0`), không NaN/Infinity, **không chuẩn hoá Unicode** (NFC và NFD băm khác nhau).

- `content_hash` = SHA-256 (hex thường) của dạng chuẩn của **thân điểm** (`points/<id>.json`).
- `package_hash` = SHA-256 của dạng chuẩn của
  `{export_profile, schema_version, language, functions, points:[{id, version, content_hash}], r5_map}`.
  `source_commit`, `exported_at`, `set_version`, `validator`, `provenance` là dữ liệu audit, **ngoài** hàm băm: cùng nội dung
  xuất lại từ commit khác cho cùng `package_hash`, nên import vẫn idempotent.
- **Golden vector**: `fixtures/export/golden_vector.json` (chữ Việt có dấu, chữ Hán, pinyin có dấu thanh) giữ `value`, đúng
  chuỗi `canonical_json` được băm và `sha256`
  (`cf92888909aadba47cac25209a173fdf1fa9ee0f66dacd7e425b2326be19ee27`). Test khoá cả ba; importer chạy cùng vector.

## 6. Lệnh (không gọi provider)

```bash
python -m grammar_lab.pipeline.cli export-profile [--write]     # suy ra / kiểm schema profile; lệch thì exit 1
python -m grammar_lab.pipeline.cli export-package --lang en --level A1 --out <thư mục mới> --set-version 2026-10-01.en.A1 \
    [--zip] [--with-dropped] [--source-commit <sha>] [--allow-dirty]
python -m grammar_lab.pipeline.cli validate-package <thư mục gói>  # chỉ đọc file của gói
```

`export-package` gom **mọi** vấn đề và không ghi gì nếu còn một vấn đề (exit 2). Từ chối khi:

| Mã | Khi |
| --- | --- |
| `point.not_approved`, `point.flagged`, `point.no_review` | điểm không `approved`, còn cờ, hoặc thiếu review |
| `point.no_content`, `point.not_in_catalog` | chọn một điểm chưa có file hoặc ngoài danh mục |
| `metadata.default_safe` | metadata chưa ai duyệt; **không có override** ở đường xuất |
| `catalog.stale` | `catalog_<lang>.yaml` cũ hoặc thiếu so với canonical v1 |
| `profile.drift` | schema profile lệch schema nội bộ |
| `validate:<mã>`, `profile.schema` | lỗi validate của Grammar Lab trên điểm đã phân giải theo danh mục; vi phạm schema đóng |
| `locale.missing`, `locale.en_placeholder` | thiếu `vi`/`en` ở bất kỳ locale map, hoặc `en` là bản sao của `vi` |
| `ref.unresolved`, `contrasts.asymmetric`, `prereqs cycle` | tham chiếu không có trong gói và không phải điểm đã duyệt; bất đối xứng; vòng |
| `r5_map.*`, `aliases.duplicate` | bảng R5 không hợp lệ (mục 4) |

Sau khi ghi, `validate_package` chạy lại trên chính các file vừa ghi (băm, schema, locale, r5_map, `package_hash`); hỏng thì xoá gói.
Khi xuất, cấu trúc (function, level, contrasts, prereqs, sequence, aliases, source_refs) lấy từ **danh mục**, không từ bản nháp
trên đĩa, đúng như `generate`.

## 7. Phía Orena (không làm ở đây)

Bảng DB, route `/api/admin/grammar/*`, `/api/grammar/v1/*`, tiến độ, đổi seam `/next`, bỏ R5: toàn bộ thuộc
`GRAMMAR_CONTENT_STORE.md` và lane `codex/work`, qua review kiến trúc độc lập. Việc của Grammar Lab còn lại cho bước 3 trong
thứ tự cắt chuyển của đề xuất đó: lô đầu tiên có điểm `approved` thật, với `en` thật. Hiện chưa điểm nào `approved`, nên thực tế
chưa gói nào xuất được; đó là hành vi đúng.

## 8. Hiện trạng vs. bản 28/09

Bỏ: lưu trữ trong repo, provider nạp lúc khởi động, `cli publish`, `index.json`, `r5_redirects.json` đi cùng mã nguồn. Giữ: hình
dạng route (`/points`, `/points/{id}`, `/by-error`), ý tưởng chuyển hướng id R5 (nay là `r5_map` trong DB), nguyên tắc "tiến độ
khoá theo id điểm, không theo version", và "hoàn thành không phải thành thạo". Kiểm kê phụ thuộc R5 vẫn ở `R5_DEPENDENCY_INVENTORY.md`.
