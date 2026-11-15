# So sánh thuật toán xếp thời khoá biểu cá nhân trên JSON Structure v2

> Phần B của lộ trình (`docs/specs/README.md`). Spec: `docs/specs/algorithms/`. Mọi con số dưới đây lấy từ `research/benchmark/results/` (`summary.md`, `metrics.csv`, `reference.csv`, `case_study.md`); cách chạy lại ở mục 9.

## 1. Kết luận

**Chọn CP-SAT (OR-Tools)** làm thuật toán mặc định của `/api/v2/schedule` và `/api/v2/reschedule`.

| Tiêu chí | CP-SAT | Thuật toán tốt thứ hai |
|---|---|---|
| Chất lượng trên 54 instance thật | tối ưu đã chứng minh ở 54/54; top-5 đúng bằng chuẩn | B&B: cũng chính xác, nhưng chậm bất thường ở ca nhiều lớp |
| Thời gian trên instance thật (1 luồng) | trung vị 17 ms, p95 86 ms, **tối đa 282 ms** | B&B: trung vị 1 ms nhưng tối đa **22,4 giây** |
| Ca xấu nhất (tổng hợp, tới 10²⁵ tổ hợp) | đạt tốt nhất đã biết ở 4/4; chứng minh tối ưu ở 3/4 | NSGA-II cải tiến: đạt tốt nhất đã biết ở 4/4, ~1 giây |
| Đủ 5 lịch khác nhau | 100% (trừ 1 ca tổng hợp lớn nhất hết giờ) | — |

Lý do chính:
1. **Bài toán thật nhỏ.** Không gian tìm kiếm của các instance lấy từ MongoDB nằm trong khoảng 10⁰·⁶ – 10⁷·³ tổ hợp. Ở quy mô này, solver chính xác vừa cho đáp án tối ưu được chứng minh, vừa nhanh hơn mọi metaheuristic (Friedman về thời gian: p = 3,9·10⁻⁴³; CP-SAT nhanh hơn SA, GA và cả hai bản NSGA-II với p (Holm) < 10⁻⁷).
2. **Không có metaheuristic nào tốt hơn về chất lượng.** Trên instance thật, SA, GA và NSGA-II cải tiến đạt tối ưu ở 98–100% lần chạy. Kiểm định Wilcoxon–Holm không cho thấy khác biệt có ý nghĩa giữa CP-SAT, B&B, SA, GA và NSGA-II cải tiến (mọi p (Holm) = 1), nhưng chúng cần 10–30 lần thời gian.
3. **B&B nhanh ở ca thường nhưng không đoán trước được.** B&B có trung vị thấp nhất (1 ms), nhưng mất 16–22 giây ở bộ 7 môn có nhiều lớp nhất và hết 60 giây ở 3/4 instance tổng hợp. CP-SAT ổn định hơn nhiều: tệ nhất 282 ms trên dữ liệu thật.
4. **NSGA-II của hệ thống cũ là lựa chọn kém nhất.** Chỉ 61,7% lần chạy trả đủ 5 lịch (11% chỉ trả 1 lịch). Trên instance tổng hợp, chỉ 22,5% lần chạy tìm được lịch không trùng. Trên cả 58 instance, đây là thuật toán duy nhất thua có ý nghĩa thống kê về chất lượng (so với B&B và CP-SAT: p (Holm) = 0,032; nếu chỉ xét 54 instance thật thì p (Holm) = 0,22).

**Phương án phụ:** NSGA-II cải tiến (`algorithm: "nsga2"`). Thuật toán này luôn đạt lịch tốt nhất (100% lần chạy, ổn định nhất giữa các seed, độ lệch chuẩn 0,02) và cho 5 lịch **đa dạng hơn** (đa dạng 0,54 so với 0,46 của CP-SAT trên instance tổng hợp). Đổi lại, nó chậm nhất (trung vị 0,5–1 giây) và 5 lịch của nó cố ý không phải 5 lịch có phạt thấp nhất (gap_mean 0,18 trên instance thật). Nên dùng khi muốn đưa sinh viên các kiểu đánh đổi khác nhau, ví dụ "đúng giảng viên" và "đúng buổi".

## 2. Bài toán

- **Biến:** chọn đúng một lớp cho mỗi môn: x ∈ S₁ × … × Sₙ.
- **Ràng buộc cứng:** không trùng lịch (cùng thứ, giao tiết); mọi ràng buộc `must`.
- **Mục tiêu:** so sánh theo thứ bậc (H, P): H là tổng vi phạm `must`, P là tổng phạt mềm có trọng số theo `json_v2/design.md` mục 6 và 17.
- **Đầu ra:** 5 lịch, đôi một khác nhau ít nhất d môn (d = 2 khi có ít nhất 3 môn còn tự do).
- **Hàm chấm chung:** `app/scheduling/constraints.py`, dùng chung cho cả 6 thuật toán. Ràng buộc `prefer` / `avoid` được biên dịch thành hệ số 0/1 cho từng lớp; `limit` và `relation` tính trên cả lịch; `review` được quy về `teacher` bằng `review_stats`.

## 3. Thuật toán

| Thuật toán | Họ | Cách hoạt động | Cách ra 5 lịch |
|---|---|---|---|
| **B&B** | chính xác | DFS, môn ít lớp trước; cắt nhánh khi trùng lịch, khi một môn không còn lớp hợp lệ, hoặc khi cận dưới (phạt đã gán + phần đơn điệu của `limit` + phạt nhỏ nhất của các môn còn lại) vượt lời giải tốt nhất | lặp 5 lần, lần sau bắt buộc khác các lịch trước ít nhất d môn |
| **CP-SAT** | chính xác | mô hình 0-1 theo tuyến tính hoá ở json_v2/design.md 6.8 và 17.2; mục tiêu 10⁵·H + P | lặp 5 lần, mỗi lần thêm cắt Σ x_{i,pᵢ} ≤ n − d |
| **SA** | local search | đổi lớp của một môn; nhiệt độ hạ hình học; 3 lần khởi động lại | chọn tham lam đa dạng từ mọi lời giải đã chấm |
| **GA** | tiến hoá, 1 mục tiêu | quần thể 40, tournament 3, lai đều, đột biến 1/n, giữ 2 cá thể tốt nhất | như SA |
| **NSGA-II gốc** | tiến hoá | port nguyên cấu hình DEAP của `constraints_service.py` (quần thể 30, `eaMuPlusLambda`, 1 mục tiêu, trùng lịch → `inf`), chỉ thay hàm chấm v1 bằng v2 | như bản gốc: front đầu của quần thể cuối, bỏ trùng, lấy 5 |
| **NSGA-II cải tiến** | tiến hoá, 3 mục tiêu | 3 mục tiêu (thời gian / người và nơi / hình dạng lịch); xử lý ràng buộc theo tính khả thi của Deb; toán tử sửa lời giải trùng lịch | 5 điểm đại diện trên front: P nhỏ nhất, tốt nhất theo từng mục tiêu, rồi theo crowding |

Kiểm chứng (`tests/scheduling/test_solvers.py`): trên instance nhỏ, CP-SAT khớp duyệt toàn bộ với từng loại `limit` / `relation`. B&B và CP-SAT cho top-5 đa dạng đúng chính xác. Mọi solver không bao giờ trả lịch trùng.

## 4. Thiết lập thực nghiệm

### 4.1 Dữ liệu

- **Nguồn:** MongoDB `university_db.ly_courses`, đọc ngày 2026-11-15 (chỉ đọc): 1.638 lớp, 315 môn, 1.356 nhóm (môn, sub_topic). Bản export: `research/benchmark/data/classes.json`.
- **48 instance thật:** n ∈ {3, 5, 7, 9} môn cùng ngành × 4 tầng không gian (phân vị 20%, 60%, 95%, 100% của kích thước không gian trong 400 bộ môn ngẫu nhiên) × 3 mức ràng buộc (nhẹ 1–3, vừa 4–6, nặng 7–10 ràng buộc). Ràng buộc sinh từ 37 loại nguyên tử của llm-guide, với giá trị lấy từ chính instance; mức `must` 15%, `high` 15%.
- **3 ca đặc biệt:** `must` không thoả được, ràng buộc mâu thuẫn, reschedule.
- **3 case study:** yêu cầu viết như sinh viên thật, môn thật (mục 6).
- **4 instance tổng hợp lớn:** 12–15 môn × 20–50 lớp/môn (10¹⁵·⁶ – 10²⁵·⁵ tổ hợp), thứ / tiết / giảng viên lấy theo phân bố thật.

Kích thước không gian của instance thật (log₁₀):

| n | small | medium | large | max |
|---|---|---|---|---|
| 3 | 0,6 | 1,5 | 2,5 | 3,7 |
| 5 | 1,1 | 2,5 | 3,2 | 4,4 |
| 7 | 1,8 | 3,6 | 4,2 | 7,0 |
| 9 | 2,4 | 4,8 | 5,2 | 5,9 |

### 4.2 Chạy

- 58 instance, 11.716 lần chạy, máy 8 nhân (7 tiến trình song song); CP-SAT chạy 1 luồng để công bằng.
- B&B và CP-SAT: tất định, một lần chạy, giới hạn 60 giây.
- Metaheuristic: ngân sách chính 5.000 lần đánh giá × 30 seed; thêm 1.500 và 20.000 lần × 10 seed. Lời giải đã gặp không chấm lại và không tính vào ngân sách (NSGA-II gốc giữ cách đếm của DEAP).
- **Chuẩn so sánh:** top-5 của B&B hoặc CP-SAT khi đã chứng minh tối ưu (57/58 instance). Riêng `synthetic_n15_c50` dùng lời giải tốt nhất đã biết.

### 4.3 Chỉ số

| Chỉ số | Ý nghĩa |
|---|---|
| khả thi | không trùng lịch và H bằng H của chuẩn |
| đạt tối ưu | lịch tốt nhất có P bằng chuẩn |
| gap_mean | P trung bình của các lịch trả về trừ P trung bình của top-5 chuẩn; lịch thiếu tính bằng P lớn nhất của chuẩn + 1 |
| đa dạng | khoảng cách Hamming trung bình giữa các cặp lịch, chia cho n |
| HV | hypervolume của các lịch trả về trong không gian 3 mục tiêu, chuẩn hoá về [0, 1] |

## 5. Kết quả

### 5.1 Instance thật (54 instance: 48 thật + 3 đặc biệt + 3 case study)

Metaheuristic ở ngân sách 5.000 lần đánh giá, 30 seed.

| Thuật toán | khả thi % | đạt tối ưu % | đủ 5 lịch % | gap_mean | đa dạng | HV | trung vị (ms) | p95 (ms) | tối đa (ms) |
|---|---|---|---|---|---|---|---|---|---|
| B&B | 100 | 100 | 100 | 0,00 | 0,35 | 0,43 | 1,1 | 329 | 22.447 |
| **CP-SAT** | **100** | **100** | **100** | **0,01** | 0,40 | 0,43 | 17,0 | 86 | **282** |
| SA | 99,7 | 98,0 | 100 | 0,05 | 0,36 | 0,43 | 322,8 | 596 | 2.889 |
| GA | 100 | 98,5 | 100 | 0,05 | 0,36 | 0,43 | 88,4 | 185 | 1.002 |
| NSGA-II gốc | 99,4 | 97,5 | **61,7** | 0,28 | 0,29 | 0,43 | 224,3 | 368 | 2.220 |
| NSGA-II cải tiến | 100 | 100 | 100 | 0,18 | 0,40 | 0,44 | 532,1 | 965 | 1.513 |

- gap_mean của CP-SAT (0,01) khác 0 vì khi có nhiều lịch hoà điểm, B&B và CP-SAT chọn lịch hạng 1 khác nhau, nên các lịch hạng sau cũng khác. Cả hai đều đúng định nghĩa "lịch hạng r tốt nhất trong các lịch khác các lịch trước". Cũng vì vậy mà gap_mean có lúc âm.
- NSGA-II gốc trả 1 lịch ở 176/1.620 lần chạy và 2 lịch ở 332 lần. Nguyên nhân: với một mục tiêu, front đầu chỉ gồm các cá thể hoà điểm tốt nhất.
- Thời gian theo số môn (tối đa, ms):

| n | B&B | CP-SAT | SA | GA | NSGA-II gốc | NSGA-II cải tiến |
|---|---|---|---|---|---|---|
| 3 | 20 | 36 | 2.889 | 1.002 | 2.220 | 1.428 |
| 5 | 148 | 282 | 655 | 251 | 663 | 1.513 |
| 7 | **22.447** | 70 | 369 | 208 | 301 | 885 |
| 9 | 666 | 87 | 1.151 | 187 | 339 | 859 |

Ca chậm của B&B là `real_n7_max_*` (10⁷ tổ hợp, có môn 40 và 70 lớp). Ràng buộc `limit` có `min` không đơn điệu nên không đưa được vào cận dưới, khiến B&B phải duyệt rất nhiều nút.

Biểu đồ: `research/benchmark/results/time_vs_space.png`.

### 5.2 Instance tổng hợp lớn (ca xấu nhất)

| Thuật toán | khả thi % | đạt tốt nhất đã biết % | đủ 5 lịch % | gap_mean | đa dạng | trung vị (ms) |
|---|---|---|---|---|---|---|
| B&B | 100 | 25 | 50 | 1,85 | 0,07 | 60.008 (hết giờ 3/4) |
| CP-SAT | 100 | 100 | 100* | 0,00 | 0,46 | 9.031 |
| SA | 100 | 76,7 | 100 | 0,85 | 0,31 | 264 |
| GA | 96,7 | 23,3 | 100 | 3,45 | 0,24 | 257 |
| NSGA-II gốc | **22,5** | 0 | 1,7 | 6,17 | 0,03 | 424 |
| NSGA-II cải tiến | 100 | 100 | 100 | 0,80 | 0,54 | 979 |

\* Ở `synthetic_n15_c50` (10²⁵·⁵ tổ hợp), CP-SAT hết 60 giây khi mới có 1 lịch. Lịch đó bằng lịch tốt nhất đã biết. NSGA-II cải tiến và SA tìm được 5 lịch, lịch tốt nhất cũng bằng điểm đó, trong khoảng 1 giây.

Đây là vùng duy nhất mà metaheuristic có lợi rõ ràng, và nó lớn hơn bài toán thật khoảng 10¹⁸ lần.

### 5.3 Theo ngân sách (mọi instance)

| Thuật toán | 1.500: đạt tối ưu / gap_mean | 5.000 | 20.000 |
|---|---|---|---|
| SA | 0,93 / 0,25 | 0,97 / 0,10 | 0,98 / 0,05 |
| GA | 0,89 / 0,70 | 0,93 / 0,28 | 0,96 / 0,13 |
| NSGA-II gốc | 0,89 / 0,29 | 0,91 / 0,38 | 0,92 / 0,41 |
| NSGA-II cải tiến | 1,00 / 0,22 | 1,00 / 0,22 | 1,00 / 0,23 |

- NSGA-II cải tiến đạt lịch tốt nhất ngay từ 1.500 lần đánh giá, nhờ toán tử sửa trùng lịch. gap_mean của nó không giảm khi tăng ngân sách, vì đó là cái giá của cách chọn 5 lịch đại diện trên front.
- NSGA-II gốc không cải thiện khi tăng ngân sách: quần thể nhỏ, hội tụ sớm.

Biểu đồ: `research/benchmark/results/convergence.png`.

### 5.4 Kiểm định thống kê

- **Chất lượng** (gap_mean, trung vị qua seed, 54 instance thật): Friedman χ² = 22,16, p = 4,9·10⁻⁴. Hạng trung bình: B&B 3,30; CP-SAT 3,33; GA 3,35; SA 3,38; NSGA-II cải tiến 3,67; NSGA-II gốc 3,97.
  - Trên cả 58 instance: χ² = 30,50, p = 1,2·10⁻⁵.
  - Post-hoc Wilcoxon–Holm trên 54 instance thật: không cặp nào khác nhau có ý nghĩa (nhỏ nhất là NSGA-II gốc so với B&B / CP-SAT, p (Holm) = 0,22). Trên 58 instance: chỉ NSGA-II gốc thua có ý nghĩa, so với B&B và CP-SAT (p (Holm) = 0,032); mọi cặp còn lại có p (Holm) ≥ 0,07.
- **Thời gian:** Friedman χ² = 208,7, p = 3,9·10⁻⁴³. Thứ tự: B&B (1,37) < CP-SAT (1,93) < GA (3,06) < NSGA-II gốc (4,31) < SA (4,94) < NSGA-II cải tiến (5,39). Mọi cặp khác nhau có ý nghĩa (p (Holm) ≤ 0,001).
- **Độ ổn định** (độ lệch chuẩn của gap_mean giữa các seed): NSGA-II cải tiến 0,02; SA 0,13; GA 0,24; NSGA-II gốc 0,32. Tỉ lệ instance đạt tối ưu ở mọi seed: NSGA-II cải tiến 100%, SA 89,7%, GA 87,9%, NSGA-II gốc 86,2%.

### 5.5 Đánh giá giả thuyết (README mục 7.7)

| Giả thuyết | Kết quả |
|---|---|
| Ở quy mô VKU, B&B và CP-SAT cho top-5 tối ưu nhanh hơn metaheuristic | **Đúng.** Xét trung vị thì đúng cho cả hai. Riêng B&B có đuôi rất dài (22 giây), CP-SAT thì không |
| Metaheuristic chỉ có lợi khi không gian tìm kiếm lớn, hoặc khi cần nhiều kiểu đánh đổi | **Đúng.** Có lợi ở instance tổng hợp từ 10¹⁵ tổ hợp trở lên (CP-SAT mất 9–60 giây), và NSGA-II cải tiến cho 5 lịch đa dạng hơn |

## 6. Case study trên dữ liệu thật

Chi tiết đầy đủ (5 lịch của mỗi thuật toán, kèm vi phạm): `research/benchmark/results/case_study.md`.

**Case A, sinh viên IT năm 2, 7 môn** (Cơ sở dữ liệu, Lập trình hướng đối tượng, Kiến trúc máy tính, Nguyên lý hệ điều hành, Phân tích và thiết kế giải thuật, Triết học Mác - Lênin, Tiếng Anh nâng cao 2; 1,9·10⁷ tổ hợp):

> "Em muốn học Cơ sở dữ liệu với cô Mai Nga, tránh thầy Nguyễn Văn Lợi. Em thích học buổi sáng, riêng thứ 5 thì học chiều. Tuyệt đối không học thứ 7. Mỗi ngày tối đa 2 môn, lên trường tối đa 4 ngày, không học quá 4 tiết liền. Lập trình hướng đối tượng em muốn học lớp tiếng Việt. Cơ sở dữ liệu và Lập trình hướng đối tượng không học chung một ngày. Em muốn học với giảng viên dạy dễ hiểu. Em muốn học cùng lớp với bạn Nam."

11 ràng buộc JSON v2; "học cùng lớp với bạn Nam" vào `unsupported`.

| Thuật toán | số lịch | P của 5 lịch | thời gian |
|---|---|---|---|
| B&B | 5 | 8, 8, 8, 8, 8 | 19 ms |
| CP-SAT | 5 | 8, 8, 8, 8, 8 | 37 ms |
| SA | 5 | 8, 8, 8, 8, 8 | 213 ms |
| GA | 5 | 8, 8, 8, 8, 9 | 84 ms |
| NSGA-II gốc | **2** | 14, 14 | 124 ms |
| NSGA-II cải tiến | 5 | 8, 8, 14, 14, 14 | 389 ms |

- **Lịch tốt nhất (P = 8)** không thể thoả hết mọi ý. Vi phạm giải thích được:
  - 2 lớp buổi chiều (phạt 2 × 2);
  - hai ý "học cô Mai Nga" và "giảng viên dạy dễ hiểu" kéo về hai giảng viên khác nhau của môn Cơ sở dữ liệu. Theo `review_stats` của case này, giảng viên dạy dễ hiểu nhất là thầy Hồ Văn Phi. Chọn ai cũng vi phạm một ý, cùng trọng số 4, nên hai kiểu lịch hoà điểm.
- B&B, CP-SAT và SA đều chọn thầy Hồ Văn Phi cho cả 5 lịch; 5 lịch chỉ khác nhau ở 2–3 môn.
- NSGA-II cải tiến (và GA) đưa ra cả lịch P = 8 **đúng cô Mai Nga**. Đây là loại đánh đổi mà cách chọn Pareto nhắm tới: cùng mức phạt, nhưng sinh viên thấy được cả hai lựa chọn.
- NSGA-II gốc dừng ở P = 14 với 2 lịch.

**Case B, năm 3, 6 môn** (7,4·10⁵ tổ hợp): "chỉ học nếu lớp bắt đầu sau 8 giờ", "dồn lịch", "nghỉ ít nhất 1 tiết", "Trí tuệ nhân tạo trước Lập trình mạng", "tránh thầy Lê Tân", "rất không muốn học thứ 2". CP-SAT cho 5 lịch tối ưu trong 46 ms; NSGA-II gốc chỉ trả 1 lịch.

**Case C, reschedule** (ghim Lập trình hướng đối tượng nhóm 6, Triết nhóm 9, Tiếng Anh nâng cao 2 nhóm 7): CP-SAT 22 ms, 5 lịch, mọi lịch giữ đúng 3 lớp đã ghim.

## 7. Hạn chế

- **Nhóm lớp học nhiều buổi mỗi tuần.** 34/965 nhóm lớp có từ 2 buổi có lịch trở lên. Ví dụ: Cơ sở dữ liệu nhóm 1 học thứ 2 tiết 1–3 và tiết 6–9; Lập trình hướng đối tượng nhóm 12 có 3 buổi. Như hệ thống v1, mỗi dòng được coi là một lớp riêng. Vì vậy một lịch có thể chỉ chứa một buổi của nhóm đó. Kết quả so sánh thuật toán không đổi, vì mọi thuật toán dùng chung mô hình, nhưng để lịch đúng thực tế cần gộp các buổi của một nhóm thành một lựa chọn. Đây là việc riêng, cần quyết định thêm (xem mục 8).
- **`review_stats` là số liệu giả** sinh ngẫu nhiên, vì repo không có dữ liệu Review service. Chúng chỉ ảnh hưởng tới các ràng buộc `review`.
- **Ràng buộc do script sinh, không qua LLM.** Việc này giữ nhãn đúng, nhưng phân bố loại ràng buộc có thể khác yêu cầu thật của sinh viên.
- **Thời gian đo khi 7 tiến trình chạy song song** trên cùng máy. So sánh giữa các thuật toán vẫn công bằng; giá trị tuyệt đối khi chạy một mình sẽ thấp hơn. API dùng CP-SAT với 4 luồng.
- **Chỉ có một instance (`synthetic_n15_c50`) mà chuẩn không được chứng minh tối ưu.**

## 8. Tích hợp và việc tiếp theo

- **Đã làm:**
  - `POST /api/v2/schedule` và `POST /api/v2/reschedule` (`app/api/v2/schedule_api.py`), mặc định `algorithm = "cpsat"`, `time_limit = 10` giây, 4 luồng;
  - tham số `algorithm` chọn được cả 6 thuật toán;
  - response theo json_v2/design.md mục 10, kèm `objectives`, `meta.optimal` và `infeasible`.
- **Khi CP-SAT hết giờ:** CP-SAT trả các lịch đã tìm được, có thể ít hơn 5, kèm `meta.optimal = false`. Với dữ liệu hiện có, chưa ca thật nào chạm giới hạn này: tối đa 282 ms so với giới hạn 10 giây.
- **Chưa làm:**
  - gộp các buổi của cùng một nhóm lớp (mục 7);
  - chuyển frontend sang `/api/v2` rồi gỡ `/api/schedule` v1;
  - khảo sát nhỏ với sinh viên: so sánh 5 lịch top-k của CP-SAT với 5 lịch Pareto của NSGA-II cải tiến.

## 9. Tái lập

```bash
uv pip install --python .venv/bin/python -r requirements-dev.txt -r requirements-research.txt
.venv/bin/python -m research.benchmark.export_classes            # cần MONGO_URI; đã commit data/classes.json
.venv/bin/python -m research.benchmark.generate_instances        # seed 2026
.venv/bin/python -m research.benchmark.case_study --write-instances
.venv/bin/python -m research.benchmark.run_benchmark             # ~14 phút trên 8 nhân -> results/runs.csv
.venv/bin/python -m research.benchmark.run_benchmark --instances case_a_year2 case_b_year3 case_c_reschedule --out research/benchmark/results/runs_case.csv
.venv/bin/python -m research.benchmark.analyze                   # -> summary.md, metrics.csv, reference.csv, *.png
.venv/bin/python -m research.benchmark.case_study                # -> case_study.md
```

Mọi solver tất định theo seed: chạy lại cho cùng điểm, chỉ cột thời gian thay đổi.
