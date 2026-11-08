# Plan: tăng độ đa dạng của type `unsupported` (n8n) và viết spec cho `review` và `relation`

> Trạng thái: đã duyệt plan (2026-11-08). Phần 2 là spec đề xuất, chờ duyệt trước khi code.

## Context

Tab `[NEW] unsupported` (200 câu) do workflow `validation/n8n/generate_single_sentences.workflow.json` sinh ra có nhiều câu lặp:
- Chỉ có 4 style: `lich_su`, `co_ly_do`, `nho_va`, `nhan_tin`. Lý do là mỗi lượt gọi AI chỉ dùng một style, và 200 câu chỉ cần 4 lượt.
- Theme được chọn ngẫu nhiên nên không đều. Theme `doi_khu` có sẵn câu mẫu, AI chép gần nguyên văn khoảng 30 lần.
- Chỉ có 11 theme, và mỗi theme có ít giá trị để điền vào.

Hai nhóm câu đang nằm trong `unsupported` thật ra **có thể biểu diễn được** nếu mở rộng JSON v2:
- Câu có cột `supported_by_review_service = yes`, kiểu giảng viên dễ hiểu, dễ tính, chấm thoáng. VKU_SA_Model_Service (`POST /predict` → `{sentiment, aspect}`) xác định được aspect của câu. Bảng Review (`ID, Text, Sentiment, Aspect, Subject, Lecturer`) cho biết giảng viên nào được đánh giá tốt ở aspect đó. Câu `yes` về phòng (máy lạnh, wifi…) thì không quy về đối tượng cụ thể được, vì bảng Review không có cột phòng.
- Câu có remark `xem xét bổ sung kiểu JSON`: hai môn học cùng ngày, khác ngày, hoặc môn A học trước môn B.

Những điểm user đã chốt:
- **Bỏ hẳn ý "đổi khu giữa hai lớp liền nhau".** Thời khoá biểu cố định của trường đã tự xử lý việc này.
- **Thêm type `review`.** Type này dành cho câu thuộc các khía cạnh mà SA review service hỗ trợ (11 aspect; 8 aspect gắn với giảng viên dùng được, xem 2.1). LLM chỉ đánh dấu và chép cụm mô tả. Việc chọn đối tượng cụ thể trong từng khía cạnh để thuật toán xếp lịch làm sau, ở Phần B.
- **Thêm loại ràng buộc `relation`** với 3 giá trị: `same_day`, `different_day`, `before`.
- **Phạm vi lần này:** sửa n8n cho `unsupported` và viết spec bổ sung để user duyệt. Chưa code `app/scheduling`, chưa thêm type mới vào n8n, vì theo CLAUDE.md spec phải được duyệt trước.

## Phần 1 — Workflow n8n: tăng độ đa dạng cho `unsupported`

File: `validation/n8n/generate_single_sentences.workflow.json`. Sửa code trong 3 node.

### Node `Dataset Config` (`UNSUPPORTED_THEMES`, `UNSUPPORTED_FILL`)

Bỏ các theme sau:
- `doi_khu`: trường đã hỗ trợ.
- `giang_vien`: chuyển sang type `review`. Giữ `co_so_vat_chat`, vì bảng Review không có cột phòng (xem 2.1).
- `thu_tu_mon` và `cung_ngay`: chuyển sang type `relation`.

Viết lại `text` của mỗi theme để chỉ mô tả *ý*, không đưa câu mẫu, để AI không chép nguyên văn.

Mở rộng các theme cũ và tăng số giá trị điền:
- `lich_thi`: thêm "thi trên máy", "không thi cuối tuần", "thi cùng phòng".
- `ban_be`: thêm "bạn cùng phòng trọ", "anh chị khoá trên"; thêm tên bạn và mã lớp sinh hoạt.
- `online`, `si_so`, `tuan_hoc`, `lop_sinh_hoat`: thêm cách nói khác.

Thêm theme mới. Câu nào cũng không được nhắc thứ, buổi, tiết, giờ hay tên môn, và không rơi vào 11 khía cạnh của review:
- `vi_tri_phong`: phòng gần nhà xe, căng tin hoặc thư viện; phòng ở tầng thấp; phòng gần thang máy. Đây là vị trí phòng, không phải chất lượng thiết bị.
- `giang_vien_ca_nhan`: giảng viên nữ hoặc nam, giảng viên trẻ, có học vị tiến sĩ, người nước ngoài. Không nêu tên. Đây là đặc điểm cá nhân, không phải khía cạnh review.
- `tin_chi`: tổng tín chỉ không quá N, đăng ký đủ số tín chỉ tối thiểu.
- `loai_lop`: lớp chất lượng cao, lớp học phí thấp.
- `hoat_dong_ngoai`: không trùng lịch câu lạc bộ, thực tập hoặc đội tuyển, không nêu giờ.
- `hoc_lai`: học lại hoặc học cải thiện cùng lớp cũ.
- `tinh_nang`: nhắc lịch, xuất lịch sang Google Calendar, gửi lịch qua email.

Mỗi theme mới có regex `re` riêng, viết theo cách đang dùng: so trên câu đã bỏ dấu, có khoảng trắng ở hai đầu.

### Node `Compute Batch` (`makeUnsupportedSlot` và phần dựng prompt)

- **Chia đều theme trong một batch.** Xáo trộn danh sách theme một lần, rồi slot i lấy `themes[(i + attempt) % n]` thay cho `pick(...)`.
- **Gán style theo từng slot, chỉ cho `unsupported`.** Slot i dùng `cfg.styles[(i + attempt) % 8]` và ghi style ngay trong dòng mô tả slot, để một batch có đủ 8 style. Các type khác giữ cách cũ.
- **Thêm vào prompt:** "Chủ đề chỉ là ý; viết bằng lời của sinh viên, không chép nguyên văn; không mở đầu giống các câu đã có."

### Node `Parse & Validate`

- **Loại câu gần trùng.** Bỏ dấu và tách token, rồi so Jaccard với:
  - các câu `existing` (lấy từ output của Compute Batch, theo cách node này đang đọc `slots`);
  - các câu đã nhận trong cùng batch.

  Nếu Jaccard ≥ 0,75 thì loại câu, ghi lý do "gần trùng câu đã có". Áp dụng cho mọi type.
- Cột `style` lấy theo slot nếu slot có ghi style.

### Việc user làm trên Google Sheet

Ghi cả vào sticky `Ghi chú`:
- **Xoá** các dòng `doi_khu`: câu có "di chuyển / chạy / qua lại … khu K … khu V".
- **Chuyển** các dòng `yes` và `xem xét bổ sung kiểu JSON` sang tab `[RELABEL] unsupported`. Các dòng này sẽ làm seed cho type `review` và `relation`.
- **Chạy lại** với `onlyTypes = unsupported`, và tăng `targetPerType` (ví dụ 400) để sinh thêm câu.

## Phần 2 — Spec bổ sung (để duyệt, chưa code)

Viết thẳng vào `docs/specs/json_v2/`, mỗi phần mở rộng ghi rõ "A2 — đề xuất, chờ duyệt":
- `requirements.md`: thêm mục yêu cầu A2.
- `design.md`: thêm **mục 17 "Mở rộng A2: `review` và `relation`"** ở cuối file (design đã có tới mục 16), gồm nội dung 2.1–2.3 bên dưới.
  - Ví dụ dùng tiêu đề `### R1`…`### R6`.
  - Regex `_HEADING` trong `tests/scheduling/conftest.py` chỉ khớp `### E\d+` và `### 12.2`, nên golden test không parse các ví dụ có key mới và `test_examples.py` vẫn pass.
  - Mục 13 (E1–E32) giữ nguyên.
- `tasks.md`: thêm "Giai đoạn 7 — Mở rộng A2", các task T13–T18 chưa đánh dấu (xem 2.4).
- `llm-guide.md`: chưa sửa. Chỉ cập nhật khi code (task T17), để LLM không học key chưa được duyệt.
- `docs/specs/README.md`: thêm dòng "A2 — Mở rộng: review, relation" vào bảng trạng thái mục 5.

### 2.1 Thuộc tính `review` (Filter, 11 khía cạnh của SA review service)

- **LLM ghi**, giá trị là cụm mô tả chép nguyên văn:
  - `{"prefer": {"review": "giảng viên dạy dễ hiểu"}, "scope": {"course": "X"}}`
  - `{"avoid": {"review": "giảng viên chấm điểm khắt khe"}}`
  - `{"prefer": {"review": "thầy cô nhiệt tình"}}`
- **Chuẩn hoá ở repo này** (nhẹ): gọi SA `/predict` với cụm đó, rồi lưu `aspect` (một trong 11 giá trị) và `sentiment` vào ràng buộc đã chuẩn hoá.
  - Gọi SA qua interface `SentimentProvider` được inject, có bản fake để test.
  - SA lỗi → ràng buộc vẫn giữ, kèm warning, `aspect = null`. Không âm thầm bỏ ràng buộc.
- **Cách thuật toán tìm đối tượng cụ thể** (ghi trong spec dưới dạng hướng đi cho Phần B; code ở Phần B). Bảng `Review` có `ID, Text, Sentiment, Aspect, Subject, Lecturer`, nên đối tượng tìm được là **giảng viên của một môn**.
  1. **Lọc:** `Subject = môn trong scope` (thiếu scope thì lấy mọi môn đã chọn) và `Aspect = aspect của ràng buộc`. Aspect `noi_chung` thì lấy mọi aspect.
  2. **Gom theo `Lecturer`:** đếm số review positive (p), negative (q) và tổng (n).
  3. **Tính điểm:** dùng điểm làm trơn s = (p − q) / (n + α), α = 5, để giảng viên có ít review không lấn át người có nhiều review. Giảng viên có n = 0 thì coi là "không xác định", giống quy tắc 6.7.
  4. **Ghép tên:** so `Lecturer` với giảng viên của các lớp ứng viên, dùng lại cách khớp tên ở design 7.5 / `normalize.py`.
  5. **Đổi thành ràng buộc có sẵn:**
     - `prefer` → `prefer {teacher: giảng viên có s cao nhất}`;
     - `avoid` → `avoid {teacher: giảng viên có s thấp nhất}`, xếp hạng theo sentiment của cụm.

     Từ đây scorer và solver xử lý như mọi ràng buộc `teacher`. Có thể nâng cấp sau: phạt theo mức, a_l = 1 − chuẩn hoá(s), vẫn tuyến tính hoá được theo 6.8.
- **Giới hạn của dữ liệu:** bảng `Review` không có cột phòng. Vì vậy:
  - Câu về phòng (máy lạnh, wifi, ổ cắm, bàn ghế; aspect `thiet_bi_day_hoc`) **không** quy được về một phòng cụ thể, nên vẫn để ở `unsupported`. Theme `co_so_vat_chat` trong n8n được giữ lại.
  - Aspect `chuong_trinh_hoc`, `de_xuat` nói về môn học, không về người dạy. Với các aspect này thì báo warning và chuyển vào `unsupported`.
  - Như vậy `review` dùng được cho 8 aspect: `ky_nang_giang_day`, `kinh_nghiem`, `hanh_vi`, `bai_tap`, `cham_diem`, `cung_cap_tai_lieu`, `kien_thuc`, `noi_chung`.
- **Trọng số tạm:** 4, nhóm Người, chỉnh được trong `vocab.py`.
- **Quy tắc ngoại lệ:** nhóm theo key `{review}`, như các thuộc tính khác.

### 2.2 Loại ràng buộc `relation` (loại thứ 4, cạnh `prefer` / `avoid` / `limit`)

**Cú pháp.** `{"relation": "same_day" | "different_day" | "before", "courses": ["A", "B"], "level"?: ...}`
- Không có `scope`.
- `courses` gồm đúng 2 môn khác nhau trong danh sách đã chọn. Kiểm tra bằng rule V12; vi phạm thì chuyển vào `unsupported`.

**Phạt.** Gọi D_A, D_B là tập các thứ có lớp được chọn của môn A và môn B. Lớp không có lịch không được tính (design 6.7).
- `same_day`: v = 1 nếu D_A ∩ D_B = ∅; ngược lại v = 0.
- `different_day` (dùng cho cả "không cùng ngày" và "hai ngày khác nhau"): v = |D_A ∩ D_B|.
- `before` ("A trước B trong cùng ngày"):
  - nếu D_A ∩ D_B = ∅ thì v = 1;
  - ngược lại, v = số ngày chung mà lớp A không bắt đầu trước lớp B.

**Trọng số:** 3, nhóm Mốc thời gian.

**Quy tắc ngoại lệ:** `relation` không thuộc nhóm nào.

**Tuyến tính hoá:** tính trước chi phí c(l_A, l_B) cho từng cặp lớp ứng viên; đặt z ≥ x_A + x_B − 1; v = Σ c·z.

### 2.3 Dataset và llm-guide (ghi trong design của spec mới, áp dụng khi code)

- **Số type tăng từ 33 lên 38:**
  - `prefer_review`, `avoid_review`: cùng cú pháp `prefer` / `avoid` như các thuộc tính khác;
  - `relation_same_day`, `relation_different_day`, `relation_before`.
- **Gán lại nhãn cho tab `[RELABEL] unsupported`:**
  - câu `yes` về giảng viên → `prefer_review`;
  - câu `yes` về phòng → trả về `unsupported`;
  - câu `xem xét` → type `relation` tương ứng.
- **Bỏ ví dụ "chạy từ khu K sang khu V"** ở llm-guide mục 6.C và E28; thay bằng ví dụ unsupported khác.
- **Ví dụ R1–R6**, mỗi ví dụ có JSON đầu vào, kết quả chuẩn hoá mong đợi và giá trị phạt mẫu cho `relation`:
  - `review` cho giảng viên;
  - `review` cho phòng, kết quả: vào `unsupported` kèm warning;
  - 3 ví dụ `relation`;
  - 1 ví dụ hỗn hợp có `unsupported`.

  Dùng tiêu đề `### R…` để không khớp regex `### E…` của golden test.

### 2.4 Giai đoạn 7 trong `tasks.md` (chưa làm lần này)

- `vocab.py`: thêm thuộc tính `review`, thêm `relation`.
- `schema.py`: thêm model `Relation` và rule V12; export lại schema.
- `normalize.py`: thêm `SentimentProvider`, gồm bản HTTP và bản fake.
- Tests: golden R1–R6.
- Gộp nội dung vào `json_v2/design.md` và `llm-guide.md`.
- n8n: thêm 5 type vào `TYPES`, kèm slot và kiểm tra tương ứng trong `Compute Batch` / `Parse & Validate`.
- Phần B: chọn đối tượng theo review, và chấm phạt `review` / `relation`.

## File sẽ sửa hoặc tạo

- **Bước đầu tiên:** lưu nguyên nội dung plan này vào `docs/specs/json_v2/plan-a2-review-relation.md`. File này vào commit `docs(specs)`.
- `validation/n8n/generate_single_sentences.workflow.json`: sửa code của 3 node và sticky `Ghi chú`.
- `docs/specs/json_v2/requirements.md`, `design.md` (mục 17), `tasks.md` (Giai đoạn 7): thêm phần A2.
- `docs/specs/README.md`: thêm dòng trạng thái A2.

Hai commit theo Conventional Commits:
- `feat(validation): diversify unsupported sentence generation`
- `docs(specs): propose review and relation extension`

## Kiểm tra

- Tách `jsCode` của 3 node ra file tạm trong scratchpad, chạy `node --check` cho từng file.
- Chạy harness nhỏ với `cfg` giả:
  - in 20 slot `unsupported` để thấy đủ theme và style, không còn `doi_khu`;
  - thử hàm Jaccard trên vài cặp câu trùng và gần trùng.
- Kiểm tra workflow vẫn là JSON hợp lệ: `python3 -c "import json; json.load(open(...))"`.
- Nếu có n8n MCP thì chạy `validate_workflow`. Sau đó user chạy workflow với `onlyTypes = unsupported` và xem phân bố theme và style.
- Chạy `.venv/bin/python -m pytest` để chắc golden test vẫn pass. Lần này không đụng code.
