# Lộ trình nghiên cứu: JSON Structure v2 và thuật toán xếp lịch

> Đọc file này trước khi bắt đầu bất kỳ phần nào. File này là nguồn duy nhất về lộ trình, các quyết định đã chốt và trạng thái từng phần. Mỗi khi một phần đổi trạng thái, cập nhật bảng ở mục 5.

## 1. Bối cảnh

Đây là đồ án tốt nghiệp: hệ thống xếp thời khoá biểu cá nhân cho sinh viên VKU.

```
Văn bản yêu cầu của sinh viên
        │
        ▼
Module LLM (fine-tune, module riêng)  ──►  JSON ràng buộc
                                                │
                                                ▼
                                Module xếp lịch (repo này)  ──►  ~5 lịch để sinh viên chọn
```

Nghiên cứu cần cho ra hai kết quả:
1. **JSON Structure v2:** cấu trúc ràng buộc mới, thay cho schema v1 (`data/docs-feature.md`).
2. **Thuật toán xếp lịch phù hợp nhất:** chọn dựa trên so sánh thực nghiệm giữa nhiều thuật toán.

## 2. Quyết định đã chốt (2026-10-18)

| # | Quyết định | Ghi chú |
|---|---|---|
| 1 | JSON v2 theo hướng "ngữ pháp cố định, tổ hợp mở" | Tài liệu là danh sách phẳng các ràng buộc nguyên tử. Mỗi ràng buộc gồm phạm vi, điều kiện hoặc chỉ số, và mức độ; kèm kênh `unsupported`. Đã loại hai hướng khác: schema cố định liệt kê mọi trường hợp, và schema mở để LLM tự sinh code |
| 2 | Thuật toán chọn theo kết quả so sánh | Không bắt buộc NSGA-II; NSGA-II chỉ là một ứng viên |
| 3 | Đầu ra: khoảng 5 lịch | Các lịch phải khả thi, tốt, và đủ khác nhau để sinh viên chọn |
| 4 | Module fine-tune LLM là module riêng | Repo này chỉ cung cấp cho module đó JSON Schema, ví dụ và hướng dẫn viết |
| 5 | Không xét cột `Tuần học` | Hai lớp trùng lịch khi cùng thứ và có tiết giao nhau |
| 6 | Code hiện tại trong `app/` viết theo schema v1 | Sẽ được thay thế. Chỉ cần tương thích ngược nếu đã có lịch lưu theo định dạng v1 |

## 3. Dữ kiện dữ liệu (`data/input/Final_Dataset.xlsx`)

- **Quy mô:**
  - 809 lớp thuộc 184 môn.
  - Số lớp mỗi môn: trung vị 2, trung bình 4,4, tối đa 31 (Tiếng Anh chuyên ngành 2).
  - Một yêu cầu 7 môn thường có 10³–10⁵ tổ hợp lớp. Ca xấu nhất, khi chọn toàn môn đông lớp, khoảng 10⁹.
- **Lớp không có lịch:** 89 lớp (11%), với `Tiết = []` và `Thứ` là `Thứ _` hoặc trống.
- **Giá trị không xác định:**
  - khu vực `Khác`, `(Chọn)`, `Chưa xếp phòng`, `-`;
  - phòng `_`;
  - giảng viên dạng `Khoa.…` hoặc `.`;
  - 27 lớp thiếu số nhóm lớp.
- **Thứ và tiết:**
  - Thứ chỉ có từ Thứ Hai đến Thứ Bảy, không có Chủ nhật.
  - Tiết lớn nhất là 9.
  - Mỗi lớp dài 2–5 tiết, bắt đầu ở tiết 1, 2, 3, 6, 7 hoặc 8.
- **Giá trị khác:**
  - Nhóm lớp (cột `Lớp`) là chuỗi số từ `"1"` đến `"22"`.
  - Ngôn ngữ: Tiếng Việt (725 lớp), Tiếng Anh (84 lớp).

## 4. Quy trình làm việc

- **Spec trước, code sau.** Mỗi phần có một thư mục trong `docs/specs/`, gồm 3 file:
  - `requirements.md`: làm gì, tại sao;
  - `design.md`: làm thế nào;
  - `tasks.md`: các bước, dạng checklist.
- Chỉ viết code sau khi spec của phần đó được duyệt.
- **Mỗi phần một branch.** Phần trước được duyệt xong mới sang phần sau.
- **Branch của Phần B** tạo từ `feature/new_json_structure`, hoặc từ nhánh đã merge Phần A, để có đủ tài liệu và code của Phần A.

## 5. Trạng thái

| Phần | Nội dung | Branch | Spec | Trạng thái |
|---|---|---|---|---|
| A | JSON Structure v2 | `feature/new_json_structure` | [`json_v2/`](json_v2/) | Đã viết spec, chờ duyệt |
| B | Thuật toán và so sánh | chưa tạo | `algorithms/` (chưa tạo) | Chưa bắt đầu; kế hoạch ở mục 7 |

## 6. Phần A — JSON Structure v2 (tóm tắt)

- **Mục tiêu:** thiết kế "hợp đồng" giữa module LLM và module xếp lịch. JSON v2 phải:
  - biểu đạt được hầu hết yêu cầu thực tế với phạm vi tuỳ ý;
  - dễ cho LLM sinh đúng;
  - có ngữ nghĩa phạt chính xác;
  - không làm mất thông tin âm thầm.
- **Sản phẩm:**
  - spec trong `json_v2/`;
  - sau khi spec được duyệt mới đến code: package `app/scheduling/` (`vocab.py`, `schema.py` dùng Pydantic, `normalize.py`), JSON Schema xuất ra `json_v2/schema.json`, và tests.
- **Ranh giới với Phần B:** Phần A định nghĩa ngữ nghĩa phạt của từng ràng buộc. Phần B hiện thực hàm chấm và các thuật toán dựa trên ngữ nghĩa đó.
- **Chi tiết:** [`json_v2/requirements.md`](json_v2/requirements.md), [`json_v2/design.md`](json_v2/design.md), [`json_v2/tasks.md`](json_v2/tasks.md).

## 7. Phần B — Thuật toán và so sánh (kế hoạch)

> Khi bắt đầu Phần B: tạo branch mới, rồi tách mục này thành `docs/specs/algorithms/requirements.md`, `design.md`, `tasks.md`.

### 7.1 Bài toán

- **Biến quyết định:** chọn đúng một lớp cho mỗi môn: x ∈ S₁ × … × Sₙ, với Sᵢ là các lớp ứng viên của môn i.
- **Ràng buộc cứng:**
  - không trùng lịch (cùng thứ và có tiết giao nhau);
  - mọi ràng buộc `must` trong JSON v2.
- **Mục tiêu:** tối thiểu tổng phạt mềm có trọng số, theo ngữ nghĩa ở `json_v2/design.md` mục 6.
- **Đầu ra:** k = 5 lịch.
- **`/reschedule`:** các lớp đã đăng ký thành công được ghim, tức môn đó chỉ còn đúng một lớp ứng viên.

### 7.2 Hai cách định nghĩa "5 lịch"

So sánh hai cách này cũng là một câu hỏi nghiên cứu.
- **Top-k đa dạng:** 5 lịch có phạt thấp nhất, đôi một khác nhau ít nhất d môn.
- **Pareto:** tách phạt mềm thành 3 mục tiêu, rồi chọn 5 lịch đại diện trên mặt Pareto:
  - thời gian: thứ, buổi, tiết, giờ;
  - người và nơi: giảng viên, nhóm lớp, khu, phòng, ngôn ngữ;
  - hình dạng lịch: các ràng buộc `limit`.

### 7.3 Thuật toán đưa vào so sánh

| Nhóm | Thuật toán | Cách ra 5 lịch | Lý do đưa vào |
|---|---|---|---|
| Chính xác | Backtracking + Branch & Bound | Giữ heap top-k trong lúc duyệt, rồi chọn đa dạng | Đơn giản; cho đáp án đúng để làm chuẩn so sánh |
| Chính xác | CP-SAT (OR-Tools) | Giải lặp; mỗi lần thêm ràng buộc "khác các lịch trước ít nhất d môn" | Tối ưu được chứng minh; chịu được ca xấu nhất |
| Đơn mục tiêu | GA có cơ chế giữ đa dạng | 5 cá thể tốt nhất, khác nhau, trong archive | Baseline tiến hoá cổ điển |
| Đơn mục tiêu | Simulated Annealing | Archive các lời giải tốt qua nhiều lần chạy | Baseline local search |
| Đa mục tiêu | NSGA-II, sửa lại: xử lý ràng buộc theo tính khả thi, sửa lời giải bị trùng lịch | 5 điểm đại diện trên front (crowding hoặc phân cụm) | Thuật toán của hệ thống cũ |
| Đa mục tiêu | MOEA/D (hoặc NSGA-III) | Các vector trọng số tương ứng với các kiểu đánh đổi | Ánh xạ tự nhiên: 5 hướng ưu tiên ↔ 5 lịch |
| Tuỳ chọn | ACO; NSGA-II + local search (memetic) | — | Nếu còn thời gian |

### 7.4 Thiết kế thực nghiệm

- **Instance từ dữ liệu thật:**
  - tập môn n ∈ {3, 5, 7, 9}, phân tầng theo kích thước không gian tìm kiếm (nhỏ, vừa, lớn);
  - bộ ràng buộc sinh tự động từ 49 mẫu câu trong `validation/data/create_override_data_VIT5.py`, viết thẳng bằng JSON v2 nên nhãn chắc chắn đúng, không qua LLM;
  - 3 mức: nhẹ 1–3, vừa 4–6, nặng 7–10 ràng buộc, có kèm `must`;
  - có cả ca vô nghiệm và ca ràng buộc mâu thuẫn.
- **Instance tổng hợp lớn:** n 12–15, 20–50 lớp/môn, để tìm điểm mà metaheuristic bắt đầu có lợi.
- **Công bằng:**
  - mọi thuật toán được chấm bằng cùng một hàm chấm chung;
  - metaheuristic dùng cùng ngân sách số lần đánh giá (ví dụ 1.500 / 5.000 / 20.000), tham số tinh chỉnh bằng grid nhỏ;
  - chạy 30 seed cho mỗi cặp thuật toán × instance.
- **Tái lập:** seed cố định, file instance được commit vào repo.

### 7.5 Chỉ số đo

- Tỉ lệ khả thi: cả 5 lịch đều thoả ràng buộc cứng khi bài toán có nghiệm.
- Chất lượng: phạt tốt nhất và trung bình của 5 lịch; chênh lệch so với top-5 chính xác (do B&B hoặc CP-SAT tìm ra).
- Độ đa dạng: khoảng cách Hamming trung bình giữa các lịch.
- Với cách Pareto: hypervolume và IGD, so với front chính xác lấy từ duyệt toàn bộ ở instance nhỏ.
- Thời gian chạy: median và p95; số lần đánh giá.
- Độ ổn định: độ lệch chuẩn giữa các seed; tỉ lệ đạt tối ưu.

### 7.6 Kiểm định thống kê

Friedman test, rồi post-hoc (Wilcoxon với hiệu chỉnh Holm, hoặc Nemenyi).

### 7.7 Giả thuyết (để số liệu xác nhận hay bác bỏ)

- Ở quy mô VKU, B&B và CP-SAT cho top-5 tối ưu nhanh hơn metaheuristic.
- Metaheuristic chỉ có lợi khi không gian tìm kiếm lớn, hoặc khi cần nhiều kiểu đánh đổi.
- Kết luận chọn thuật toán dựa trên số liệu.
- Tuỳ chọn: khảo sát nhỏ, cho sinh viên chấm 5 lịch của cách top-k và 5 lịch của cách Pareto.

### 7.8 Kiến trúc code dự kiến

```
app/scheduling/            # Phần A tạo vocab.py, schema.py, normalize.py
  model.py                 # Problem: lớp ứng viên, ma trận trùng lịch, bảng phạt tính sẵn
  constraints.py           # bộ lọc, registry chỉ số, hàm chấm chung, báo cáo vi phạm
  topk.py                  # chọn 5 lịch đa dạng, dùng chung cho mọi solver
  solvers/                 # base.py (interface solve(problem, k, budget, seed)), enumerate.py,
                           # cpsat.py, ga.py, sa.py, nsga2.py, moead.py
research/benchmark/        # không đóng gói vào Docker
  generate_instances.py, instances/, run_benchmark.py, analyze.py  →  results/*.csv, biểu đồ
docs/algorithm-comparison.md
```

- **Thư viện:**
  - `ortools` cho CP-SAT;
  - `pymoo` cho GA, NSGA-II, NSGA-III, MOEA/D, có sẵn hypervolume và IGD;
  - chỉ dùng cho nghiên cứu: `pandas`, `matplotlib`, `scipy`.
  - Kiểm tra tương thích Python 3.12 khi cài.
- **Dùng lại:** `normalize_day`, `SCHEDULE_OF_CLASSES`, phần lõi tính toán của các hàm chấm v1.

### 7.9 Các bước

1. **Engine:** `model.py` và `constraints.py` hiện thực ngữ nghĩa ở `json_v2/design.md` mục 6, kèm test.
2. **Solvers:**
   - `enumerate` trước, làm chuẩn đúng cho các bước sau;
   - rồi `cpsat`;
   - rồi `ga`, `sa`, `nsga2`, `moead`, cùng `topk`.
3. **Benchmark:** sinh instance, chạy, thống kê, vẽ biểu đồ. Kết quả viết vào `docs/algorithm-comparison.md` cho chương thực nghiệm.
4. **Tích hợp:** chọn thuật toán theo kết quả benchmark.
   - `/api/schedule` nhận JSON v2, trả 5 lịch kèm báo cáo theo `json_v2/design.md` mục 10.
   - `/api/reschedule` ghim các lớp đã đăng ký.
   - Gỡ code v1.
5. **Cập nhật** CLAUDE.md và bảng trạng thái ở mục 5.

### 7.10 Verification

- `enumerate` và `cpsat` cho cùng điểm top-k trên mọi instance nhỏ.
- Giá trị mục tiêu của CP-SAT bằng điểm của hàm chấm chung.
- Trên instance nhỏ, metaheuristic đạt tối ưu ở đa số seed.
- Benchmark tái lập được.
- End-to-end: `POST /api/schedule` với một ví dụ JSON v2, nhận về 5 lịch khả thi kèm báo cáo.

### 7.11 Đầu vào từ Phần A

- Ràng buộc đã chuẩn hoá (`NormalizedDocument`, `json_v2/design.md` mục 9).
- Ngữ nghĩa phạt và cách tuyến tính hoá (`json_v2/design.md` mục 6).
- Các ví dụ có sẵn kết quả, dùng làm ca test đầu tiên cho hàm chấm.

## 8. Ghi chú

- **Bảo mật:** `data/gemini_batch_translate.py:7` chứa Gemini API key viết thẳng trong code và đã commit vào git. Cần thu hồi key đó.
