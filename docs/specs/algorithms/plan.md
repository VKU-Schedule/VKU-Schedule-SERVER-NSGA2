# Phần B — So sánh thuật toán xếp lịch trên JSON v2 và chọn thuật toán

## Context

Phần A (JSON Structure v2) đã xong: `app/scheduling/` chuẩn hoá và validate được tài liệu ràng buộc, nhưng **chưa có hàm chấm, chưa có solver**, và `/api/schedule` vẫn chạy NSGA-II v1 (`app/service/constraints_service.py`) với JSON cũ. Task này là Phần B của lộ trình (`docs/specs/README.md` mục 7): hiện thực các thuật toán trên JSON v2, **chạy thật trên dữ liệu lớp học VKU trong MongoDB**, so sánh, viết report và chọn thuật toán tốt nhất, rồi đưa vào API mới dưới `/api/v2/...`.

Quyết định đã chốt với người dùng:
- Thuật toán so sánh (6 biến thể): **B&B, CP-SAT, SA, GA, NSGA-II gốc (port), NSGA-II cải tiến**.
- Phạm vi: làm trọn tới report **và** tích hợp API, đặt ở `/api/v2/...` (API v1 giữ nguyên, không gỡ).
- Duyệt plan này = duyệt spec Phần B (quy tắc "spec trước, code sau" của CLAUDE.md).
- Thuật toán phải chạy trên bài toán thật, không chỉ benchmark tổng hợp.

## 0. Nhánh và spec

- `git checkout -b feature/algorithm-comparison` từ `feature/new_json_structure`. Thay đổi chưa commit `D data/gemini_batch_translate.py` để nguyên, không đưa vào commit nào.
- Tách README mục 7 thành `docs/specs/algorithms/requirements.md`, `design.md`, `tasks.md` (ngắn gọn, cập nhật theo các quyết định trên). Commit `docs(specs): …`.
- Mỗi bước dưới đây một commit Conventional Commits.

## 1. Engine chấm điểm chung (`app/scheduling/`)

Mọi solver dùng chung một hàm chấm, hiện thực đúng design.md mục 6 và 17.

- `model.py` — `Problem`: danh sách môn, lớp ứng viên mỗi môn (đã ghim cho reschedule), ma trận trùng lịch (cùng thứ + giao tiết; lớp không lịch không trùng ai — 6.7), và bảng tính sẵn theo từng lớp.
  - Dùng lại helper đọc dữ liệu lớp trong `normalize.py`: `class_day_code`, `class_has_schedule`, `class_area`, `class_room`, `class_teacher_known`, `class_group_number`, `class_language`, `class_time_range`; bảng tiết/buổi trong `vocab.py`.
- `constraints.py`:
  - khớp bộ lọc đã chuẩn hoá (`NormalizedFilter`) với một lớp; tính S_c (scope, `exclude`, giá trị không xác định);
  - `prefer`/`avoid` (6.2: prefer buổi/tiết = nằm trọn, avoid = có chạm), 6 chỉ số `limit` (6.3, `subjects_per_day` bình phương), 3 loại `relation` (17.2);
  - quy `review` → ràng buộc `teacher` bằng `review_stats` (17.1: s = (p − q)/(n + 5), T* = k lớn nhất và > 0, khớp tên bằng `match_teachers`);
  - `evaluate(problem, schedule) → (conflicts, H, P, violations[])`, so sánh theo thứ bậc (trùng lịch, H của `must`, P mềm) — 6.6;
  - tách P thành 3 mục tiêu (thời gian / người-nơi / hình dạng lịch) cho NSGA-II cải tiến;
  - báo cáo vi phạm và `infeasible` theo design mục 10.
- `topk.py` — chọn k = 5 lịch đa dạng (đôi một khác ≥ d môn, d = 1 mặc định, nới dần khi không đủ), dùng chung cho mọi solver.
- Test: `tests/scheduling/test_scoring.py` lấy các con số có sẵn trong design.md (E1, E2, E8, E10, E24, E25, E26, ví dụ 6.3, 17.2…) làm ca kiểm; fixtures từ `tests/scheduling/conftest.py`.

## 2. Solvers (`app/scheduling/solvers/`)

Interface chung `solve(problem, k=5, budget, seed) → SolveResult(schedules, evaluations, elapsed_ms, meta)` trong `base.py`.

| File | Thuật toán | Ghi chú |
|---|---|---|
| `bnb.py` | Backtracking + Branch & Bound | Sắp môn theo số lớp tăng dần, cắt nhánh khi trùng lịch; cận dưới từ phạt `prefer`/`avoid` tính sẵn theo lớp; giữ heap top-N rồi qua `topk`. Là đáp án chuẩn. |
| `cpsat.py` | CP-SAT (OR-Tools) | Mô hình theo tuyến tính hoá 6.8 / 17.2; mục tiêu lexicographic (H rồi P); giải lặp, mỗi lần thêm cut "khác các lịch trước ≥ d môn". |
| `sa.py` | Simulated Annealing | Láng giềng: đổi lớp của 1 môn; nhiều lần restart, archive lời giải tốt. |
| `ga.py` | GA đơn mục tiêu | DEAP, tournament + elitism, archive lời giải khác nhau. |
| `nsga2_legacy.py` | NSGA-II gốc | Port nguyên trạng `constraints_service.run_nsga_ii`: DEAP, 1 mục tiêu, pop 30, 50 thế hệ, `cxUniform` + `mutUniformInt`, `eaMuPlusLambda`, seed 42; chỉ thay hàm chấm v1 bằng v2 (trùng lịch → phạt rất lớn như `inf` cũ). Không dùng `creator`/`toolbox` toàn cục. |
| `nsga2.py` | NSGA-II cải tiến | 3 mục tiêu, xử lý ràng buộc theo tính khả thi (Deb), toán tử sửa trùng lịch, chọn 5 điểm đại diện trên front. |

- Thư viện thêm: `ortools` (runtime), `deap` đã có; nghiên cứu: `scipy`, `matplotlib`, `pandas`. Thêm vào `requirements-dev.txt` / `app/requirements.txt`, kiểm tra trên Python 3.12.
- Test: `tests/scheduling/test_solvers.py` — B&B và CP-SAT cùng điểm top-k trên instance nhỏ; giá trị mục tiêu CP-SAT = điểm của hàm chấm chung; mọi solver trả lịch không trùng; metaheuristic đạt tối ưu ở đa số seed trên instance nhỏ.

## 3. Chạy trên bài toán thật + benchmark (`research/benchmark/`)

- `export_classes.py`: **chỉ đọc** `university_db.ly_courses` (qua `MONGO_URI` trong `.env`) → `research/benchmark/data/classes.json` (commit để tái lập). Nếu không kết nối được Mongo thì đọc `data/input/Final_Dataset.xlsx` với cùng ánh xạ cột như `database/embedding/embedding_data.py` và ghi rõ trong report.
- `generate_instances.py` → `instances/*.json` (commit, seed cố định):
  - **Kịch bản thật**: các bộ môn thật n ∈ {3, 5, 7, 9}, phân tầng theo kích thước không gian tìm kiếm (10³ … 10⁹); ràng buộc JSON v2 lấy từ các ví dụ E1–E41 / 12.2 của design.md và mẫu câu trong `validation/data/create_override_data_VIT5.py`; 3 mức nhẹ / vừa / nặng, có `must`, có ca vô nghiệm và ca mâu thuẫn; có ca reschedule (ghim lớp).
  - **Tổng hợp lớn**: n 12–15, 20–50 lớp/môn, để xem lúc nào metaheuristic có lợi.
- `run_benchmark.py`: 6 solver × instance × 30 seed, ngân sách đánh giá bằng nhau cho metaheuristic (1.500 / 5.000 / 20.000); B&B và CP-SAT có giới hạn thời gian → `results/*.csv`.
- `analyze.py`: bảng + biểu đồ; Friedman rồi Wilcoxon–Holm.
- Chỉ số: tỉ lệ khả thi, phạt tốt nhất / trung bình của 5 lịch, gap so với top-5 chính xác, độ đa dạng (Hamming), thời gian median / p95, số lần đánh giá, độ lệch giữa các seed, tỉ lệ đạt tối ưu; hypervolume cho hai bản NSGA-II.
- `case_study.py`: vài yêu cầu thật của sinh viên (ví dụ câu "đầy đủ" trong llm-guide mục 7) chạy qua cả 6 solver, in 5 lịch mỗi solver kèm vi phạm — đưa vào report làm minh hoạ cụ thể.

## 4. Report

`docs/algorithm-comparison.md` (tiếng Việt, dùng được cho chương thực nghiệm): bài toán và mô hình; mô tả 6 thuật toán và độ phức tạp; thiết lập thực nghiệm; kết quả (bảng, biểu đồ, kiểm định); case study trên dữ liệu thật; hạn chế; **kết luận chọn thuật toán dựa trên số liệu** (kèm phương án dự phòng cho ca xấu nhất). Số liệu nào chưa chạy được thì ghi rõ, không suy đoán.

## 5. API v2

- `app/api/v2/schedule_api.py`, blueprint đăng ký ở `app/main.py` với prefix `/api/v2`:
  - `POST /api/v2/schedule` — request/response theo design.md mục 10 (`courses`, `preferences`, `review_stats`, `k`; trả `schedules` có `hard_violations`, `penalty`, `violations`, cùng `constraints`, `unsupported`, `warnings`, `infeasible`, `meta.algorithm`, `meta.elapsed_ms`).
  - `POST /api/v2/reschedule` — thêm `pinned`.
  - Tham số tuỳ chọn `algorithm` (mặc định = thuật toán thắng) để gọi bất kỳ solver nào trên dữ liệu thật.
- Dùng lại cách nạp lớp từ Mongo của `app/api/schedule_api.py` và luồng `parse_document` → `normalize_document` của `app/api/preferences_api.py`. Docstring YAML cho Swagger.
- API v1 (`/api/schedule`, `/api/reschedule`, `constraints_service.py`) không đổi.
- Test bằng Flask test client với lớp giả (không cần Mongo): `tests/scheduling/test_schedule_api_v2.py`.

## 6. Cập nhật tài liệu

`docs/specs/README.md` (bảng trạng thái mục 5, mục 7 trỏ sang `algorithms/`), `CLAUDE.md` (kiến trúc mới, lệnh benchmark, API v2).

## Verification

1. `.venv/bin/python -m pytest` — 432 test cũ vẫn qua, cộng test chấm điểm, solver, API v2.
2. B&B và CP-SAT trùng điểm top-k trên mọi instance nhỏ; mục tiêu CP-SAT = hàm chấm chung.
3. `python research/benchmark/run_benchmark.py` chạy lại ra cùng CSV (seed cố định).
4. End-to-end trên dữ liệu thật: `python -m app.main`, `POST /api/v2/schedule` với một ví dụ JSON v2 và môn thật trong Mongo → 5 lịch không trùng, kèm báo cáo vi phạm; thử lần lượt `algorithm` = 6 solver.
5. Report: mọi con số trong `docs/algorithm-comparison.md` truy được về `results/*.csv`.

## Rủi ro

- Không kết nối được MongoDB từ máy này → dùng xlsx cho benchmark, API v2 kiểm bằng test client; nói rõ trong report.
- Benchmark đầy đủ (30 seed × 3 ngân sách) có thể chạy lâu → chạy nền; nếu quá lâu thì giảm lưới và ghi rõ phần đã giảm.
