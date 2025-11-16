# 📅 Schedule_Project - VKU Timetable Optimizer

> **Specialized Project 1 | Vietnam - Korea University of Information and Communication Technology (VKU)**  
> **Title**: *Combining LLM, RAG, and NSGA-II to Resolve Constraints for Automatic Timetable Optimization for VKU Students*

---

## Tổng quan

**Schedule_Project** là hệ thống tự động tối ưu hóa lịch học cho sinh viên VKU, giải quyết bài toán tối ưu đa mục tiêu với nhiều ràng buộc phức tạp trong việc sắp xếp lịch học.

### Vấn đề
Mỗi học kỳ, sinh viên phải tự sắp xếp lịch học từ hàng trăm lớp học khác nhau, với các yêu cầu như:
- Chọn giảng viên yêu thích
- Tránh xung đột thời gian giữa các môn
- Cân bằng số lượng môn học mỗi ngày
- Phù hợp với khung giờ ưa thích (sáng, chiều, tối)
- Yêu cầu về địa điểm học (cơ sở, phòng học)
- Ràng buộc cá nhân (nghỉ giữa các tiết, không học liên tục nhiều giờ)

Quá trình này thường mất 30 phút đến hơn 1 giờ, gây căng thẳng và dễ mắc sai sót.

### Giải pháp
Hệ thống sử dụng sự kết hợp của **LLM (VIT5)**, **RAG (Retrieval-Augmented Generation)** và thuật toán **NSGA-II** để:
1. **Tìm kiếm và lọc lớp học**: Sinh viên chỉ cần chọn 7 môn học, hệ thống tự động tìm và lọc ra khoảng 70 lớp học liên quan từ cơ sở dữ liệu.
2. **Phân tích yêu cầu**: LLM (VIT5) phân tích các sở thích và ràng buộc cá nhân từ prompt tự nhiên (ví dụ: "Tôi chỉ học lớp bắt đầu sau 10 giờ sáng", "Tôi thích lịch học trải đều trong tuần").
3. **Tối ưu hóa**: Thuật toán NSGA-II tối ưu hóa đa mục tiêu để tìm ra các lịch học tốt nhất, cân bằng giữa các yêu cầu và ràng buộc.
4. **Kết quả**: Sinh viên nhận được nhiều phương án lịch học tối ưu chỉ trong vài giây.

### Lợi ích
- ⚡ **Tiết kiệm thời gian**: Từ 30 phút–1 giờ xuống còn vài giây
- 🎯 **Tối ưu hóa**: Tự động cân bằng nhiều yêu cầu và ràng buộc
- 📊 **Đa phương án**: Cung cấp nhiều lịch học để lựa chọn
- 🤖 **Thông minh**: Hiểu được ngôn ngữ tự nhiên và sở thích cá nhân

---

## Technologies Used

- **LLM (VIT5)**: Analyzes personal preferences such as teachers, time slots, locations, days, and generates initial timetable solutions.
- **NSGA-II**: A multi-objective evolutionary algorithm to optimize the timetable under complex constraints and user preferences.
- **LLM-NSGA**: A hybrid model combining LLM and NSGA-II to enhance optimization accuracy and flexibility.
- **RAG (Retrieval-Augmented Generation)** *(optional)*: Supports LLMs with external data retrieval to enrich and improve schedule generation.

---

## Objectives

- Automate personalized timetable generation for VKU students.
- Solve a highly-constrained combinatorial optimization problem: preferences for teachers, rooms, days, breaks, subject distribution, etc.
- Deliver a fast, user-friendly web app powered by cutting-edge AI and evolutionary algorithms.

---

## Key Results

- Updating...

---

## Research Question

...

---


