# Phần B — Thuật toán xếp lịch và so sánh: Requirements

> Tách từ `docs/specs/README.md` mục 7. Kế hoạch đã duyệt: [`plan.md`](plan.md). Thiết kế: [`design.md`](design.md). Các bước: [`tasks.md`](tasks.md).

## 1. Mục tiêu

1. Hiện thực hàm chấm chung cho JSON v2, đúng ngữ nghĩa phạt ở `json_v2/design.md` mục 6 và 17.
2. Hiện thực 6 thuật toán trên cùng hàm chấm, **chạy trên dữ liệu lớp học thật trong MongoDB** (`university_db.ly_courses`):
   - Branch & Bound (chính xác);
   - CP-SAT, OR-Tools (chính xác);
   - Simulated Annealing;
   - GA đơn mục tiêu;
   - NSGA-II gốc: port nguyên cấu hình của `app/service/constraints_service.py`, chỉ thay hàm chấm v1 bằng v2;
   - NSGA-II cải tiến: 3 mục tiêu, xử lý ràng buộc theo tính khả thi, sửa lời giải trùng lịch.
3. So sánh thực nghiệm, viết report `docs/algorithm-comparison.md`, chọn thuật toán phù hợp nhất dựa trên số liệu.
4. Đưa thuật toán vào API mới `/api/v2/schedule` và `/api/v2/reschedule`. API v1 giữ nguyên.

## 2. Yêu cầu chức năng

| # | Yêu cầu |
|---|---|
| B1 | Đầu vào của solver là `Problem`: các môn, lớp ứng viên của từng môn, và `NormalizedDocument` của Phần A |
| B2 | Không lịch nào trả về được trùng lịch (cùng thứ, có tiết giao nhau) |
| B3 | So sánh lịch theo thứ bậc: tổng vi phạm `must` (H) trước, tổng phạt mềm (P) sau |
| B4 | Trả tối đa k = 5 lịch, đôi một khác nhau ít nhất d môn (mục 4 của design) |
| B5 | `review` được quy về giảng viên bằng `review_stats` (json_v2/design.md 17.1) |
| B6 | Mỗi lịch kèm báo cáo vi phạm theo từng ràng buộc; không thoả được `must` thì có `infeasible` |
| B7 | `/reschedule`: môn được ghim chỉ còn đúng lớp đã đăng ký |
| B8 | Request chọn được thuật toán qua field `algorithm`; mặc định là thuật toán được chọn trong report |

## 3. Yêu cầu thực nghiệm

| # | Yêu cầu |
|---|---|
| E1 | Instance lấy từ dữ liệu thật của MongoDB, export ra file JSON được commit để tái lập |
| E2 | Phân tầng theo số môn n ∈ {3, 5, 7, 9} và kích thước không gian tìm kiếm; 3 mức số ràng buộc; có ca `must` không thoả được, ca mâu thuẫn, ca reschedule |
| E3 | Có instance tổng hợp lớn (n 12–15, 20–50 lớp/môn) |
| E4 | Mọi thuật toán dùng chung hàm chấm; metaheuristic dùng chung ngân sách số lần đánh giá |
| E5 | Nhiều seed cho mỗi cặp thuật toán × instance; kiểm định Friedman + Wilcoxon–Holm |
| E6 | Chỉ số: tỉ lệ khả thi, số lịch trả về, phạt tốt nhất / trung bình, gap so với top-5 chính xác, đa dạng, hypervolume, thời gian, số lần đánh giá, độ ổn định |
| E7 | Có case study: yêu cầu cụ thể của sinh viên với môn thật, in 5 lịch của từng thuật toán |

## 4. Ngoài phạm vi

- Gỡ code v1 (`/api/schedule`, `constraints_service.py`): giữ lại cho tới khi frontend chuyển sang v2.
- Gọi SA / Review / LLM service: repo này chỉ nhận dữ liệu đã resolve.
- Cột `Tuần học` (README quyết định 5).
