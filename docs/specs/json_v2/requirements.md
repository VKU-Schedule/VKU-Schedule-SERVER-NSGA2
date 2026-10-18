# Phần A — JSON Structure v2: Yêu cầu

> Tài liệu 1/3 của spec Phần A. Tài liệu này trả lời: **làm gì và tại sao**.
> - Cách làm: [design.md](design.md)
> - Các bước: [tasks.md](tasks.md)
> - Lộ trình chung: [../README.md](../README.md)

## 1. Bối cảnh

Sinh viên nhập yêu cầu xếp lịch bằng ngôn ngữ tự nhiên, ví dụ: "Tôi chỉ học nếu lớp bắt đầu sau 10 giờ sáng, không học thứ 7". Yêu cầu đi qua pipeline:

```
Văn bản → Module LLM → JSON ràng buộc → Module xếp lịch → ~5 lịch
```

JSON ràng buộc là **hợp đồng** giữa hai module phát triển độc lập:
- Module LLM (module riêng, fine-tune) **sinh** JSON.
- Module xếp lịch (repo này) **đọc** JSON. Mỗi ràng buộc trở thành một thành phần của hàm mục tiêu.

Vì vậy cấu trúc JSON quyết định cùng lúc hai điều: LLM có sinh đúng không, và thuật toán có hiểu đúng ý sinh viên không.

## 2. Vấn đề của schema v1

Schema v1 được mô tả trong `data/docs-feature.md` (ví dụ đầy đủ ở `data/prompt.json`) và được đọc bởi `evaluate()` trong `app/service/constraints_service.py`. Các số dòng trong mục này tính theo commit `f359585`.

### 2.1 Nguyên nhân gốc

1. **Phạm vi gắn cứng vào cấu trúc.**
   - Chỉ có hai phạm vi: `defaults` (cả tuần) và `periods[]` (đúng một ngày).
   - Không biểu diễn được phạm vi theo môn, theo buổi, theo nhiều ngày, hoặc có điều kiện.
   - Muốn thêm phạm vi thì phải nhân bản các field, nên số vị trí field tăng theo tích: (số loại ràng buộc) × (số kiểu phạm vi).
2. **Một ý có nhiều cách viết.**
   - `like` nằm ở hai tầng: trên `day` và trên từng ràng buộc.
   - Giờ và tiết là hai field song song (`hour_onward`, `period_onward`).
   - `area` là object còn `room` là list.
   - Giảng viên nằm ở ba vị trí khác nhau tuỳ phiên bản schema.
3. **LLM phải tự tính toán:** đổi "buổi sáng" thành tiết 1–5, "10 giờ" thành số tiết, tách "V.A201" thành khu và phòng.
4. **Output dài.** Mỗi entry `periods` lặp lại khoảng 11 key, phần lớn là `null` hoặc mảng rỗng. Ví dụ `data/prompt.json` dài khoảng 140 dòng.

### 2.2 Bằng chứng

Trong 49 mẫu câu của bộ sinh dữ liệu `validation/data/create_override_data_VIT5.py`, có **ít nhất 10 mẫu không biểu diễn đúng được bằng v1**:

| Mẫu câu | Vì sao v1 không biểu diễn được |
|---|---|
| "Tôi không muốn học vào cuối tuần như thứ 7" | Không có cách tránh một ngày: `like: false` của `day` bị bỏ qua |
| "Tôi muốn học môn {X} vào sáng {thứ} nếu có thể" | Không có phạm vi theo môn cho ràng buộc thời gian |
| "Tôi muốn học môn {X} vào buổi sáng {thứ}" | Như trên |
| "Tôi muốn học môn {X} vào thứ {N} và có nghỉ giữa giờ" | Như trên |
| "Tôi muốn học môn {X} sáng {thứ}, tránh chiều" | Như trên |
| "Tôi không muốn học môn {X} vào thứ {N}" | Như trên, cộng thêm lỗi `like` của `day` |
| "Tôi muốn học môn {X} nhưng không phải sáng {thứ}" | Như trên |
| "Tôi ưu tiên học môn {X} ở khu {K/V}" | Không có phạm vi theo môn cho khu vực |
| "Tôi thích học ở khu vực {K/V} vào buổi chiều" | Không có phạm vi theo buổi |
| "Tôi thích học buổi sáng nếu lớp ở phòng {P}" | Không có phạm vi có điều kiện |

Các lỗi cụ thể trong `app/service/constraints_service.py`:

| Hiện tượng | Dòng | Hậu quả |
|---|---|---|
| `like` của `day` trong `periods` bị bỏ qua: code chỉ đọc `value` và lọc `key != "day"` | 428–445 | "Không học thứ 7" không có tác dụng. "Không học sáng thứ 7" có thể thành **thưởng** cho lớp sáng thứ 7 |
| `subject_count` và `teacher` (cấp ngoài) không có trong `CONSTRAINT_FUNCTIONS` | 388–400 | Bị bỏ qua âm thầm |
| Ba phiên bản schema lệch nhau: `data/docs-feature.md`; `data/gemini_batch_translate.py` (teacher ở cấp ngoài); `app/constant/constant_input_test.py` (teacher lồng trong `class`, `area: []`) | — | Nhãn train và thuật toán hiểu khác nhau |
| Doc ghi "tối đa N môn" nhưng code tính `abs(N - count)` | 154–193 | Ngày ít môn hơn N cũng bị phạt |
| "Tránh tiết" kiểm tra *nằm trọn* thay vì *có giao* | 51–64 | Tránh tiết 1–2, nhưng lớp tiết [1, 2, 3] không bị phạt |
| Thưởng theo số lớp khớp trong phạm vi một ngày | `evaluate` | Thuật toán có lợi khi dồn thêm lớp vào ngày đó |
| Điểm trả về là `abs(fitness)` | 536, 577 | Lịch được thưởng 12 và lịch bị phạt 12 hiển thị như nhau |
| `fuzzy_name_match` khớp theo họ (từ đầu tiên); bỏ chức danh bằng `replace` chuỗi | 361–380 | "Nguyễn Đức Hiển" khớp mọi giảng viên họ Nguyễn; "PGS.TS.Nguyễn…" thành "pnguyễn…" |
| Không có mức độ bắt buộc | — | "Chỉ học sau 10h" (trọng số 3) bị ưu tiên giảng viên (trọng số 4) lấn át |
| Lớp không có lịch (`periods = []`) | 163, 231, 253, 277 | Gặp một trong 89 lớp không có lịch thì `min([])` gây lỗi |

## 3. Mục tiêu và phi mục tiêu

### Mục tiêu

- **G1.** Biểu đạt được hầu hết yêu cầu thực tế với phạm vi tuỳ ý, không phải đổi cấu trúc.
- **G2.** Dễ cho LLM sinh đúng: ngắn, mỗi ý một cách viết, không bắt LLM tính toán.
- **G3.** Ngữ nghĩa chính xác: mỗi ràng buộc có một công thức phạt, thuật toán nào cũng tính ra cùng một điểm.
- **G4.** Không mất thông tin âm thầm: phần không hiểu hoặc không hợp lệ đều được báo lại.
- **G5.** Dễ mở rộng: thêm thuộc tính hoặc chỉ số mới mà cấu trúc không đổi.

### Phi mục tiêu (không làm trong Phần A)

- **NG1.** Thuật toán tìm lịch và cách chọn 5 lịch: thuộc Phần B. Phần A chỉ định nghĩa ngữ nghĩa phạt.
- **NG2.** Fine-tune hoặc viết prompt cho LLM: thuộc module riêng. Phần A chỉ cung cấp JSON Schema, ví dụ và hướng dẫn viết.
- **NG3.** Cột `Tuần học`.
- **NG4.** Ràng buộc quan hệ giữa các môn, ví dụ "môn A và môn B cùng ngày". Để dành cho v2.x.
- **NG5.** Tình trạng còn chỗ khi đăng ký và sĩ số. Lý do trong câu ("vì gần nhà") cũng không được ghi nhận.

## 4. Các bên liên quan

| Bên | Cần gì từ JSON v2 |
|---|---|
| Module LLM (sinh JSON) | Cấu trúc ngắn và rõ; JSON Schema để dùng cho structured output và gán nhãn; ví dụ; quy tắc viết |
| Module xếp lịch (đọc JSON, Phần B) | Ngữ nghĩa phạt chính xác; dạng đã chuẩn hoá |
| Frontend | Response giải thích được: lịch nào vi phạm ràng buộc nào, phần nào hệ thống không hiểu |
| Sinh viên | Ý mình được hiểu đúng; biết phần nào hệ thống chưa hỗ trợ |
| Báo cáo đồ án | Lý do thiết kế và tiêu chí đánh giá |

## 5. Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| Môn (course) | Học phần sinh viên chọn, ví dụ "Lập trình Java" |
| Lớp (class) | Một lớp học phần cụ thể của môn, gồm nhóm lớp, giảng viên, thứ, tiết, khu, phòng, ngôn ngữ. Mỗi lịch chọn đúng một lớp cho mỗi môn |
| Lớp ứng viên | Tất cả các lớp của các môn đã chọn, lấy từ cơ sở dữ liệu |
| Ràng buộc (constraint) | Một object trong mảng `constraints` |
| Điều kiện | Bộ lọc trong `prefer` / `avoid`: điều mà lớp nên thoả hoặc nên tránh |
| Phạm vi (`scope`) | Bộ lọc chọn ra các lớp mà ràng buộc áp dụng |
| Chỉ số (metric) | Đại lượng đo hình dạng lịch, dùng trong `limit` |
| Đơn vị đo | Phần của lịch mà chỉ số được đo trên đó: ngày, buổi, cặp lớp liền nhau, hoặc cả lịch |
| Phạt (penalty) | Số không âm; 0 nghĩa là ràng buộc được thoả |
| Giá trị bề mặt | Giá trị đúng như sinh viên nói: "sáng", "sau 10 giờ", "thầy Sơn" |
| Chuẩn hoá | Chuyển giá trị bề mặt thành giá trị chuẩn mà thuật toán dùng được |

## 6. Yêu cầu

Mỗi yêu cầu có ID, mô tả và tiêu chí chấp nhận (**TC**). Các task trong [tasks.md](tasks.md) tham chiếu tới các ID này.

### R1 — Độ phủ biểu đạt

JSON v2 phải biểu đạt được các nhóm yêu cầu sau, với phạm vi tuỳ ý (theo môn, thứ, buổi, giảng viên, phòng… và tổ hợp của chúng):
- **Thời gian:** thứ, buổi, tiết, tiết bắt đầu/kết thúc, giờ bắt đầu/kết thúc, số tiết của lớp.
- **Người và nơi:** giảng viên, nhóm lớp, khu, phòng, ngôn ngữ giảng dạy.
- **Hình dạng lịch:** số môn mỗi ngày, số môn mỗi buổi, số tiết mỗi ngày, khoảng nghỉ giữa hai lớp liền nhau, số tiết học liên tục, số ngày đi học.

TC:
- Cả 49 mẫu câu trong `create_override_data_VIT5.py` đều có cách biểu diễn trong v2. Lý do như "vì…" được bỏ qua theo NG5.
- 10 mẫu ở mục 2.2 đều có ví dụ v2 trong design.md.
- Thêm một yêu cầu mới thuộc các nhóm trên không cần đổi cấu trúc tài liệu.

### R2 — Mỗi ý một cách viết

TC:
- Polarity (thích / tránh) chỉ thể hiện ở `prefer` / `avoid`. `limit` dùng `min` / `max`.
- Mỗi khái niệm có đúng một tên thuộc tính; không có field trùng nghĩa.
- Quy tắc kết hợp được định nghĩa rõ: các key trong một bộ lọc là AND, list là OR, `{min, max}` là khoảng đóng.
- Những chỗ còn hai cách viết (ví dụ `course` đặt trong điều kiện) được server đưa về một dạng chuẩn.

### R3 — Gọn và thân thiện với LLM

TC:
- Tài liệu chỉ chứa các ràng buộc được nhắc tới; LLM không cần sinh `null` hay mảng rỗng.
- JSON Schema không dùng `oneOf` / `anyOf` ở cấp ràng buộc, để tương thích structured output của nhiều LLM.
- Ví dụ `data/prompt.json` viết lại bằng v2 ngắn hơn rõ rệt; phần so sánh có trong design.md.

### R4 — Mức độ

TC:
- `level` nhận một trong ba giá trị: `must` (bắt buộc), `high` (rất muốn), `normal` (mặc định).
- LLM không phải sinh trọng số dạng số. Trọng số mặc định nằm ở server và cấu hình được.
- Có bảng từ khoá gợi ý mức độ cho module LLM.

### R5 — Ngữ nghĩa xác định

TC:
- Mỗi loại ràng buộc và mỗi chỉ số có một công thức phạt không âm, bằng 0 khi được thoả.
- Mọi công thức tuyến tính hoá được trên biến chọn lớp (0/1). Nhờ vậy bộ giải chính xác (CP-SAT) và hàm chấm chung cho cùng một điểm.
- Cùng một tài liệu và cùng một lịch luôn cho cùng một điểm.

### R6 — Chuẩn hoá ở server

TC:
- LLM chỉ sinh giá trị bề mặt theo bảng từ vựng. Server chuẩn hoá mọi thuộc tính theo bảng quy tắc trong design.md.
- Tên môn và tên giảng viên được khớp với danh sách lớp ứng viên thật:
  - khớp nhiều kết quả: dùng tất cả, kèm warning;
  - không khớp: đưa vào `unsupported` kèm lý do.
- Chuẩn hoá chạy tất định và không gọi LLM.

### R7 — Không mất thông tin âm thầm

TC:
- Validate theo từng ràng buộc: một ràng buộc lỗi không làm hỏng cả tài liệu.
- Ràng buộc lỗi hoặc không chuẩn hoá được nằm trong `unsupported`, kèm lý do và nội dung gốc.
- Các chuỗi `unsupported` do LLM sinh được giữ nguyên và trả về.
- Tài liệu sai định dạng toàn bộ trả lỗi 400 kèm thông báo, không bao giờ trả 500.

### R8 — Một nguồn schema duy nhất

TC:
- Pydantic models là nguồn duy nhất. JSON Schema được xuất tự động ra `docs/specs/json_v2/schema.json`, kèm một bản không dùng `$ref`.
- Mọi ví dụ trong design.md được test tự động là hợp lệ.
- Test thất bại nếu models thay đổi mà chưa xuất lại schema.

### R9 — Response giải thích được

TC: response (dùng khi tích hợp ở Phần B) phải có:
- với mỗi lịch: các ràng buộc bị vi phạm, mức vi phạm và phần phạt tương ứng;
- danh sách ràng buộc đã chuẩn hoá, có ID;
- `unsupported`, `warnings`, `infeasible`.

### R10 — Dễ mở rộng

TC:
- Thêm một thuộc tính lọc hoặc chỉ số chỉ cần thêm vào bảng từ vựng, quy tắc chuẩn hoá và hàm đo tương ứng. Cấu trúc tài liệu không đổi.
- Quy trình mở rộng được viết trong design.md.

### R11 — Phiên bản

TC:
- Tài liệu có `version`; thiếu thì mặc định là `"2.0"`.
- Tài liệu dạng v1 (có `defaults` / `periods`) được chuyển sang v2 qua adapter, vì đã có lịch lưu `parsed_prompt` v1 (câu hỏi Q2). Không chuyển được thì bị từ chối với thông báo rõ ràng.

### R12 — Dữ liệu thiếu hoặc không xác định

TC:
- Lớp không có lịch không gây lỗi, không trùng lịch với lớp nào, và bị loại khỏi phạm vi của mọi ràng buộc liên quan đến thời gian.
- Lớp có giá trị không xác định (khu, phòng, giảng viên, nhóm lớp; danh sách trong design.md) bị loại khỏi phạm vi của các ràng buộc dùng thuộc tính đó.

### R13 — Quy tắc chung và ngoại lệ

Sinh viên hay nói theo kiểu "quy tắc chung + ngoại lệ", ví dụ "Tôi thích học buổi sáng, riêng thứ 2 thì học chiều". v1 xử lý trường hợp này bằng cách cho `periods` ghi đè `defaults`.

TC:
- LLM viết tự nhiên hai ràng buộc: một chung, một có phạm vi hẹp hơn. Server tự áp dụng ràng buộc cụ thể hơn trong phần giao, theo quy tắc trong design.md.
- Hai ràng buộc cùng phạm vi nhưng ngược chiều nhau sinh ra warning.

## 7. Ràng buộc kỹ thuật

- Python 3.12, Flask, như hiện tại. Thêm dependency `pydantic` v2.
- Dữ liệu lớp lấy từ MongoDB `university_db.ly_courses`, với các field như `ClassInfo` (`app/model/Class_Info.py`).
- JSON mã hoá UTF-8, giữ nguyên dấu tiếng Việt.

## 8. Tiêu chí hoàn thành Phần A

- Spec (3 file) được duyệt; các câu hỏi mở đã được trả lời.
- Các task bắt buộc trong tasks.md hoàn thành; tests chạy xanh.
- `schema.json` đã được xuất và commit.
- Mọi ví dụ trong design.md hợp lệ và chuẩn hoá ra đúng kết quả mong đợi.

## 9. Câu hỏi mở

Trả lời ngày 2026-10-18.

| # | Câu hỏi | Trả lời |
|---|---|---|
| Q1 | Mỗi tiết kết thúc lúc nào? Ranh giới các buổi ra sao? Có buổi tối không? | Giờ bắt đầu: sáng 07:30, 08:30, 09:30, 10:30, 11:30 (tiết 1–5); chiều 13:00, 14:00, 15:00, 16:00, 17:00 (tiết 6–10). Không có buổi tối. Vẫn là giả định: mỗi tiết dài 50 phút; "sáng sớm" = 1–2, "chiều muộn" = 8–10 |
| Q2 | Đã có lịch lưu với `parsed_prompt` v1 (dùng cho `/reschedule`) chưa? | Đã có, nên làm adapter v1 → v2 (task T9 thành bắt buộc) |
| Q3 | Trọng số mặc định cho từng nhóm thuộc tính? | Chưa trả lời, dùng giả định: kế thừa `PRIORITY_WEIGHTS` (bảng ở design.md mục 6.5); `high` nhân 2. Các trọng số là hằng số trong `vocab.py`, có thể chỉnh sau |
| Q4 | Đổi khu K↔V giữa hai lớp liền nhau có phải là vấn đề thật với sinh viên không? | Không, nên bỏ chỉ số `area_switch`. Câu về đổi khu vào `unsupported` (design.md E28) |
| Q5 | Khi ràng buộc `must` không thoả được: trả lịch tốt nhất kèm cảnh báo, hay không trả lịch nào? | Trả lịch tốt nhất kèm `infeasible` |

Đã xác minh từ dữ liệu, không cần hỏi: nhóm lớp (cột `Lớp`) là chuỗi số từ `"1"` đến `"22"`, nên được so sánh theo số nguyên.
