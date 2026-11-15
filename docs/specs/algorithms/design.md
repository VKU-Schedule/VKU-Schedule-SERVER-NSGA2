# Phần B — Thuật toán xếp lịch và so sánh: Design

> Ngữ nghĩa phạt lấy nguyên từ `json_v2/design.md` mục 6 và 17. Tài liệu này chỉ mô tả cách hiện thực và cách so sánh.

## 1. Mô hình bài toán (`app/scheduling/model.py`)

- **Biến:** x = (x₁ … xₙ), xᵢ là chỉ số lớp được chọn của môn i trong danh sách ứng viên Sᵢ.
- **Lớp ứng viên:** `ClassView` tính sẵn mọi giá trị đã chuẩn hoá của lớp: mã thứ, tập tiết, tiết đầu/cuối, giờ đầu/cuối (phút), số tiết, khu, phòng, giảng viên (None nếu không xác định), nhóm lớp, ngôn ngữ, và bitmask (thứ, tiết) để kiểm tra trùng lịch.
- **Lớp trùng hệt nhau** (cùng nhóm lớp, giảng viên, thứ, tiết, khu, phòng, ngôn ngữ) trong cùng một môn bị gộp: dữ liệu Mongo có 126 dòng lặp, nếu giữ thì "5 lịch khác nhau" có thể là cùng một lịch.
- **Ghim (`/reschedule`):** môn được ghim chỉ còn lớp đã đăng ký.

## 2. Hàm chấm chung (`app/scheduling/constraints.py`)

Mỗi `NormalizedConstraint` được biên dịch một lần thành dạng tính nhanh:

| Loại | Biên dịch | Tính khi chấm |
|---|---|---|
| `prefer` / `avoid` (kể cả `review` đã quy về `teacher`) | hệ số aᵢₗ ∈ {0, 1} cho từng lớp: lớp thuộc S_c và vi phạm | cộng dồn, tách được theo môn (unary) |
| `limit` | cờ "thuộc S_c" cho từng lớp (scope, exclude, lớp có lịch) | gom lớp được chọn theo ngày / buổi, tính mục 6.3 |
| `relation` | chỉ số các môn | tính mục 17.2 trên ngày, tiết bắt đầu của lớp được chọn |

- **Khớp bộ lọc:** theo bảng mục 4 của json_v2/design: `prefer` và `scope` dùng "nằm trọn" cho `session` / `periods`; `avoid` dùng "có giao". `exclude` khớp như `scope`.
- **S_c:** lớp khớp `scope`, không khớp phạm vi nào trong `exclude`, và mọi thuộc tính mà ràng buộc dùng đều xác định với lớp (6.7).
- **Kết quả chấm:** `Score(conflicts, hard, soft, objectives)`:
  - `conflicts`: số cặp lớp trùng lịch;
  - `hard` = H = Σ v(c) trên ràng buộc `must` (không nhân trọng số);
  - `soft` = P = Σ w(c) · v(c) trên ràng buộc còn lại;
  - `objectives` = P tách thành 3 nhóm cho NSGA-II cải tiến: **thời gian** (điều kiện chỉ gồm `day`, `session`, `periods`, `start_*`, `end_*`, `duration`), **người và nơi** (điều kiện có `teacher`, `class_group`, `review`, `language`, `area`, `room`), **hình dạng lịch** (`limit`, `relation`).
- **Thứ tự:** (conflicts, H, P) so sánh từ điển. Metaheuristic dùng một số vô hướng f = 10⁷ · conflicts + 10⁵ · H + P; P của mọi instance trong benchmark nhỏ hơn 10⁵ nên f giữ đúng thứ tự từ điển.
- `explain(x)` trả danh sách vi phạm `{constraint_id, amount, penalty, hard}` cho response (json_v2/design.md mục 10).

### 2.1 Quy `review` về giảng viên

Đúng json_v2/design.md 17.1: với mỗi môn m trong phạm vi, s = (p − q) / (n + 5) theo `review_stats` của (m, aspect) (`noi_chung` cộng mọi aspect); k = s hoặc −s theo sentiment mục tiêu; T* = giảng viên có k lớn nhất và k > 0, khớp tên bằng `teacher_name_matches`. Ràng buộc được thay bằng `prefer` / `avoid` `{teacher: T*}` với `scope` thêm `course = m`, giữ id, mức độ, trọng số. Môn không có T* bị bỏ, kèm warning.

## 3. Thuật toán (`app/scheduling/solvers/`)

Interface chung (`base.py`): `solve(problem, k=5, budget=None, seed=0, time_limit=None) → SolveResult` gồm `schedules` (mỗi lịch là x kèm `Score`), `evaluations`, `elapsed_ms`, `optimal` (với solver chính xác), `meta`.

| Solver | Ý tưởng | Cách ra k lịch |
|---|---|---|
| `bnb` | DFS theo thứ tự môn ít lớp trước; lớp trong mỗi môn xếp theo phạt unary tăng dần. Cắt nhánh khi trùng lịch, khi một môn chưa gán không còn lớp hợp lệ (forward checking), hoặc khi cận dưới ≥ lời giải tốt nhất. Cận dưới = phạt đã gán + phần đơn điệu của `limit` / `relation` (các số hạng `max` của `subjects_per_day`, `subjects_per_session`, `periods_per_day`, `study_days`, `consecutive_periods`, và `different_day`) + Σ phạt unary nhỏ nhất của các môn chưa gán | Lặp k lần; lần r tìm lịch tốt nhất khác mọi lịch đã chọn ít nhất d môn (cắt nhánh khi số môn còn lại không đủ để khác d môn) |
| `cpsat` | Mô hình 0-1 theo tuyến tính hoá 6.8 / 17.2: mỗi (thứ, tiết) có tối đa một lớp; `subjects_per_day` bình phương bằng `AddMultiplicationEquality`; `gap_periods` và `before` bằng biến cặp z ≥ x_A + x_B − 1 − Σ (lớp ở giữa). Giải hai pha: min H, cố định H, rồi min P | Lặp k lần, mỗi lần thêm cắt Σᵢ x_{i, pᵢ} ≤ n − d cho mọi lịch p đã chọn |
| `sa` | Láng giềng: đổi lớp của một môn (50% chọn trong các lớp không trùng lịch với phần còn lại). Nhiệt độ hạ hình học, T₀ ước lượng từ mẫu Δ; 3 lần khởi động lại chia đều ngân sách | Chọn tham lam đa dạng từ archive mọi lời giải đã đánh giá |
| `ga` | Quần thể 40, tournament 3, lai đều (p = 0,9), đột biến từng gen xác suất 1/n, giữ 2 cá thể tốt nhất | Như `sa` |
| `nsga2_legacy` | Port `run_nsga_ii`: DEAP, 1 mục tiêu (`weights=(-1,)`), quần thể 30, `cxUniform(0,5)`, `mutUniformInt(indpb=0,5)`, `eaMuPlusLambda(μ=λ=30, cxpb=0,5, mutpb=0,5)`, `selNSGA2`; trùng lịch → `inf`. Số thế hệ = (ngân sách − 30) / 30, nên ngân sách 1.500 ứng với 49 thế hệ, gần cấu hình gốc (50) | Như bản gốc: front đầu của quần thể cuối, bỏ trùng, xếp theo fitness, lấy 5. Với 1 mục tiêu, front đầu chỉ gồm các cá thể hoà điểm tốt nhất, nên thường trả ít hơn 5 lịch |
| `nsga2` | Tự hiện thực NSGA-II: 3 mục tiêu (mục 2), so sánh theo tính khả thi của Deb (CV = 10⁷ · conflicts + H: khả thi thắng không khả thi; hai lời giải không khả thi so CV; hai lời giải khả thi so Pareto + crowding). Toán tử sửa: môn bị trùng lịch được gán lại lớp không trùng (thứ tự ngẫu nhiên). Quần thể 40 | Từ archive: front không bị trội của các lời giải có (conflicts, H) nhỏ nhất; chọn lời giải P nhỏ nhất, rồi lời giải tốt nhất theo từng mục tiêu, rồi theo crowding; thiếu thì lấy front sau |

Thư viện: `ortools` cho CP-SAT, `deap` cho bản gốc. GA, SA, NSGA-II cải tiến tự viết (vài chục dòng mỗi thuật toán) để đếm đúng số lần đánh giá và dùng chung bộ chấm.

## 4. Chọn k lịch đa dạng (`app/scheduling/topk.py`)

- d = 2 nếu số môn còn tự do (nhiều hơn một lớp ứng viên) ≥ 3, ngược lại d = 1. "Khác d môn" = khoảng cách Hamming giữa hai vector x.
- Tham lam: duyệt các lịch không trùng lịch theo (H, P, x) tăng dần, nhận lịch khác mọi lịch đã nhận ít nhất d môn. Thiếu thì nới d về 1.
- Mọi solver (trừ `nsga2_legacy`, giữ nguyên cách ra kết quả gốc, và `nsga2`, dùng cách Pareto) dùng chung hàm này.
- **Chuẩn so sánh (top-5 chính xác):** kết quả của `bnb` / `cpsat` khi đã chứng minh tối ưu. Hai solver phải cho cùng chuỗi phạt; test kiểm tra điều này.

## 5. Thực nghiệm (`research/benchmark/`)

### 5.1 Dữ liệu

- `export_classes.py`: đọc `ly_courses` (chỉ đọc) → `data/classes.json`. Nhóm môn theo (`course_name`, `sub_topic`).
- `generate_instances.py` → `instances/*.json`, seed 2026. Mỗi file tự chứa: lớp ứng viên, tài liệu JSON v2, `review_stats`, `pinned`, metadata.
  - Thật: n ∈ {3, 5, 7, 9} × tầng không gian (nhỏ / vừa / lớn theo tích số lớp) × mật độ ràng buộc (nhẹ 1–3, vừa 4–6, nặng 7–10). Bộ môn lấy ngẫu nhiên trong cùng một ngành (`field`) để giống lựa chọn thật của sinh viên, chỉ lấy nhóm môn có ít nhất một lớp có lịch.
  - Ràng buộc sinh từ 37 loại nguyên tử (llm-guide mục 6), giá trị lấy từ chính dữ liệu của instance (giảng viên, nhóm lớp, phòng của các môn đã chọn); mức `normal` 70%, `high` 15%, `must` 15%; mức nặng luôn có ít nhất một `must`.
  - Đặc biệt: `must` không thoả được, ràng buộc mâu thuẫn, reschedule (ghim một nửa số môn).
  - `review_stats` sinh giả cho giảng viên của instance (dữ liệu review thật không nằm trong repo); ghi rõ trong report.
  - Tổng hợp lớn: n 12–15, 20–50 lớp/môn, thứ và tiết lấy theo phân bố thật.
- Ràng buộc đi qua đúng `normalize_document` như API.

### 5.2 Chạy

- `run_benchmark.py`: mỗi instance × solver × seed, chạy song song theo tiến trình.
  - Metaheuristic: ngân sách chính 5.000 lần đánh giá × 30 seed; thêm 1.500 và 20.000 lần × 10 seed để vẽ đường hội tụ.
  - `bnb`, `cpsat`: tất định, 1 lần, giới hạn 60 giây.
- Kết quả: `results/runs.csv` (một dòng một lần chạy), `results/reference.csv`.

### 5.3 Chỉ số

| Chỉ số | Định nghĩa |
|---|---|
| `returned` | số lịch trả về (tối đa 5) |
| `feasible` | 1 nếu mọi lịch trả về không trùng lịch và có H bằng H tốt nhất của chuẩn |
| `best_p`, `mean_p` | P của lịch tốt nhất / trung bình các lịch trả về (cùng H) |
| `gap_best`, `gap_mean` | chênh với chuẩn; `gap_mean` so trên số lịch chuẩn, lịch thiếu bị tính bằng P lớn nhất của chuẩn + 1 để không có lợi khi trả ít lịch |
| `hit` | 1 nếu `best_p` bằng chuẩn |
| `diversity` | Hamming trung bình giữa các cặp lịch, chia cho n |
| `hv` | hypervolume của các lịch trả về trong không gian 3 mục tiêu, chuẩn hoá theo điểm tham chiếu chung của instance |
| `elapsed_ms`, `evaluations` | thời gian, số lần gọi hàm chấm |

### 5.4 Thống kê

`analyze.py`: bảng theo nhóm instance; Friedman trên `gap_mean` (trung vị qua seed) cho mọi instance; post-hoc Wilcoxon có hiệu chỉnh Holm; biểu đồ `results/*.png`.

### 5.5 Case study

`case_study.py`: yêu cầu kiểu "Prompt (đầy đủ)" của llm-guide mục 7, viết lại với các môn thật của một ngành trong Mongo; in 5 lịch của mỗi thuật toán kèm vi phạm vào `results/case_study.md`.

## 6. API v2 (`app/api/v2/schedule_api.py`)

- `POST /api/v2/schedule`: body theo json_v2/design.md mục 10 (`courses`, `preferences`, `review_stats`, `k`), thêm `algorithm` (tuỳ chọn) và `time_limit` (tuỳ chọn).
- `POST /api/v2/reschedule`: thêm `pinned: [{"course", "class_index"}]`.
- Luồng: nạp lớp từ Mongo theo (`name`, `sub_topic`) → `normalize_document` → `build_problem` → solver → response mục 10, với `meta.algorithm`, `meta.elapsed_ms`, `meta.optimal`.
- Lỗi tài liệu → 400 như `/api/preferences/validate`.
