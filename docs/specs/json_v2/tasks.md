# Phần A — JSON Structure v2: Các bước

> Tài liệu 3/3 của spec Phần A. Tài liệu này trả lời: **làm theo bước nào**.
> - Yêu cầu: [requirements.md](requirements.md)
> - Thiết kế: [design.md](design.md)
>
> **Trạng thái:** chưa bắt đầu task nào. Chỉ làm từ T1 trở đi sau khi T0 xong (spec được duyệt).
>
> Quy ước: `[ ]` chưa làm, `[x]` đã xong. Mỗi task ghi rõ file, yêu cầu liên quan (R…) và điều kiện "Xong khi".

## Thứ tự và phụ thuộc

```
T0 ──► T1 ──► T2 ──► T3 ──► T4
               │
               └──► T5 ──► T6 ──► T7 ──► T8 ──► T11 ──► T12
                                   │
                                   ├──► T9
                                   └──► T10 (tuỳ chọn)
```

## Giai đoạn 0 — Duyệt spec

- [ ] **T0 — Review spec và trả lời câu hỏi mở**
  - Làm:
    - Bạn đọc 3 file spec.
    - Trả lời Q1–Q5 (requirements.md mục 9).
    - Cập nhật design.md nếu có câu trả lời khác giả định.
  - Yêu cầu: tất cả.
  - Xong khi: spec được duyệt; requirements.md mục 9 ghi rõ câu trả lời của từng câu hỏi.

## Giai đoạn 1 — Nền tảng

- [ ] **T1 — Thêm dependency**
  - Làm:
    - Thêm `pydantic>=2` vào `app/requirements.txt`.
    - Tạo `requirements-dev.txt` chứa `pytest`.
  - Yêu cầu: R8.
  - Xong khi: cài được trên Python 3.12; `python -c "import pydantic; print(pydantic.VERSION)"` in ra 2.x.

- [ ] **T2 — Từ vựng** (`app/scheduling/__init__.py`, `app/scheduling/vocab.py`)
  - Làm: các hằng số và bảng:
    - danh sách thuộc tính, kèm kiểu giá trị, có thứ tự hay không, trọng số cơ sở;
    - danh sách chỉ số, kèm cận cho phép và trọng số;
    - mức độ và hệ số của `high`;
    - bảng giờ tiết; bảng buổi;
    - alias thứ, nhóm ngày, alias ngôn ngữ;
    - giá trị không xác định của từng thuộc tính.
  - Yêu cầu: R1, R4, R6, R10, R12.
  - Xong khi: nội dung khớp design.md mục 4, 5, 6.5, 6.7, 7.1–7.3; không còn hằng số nào bị lặp ở file khác.

## Giai đoạn 2 — Schema và validation

- [ ] **T3 — Pydantic models và validation** (`app/scheduling/schema.py`, `tests/scheduling/test_schema.py`)
  - Làm:
    - Models `PreferenceDocument`, `Constraint`, `Range` và kiểu `Filter`.
    - Validators V1–V7.
    - Hàm `parse_document(raw) -> ParsedDocument`, tách ràng buộc hợp lệ khỏi `unsupported` (gồm `index`, `source`, `reason`).
    - Xử lý V8 (key lạ → warning), V9 / V10 / V11 (lỗi cả tài liệu).
  - Yêu cầu: R2, R3, R7, R11.
  - Xong khi: mỗi quy tắc V1–V11 có ít nhất một test hợp lệ và một test vi phạm, tất cả chạy xanh. Một ràng buộc lỗi không làm hỏng các ràng buộc khác trong cùng tài liệu.

- [ ] **T4 — Xuất JSON Schema** (`app/scheduling/schema.py`, `docs/specs/json_v2/schema.json`, `docs/specs/json_v2/schema.inline.json`)
  - Làm:
    - Lệnh `python -m app.scheduling.schema --export docs/specs/json_v2/`, xuất hai bản: có `$ref` và không có `$ref`.
    - Schema không dùng `oneOf` / `anyOf` ở cấp ràng buộc.
    - Test snapshot so sánh schema xuất ra với file đã commit.
  - Yêu cầu: R3, R8.
  - Xong khi: hai file schema được commit; test snapshot thất bại nếu đổi models mà chưa xuất lại.

## Giai đoạn 3 — Chuẩn hoá

- [ ] **T5 — Chuẩn hoá giá trị** (`app/scheduling/normalize.py`, `tests/scheduling/test_normalize.py`)
  - Làm: các hàm chuẩn hoá cho `day`, `session`, `periods`, `start_period` / `end_period` / `duration`, `start_time` / `end_time`, `area`, `room` (tách khu và phòng), `language`, `class_group`; chuẩn hoá giá trị thứ trong dữ liệu lớp.
  - Dùng lại: logic `normalize_day` (`app/service/constraints_service.py:116`).
  - Yêu cầu: R6, R12.
  - Xong khi: test dạng bảng phủ mọi alias ở design.md mục 7.1–7.3; giá trị không chuẩn hoá được trả về lý do để đưa vào `unsupported`.

- [ ] **T6 — Khớp thực thể** (`app/scheduling/normalize.py`, `tests/scheduling/test_normalize.py`)
  - Làm:
    - Khớp tên môn với danh sách môn đã chọn (design.md mục 7.4).
    - Khớp tên giảng viên với các lớp ứng viên (mục 7.5): làm sạch chức danh bằng regex; khớp theo toàn tên, phần cuối tên, hoặc họ + tên.
    - Khớp nhiều kết quả → warning; giá trị giảng viên không xác định không tham gia so khớp.
  - Yêu cầu: R6, R7.
  - Xong khi: có test cho các ca:
    - "Sơn" khớp nhiều người → warning;
    - "Nguyễn" một mình không khớp ai;
    - `PGS.TS.Nguyễn Thanh Bình` được làm sạch đúng;
    - "Mai Nga" khớp `ThS.Dương Thị Mai Nga`;
    - tên môn không có trong danh sách → `unsupported`.

- [ ] **T7 — Chuẩn hoá cả tài liệu** (`app/scheduling/normalize.py`)
  - Làm: `normalize_document(doc, selected_courses, candidates) -> NormalizedDocument`, gồm:
    - gán ID;
    - chuyển `course` từ điều kiện sang `scope`;
    - tính trọng số (mục 6.5);
    - áp dụng quy tắc ngoại lệ, sinh `exclude` (mục 6.4);
    - phát hiện mâu thuẫn;
    - gộp `unsupported` từ validation, từ chuẩn hoá và từ LLM.
  - Yêu cầu: R5, R6, R7, R9, R13.
  - Xong khi:
    - E31 ra đúng `exclude = [{day: T2}]`;
    - tài liệu 12.2 sinh ra đúng các loại trừ mô tả trong design.md;
    - hai ràng buộc ngược chiều cùng phạm vi sinh warning.

## Giai đoạn 4 — Kiểm thử tổng hợp

- [ ] **T8 — Golden tests** (`tests/scheduling/examples.json`, `tests/scheduling/test_examples.py`)
  - Làm:
    - Trích mọi ví dụ E1–E32 và tài liệu 12.2 từ design.md, mỗi ví dụ gồm JSON đầu vào và kết quả chuẩn hoá mong đợi.
    - Dùng một bộ lớp ứng viên mẫu dựa trên `app/constant/constant_input_test.py`, bổ sung lớp không có lịch và lớp có khu không xác định.
  - Yêu cầu: R1, R2, R7, R8, R12.
  - Xong khi: tất cả ví dụ hợp lệ và chuẩn hoá đúng; 10 mẫu câu v1 không biểu diễn được (E1–E9) đều chạy xanh.

## Giai đoạn 5 — Adapter và công cụ

- [ ] **T9 — Adapter v1 → v2** (`app/scheduling/v1_adapter.py`, `tests/scheduling/test_v1_adapter.py`; bắt buộc vì Q2 xác nhận đã có lịch lưu theo v1)
  - Làm:
    - Hàm chuyển tài liệu v1 sang v2 theo bảng design.md mục 12.1.
    - `parse_document` gọi adapter khi gặp tài liệu v1 (V10).
  - Yêu cầu: R11.
  - Xong khi: `data/prompt.json` chuyển ra đúng 29 ràng buộc ở design.md mục 12.2.

- [ ] **T10 — Endpoint kiểm tra** (tuỳ chọn) `POST /api/preferences/validate`
  - Làm:
    - Endpoint nhận `{courses, preferences}`, trả về ràng buộc đã chuẩn hoá, `unsupported` và `warnings`, không xếp lịch.
    - Thêm docstring Swagger.
    - Mục đích: module LLM tự kiểm tra output của mình.
  - Yêu cầu: R7, R9.
  - Xong khi: gọi được qua Swagger (`/api-docs`) với các ví dụ E1–E32.

## Giai đoạn 6 — Đóng Phần A

- [ ] **T11 — Cập nhật tài liệu**
  - Làm:
    - CLAUDE.md: thêm package `app/scheduling/` và lệnh chạy test.
    - `docs/specs/README.md`: cập nhật bảng trạng thái.
  - Xong khi: một phiên làm việc mới chỉ cần đọc CLAUDE.md và `docs/specs/README.md` là biết trạng thái hiện tại.

- [ ] **T12 — Checkpoint, rồi sang Phần B**
  - Làm:
    - Bạn duyệt kết quả Phần A.
    - Tạo branch Phần B từ branch này, hoặc từ nhánh đã merge Phần A.
    - Viết `docs/specs/algorithms/` (requirements, design, tasks) từ `docs/specs/README.md` mục 7.
  - Xong khi: bảng trạng thái ghi Phần A "đã xong" và Phần B "đang làm".

## Ma trận truy vết

| Yêu cầu | Task |
|---|---|
| R1 Độ phủ biểu đạt | T2, T8 |
| R2 Mỗi ý một cách viết | T3, T7, T8 |
| R3 Gọn, thân thiện với LLM | T3, T4 |
| R4 Mức độ | T2, T7 |
| R5 Ngữ nghĩa xác định | T7; hàm chấm ở Phần B |
| R6 Chuẩn hoá ở server | T2, T5, T6, T7 |
| R7 Không mất thông tin âm thầm | T3, T6, T7, T8, T10 |
| R8 Một nguồn schema | T1, T4, T8 |
| R9 Response giải thích được | T7, T10; response đầy đủ ở Phần B |
| R10 Dễ mở rộng | T2 |
| R11 Phiên bản | T3, T9 |
| R12 Dữ liệu không xác định | T2, T5, T8 |
| R13 Quy tắc chung và ngoại lệ | T7 |
