# Phần B — Tasks

Branch: `feature/algorithm-comparison` (từ `feature/new_json_structure`).

- [ ] **B1** Spec: `requirements.md`, `design.md`, `tasks.md`, `plan.md`
- [ ] **B2** `model.py`: `ClassView`, `Problem`, `build_problem` (gộp lớp trùng hệt, ghim)
- [ ] **B3** `constraints.py`: khớp bộ lọc, S_c, biên dịch ràng buộc, quy `review`, `evaluate`, `explain`, 3 mục tiêu
- [ ] **B4** `topk.py`: chọn k lịch đa dạng
- [ ] **B5** Test hàm chấm (`tests/scheduling/test_scoring.py`)
- [ ] **B6** Solvers: `bnb`, `cpsat`, `sa`, `ga`, `nsga2_legacy`, `nsga2`
- [ ] **B7** Test solver (`tests/scheduling/test_solvers.py`): bnb = cpsat; mục tiêu CP-SAT = hàm chấm; không trùng lịch
- [ ] **B8** `research/benchmark/`: export dữ liệu Mongo, sinh instance
- [ ] **B9** Chạy benchmark, phân tích, case study
- [ ] **B10** Report `docs/algorithm-comparison.md`, chọn thuật toán
- [ ] **B11** API `/api/v2/schedule`, `/api/v2/reschedule` + test
- [ ] **B12** Cập nhật `docs/specs/README.md`, `CLAUDE.md`
