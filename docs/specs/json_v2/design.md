# Phần A — JSON Structure v2: Thiết kế

> Tài liệu 2/3 của spec Phần A. Tài liệu này trả lời: **làm thế nào**.
> - Yêu cầu (R1–R13): [requirements.md](requirements.md)
> - Các bước: [tasks.md](tasks.md)
>
> Các giá trị ghi "giả định" phụ thuộc vào câu hỏi mở trong requirements.md mục 9.

## 1. Tổng quan

```
Module LLM ──► Tài liệu ưu tiên v2 (JSON)
                    │
                    ▼
        [1] Validate (Pydantic, theo từng ràng buộc) ─────────► unsupported (lỗi cấu trúc)
                    │
                    ▼
        [2] Chuẩn hoá (theo môn đã chọn + lớp ứng viên) ──────► unsupported, warnings
                    │
                    ▼
        Ràng buộc đã chuẩn hoá (ID, trọng số, phạm vi loại trừ)
                    │
                    ▼
        [3] Bộ giải (Phần B) ──► Response v2: ~5 lịch + giải thích
```

Phần A làm bước [1], bước [2], và định nghĩa ngữ nghĩa mà bước [3] phải tuân theo (mục 6).

## 2. Quyết định thiết kế

| # | Quyết định | Lý do | Yêu cầu |
|---|---|---|---|
| D1 | Tài liệu là danh sách phẳng các ràng buộc nguyên tử | Ngắn; mỗi ý độc lập; đếm và đánh giá được theo từng ràng buộc | R1, R3 |
| D2 | Loại ràng buộc thể hiện bằng key: `prefer`, `avoid`, `limit` | Ngắn hơn một field `type` riêng; đọc như câu, ví dụ "avoid day thứ 7" | R3 |
| D3 | Phạm vi là một bộ lọc dùng chung, đặt ở key `scope` | Thay cho cặp `defaults` / `periods`; mọi tổ hợp phạm vi đều viết được. Không dùng tên `for` vì đó là từ khoá Python và kém rõ nghĩa | R1 |
| D4 | Trong bộ lọc: các key là AND, list là OR, `{min, max}` là khoảng đóng | Ba quy tắc đủ cho mọi tổ hợp và dễ học | R2 |
| D5 | Polarity chỉ nằm ở `prefer` / `avoid`; `limit` dùng `min` / `max` | Bỏ `like` và `up_or_down` của v1 | R2 |
| D6 | `level` có ba mức: `must` / `high` / `normal` | LLM phân biệt được ba mức qua từ khoá; trọng số dạng số do server lo | R4 |
| D7 | Với tiết/buổi: `prefer` = nằm trọn, `avoid` = có giao; trong `scope` = nằm trọn | Đúng ý "muốn học trong khung giờ" và "tránh khung giờ" | R5 |
| D8 | Chỉ phạt (≥ 0), không thưởng | 0 = thoả hết; thuật toán không có lợi khi dồn lớp vào một phạm vi để lấy thưởng; giải thích được | R5, R9 |
| D9 | `limit` chỉ đo trên các đơn vị có học | Ngày không có lớp không bị phạt vì "ít môn" | R5 |
| D10 | Ràng buộc cụ thể hơn thắng trong phần giao | Giữ ý đồ "periods ghi đè defaults" của v1, nhưng tổng quát cho mọi loại phạm vi | R13 |
| D11 | Lớp có giá trị không xác định bị loại khỏi phạm vi | Không phạt oan, không gây lỗi | R12 |
| D12 | `must` được tối ưu theo thứ bậc: vẫn trả lịch, kèm `infeasible`. Trùng lịch luôn bị cấm | Sinh viên vẫn có lịch để xem và biết ràng buộc nào không thể thoả | R4, R9 |
| D13 | LLM sinh giá trị bề mặt; server chuẩn hoá tất định | Bớt việc tính toán cho LLM; đúng và kiểm thử được | R6 |
| D14 | Validate theo từng ràng buộc; lỗi → `unsupported` kèm lý do | Không mất thông tin âm thầm | R7 |
| D15 | JSON Schema phẳng (không `oneOf`), có thêm bản không `$ref` | Tương thích structured output của nhiều LLM | R3, R8 |
| D16 | ID ràng buộc do server gán (theo thứ tự trong mảng); `version` mặc định `"2.0"` | LLM sinh ít hơn | R9, R11 |
| D17 | Mọi chỉ số được định nghĩa sao cho tuyến tính hoá được | So sánh công bằng giữa thuật toán chính xác và metaheuristic (Phần B) | R5 |
| D18 | Trọng số = trọng số lớn nhất của các thuộc tính trong điều kiện và `scope` (trừ `course`), nhân 2 nếu `high` | Quy tắc đơn giản; chuyển thuộc tính qua lại giữa điều kiện và phạm vi không làm đổi điểm | R2, R4 |

## 3. Cấu trúc tài liệu ưu tiên (input)

### 3.1 Top-level

```json
{
  "version": "2.0",
  "constraints": [],
  "unsupported": []
}
```

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `version` | string | Không, mặc định `"2.0"` | Phiên bản cấu trúc |
| `constraints` | mảng `Constraint` | Có (được phép rỗng) | Các ràng buộc |
| `unsupported` | mảng string | Không | Nguyên văn các đoạn mà LLM không ánh xạ được |

### 3.2 `Constraint`

Mỗi ràng buộc có **đúng một** trong ba key `prefer`, `avoid`, `limit`.

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `prefer` | `Filter` | Đúng một trong `prefer` / `avoid` / `limit` | Các lớp trong phạm vi **nên thoả** bộ lọc |
| `avoid` | `Filter` | Đúng một trong `prefer` / `avoid` / `limit` | Các lớp trong phạm vi **nên tránh** bộ lọc |
| `limit` | tên chỉ số (mục 5) | Đúng một trong `prefer` / `avoid` / `limit` | Chỉ số hình dạng lịch cần giới hạn |
| `min` | số nguyên ≥ 0 | Chỉ đi với `limit`; cần ít nhất một trong `min` / `max` | Cận dưới, tính cả biên |
| `max` | số nguyên ≥ 0 | Chỉ đi với `limit`; cần ít nhất một trong `min` / `max` | Cận trên, tính cả biên |
| `scope` | `Filter` | Không; thiếu nghĩa là mọi lớp | Ràng buộc áp dụng cho những lớp nào |
| `level` | `"must"` / `"high"` / `"normal"` | Không, mặc định `"normal"` | Mức độ |

Ví dụ:

```json
{"avoid": {"day": "thứ 7", "session": "sáng"}, "level": "must"}
```
```json
{"prefer": {"teacher": "Mai Nga"}, "scope": {"course": "Automat và ngôn ngữ hình thức"}}
```
```json
{"limit": "subjects_per_day", "max": 2, "scope": {"day": ["thứ 2", "thứ 4"]}}
```

### 3.3 `Filter` và các dạng giá trị

`Filter` là một object. Key là tên thuộc tính (mục 4). Value có một trong ba dạng:

| Dạng | Ví dụ | Nghĩa |
|---|---|---|
| Đơn | `"day": "thứ 2"` | Bằng giá trị này |
| List | `"day": ["thứ 2", "thứ 4"]` | Bằng một trong các giá trị (OR) |
| Khoảng | `"start_period": {"min": 3}` | Nằm trong khoảng đóng; cần ít nhất một trong `min`, `max` |

- Các key trong cùng một bộ lọc kết hợp bằng AND.
- Khoảng chỉ dùng cho các thuộc tính có thứ tự (cột "Khoảng" ở mục 4).
- Bộ lọc không được rỗng.

## 4. Thuộc tính lọc

| Thuộc tính | LLM sinh (giá trị bề mặt) | Giá trị chuẩn | Lấy từ lớp | Khoảng | Khớp trong `prefer` / `scope` | Khớp trong `avoid` |
|---|---|---|---|---|---|---|
| `course` | tên môn như sinh viên nói | tên môn trong danh sách đã chọn | `course_name` | — | bằng | bằng |
| `class_group` | số nhóm: `2`, `"nhóm 2"` | số nguyên | `class_index` | — | bằng | bằng |
| `teacher` | tên như sinh viên nói: `"thầy Sơn"`, `"Mai Nga"` | tập tên giảng viên thật | `teacher` | — | thuộc tập | thuộc tập |
| `language` | `"tiếng Anh"`, `"tiếng Việt"` | `Tiếng Anh` / `Tiếng Việt` | `language` | — | bằng | bằng |
| `day` | `"thứ 2"` … `"thứ 7"`, `"chủ nhật"`, `"cuối tuần"` | tập mã `T2` … `T7`, `CN` | `day` | — | thuộc tập | thuộc tập |
| `session` | `"sáng"`, `"chiều"`, `"sáng sớm"`, `"chiều muộn"` | tập tiết (mục 7.2) | `periods` | — | tiết của lớp nằm trọn trong tập | lớp có ít nhất một tiết thuộc tập |
| `periods` | list tiết `[1, 2]` hoặc khoảng `{"min": 1, "max": 2}` | tập tiết | `periods` | có | nằm trọn | có giao |
| `start_period` | số tiết hoặc khoảng | khoảng tiết | tiết đầu của lớp | có | trong khoảng | trong khoảng |
| `end_period` | số tiết hoặc khoảng | khoảng tiết | tiết cuối của lớp | có | trong khoảng | trong khoảng |
| `start_time` | `"10:00"` hoặc khoảng | phút trong ngày | giờ bắt đầu của tiết đầu | có | trong khoảng | trong khoảng |
| `end_time` | `"16:00"` hoặc khoảng | phút trong ngày | giờ kết thúc của tiết cuối | có | trong khoảng | trong khoảng |
| `duration` | số tiết hoặc khoảng | khoảng | số tiết của lớp | có | trong khoảng | trong khoảng |
| `area` | `"K"`, `"khu V"` | `K` / `V` | `area` | — | bằng | bằng |
| `room` | `"A212"`, `"V.A201"` | mã phòng (kèm khu nếu có tiền tố) | `room` (và `area`) | — | bằng | bằng |

Ghi chú:
- **`course`** chỉ có nghĩa trong `scope`. Nếu `course` xuất hiện trong `prefer` / `avoid`, server chuyển nó sang `scope` (R2).
- **`periods` và `session`** là thuộc tính dạng tập: list nghĩa là một tập tiết, không phải các lựa chọn. List nhiều buổi, ví dụ `["sáng sớm", "chiều muộn"]`, là hợp của các tập tiết.
- **Giờ và tiết:** LLM dùng đúng đơn vị mà sinh viên nói. "Từ tiết 3" → `start_period`; "sau 10 giờ" → `start_time`. Một bộ lọc có cả hai vẫn hợp lệ.

## 5. Chỉ số cho `limit`

| Chỉ số | Đơn vị đo | Giá trị đo trên mỗi đơn vị | Cận cho phép | Ví dụ câu → ràng buộc |
|---|---|---|---|---|
| `subjects_per_day` | Mỗi ngày có ít nhất một lớp trong phạm vi | Số lớp trong ngày | `min`, `max` | "tối đa 2 môn mỗi ngày" → `max: 2` |
| `subjects_per_session` | Mỗi cặp (ngày, buổi) có lớp. Buổi tính theo tiết bắt đầu: ≤ 5 là sáng, ≥ 6 là chiều | Số lớp trong buổi | `min`, `max` | "mỗi buổi chỉ 1 môn" → `max: 1` |
| `periods_per_day` | Mỗi ngày có lớp | Tổng số tiết | `min`, `max` | "mỗi ngày không quá 6 tiết" → `max: 6` |
| `gap_periods` | Mỗi cặp lớp liền nhau trong cùng ngày (xếp theo tiết bắt đầu) | Số tiết trống giữa hai lớp | `min`, `max` | "nghỉ ít nhất 1 tiết giữa các môn" → `min: 1` |
| `consecutive_periods` | Mỗi khối học liên tục trong ngày (các lớp nối nhau, không có tiết trống) | Số tiết của khối | `max` | "không học quá 4 tiết liền" → `max: 4` |
| `study_days` | Cả lịch | Số ngày có lớp | `min`, `max` | "chỉ lên trường 3 ngày" → `max: 3` |

- `scope` của `limit` giới hạn những lớp được tính. Ví dụ `"scope": {"day": ["thứ 2", "thứ 4"]}` chỉ đo trên thứ 2 và thứ 4.
- Hai cách viết khi sinh viên không nói con số cụ thể:
  - "Dồn lịch vào ít ngày nhất" → `{"limit": "study_days", "max": 1}`. Mỗi ngày học thêm bị phạt 1, nên tương đương với tối thiểu số ngày học.
  - "Trải đều lịch trong tuần" → `{"limit": "subjects_per_day", "max": 1}`. Mỗi môn thêm vào cùng một ngày bị phạt 1, nên tương đương với trải ra nhiều ngày nhất.

## 6. Ngữ nghĩa và cách tính phạt

### 6.1 Ký hiệu

- **Lịch S:** tập các lớp được chọn, đúng một lớp cho mỗi môn.
- Với một ràng buộc c:
  - σ là `scope`; thiếu `scope` thì σ luôn đúng;
  - E là danh sách phạm vi loại trừ, do quy tắc ngoại lệ (6.4) gán.
- **Tập lớp trong phạm vi:**

  S_c = { x ∈ S : σ(x) đúng, x không khớp phạm vi nào trong E, và mọi thuộc tính mà c dùng đều xác định với x }.

### 6.2 `prefer` và `avoid`

- `prefer F`: vi phạm v(c) = số lớp trong S_c **không** khớp F.
- `avoid F`: vi phạm v(c) = số lớp trong S_c **khớp** F.

Ví dụ: với `{"avoid": {"day": "thứ 7"}}`, lịch có 2 lớp vào thứ 7 thì v = 2.

### 6.3 `limit`

v(c) = Σ trên các đơn vị u của chỉ số, chỉ tính lớp trong S_c, của:

  max(0, m_u − max) + max(0, min − m_u)

Cận nào không có thì bỏ số hạng tương ứng.

Ví dụ: với `{"limit": "subjects_per_day", "max": 2}`, lịch có thứ 2 học 3 môn và thứ 4 học 1 môn thì v = (3 − 2) + 0 = 1. Thứ 4 không bị phạt vì ràng buộc không có `min`.

### 6.4 Quy tắc ngoại lệ (D10)

- **Cùng nhóm:** hai ràng buộc cùng nhóm khi:
  - cả hai là `prefer` / `avoid` (không cần cùng loại) và tập key của điều kiện giống nhau; hoặc
  - cả hai là `limit` với cùng một chỉ số.
- **Cụ thể hơn:** ràng buộc A cụ thể hơn B khi phạm vi của A nằm trong phạm vi của B và khác B. Cụ thể là: mọi key trong scope(B) đều có trong scope(A), và giá trị ở A là tập con của giá trị ở B (so sánh sau chuẩn hoá). Thiếu `scope` nghĩa là "mọi lớp".
- **Áp dụng:** khi A cụ thể hơn B và hai ràng buộc cùng nhóm, scope(A) được thêm vào danh sách loại trừ E của B. Trong phần giao, chỉ A áp dụng.
- **Mâu thuẫn:** hai ràng buộc cùng nhóm, cùng phạm vi, cùng điều kiện (cả key lẫn giá trị) nhưng một là `prefer`, một là `avoid` → warning "mâu thuẫn". Cả hai vẫn áp dụng.
- **Giao nhau mà không lồng nhau:** cả hai cùng áp dụng, không có warning.

Ví dụ: "Tôi thích học buổi sáng, riêng thứ 2 thì học chiều" →

```json
{"constraints": [
  {"prefer": {"session": "sáng"}},
  {"prefer": {"session": "chiều"}, "scope": {"day": "thứ 2"}}
]}
```

Ràng buộc 1 cụ thể hơn ràng buộc 0 và cùng nhóm `{session}`. Vì vậy ràng buộc 0 nhận E = [`{day: T2}`]: lớp thứ 2 chỉ bị chấm theo "chiều".

### 6.5 Mức độ và trọng số

- Phạt của một ràng buộc: p(c) = w(c) · v(c).
- **Trọng số w(c):**
  - với `prefer` / `avoid`: trọng số cơ sở lớn nhất trong các thuộc tính xuất hiện ở điều kiện và `scope` (trừ `course`);
  - với `limit`: trọng số của chỉ số;
  - nhân 2 nếu `level` là `high`.
- Trọng số cơ sở (kế thừa `PRIORITY_WEIGHTS` của v1; câu hỏi Q3 chốt giữ giả định, chỉnh được sau trong `vocab.py`):

| Nhóm | Thuộc tính / chỉ số | Trọng số |
|---|---|---|
| Người | `teacher`, `class_group` | 4 |
| Mốc thời gian | `day`, `start_period`, `end_period`, `start_time`, `end_time` | 3 |
| Khung thời gian | `session`, `periods` | 2 |
| Ngôn ngữ | `language` | 2 |
| Khối lượng | `subjects_per_day`, `subjects_per_session`, `periods_per_day`, `study_days` | 2 |
| Thời lượng lớp | `duration` | 1 |
| Nơi học | `area`, `room` | 1 |
| Nhịp học | `gap_periods`, `consecutive_periods` | 1 |

### 6.6 `must` và trùng lịch

- **Trùng lịch luôn bị cấm.** Hai lớp trùng lịch khi cùng thứ và có tiết giao nhau (không xét `Tuần học`). Không lịch nào bị trùng lịch được trả về.
- **`must` là ràng buộc cứng.** Các lịch được so sánh theo thứ bậc:
  1. trước hết là tổng vi phạm cứng: H = Σ v(c) trên các ràng buộc `must`;
  2. sau đó là tổng phạt mềm: P = Σ p(c) trên các ràng buộc còn lại.
- **Khi không thoả được `must`:** nếu không lịch nào đạt H = 0, vẫn trả các lịch có H nhỏ nhất, kèm `infeasible` cho biết ràng buộc nào không thể thoả và lý do (ví dụ "Không lớp nào của môn X thoả"). Đã xác nhận ở câu hỏi Q5.

### 6.7 Lớp không có lịch và giá trị không xác định

| Thuộc tính | Giá trị coi là không xác định |
|---|---|
| `day`, `session`, `periods`, `start_period`, `end_period`, `start_time`, `end_time`, `duration` | Lớp không có lịch: `periods` rỗng, hoặc `day` là `Thứ _` hay trống |
| `area` | `Khác`, `(Chọn)`, `Chưa xếp phòng`, `-`, trống |
| `room` | `_`, trống |
| `teacher` | Bắt đầu bằng `Khoa.`; `.`; trống |
| `class_group` | Trống |

- Lớp có giá trị không xác định với một thuộc tính bị loại khỏi S_c của mọi ràng buộc dùng thuộc tính đó, dù ở điều kiện hay phạm vi.
- Lớp không có lịch không trùng lịch với lớp nào, và không được tính trong các chỉ số thời gian (`subjects_per_day`, `gap_periods`…).

### 6.8 Tuyến tính hoá (ghi chú cho Phần B)

Đặt x_l ∈ {0, 1} là biến "chọn lớp l". Mọi đại lượng ở trên đều biểu diễn tuyến tính được:

| Loại | Cách tuyến tính hoá |
|---|---|
| `prefer` / `avoid` | v = Σ a_l · x_l, với a_l ∈ {0, 1} tính trước cho từng lớp ứng viên |
| `subjects_per_day`, `subjects_per_session`, `periods_per_day` | m_u = Σ_{l ∈ u} hệ số_l · x_l. Biến phụ e_u ≥ m_u − max và d_u ≥ min · b_u − m_u, với b_u ∈ {0, 1} báo đơn vị u có học |
| `gap_periods` | Với mỗi cặp lớp (A, B) cùng ngày, A bắt đầu trước B: q_AB ≥ x_A + x_B − 1 − Σ_{C bắt đầu giữa A và B} x_C. Phạt = q_AB nhân với độ lệch của khoảng trống so với cận |
| `consecutive_periods` | o_{d,t} = Σ x_l của các lớp phủ (ngày d, tiết t). Với mỗi cửa sổ (max + 1) tiết liên tiếp: w ≥ Σ o − max. Tổng w bằng Σ trên các khối của max(0, độ dài − max) |
| `study_days` | y_d ≥ x_l với mọi lớp l vào ngày d; y_d ≤ Σ x_l; giá trị = Σ y_d |

## 7. Chuẩn hoá

### 7.1 Bảng giờ của tiết (Q1)

| Tiết | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Bắt đầu | 07:30 | 08:30 | 09:30 | 10:30 | 11:30 | 13:00 | 14:00 | 15:00 | 16:00 | 17:00 |
| Kết thúc | 08:20 | 09:20 | 10:20 | 11:20 | 12:20 | 13:50 | 14:50 | 15:50 | 16:50 | 17:50 |

- Giờ bắt đầu đã được xác nhận (Q1) và trùng với `SCHEDULE_OF_CLASSES` (`app/constant/constant_of_schedule.py`).
- Giờ kết thúc vẫn là giả định: mỗi tiết dài 50 phút.
- Giờ bắt đầu của lớp = giờ bắt đầu của tiết đầu. Giờ kết thúc của lớp = giờ kết thúc của tiết cuối.

### 7.2 Buổi (Q1)

| Giá trị | Tiết |
|---|---|
| `sáng` (chấp nhận cả "buổi sáng") | 1–5 |
| `chiều` (chấp nhận cả "buổi chiều") | 6–10 |
| `sáng sớm` | 1–2 |
| `chiều muộn` | 8–10 |

- Sáng = tiết 1–5 và chiều = tiết 6–10 đã được xác nhận (Q1). Không có buổi tối.
- `sáng sớm` và `chiều muộn` vẫn là giả định.
- Giá trị khác, ví dụ "trưa", "tối" → `unsupported`, lý do "buổi không xác định".

### 7.3 Quy tắc theo thuộc tính

| Thuộc tính | Quy tắc |
|---|---|
| `day` | Bỏ dấu, chữ thường, bỏ khoảng trắng, như `normalize_day` hiện có. `thu2` / `thuhai` / `t2` → `T2` … `thu7` / `thubay` → `T7`; `chunhat` / `cn` → `CN`. Nhóm: "cuối tuần" → {T7, CN}; "ngày thường", "các ngày trong tuần" → {T2 … T6}. Dữ liệu lớp: `Thứ Hai` … `Thứ Bảy` → `T2` … `T7` |
| `session` | Theo bảng 7.2 |
| `periods` | List số nguyên 1–10, khoảng `{min, max}`, hoặc chuỗi `"1-3"` → tập tiết |
| `start_period`, `end_period`, `duration` | Số nguyên hoặc khoảng |
| `start_time`, `end_time` | Chấp nhận `"10:00"`, `"10h"`, `"10h30"`, `"10 giờ"`, `10`. Hậu tố "chiều" / "tối" cộng 12 giờ nếu giờ < 12. Kết quả là phút trong ngày |
| `area` | `K`, `khu K`, `V`, `khu V` (không phân biệt hoa thường) → `K` / `V`. Giá trị khác → `unsupported` |
| `room` | Viết hoa. `V.A201` → khu `V` và phòng `A201`: điều kiện `area` được thêm vào cùng bộ lọc. `A201` → chỉ phòng |
| `language` | "tiếng Anh", "English", "TA" → `Tiếng Anh`; "tiếng Việt", "TV" → `Tiếng Việt` |
| `class_group` | Số nguyên, hoặc chuỗi có số ("nhóm 2", "lớp 2") → 2. Dữ liệu lớp `"2"` → 2 |
| `course` | Khớp với danh sách môn đã chọn (7.4) |
| `teacher` | Khớp với giảng viên của các lớp ứng viên (7.5) |

### 7.4 Khớp tên môn

Đối tượng so khớp là danh sách môn sinh viên đã chọn trong request.

1. So sánh sau khi bỏ dấu, chuyển chữ thường, gộp khoảng trắng.
2. Thử theo thứ tự ưu tiên:
   - trùng khớp hoàn toàn;
   - chuỗi này chứa chuỗi kia;
   - tỉ lệ từ trùng ≥ 0,6. Tỉ lệ = số từ chung / số từ trong tên sinh viên nói.
3. Xử lý kết quả:
   - đúng một môn khớp → dùng môn đó;
   - nhiều môn khớp → dùng tất cả, kèm warning;
   - không khớp → `unsupported`, lý do "môn không có trong danh sách đã chọn".

Không xử lý viết tắt (ví dụ "CTDL&GT"). Module LLM nên nhận danh sách môn đã chọn trong prompt để ghi đúng tên.

### 7.5 Khớp tên giảng viên

Đối tượng so khớp là giảng viên của các lớp ứng viên. Nếu ràng buộc có `scope.course` thì chỉ xét các lớp của môn đó.

1. **Làm sạch tên:**
   - bỏ chức danh ở đầu bằng regex `^((PGS|GS|TS|ThS|KS|CN)\.)+` (không phân biệt hoa thường);
   - bỏ các từ "thầy", "cô", "giảng viên", "GV";
   - chuyển chữ thường, gộp khoảng trắng.

   Ví dụ: `PGS.TS.Nguyễn Thanh Bình` → `nguyễn thanh bình`.
2. **Khớp** nếu một trong các điều kiện sau đúng (so sánh theo từ):
   - trùng toàn bộ tên;
   - tên sinh viên nói là phần **cuối** của tên đầy đủ: "Sơn" khớp "Trần Đình Sơn"; "Mai Nga" khớp "Dương Thị Mai Nga";
   - từ đầu (họ) và từ cuối (tên) đều trùng: "Trần Sơn" khớp "Trần Đình Sơn".
3. **Không** khớp chỉ theo họ. "Nguyễn" không khớp mọi giảng viên họ Nguyễn (lỗi này có ở v1).
4. **Xử lý kết quả:**
   - một người khớp → dùng người đó;
   - nhiều người khớp → dùng tất cả, kèm warning, ví dụ "Có 2 giảng viên khớp 'Sơn': …";
   - không ai khớp → bỏ giá trị đó. Nếu không còn giá trị nào thì đưa ràng buộc vào `unsupported`.

Giá trị giảng viên không xác định trong dữ liệu (`Khoa.…`, `.`) không tham gia so khớp.

### 7.6 Warning và unsupported

| Tình huống | Kết quả |
|---|---|
| Lỗi cấu trúc: thiếu loại ràng buộc, sai kiểu, thuộc tính lạ… (mục 8) | `unsupported`, kèm lý do cụ thể |
| Một giá trị trong list không chuẩn hoá được, các giá trị khác dùng được | Giữ phần dùng được, thêm warning |
| Không giá trị nào chuẩn hoá được | `unsupported` |
| Khớp nhiều môn hoặc nhiều giảng viên | Dùng tất cả, thêm warning |
| Hai ràng buộc mâu thuẫn (6.4) | Warning |
| Chuỗi `unsupported` do LLM sinh | Giữ nguyên, lý do "LLM không ánh xạ được" |

## 8. Validation

| # | Quy tắc | Khi vi phạm |
|---|---|---|
| V1 | Mỗi ràng buộc có đúng một trong `prefer`, `avoid`, `limit` | `unsupported` |
| V2 | `limit` nằm trong danh sách chỉ số; có ít nhất một trong `min` / `max`; giá trị là số nguyên ≥ 0; `min ≤ max`; cận phải được chỉ số cho phép (mục 5) | `unsupported` |
| V3 | `min` / `max` ở cấp ràng buộc chỉ đi với `limit` | `unsupported` |
| V4 | Bộ lọc (`prefer`, `avoid`, `scope`) không rỗng; mọi key thuộc danh sách ở mục 4 | `unsupported` |
| V5 | Khoảng chỉ dùng cho thuộc tính có thứ tự; có ít nhất một cận; `min ≤ max` | `unsupported` |
| V6 | Kiểu giá trị đúng với thuộc tính: chuỗi, số, list hay khoảng | `unsupported` |
| V7 | `level` là một trong `must` / `high` / `normal` | `unsupported` |
| V8 | Key lạ ở cấp ràng buộc hoặc top-level | Bỏ qua key đó, thêm warning |
| V9 | `constraints` thiếu hoặc không phải mảng | Lỗi 400 cho cả tài liệu |
| V10 | Tài liệu có `defaults` hoặc `periods` (dạng v1) | Chuyển sang v2 qua adapter (mục 12.1; câu hỏi Q2), thêm warning "đã chuyển từ v1". Adapter lỗi → lỗi 400 |
| V11 | `version` có phiên bản chính khác 2 | Lỗi 400 |

Mỗi phần tử `unsupported` sinh ra từ validation gồm:
- `index`: vị trí của ràng buộc trong mảng;
- `source`: JSON gốc của ràng buộc;
- `reason`: lý do.

Ví dụ: ràng buộc `{"prefer": {"weather": "nắng"}}` ở vị trí 3 cho ra:

```json
{"index": 3, "source": {"prefer": {"weather": "nắng"}}, "reason": "Thuộc tính 'weather' không có trong từ vựng"}
```

## 9. Mô hình nội bộ sau chuẩn hoá

**`NormalizedConstraint`**

| Field | Ý nghĩa |
|---|---|
| `id` | Vị trí trong mảng `constraints` gốc |
| `kind` | `prefer` / `avoid` / `limit` |
| `condition` | Bộ lọc đã chuẩn hoá (với `prefer` / `avoid`) |
| `metric`, `min`, `max` | Với `limit` |
| `scope` | Bộ lọc đã chuẩn hoá; rỗng nghĩa là mọi lớp |
| `exclude` | Danh sách phạm vi loại trừ (6.4) |
| `level`, `weight` | Mức độ và trọng số đã tính (6.5) |
| `source` | JSON gốc, dùng để hiển thị và giải thích |

**Bộ lọc đã chuẩn hoá:** mỗi thuộc tính được ánh xạ sang một trong ba dạng:
- tập giá trị chuẩn: `course`, `class_group`, `teacher`, `language`, `day`, `area`, `room`;
- tập tiết: `session`, `periods`. Hai key này giữ riêng để đúng quy tắc AND ở mục 3.3;
- khoảng [a, b]: `start_period`, `end_period`, `start_time` và `end_time` (tính bằng phút), `duration`.

**`NormalizedDocument`** gồm `version`, `constraints` (danh sách `NormalizedConstraint`), `unsupported`, `warnings`.

## 10. Request và response v2 (dùng khi tích hợp ở Phần B)

Request `POST /api/schedule`:

```json
{
  "courses": [
    {"name": "Lập trình Java"},
    {"name": "Phân tích dữ liệu", "sub_topic": "Pandas, trực quan hóa với Matplotlib"}
  ],
  "preferences": {
    "version": "2.0",
    "constraints": [{"avoid": {"day": "thứ 7"}}],
    "unsupported": []
  },
  "k": 5
}
```

`/api/reschedule` thêm field `pinned`, chứa các lớp đã đăng ký thành công, ví dụ `[{"course": "Lập trình Java", "class_index": "2"}]`. Môn được ghim chỉ còn đúng lớp đó làm ứng viên.

Response:

```json
{
  "version": "2.0",
  "schedules": [
    {
      "rank": 1,
      "classes": [
        {"course_name": "Lập trình Java", "class_index": "2", "teacher": "ThS.Nguyễn Văn A", "day": "Thứ Hai", "periods": [1, 2, 3], "area": "K", "room": "A212", "language": "Tiếng Việt", "class_size": 65}
      ],
      "hard_violations": 0,
      "penalty": 3.0,
      "violations": [{"constraint_id": 1, "amount": 1, "penalty": 3.0}]
    }
  ],
  "constraints": [
    {"id": 0, "kind": "avoid", "level": "normal", "weight": 3, "source": {"avoid": {"day": "thứ 7"}}}
  ],
  "unsupported": [
    {"index": null, "source": "muốn học cùng lớp với bạn Nam", "reason": "LLM không ánh xạ được"}
  ],
  "warnings": [],
  "infeasible": [],
  "meta": {"algorithm": "cpsat", "elapsed_ms": 12}
}
```

## 11. Bố cục code dự kiến (Phần A)

| File | Nội dung | Task |
|---|---|---|
| `app/scheduling/__init__.py` | Package mới | T2 |
| `app/scheduling/vocab.py` | Danh sách thuộc tính, chỉ số, mức độ, trọng số cơ sở; bảng giờ tiết; buổi; alias thứ và ngôn ngữ; giá trị không xác định | T2 |
| `app/scheduling/schema.py` | Pydantic models, validation theo từng ràng buộc, xuất JSON Schema | T3, T4 |
| `app/scheduling/normalize.py` | Chuẩn hoá giá trị, khớp môn và giảng viên, quy tắc ngoại lệ, `normalize_document()` | T5–T7 |
| `app/scheduling/v1_adapter.py` | Chuyển tài liệu v1 sang v2 theo mục 12.1, cho các lịch đã lưu `parsed_prompt` v1 | T9 |
| `docs/specs/json_v2/schema.json`, `schema.inline.json` | JSON Schema xuất tự động | T4 |
| `tests/scheduling/` | Test validation, chuẩn hoá, golden examples | T3–T8 |

- **Dùng lại:**
  - logic của `normalize_day` (`app/service/constraints_service.py:116`);
  - các giá trị trong `SCHEDULE_OF_CLASSES`;
  - dataclass `ClassInfo`, làm đầu vào cho lớp ứng viên.
- **Code v1** (`app/service/constraints_service.py`, `app/api/schedule_api.py`) giữ nguyên trong Phần A; Phần B sẽ thay thế.

## 12. Ánh xạ v1 → v2

### 12.1 Bảng ánh xạ

Bảng phủ mọi field trong `data/docs-feature.md`.

| v1 | v2 |
|---|---|
| `defaults.subject_per_session: N` | `{"limit": "subjects_per_session", "max": N}` |
| `defaults.subject_per_day: N` | `{"limit": "subjects_per_day", "max": N}` |
| `duration_of_session {value: v, up_or_down, like}` | Khoảng: `{"duration": {"min": v}}` nếu `up`, `{"duration": {"max": v}}` nếu `down`. Loại: `like: true` → `prefer`, `like: false` → `avoid` |
| `period {value: [..], like}` | `{"prefer" hoặc "avoid": {"periods": [..]}}` |
| `period_onward {value: v, like}` | `{"prefer" hoặc "avoid": {"start_period": {"min": v}}}` |
| `hour_onward {value: h, unit, like}` | `{"prefer" hoặc "avoid": {"start_time": {"min": "hh:00"}}}`; bỏ `unit` |
| `area {value, like}` | `{"prefer" hoặc "avoid": {"area": value}}` |
| `room [{value, like}]` | Gom theo `like`: `{"prefer": {"room": [..]}}` và `{"avoid": {"room": [..]}}` |
| `class[].name` | `scope.course`. Tên rỗng → không có `scope` |
| `class[].class_group [{value, like}]` | `{"prefer" hoặc "avoid": {"class_group": [..]}, "scope": {"course": name}}` |
| `class[].teacher [{name, like}]` | `{"prefer" hoặc "avoid": {"teacher": [..]}, "scope": {"course": name}}` |
| `teacher [{name, like}]` (biến thể trong `data/gemini_batch_translate.py`) | `{"prefer" hoặc "avoid": {"teacher": [..]}}` |
| `rest_interval {value: v, up_or_down, like}` | Với `like: true`: `{"limit": "gap_periods", "min": v}` nếu `up`, `"max": v` nếu `down`. Với `like: false`: `up` → `"max": v − 1`, `down` → `"min": v + 1` |
| `periods[].day {value: d, like: true}` | Mọi ràng buộc trong entry nhận `scope.day = d`. `"Cả tuần"` → không có `scope` |
| `periods[].day {value: d, like: false}` (entry không có key nào khác) | `{"avoid": {"day": d}}` |
| `periods[].subject_count {value: v}` | `{"limit": "subjects_per_day", "min": v, "max": v, "scope": {"day": d}}` |
| `periods[].<key khác>` | Như ở `defaults`, thêm `scope.day = d`. Riêng `class`: `scope = {course, day}` |
| Quy tắc "periods ghi đè defaults" | Quy tắc ngoại lệ (6.4) tái hiện tự động |

### 12.2 Ví dụ: `data/prompt.json` viết lại bằng v2

v1 dài khoảng 140 dòng, phần lớn là `null`. v2 gồm 29 ràng buộc, mỗi ràng buộc một dòng (ID từ 0 đến 28 theo thứ tự):

```json
{"version": "2.0", "constraints": [
  {"limit": "subjects_per_session", "max": 1},
  {"limit": "subjects_per_day", "max": 3},
  {"prefer": {"duration": {"max": 2}}},
  {"prefer": {"periods": {"min": 2, "max": 7}}},
  {"prefer": {"start_period": {"min": 3}}},
  {"prefer": {"start_time": {"min": "09:00"}}},
  {"prefer": {"area": "K"}},
  {"prefer": {"room": ["A101", "A102"]}},
  {"prefer": {"teacher": "Mai Lam"}, "scope": {"course": "Automat và ngôn ngữ hình thức"}},
  {"avoid": {"teacher": "Tuấn"}, "scope": {"course": "Automat và ngôn ngữ hình thức"}},
  {"prefer": {"teacher": ["Phượng", "Trọng"]}},
  {"limit": "gap_periods", "max": 1},

  {"prefer": {"periods": {"min": 6, "max": 9}}, "scope": {"day": "thứ 2"}},
  {"limit": "subjects_per_day", "min": 1, "max": 1, "scope": {"day": "thứ 2"}},
  {"prefer": {"duration": {"min": 3}}, "scope": {"day": "thứ 2"}},
  {"limit": "gap_periods", "max": 1, "scope": {"day": "thứ 2"}},
  {"prefer": {"room": "A101"}, "scope": {"day": "thứ 2"}},
  {"prefer": {"area": "K"}, "scope": {"day": "thứ 2"}},
  {"prefer": {"class_group": [2, 4]}, "scope": {"course": "Tiếng anh nâng cao 4", "day": "thứ 2"}},
  {"prefer": {"teacher": "Kim Tuyến"}, "scope": {"course": "Tiếng anh nâng cao 4", "day": "thứ 2"}},
  {"prefer": {"start_period": {"min": 8}}, "scope": {"day": "thứ 2"}},
  {"prefer": {"start_time": {"min": "15:00"}}, "scope": {"day": "thứ 2"}},

  {"prefer": {"periods": {"min": 1, "max": 4}}, "scope": {"day": "thứ 4"}},
  {"limit": "subjects_per_day", "min": 2, "max": 2, "scope": {"day": "thứ 4"}},
  {"limit": "gap_periods", "max": 1, "scope": {"day": "thứ 4"}},
  {"avoid": {"room": "A101"}, "scope": {"day": "thứ 4"}},
  {"prefer": {"class_group": [2, 4]}, "scope": {"course": "Triết học Mac-Lenin", "day": "thứ 4"}},
  {"prefer": {"teacher": "Phượng"}, "scope": {"course": "Triết học Mac-Lenin", "day": "thứ 4"}},
  {"prefer": {"area": "K"}, "scope": {"day": "thứ 4"}}
]}
```

Quy tắc ngoại lệ tái hiện đúng hành vi ghi đè của v1. Ví dụ:
- Ràng buộc 12 (tiết 6–9, thứ 2) làm ràng buộc 3 (tiết 2–7) không áp dụng cho lớp thứ 2.
- Ràng buộc 25 (tránh A101, thứ 4) làm ràng buộc 7 (thích A101/A102) không áp dụng cho lớp thứ 4.
- Ràng buộc 17 và 6 cùng ưu tiên khu K, nhưng lớp thứ 2 chỉ bị chấm một lần, theo ràng buộc 17.

## 13. Ví dụ

Mỗi ví dụ gồm câu gốc, tài liệu v2, và ghi chú. Nguồn của câu:
- "mẫu câu": lấy từ `validation/data/create_override_data_VIT5.py`;
- "bổ sung": viết thêm để phủ đủ từ vựng.

Từ ví dụ thứ hai trở đi, `version` được lược bỏ (mặc định `"2.0"`). Các ví dụ này được trích vào golden tests (task T8).

**Bảng phủ:**

| Thành phần | Ví dụ |
|---|---|
| `course` (trong `scope`) | E2–E5, E7, E8, E10, E18, E19 |
| `class_group` | E19 |
| `teacher` | E10, E18 |
| `language` | E20 |
| `day` | E1–E4, E7, E8, E10, E12, E16, E21–E23, E29, E31, E32 |
| `session` | E2, E3, E6, E8–E10, E14, E16, E23, E29, E31 |
| `periods` | E13 |
| `start_period` / `end_period` | E12 / E14 |
| `start_time` / `end_time` | E11, E30 / E15 |
| `duration` | E17 |
| `area` / `room` | E5, E6 / E9, E21 |
| `subjects_per_day` / `subjects_per_session` / `periods_per_day` | E22, E30 / E23 / E27 |
| `gap_periods` / `consecutive_periods` | E7, E24 / E25 |
| `study_days` | E26 |
| `level: must` / `level: high` | E11, E22, E23, E30 / E26 |
| Quy tắc ngoại lệ | E31, mục 12.2 |
| `unsupported` | E28, E32 |
| 10 mẫu câu v1 không biểu diễn được (requirements.md mục 2.2) | E1–E9 |

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

## 14. Hướng dẫn cho module LLM

1. **Mỗi ý → một ràng buộc.** Câu có nhiều ý → nhiều ràng buộc. Một ý gồm nhiều điều kiện cùng lúc ("sáng thứ 6 với thầy Sơn") → một bộ lọc có nhiều key.
2. **Chỉ ghi điều sinh viên nói.** Không sinh `null`, mảng rỗng, hay ràng buộc mặc định.
3. **Giữ giá trị bề mặt và đơn vị sinh viên dùng.** "Từ tiết 3" → `start_period`; "sau 10 giờ" → `start_time`. Không tự đổi giờ ↔ tiết hay buổi → tiết.
4. **Chọn loại ràng buộc:**
   - thích / muốn / ưu tiên → `prefer`;
   - không thích / tránh / không muốn → `avoid`;
   - giới hạn số lượng ("tối đa", "ít nhất", "không quá", "khoảng") → `limit`.
5. **Phân biệt phạm vi và điều kiện:**
   - phần trả lời câu hỏi "áp dụng cho lớp nào?" (môn X, thứ 2, buổi chiều, lớp ở phòng P) → `scope`;
   - phần trả lời câu hỏi "muốn hoặc tránh điều gì?" → `prefer` / `avoid`;
   - tên môn luôn nằm trong `scope`.
6. **Mức độ:** theo bảng từ khoá 14.1.
7. **Ngoại lệ** ("riêng", "trừ", "ngoại trừ"): viết ràng buộc chung như bình thường, rồi thêm một ràng buộc cho phần ngoại lệ với `scope` hẹp hơn. Không cần sửa ràng buộc chung.
8. **Lý do** ("vì gần nhà", "để đi làm thêm") không phải ràng buộc: bỏ qua.
9. **Ý không biểu diễn được** bằng từ vựng: chép nguyên văn vào `unsupported`.
10. **"Dồn lịch" / "trải đều" không kèm số:** viết theo mục 5.
11. **Tên riêng:** nếu prompt có danh sách môn đã chọn và giảng viên (RAG), dùng đúng tên trong danh sách đó.

### 14.1 Từ khoá mức độ

| Mức | Từ khoá gợi ý |
|---|---|
| `must` | "chỉ", "bắt buộc", "phải", "không thể", "nhất định", "tuyệt đối" |
| `high` | "rất muốn", "rất cần", "quan trọng nhất", "ưu tiên hàng đầu" |
| `normal` | "thích", "muốn", "ưu tiên", "nếu được", "nếu có thể"; cả mẫu "chỉ … nếu không còn lựa chọn" (ngoại lệ của "chỉ") |

## 15. Kiểm thử

- **Validation:** mỗi quy tắc V1–V11 có ít nhất một ca hợp lệ và một ca vi phạm.
- **Chuẩn hoá:**
  - bảng dữ liệu cho từng alias ở mục 7;
  - khớp giảng viên: một người, nhiều người, không ai; "Nguyễn" một mình không khớp; chức danh `PGS.TS.` được bỏ đúng;
  - khớp môn.
- **Quy tắc ngoại lệ:** E31, và tài liệu 12.2 (tái hiện hành vi ghi đè của v1).
- **Giá trị không xác định:** lớp không có lịch, khu `(Chọn)`, giảng viên `Khoa.…`.
- **Golden tests:** mọi ví dụ ở mục 13 và 12.2 được trích vào `tests/scheduling/examples.json` (JSON đầu vào và kết quả chuẩn hoá mong đợi), chạy tự động.
- **Snapshot JSON Schema:** schema xuất từ models phải trùng với file đã commit.
- **Ngữ nghĩa phạt (mục 6):** test ở Phần B, khi đã có hàm chấm. Các ví dụ có sẵn mức vi phạm (mục 6 và 13) dùng làm ca test đầu tiên.

## 16. Quy trình mở rộng

**Thêm một thuộc tính lọc:**
1. Thêm vào `vocab.py`: tên, kiểu giá trị, có thứ tự hay không, trọng số cơ sở, các giá trị không xác định.
2. Viết quy tắc chuẩn hoá trong `normalize.py`.
3. Phần B: viết hàm lấy giá trị của thuộc tính từ lớp.
4. Cập nhật mục 4, 6.5, 6.7, 7.3 và thêm ví dụ ở mục 13.
5. Thêm test, xuất lại `schema.json`.
6. Báo cho module LLM để bổ sung ví dụ huấn luyện cho thuộc tính mới.

**Thêm một chỉ số:** làm tương tự, kèm theo đơn vị đo, cận cho phép, công thức đo và cách tuyến tính hoá (mục 5, 6.8).
