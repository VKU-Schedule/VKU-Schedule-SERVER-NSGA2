# JSON Structure v2 — Hướng dẫn cho module LLM

> Tài liệu này thay cho `data/docs-feature.md` (v1). Dùng làm system prompt / tài liệu tạo dữ liệu huấn luyện cho model chuyển câu yêu cầu của sinh viên sang JSON.
> - Schema máy đọc: [`schema.json`](schema.json) (có `$ref`) và [`schema.inline.json`](schema.inline.json) (không `$ref`, dùng cho structured output).
> - Ngữ nghĩa chi tiết và cách server chấm điểm: [`design.md`](design.md).
> - Kiểm tra output: `POST /api/preferences/validate` với `{"courses": [...], "preferences": <JSON>}`.

## 1. Cấu trúc

```
{
  "version": "2.0",                 // tuỳ chọn, mặc định "2.0"
  "constraints": [                  // bắt buộc; mỗi ý của sinh viên là một phần tử
    {
      // Đúng MỘT trong ba key sau:
      "prefer": Filter,             // muốn các lớp thoả bộ lọc này
      "avoid":  Filter,             // muốn tránh các lớp thoả bộ lọc này
      "limit":  "<tên chỉ số>",     // giới hạn hình dạng lịch, đi kèm "min" và/hoặc "max"
      "min": number, "max": number, // chỉ dùng với "limit", số nguyên ≥ 0, tính cả biên

      "scope": Filter,              // tuỳ chọn: ràng buộc áp dụng cho lớp nào; thiếu = mọi lớp
      "level": "must" | "high" | "normal"   // tuỳ chọn, mặc định "normal"
    }
  ],
  "unsupported": [string]           // tuỳ chọn: chép nguyên văn ý không biểu diễn được
}
```

**Filter** là object, key là tên thuộc tính (mục 2), value là một trong ba dạng:

| Dạng | Ví dụ | Nghĩa |
|---|---|---|
| Đơn | `"day": "thứ 2"` | bằng giá trị này |
| List | `"day": ["thứ 2", "thứ 4"]` | bằng một trong các giá trị (HOẶC) |
| Khoảng | `"start_period": {"min": 3}` | nằm trong khoảng, tính cả biên; cần ít nhất một trong `min`, `max` |

Nhiều key trong cùng một Filter kết hợp bằng **VÀ**: `{"day": "thứ 6", "session": "sáng"}` là "sáng thứ 6".

## 2. Thuộc tính của Filter

| Key | Giá trị LLM ghi | Khoảng? | Ví dụ |
|---|---|---|---|
| `course` | tên môn, **chỉ đặt trong `scope`** | không | `"scope": {"course": "Lập trình Java"}` |
| `class_group` | số nhóm lớp | không | `2`, `[13, 14]`, `"nhóm 2"` |
| `teacher` | tên giảng viên như sinh viên nói | không | `"Mai Nga"`, `"thầy Sơn"` |
| `language` | ngôn ngữ giảng dạy | không | `"tiếng Anh"`, `"tiếng Việt"` |
| `day` | thứ | không | `"thứ 2"` … `"thứ 7"`, `"chủ nhật"`, `"cuối tuần"`, `"ngày thường"` |
| `session` | buổi | không | `"sáng"`, `"chiều"`, `"sáng sớm"`, `"chiều muộn"` |
| `periods` | tập tiết | có | `[1, 2]`, `"1-3"`, `{"min": 1, "max": 2}` |
| `start_period` | tiết bắt đầu của lớp | có | `{"min": 3}` = "từ tiết 3 trở đi" |
| `end_period` | tiết kết thúc của lớp | có | `{"max": 4}` = "xong trước/đến tiết 4" |
| `start_time` | giờ bắt đầu của lớp | có | `{"min": "10:00"}` = "sau 10 giờ" |
| `end_time` | giờ kết thúc của lớp | có | `{"max": "16:00"}` = "về trước 16 giờ" |
| `duration` | số tiết của một buổi học | có | `{"min": 4}` = "lớp từ 4 tiết trở lên" |
| `area` | khu | không | `"K"`, `"V"` |
| `room` | phòng | không | `"A212"`, `"V.A201"` |

Ghi chú:
- **Giữ nguyên đơn vị sinh viên dùng.** "Từ tiết 3" → `start_period`; "sau 10 giờ" → `start_time`. Không tự đổi giờ ↔ tiết, buổi → tiết. Server tự quy đổi.
- **`prefer` buổi/tiết** nghĩa là lớp nằm trọn trong khung đó; **`avoid` buổi/tiết** nghĩa là lớp có chạm vào khung đó.
- Buổi: sáng = tiết 1–5, chiều = tiết 6–10, sáng sớm = 1–2, chiều muộn = 8–10. Không có buổi tối.
- Giờ bắt đầu tiết: 1: 07:30, 2: 08:30, 3: 09:30, 4: 10:30, 5: 11:30, 6: 13:00, 7: 14:00, 8: 15:00, 9: 16:00, 10: 17:00.

## 3. Chỉ số của `limit`

| `limit` | Đo gì | Cận | Câu mẫu → JSON |
|---|---|---|---|
| `subjects_per_day` | số môn trong mỗi ngày có học | `min`, `max` | "tối đa 2 môn mỗi ngày" → `{"limit": "subjects_per_day", "max": 2}` |
| `subjects_per_session` | số môn trong mỗi buổi có học | `min`, `max` | "mỗi buổi chỉ 1 môn" → `{"limit": "subjects_per_session", "max": 1}` |
| `periods_per_day` | tổng số tiết mỗi ngày có học | `min`, `max` | "mỗi ngày không quá 6 tiết" → `{"limit": "periods_per_day", "max": 6}` |
| `gap_periods` | số tiết trống giữa hai lớp liền nhau | `min`, `max` | "nghỉ ít nhất 1 tiết giữa các môn" → `{"limit": "gap_periods", "min": 1}` |
| `consecutive_periods` | số tiết học liên tục | chỉ `max` | "không học quá 4 tiết liền" → `{"limit": "consecutive_periods", "max": 4}` |
| `study_days` | số ngày đi học | `min`, `max` | "chỉ lên trường 3 ngày" → `{"limit": "study_days", "max": 3}` |

Không kèm con số:
- "Dồn lịch vào ít ngày nhất" → `{"limit": "study_days", "max": 1}`
- "Trải đều lịch trong tuần" → `{"limit": "subjects_per_day", "max": 1}`

## 4. Mức độ (`level`)

| Mức | Từ khoá gợi ý |
|---|---|
| `must` | "chỉ", "bắt buộc", "phải", "không thể", "nhất định", "tuyệt đối" |
| `high` | "rất muốn", "rất cần", "quan trọng nhất", "ưu tiên hàng đầu" |
| `normal` (mặc định, không cần ghi) | "thích", "muốn", "ưu tiên", "nếu được", "nếu có thể" |

Ngoại lệ: "chỉ … nếu không còn lựa chọn" là `normal`.

## 5. Quy tắc viết

1. **Mỗi ý → một ràng buộc.** Một ý có nhiều điều kiện cùng lúc ("sáng thứ 6 với thầy Sơn") → một Filter nhiều key.
2. **Chỉ ghi điều sinh viên nói.** Không sinh `null`, mảng rỗng, hay ràng buộc mặc định. Câu không có yêu cầu nào → `{"constraints": []}`.
3. **Chọn loại:** thích / muốn / ưu tiên → `prefer`; không thích / tránh / không muốn → `avoid`; giới hạn số lượng ("tối đa", "ít nhất", "không quá") → `limit`.
4. **Phạm vi và điều kiện:**
   - "áp dụng cho lớp nào?" (môn X, thứ 2, buổi chiều, lớp ở phòng P) → `scope`;
   - "muốn hoặc tránh điều gì?" → `prefer` / `avoid`;
   - tên môn luôn nằm trong `scope`.
5. **Ngoại lệ** ("riêng", "trừ", "ngoại trừ"): viết ràng buộc chung như bình thường, rồi thêm một ràng buộc cho phần ngoại lệ với `scope` hẹp hơn. Server tự hiểu phần hẹp hơn thắng.
6. **Lý do** ("vì gần nhà", "để đi làm thêm") không phải ràng buộc: bỏ qua.
7. **Ý không biểu diễn được** (học cùng bạn, đổi khu giữa hai lớp…): chép nguyên văn vào `unsupported`.
8. **Tên riêng:** nếu prompt có danh sách môn đã chọn và giảng viên, dùng đúng tên trong danh sách.

## 6. Ví dụ

**Prompt:** "Tôi không muốn học vào cuối tuần"

```json
{"constraints": [
  {"avoid": {"day": "cuối tuần"}}
]}
```

**Prompt:** "Tôi muốn học môn Lập trình Java vào sáng thứ 3 nếu có thể"

```json
{"constraints": [
  {"prefer": {"day": "thứ 3", "session": "sáng"}, "scope": {"course": "Lập trình Java"}}
]}
```

**Prompt:** "Tôi chỉ học nếu lớp bắt đầu sau 10 giờ sáng. Tôi thích lịch học trải đều trong tuần"

```json
{"constraints": [
  {"prefer": {"start_time": {"min": "10:00"}}, "level": "must"},
  {"limit": "subjects_per_day", "max": 1}
]}
```

**Prompt:** "Tôi thích học ở khu K vào buổi chiều, và không thích phòng V.A201 vào thứ 3 vì hơi ồn"

```json
{"constraints": [
  {"prefer": {"area": "K"}, "scope": {"session": "chiều"}},
  {"avoid": {"room": "V.A201"}, "scope": {"day": "thứ 3"}}
]}
```

**Prompt:** "Môn Tiếng Anh chuyên ngành 2 tôi muốn nhóm 13 hoặc 14, ưu tiên lớp dạy bằng tiếng Anh"

```json
{"constraints": [
  {"prefer": {"class_group": [13, 14]}, "scope": {"course": "Tiếng Anh chuyên ngành 2"}},
  {"prefer": {"language": "tiếng Anh"}}
]}
```

**Prompt:** "Không học quá 4 tiết liền, nghỉ giữa các môn ít nhất 1 tiết. Điều quan trọng nhất là chỉ lên trường khoảng 3 ngày"

```json
{"constraints": [
  {"limit": "consecutive_periods", "max": 4},
  {"limit": "gap_periods", "min": 1},
  {"limit": "study_days", "max": 3, "level": "high"}
]}
```

**Prompt (đầy đủ):** "Tôi muốn học Automat với cô Mai Nga, tránh thầy Sơn. Tôi thích học buổi sáng, riêng thứ 2 thì học chiều. Tuyệt đối không học thứ 7. Mỗi ngày tối đa 2 môn, và chỉ học nếu lớp bắt đầu sau 8 giờ. Tôi muốn học cùng lớp với bạn Nam."

```json
{
  "version": "2.0",
  "constraints": [
    {"prefer": {"teacher": "Mai Nga"}, "scope": {"course": "Automat và ngôn ngữ hình thức"}},
    {"avoid": {"teacher": "Sơn"}, "scope": {"course": "Automat và ngôn ngữ hình thức"}},
    {"prefer": {"session": "sáng"}},
    {"prefer": {"session": "chiều"}, "scope": {"day": "thứ 2"}},
    {"avoid": {"day": "thứ 7"}, "level": "must"},
    {"limit": "subjects_per_day", "max": 2},
    {"prefer": {"start_time": {"min": "8:00"}}, "level": "must"}
  ],
  "unsupported": ["muốn học cùng lớp với bạn Nam"]
}
```

Thêm 32 ví dụ có ghi chú ở [design.md mục 13](design.md#13-ví-dụ).

## 7. Lỗi thường gặp

| Sai | Đúng | Vì sao |
|---|---|---|
| `{"prefer": {"day": "thứ 2"}, "avoid": {"day": "thứ 7"}}` | hai ràng buộc riêng | mỗi ràng buộc chỉ có một trong `prefer` / `avoid` / `limit` |
| `{"prefer": {"periods": [1,2,3,4,5]}}` cho "thích học sáng" | `{"prefer": {"session": "sáng"}}` | giữ đơn vị sinh viên dùng |
| `{"prefer": {"start_period": {"min": 4}}}` cho "sau 10 giờ" | `{"prefer": {"start_time": {"min": "10:00"}}}` | không tự đổi giờ sang tiết |
| `{"avoid": {"day": "thứ 7"}, "max": 0}` | bỏ `max` | `min` / `max` chỉ đi với `limit` |
| `{"limit": "subjects_per_day", "max": 2, "scope": null, "level": null}` | bỏ các key `null` | chỉ ghi điều sinh viên nói |
| `{"prefer": {"teacher": "Sơn", "course": "Java"}}` | `{"prefer": {"teacher": "Sơn"}, "scope": {"course": "Java"}}` | tên môn nằm trong `scope` (server vẫn tự sửa, nhưng nên viết đúng) |
