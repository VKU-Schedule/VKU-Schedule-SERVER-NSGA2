
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import random
import argparse
import re

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    pass


def get_course_names_from_mongo(uri, db_name="university_db", collection_name="ly_courses"):
    client = MongoClient(uri)
    db = client[db_name]
    coll = db[collection_name]
    try:
        names = coll.distinct("course_name")
    finally:
        client.close()
    cleaned = [str(n).strip() for n in names if n and str(n).strip()]
    return cleaned


def make_group_string(force_kind=False):
    # Nếu bắt buộc ghi rõ nhóm/lớp
    if force_kind:
        kind = random.choice(["nhóm", "lớp"])
    else:
        kind = random.choice(["nhóm", "lớp", ""]) # cho phép rỗng

    choice = random.choice(["dash_range", "comma_list", "single", "and", "or"])

    nums = list(range(1, 15))
    if choice == "single":
        n = random.choice(nums)
        grp = str(n)
    elif choice in ["dash_range", "and", "or"]:
        a, b = sorted(random.sample(nums, 2))

        if choice == "dash_range":
            grp = f"{a} - {b}"
        elif choice == "and":
            grp = f"{a} và {b}"
        elif choice == "or":
            grp = f"{a} hoặc {b}"
    elif choice == "comma_list":
        k = random.choice([2, 3])
        sel = sorted(random.sample(nums, k))
        grp = ", ".join(str(x) for x in sel)
    else:
        grp = ""


    # Đôi khi dùng ngoặc (2), hoặc không
    use_paren = random.random() < 0.25
    if use_paren:
        grp = f"({grp})"

    if kind:
        return f" {kind} {grp}"
    else:
        # có khi không ghi chữ 'nhóm'/'lớp', chỉ để số/ngoặc ngay sau tên môn
        return f" {grp}"


TEMPLATES = [
    "Tôi rất thích học {course}{group}",
    "Tôi không thích học {course} nhưng vẫn phải học{group}",
    "Môn {course}{group} luôn thu hút tôi",
    "Tôi thấy môn {course}{group} khá khó khăn",
    "Học môn {course}{group} rất thú vị",
    "Tôi cảm thấy không hứng thú với môn {course}{group}",
    "Tôi muốn học môn {course}{group} để nâng cao kỹ năng",
    "Môn {course}{group} rất hữu ích cho tôi",
    "Tôi rất đam mê học môn {course}{group}",
    "Môn {course}{group} là môn tôi ít khi quan tâm",
    "Môn {course}{group} rất quan trọng trong ngành của tôi",
    "Học môn {course}{group} khá là khô khan",
    "Môn {course}{group} là một thử thách lớn đối với tôi",
    "Tôi thấy mình học tốt môn {course}{group}",
    "Môn {course}{group} có một số bài tập khó",
    "Tôi muốn cải thiện kiến thức về {course}{group}",
    "Tôi muốn đăng ký học {course}{group} trong kỳ tới",
    "Tôi dự định chọn lớp {course}{group} vì lịch học phù hợp",
    "Tôi ưu tiên học môn {course}{group} nếu còn chỗ trống",
    "Tôi cảm thấy hứng thú với môn {course}{group}",
    "Tôi thấy môn {course}{group} sẽ giúp ích nhiều cho chuyên ngành",
    "Tôi mong được học môn {course}{group} với giảng viên giỏi",
    "Tôi nghĩ môn {course}{group} sẽ khá thú vị",
    "Tôi muốn trải nghiệm cách giảng dạy của lớp {course}{group}",
    "Tôi hy vọng môn {course}{group} không quá khó",
    "Tôi nghe bạn bè nói môn {course}{group} rất đáng để học",
]


def should_skip(course_name: str):
    keywords = ["đồ án", "Đồ án", "thực tập", "Thực tập", "Khóa luận", "Đề án"]
    return any(k in course_name for k in keywords)

# ------------------------------- # Phát hiện môn có số cuối # -------------------------------
def extract_course_number(course_name: str):
    """ Nếu tên môn kết thúc bằng số, trả về số đó. Ví dụ: "Giải tích 2" -> 2 """
    match = re.search(r"(\d+)$", course_name)
    if match:
        return int(match.group(1))

    return None

def generate_sentences(course_names, n=120):
    valid_courses = [c for c in course_names if not should_skip(c)]
    out = []
    if not course_names:
        # fallback: một số course mặc định nếu db rỗng
        course_names = [
            "Cấu trúc dữ liệu và thuật toán",
            "Hệ điều hành",
            "Lập trình hướng đối tượng",
            "Phân tích và thiết kế giải thuật",
            "Toán rời rạc và lý thuyết đồ thị",
            "Cơ sở dữ liệu",
            "Kỹ thuật phần mềm",
            "Ngôn ngữ lập trình Python",
            "Lý thuyết ngôn ngữ hình thức",
            "Hệ thống nhúng",
            "Mạng máy tính",
            "Lý thuyết xác suất và thống kê",
            "Phát triển phần mềm",
            "Mô phỏng và mô hình hóa",
            "Học máy và trí tuệ nhân tạo",
        ]

    for i in range(n):
        if not valid_courses:
            break

        course = random.choice(valid_courses)
        # detect môn kết thúc bằng số
        num = extract_course_number(course)
        force_kind = num is not None # môn đặc biệt → bắt buộc thêm chữ “nhóm/lớp”
        group = make_group_string(force_kind=force_kind)
        template = random.choice(TEMPLATES)
        sentence = template.format(course=course, group=group).strip()

        # thêm dấu chấm hoặc cảm thán ngẫu nhiên
        if random.random() < 0.07:
            sentence += "!"
        elif random.random() < 0.07:
            sentence += "."

        out.append(sentence)

    return out


def main():
    parser = argparse.ArgumentParser(description="Sinh câu mô phỏng từ course_name trong MongoDB")
    parser.add_argument("--n", type=int, default=120, help="Số câu cần sinh")
    parser.add_argument("--save", type=str, default="generated_sentences.txt", help="File lưu kết quả")
    parser.add_argument("--db", action="store_true", help="Thử lấy tên môn từ MongoDB (yêu cầu MONGO_URI trong .env)")
    args = parser.parse_args()

    if args.db:
        if not MONGO_URI:
            print("MONGO_URI chưa được set. Không thể lấy dữ liệu từ MongoDB. Chạy lại với --db khi đã có .env")
            return
        course_names = get_course_names_from_mongo(MONGO_URI)
        print(f"Lấy {len(course_names)} course_name từ MongoDB")
    else:
        course_names = []

    sentences = generate_sentences(course_names, n=args.n)

    with open(args.save, "w", encoding="utf-8") as f:
        for s in sentences:
            f.write(s + "\n")

    print(f"Đã sinh {len(sentences)} câu và lưu vào {args.save}")


if __name__ == "__main__":
    main()
