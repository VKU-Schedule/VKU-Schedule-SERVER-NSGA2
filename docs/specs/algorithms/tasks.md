# Phần B — Tasks

Branch: `feature/algorithm-comparison` (từ `feature/new_json_structure`).

- [x] **B1** Spec: `requirements.md`, `design.md`, `tasks.md`, `plan.md`
- [x] **B2** `model.py`: `ClassView`, `Problem`, `build_problem` (gộp lớp trùng hệt, ghim)
- [x] **B3** `constraints.py`: khớp bộ lọc, S_c, biên dịch ràng buộc, quy `review`, `evaluate`, `explain`, 3 mục tiêu
- [x] **B4** `topk.py`: chọn k lịch đa dạng
- [x] **B5** Test hàm chấm (`tests/scheduling/test_scoring.py`)
- [x] **B6** Solvers: `bnb`, `cpsat`, `sa`, `ga`, `nsga2_legacy`, `nsga2`
- [x] **B7** Test solver (`tests/scheduling/test_solvers.py`): bnb = cpsat; mục tiêu CP-SAT = hàm chấm; không trùng lịch
- [x] **B8** `research/benchmark/`: export dữ liệu Mongo, sinh instance
- [x] **B9** Chạy benchmark, phân tích, case study
- [x] **B10** Report `docs/algorithm-comparison.md`, chọn thuật toán
- [x] **B11** API `/api/v2/schedule`, `/api/v2/reschedule` + test
- [x] **B12** Cập nhật `docs/specs/README.md`, `CLAUDE.md`
