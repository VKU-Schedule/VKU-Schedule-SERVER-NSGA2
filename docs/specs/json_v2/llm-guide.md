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
| `room` | phòng | không | `"A212"`, `"V.A201"`, `"K.A402"` |

Ghi chú:
- **Giữ nguyên đơn vị sinh viên dùng.** "Từ tiết 3" → `start_period`; "sau 10 giờ" → `start_time`. Không tự đổi giờ ↔ tiết, buổi → tiết. Server tự quy đổi.
- **`prefer` buổi/tiết** nghĩa là lớp nằm trọn trong khung đó; **`avoid` buổi/tiết** nghĩa là lớp có chạm vào khung đó.
- Buổi: sáng = tiết 1–5, chiều = tiết 6–10, sáng sớm = 1–2, chiều muộn = 8–10. Không có buổi tối.
- Giờ bắt đầu tiết: 1: 07:30, 2: 08:30, 3: 09:30, 4: 10:30, 5: 11:30, 6: 13:00, 7: 14:00, 8: 15:00, 9: 16:00, 10: 17:00.

## 3. Chỉ số của `limit`

| `limit` | Đo gì | Cận | Câu mẫu → JSON |
|---|---|---|---|
| `subjects_per_day` | số môn trong mỗi ngày có học | `min`, `max` | "tối đa 2 môn mỗi ngày" → `{"limit": "subjects_per_day", "max": 2}` |
| `subjects_per_session` | số môn trong mỗi buổi có học | `min`, `max` | "mỗi buổi tối đa 1 môn" → `{"limit": "subjects_per_session", "max": 1}` |
| `periods_per_day` | tổng số tiết mỗi ngày có học | `min`, `max` | "mỗi ngày không quá 6 tiết" → `{"limit": "periods_per_day", "max": 6}` |
| `gap_periods` | số tiết trống giữa hai lớp liền nhau | `min`, `max` | "nghỉ ít nhất 1 tiết giữa các môn" → `{"limit": "gap_periods", "min": 1}` |
| `consecutive_periods` | số tiết học liên tục | chỉ `max` | "không học quá 4 tiết liền" → `{"limit": "consecutive_periods", "max": 4}` |
| `study_days` | số ngày đi học | `min`, `max` | "lên trường tối đa 3 ngày" → `{"limit": "study_days", "max": 3}` |

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

**Prompt:** "Không học quá 4 tiết liền, nghỉ giữa các môn ít nhất 1 tiết. Điều quan trọng nhất là lên trường khoảng 3 ngày"

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

### E1 — Tránh cuối tuần (mẫu câu; v1 không biểu diễn được)
> "Tôi không muốn học vào cuối tuần như thứ 7"

```json
{"version": "2.0", "constraints": [
  {"avoid": {"day": "cuối tuần"}}
]}
```
- Chuẩn hoá: `day` ∈ {T7, CN}.
- Mỗi lớp vào thứ 7 tính 1 vi phạm, trọng số 3.

### E2 — Môn vào sáng một ngày (2 mẫu câu; v1 không biểu diễn được)
> "Tôi muốn học môn Lập trình Java vào sáng thứ 3 nếu có thể" và "Tôi muốn học môn Lập trình Java vào buổi sáng thứ 3"

```json
{"constraints": [
  {"prefer": {"day": "thứ 3", "session": "sáng"}, "scope": {"course": "Lập trình Java"}}
]}
```
- Lớp Java không đồng thời vào thứ 3 và nằm trọn trong tiết 1–5 → 1 vi phạm, trọng số max(3, 2) = 3.
- "nếu có thể" → `normal`.

### E3 — Môn nhưng không phải sáng một ngày (mẫu câu; v1 không biểu diễn được)
> "Tôi muốn học môn Mạng máy tính nhưng không phải sáng thứ 4"

```json
{"constraints": [
  {"avoid": {"day": "thứ 4", "session": "sáng"}, "scope": {"course": "Mạng máy tính"}}
]}
```
- Lớp Mạng máy tính vào thứ 4 và có tiết thuộc khoảng 1–5 → 1 vi phạm.

### E4 — Không học môn vào một ngày (mẫu câu; v1 không biểu diễn được)
> "Tôi không muốn học môn Chủ nghĩa xã hội khoa học vào thứ 6"

```json
{"constraints": [
  {"avoid": {"day": "thứ 6"}, "scope": {"course": "Chủ nghĩa xã hội khoa học"}}
]}
```

### E5 — Môn ở một khu (mẫu câu; v1 không biểu diễn được)
> "Tôi ưu tiên học môn Cấu trúc dữ liệu và giải thuật ở khu V"

```json
{"constraints": [
  {"prefer": {"area": "V"}, "scope": {"course": "Cấu trúc dữ liệu và giải thuật"}}
]}
```
- Lớp có khu không xác định (ví dụ `Chưa xếp phòng`) bị loại khỏi phạm vi, nên không bị phạt.

### E6 — Khu theo buổi (mẫu câu; v1 không biểu diễn được)
> "Tôi thích học ở khu vực K vào buổi chiều"

```json
{"constraints": [
  {"prefer": {"area": "K"}, "scope": {"session": "chiều"}}
]}
```
- Phạm vi là các lớp nằm trọn trong tiết 6–10. Lớp buổi sáng không chịu ràng buộc này.

### E7 — Môn vào một ngày, có nghỉ giữa giờ (mẫu câu; v1 không biểu diễn được)
> "Tôi muốn học môn Lập trình Java vào thứ 5 và có nghỉ giữa giờ"

```json
{"constraints": [
  {"prefer": {"day": "thứ 5"}, "scope": {"course": "Lập trình Java"}},
  {"limit": "gap_periods", "min": 1, "scope": {"day": "thứ 5"}}
]}
```
- "Nghỉ giữa giờ" được hiểu là có ít nhất 1 tiết trống giữa hai lớp liền nhau trong thứ 5.

### E8 — Môn sáng một ngày, tránh chiều (mẫu câu; v1 không biểu diễn được)
> "Tôi muốn học môn Cấu trúc dữ liệu và giải thuật sáng thứ 2, tránh chiều"

```json
{"constraints": [
  {"prefer": {"day": "thứ 2", "session": "sáng"}, "scope": {"course": "Cấu trúc dữ liệu và giải thuật"}},
  {"avoid": {"session": "chiều"}, "scope": {"course": "Cấu trúc dữ liệu và giải thuật"}}
]}
```
- Nhờ ràng buộc thứ hai, lớp sáng thứ 4 (phạt 3) tốt hơn lớp chiều thứ 2 (phạt 3 + 2 = 5).
- Hai ràng buộc khác nhóm (`{day, session}` và `{session}`), nên không áp dụng quy tắc ngoại lệ.

### E9 — Ưu tiên có điều kiện (mẫu câu; v1 không biểu diễn được)
> "Tôi thích học buổi sáng nếu lớp ở phòng A212"

```json
{"constraints": [
  {"prefer": {"session": "sáng"}, "scope": {"room": "A212"}}
]}
```
- Chỉ các lớp ở phòng A212 bị yêu cầu học buổi sáng.

### E10 — Điều kiện gộp (mẫu câu)
> "Tôi muốn học Lập trình Java vào sáng thứ 6 nếu có thầy Trần Đình Sơn"

```json
{"constraints": [
  {"prefer": {"day": "thứ 6", "session": "sáng", "teacher": "Trần Đình Sơn"}, "scope": {"course": "Lập trình Java"}}
]}
```
- Điều kiện AND: lớp Java phải đồng thời vào sáng thứ 6 và do thầy Sơn dạy. Trọng số max(3, 2, 4) = 4.

### E11 — Bắt buộc theo giờ (mẫu câu)
> "Tôi chỉ học nếu lớp bắt đầu sau 10 giờ sáng"

```json
{"constraints": [
  {"prefer": {"start_time": {"min": "10:00"}}, "level": "must"}
]}
```
- Chuẩn hoá: giờ bắt đầu ≥ 600 phút, tức lớp bắt đầu từ tiết 4 (10:30) trở đi.
- "chỉ" → `must`.

### E12 — Tiết bắt đầu theo ngày (mẫu câu)
> "Tôi muốn bắt đầu học từ tiết 3 trở đi vào thứ 4"

```json
{"constraints": [
  {"prefer": {"start_period": {"min": 3}}, "scope": {"day": "thứ 4"}}
]}
```
- Chỉ phạt lớp thứ 4 bắt đầu trước tiết 3. Không khuyến khích dồn thêm lớp vào thứ 4 (khác v1).

### E13 — Tránh khoảng tiết (mẫu câu)
> "Tôi muốn tránh các tiết học từ tiết 1 đến tiết 2"

```json
{"constraints": [
  {"avoid": {"periods": {"min": 1, "max": 2}}}
]}
```
- `avoid` dùng quy tắc có giao: lớp tiết [1, 2, 3] bị phạt (v1 không phạt lớp này).

### E14 — Tiết kết thúc (bổ sung)
> "Buổi sáng tôi muốn học xong trước tiết 5"

```json
{"constraints": [
  {"prefer": {"end_period": {"max": 4}}, "scope": {"session": "sáng"}}
]}
```

### E15 — Giờ kết thúc (bổ sung)
> "Tôi muốn về trước 16 giờ"

```json
{"constraints": [
  {"prefer": {"end_time": {"max": "16:00"}}}
]}
```
- Theo bảng 7.1: lớp kết thúc ở tiết 8 (15:50) thoả; lớp kết thúc ở tiết 9 (16:50) vi phạm.

### E16 — Buổi con, kèm lý do (mẫu câu)
> "Tôi tránh học chiều muộn thứ 5 vì tôi có lịch làm thêm"

```json
{"constraints": [
  {"avoid": {"session": "chiều muộn"}, "scope": {"day": "thứ 5"}}
]}
```
- "chiều muộn" → tiết 8–10. Lý do "vì tôi có lịch làm thêm" bị bỏ qua.

### E17 — Thời lượng lớp (bổ sung)
> "Tôi không thích các lớp học từ 4 tiết trở lên"

```json
{"constraints": [
  {"avoid": {"duration": {"min": 4}}}
]}
```

### E18 — Giảng viên theo môn (mẫu câu)
> "Tôi muốn học môn Automat và ngôn ngữ hình thức với cô Mai Nga, tránh thầy Sơn"

```json
{"constraints": [
  {"prefer": {"teacher": "Mai Nga"}, "scope": {"course": "Automat và ngôn ngữ hình thức"}},
  {"avoid": {"teacher": "Sơn"}, "scope": {"course": "Automat và ngôn ngữ hình thức"}}
]}
```
- Với dữ liệu mẫu trong `app/constant/constant_input_test.py`: "Mai Nga" khớp `ThS.Dương Thị Mai Nga`; "Sơn" khớp `ThS.Trần Đình Sơn`.
- Nếu có nhiều giảng viên tên Sơn dạy môn này, dùng tất cả và thêm warning.
- Hai ràng buộc cùng nhóm và cùng phạm vi nhưng khác giá trị, nên không phải mâu thuẫn.

### E19 — Nhóm lớp (dạng câu trong `generated_sentences.txt`)
> "Môn Tiếng Anh chuyên ngành 2 nhóm 13 hoặc 14 luôn thu hút tôi"

```json
{"constraints": [
  {"prefer": {"class_group": [13, 14]}, "scope": {"course": "Tiếng Anh chuyên ngành 2"}}
]}
```

### E20 — Ngôn ngữ (bổ sung)
> "Tôi muốn học các lớp dạy bằng tiếng Anh"

```json
{"constraints": [
  {"prefer": {"language": "tiếng Anh"}}
]}
```

### E21 — Phòng có tiền tố khu (mẫu câu)
> "Tôi không thích học ở phòng V.A201 vào thứ 3 vì hơi ồn"

```json
{"constraints": [
  {"avoid": {"room": "V.A201"}, "scope": {"day": "thứ 3"}}
]}
```
- Chuẩn hoá: điều kiện trở thành khu `V` AND phòng `A201`.

### E22 — Số môn mỗi ngày, nhiều ngày (mẫu câu)
> "Tôi chỉ muốn học tối đa 2 môn mỗi ngày thứ 2 và ngày thứ 4"

```json
{"constraints": [
  {"limit": "subjects_per_day", "max": 2, "scope": {"day": ["thứ 2", "thứ 4"]}, "level": "must"}
]}
```

### E23 — Số môn trong một buổi (mẫu câu)
> "Tôi chỉ học tối đa 1 môn vào chiều thứ 6"

```json
{"constraints": [
  {"limit": "subjects_per_session", "max": 1, "scope": {"day": "thứ 6", "session": "chiều"}, "level": "must"}
]}
```

### E24 — Khoảng nghỉ (mẫu câu)
> "Tôi muốn nghỉ giữa các môn ít nhất 1 tiết nếu có thể"

```json
{"constraints": [
  {"limit": "gap_periods", "min": 1}
]}
```
- Hai lớp liền nhau [1, 2] và [3, 4] cùng ngày có khoảng trống 0 tiết → 1 vi phạm.

### E25 — Học liên tục (bổ sung)
> "Tôi không muốn học quá 4 tiết liên tục"

```json
{"constraints": [
  {"limit": "consecutive_periods", "max": 4}
]}
```
- Lớp [1, 2, 3] và lớp [4, 5] tạo thành khối 5 tiết → 1 vi phạm.

### E26 — Số ngày đi học, mức cao (bổ sung)
> "Điều quan trọng nhất với tôi là dồn lịch vào khoảng 3 ngày mỗi tuần"

```json
{"constraints": [
  {"limit": "study_days", "max": 3, "level": "high"}
]}
```
- Trọng số 2 × 2 = 4.

### E27 — Số tiết mỗi ngày (bổ sung)
> "Mỗi ngày tôi không muốn học quá 6 tiết"

```json
{"constraints": [
  {"limit": "periods_per_day", "max": 6}
]}
```

### E28 — Đổi khu không được hỗ trợ (bổ sung)
> "Tôi không muốn phải chạy từ khu K sang khu V giữa hai lớp liền nhau"

```json
{"constraints": [], "unsupported": ["không muốn phải chạy từ khu K sang khu V giữa hai lớp liền nhau"]}
```
- Không có chỉ số đổi khu (câu hỏi Q4: không phải vấn đề thật với sinh viên), nên cả câu vào `unsupported`.

### E29 — "Chỉ … nếu không còn lựa chọn" là tránh mềm (mẫu câu)
> "Tôi chỉ học chiều thứ 2 nếu không còn lựa chọn nào khác"

```json
{"constraints": [
  {"avoid": {"session": "chiều"}, "scope": {"day": "thứ 2"}}
]}
```
- Mức `normal`: đây là ngoại lệ của từ khoá "chỉ" (mục 14.1).

### E30 — Ví dụ Swagger của API hiện tại
> "Tôi chỉ học nếu lớp bắt đầu sau 10 giờ sáng. Tôi thích lịch học trải đều trong tuần"

```json
{"constraints": [
  {"prefer": {"start_time": {"min": "10:00"}}, "level": "must"},
  {"limit": "subjects_per_day", "max": 1}
]}
```
- "Trải đều" không kèm số → `subjects_per_day` với `max: 1` (mục 5).

### E31 — Quy tắc chung và ngoại lệ (bổ sung)
> "Tôi thích học buổi sáng, riêng thứ 2 thì muốn học buổi chiều"

```json
{"constraints": [
  {"prefer": {"session": "sáng"}},
  {"prefer": {"session": "chiều"}, "scope": {"day": "thứ 2"}}
]}
```
- Theo quy tắc ngoại lệ (6.4), ràng buộc 0 nhận `exclude = [{day: T2}]`.

### E32 — Có phần không hỗ trợ (bổ sung)
> "Tôi muốn học cùng lớp với bạn Nam, và không học thứ 7"

```json
{"constraints": [
  {"avoid": {"day": "thứ 7"}}
], "unsupported": ["muốn học cùng lớp với bạn Nam"]}
```


## 7. Lỗi thường gặp

| Sai | Đúng | Vì sao |
|---|---|---|
| `{"prefer": {"day": "thứ 2"}, "avoid": {"day": "thứ 7"}}` | hai ràng buộc riêng | mỗi ràng buộc chỉ có một trong `prefer` / `avoid` / `limit` |
| `{"prefer": {"periods": [1,2,3,4,5]}}` cho "thích học sáng" | `{"prefer": {"session": "sáng"}}` | giữ đơn vị sinh viên dùng |
| `{"prefer": {"start_period": {"min": 4}}}` cho "sau 10 giờ" | `{"prefer": {"start_time": {"min": "10:00"}}}` | không tự đổi giờ sang tiết |
| `{"avoid": {"day": "thứ 7"}, "max": 0}` | bỏ `max` | `min` / `max` chỉ đi với `limit` |
| `{"limit": "subjects_per_day", "max": 2, "scope": null, "level": null}` | bỏ các key `null` | chỉ ghi điều sinh viên nói |
| `{"prefer": {"teacher": "Sơn", "course": "Java"}}` | `{"prefer": {"teacher": "Sơn"}, "scope": {"course": "Java"}}` | tên môn nằm trong `scope` (server vẫn tự sửa, nhưng nên viết đúng) |
