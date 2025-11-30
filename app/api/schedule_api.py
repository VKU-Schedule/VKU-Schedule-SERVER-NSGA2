from collections import defaultdict
from typing import Dict, List

from flask import Blueprint, request, jsonify, current_app

from app.model.Class_Info import ClassInfo
from app.service.constraints_service import run_nsga_ii

schedule_bp = Blueprint("schedule", __name__)


#
# @schedule_bp.route("/schedule", methods=["POST"])
# def schedule():
#     data = request.json
#     queries = data.get("queries", [])
#     top_k = data.get("top_k", 20)
#
#     if not queries:
#         return jsonify({"error": "Missing queries"}), 400
#
#     collection = current_app.db["ly_courses"]
#     model = current_app.model
#
#     courses_data = {}
#
#     for query in queries:
#         query_vector = model.encode(query).tolist()
#
#         pipeline = [
#             {
#                 "$vectorSearch": {
#                     "index": "vector_index",
#                     "path": "embedding",
#                     "queryVector": query_vector,
#                     "numCandidates": 1000,
#                     "limit": top_k
#                 }
#             },
#             {"$unset": "embedding"},
#             {"$project": {...}}
#         ]
#
#         results = list(collection.aggregate(pipeline))
#
#         formatted_results = []
#         for item in results:
#             tiets = eval(item["Tiết"]) if isinstance(item["Tiết"], str) else item["Tiết"]
#             course_info = {...}  # giống như trước
#             formatted_results.append(course_info)
#
#         courses_data[query] = formatted_results or [("Không tìm thấy", "", "", "", "", "", "", [], "", "", "")]
#
#     schedules = run_nsga_ii(courses_data)
#
#     return jsonify({"schedules": schedules, "message": "Đã sắp xếp thành công"})
def parse_query_string(query_str):

    if "@" in query_str:
        course_name, sub_topic = query_str.split("@", 1)
        return course_name.strip(), sub_topic.strip()
    return query_str.strip(), None


@schedule_bp.route("/schedule", methods=["POST"])
def schedule():
    data = request.json
    queries = data.get("queries", [])
    prompt = data.get("prompt", {})

    if not queries:
        return jsonify({"error": "Missing queries"}), 400
    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    collection = current_app.db["ly_courses"]

    courses_data: Dict[str, List[ClassInfo]] = defaultdict(list)

    for query in queries:
        course_name, sub_topic = parse_query_string(query)

        search_criteria = {
            "$and": []
        }
        if course_name:
            search_criteria["$and"].append({"course_name": course_name})
        if sub_topic:
            search_criteria["$and"].append({"sub_topic": sub_topic})
        matching_classes = list(collection.find(search_criteria))


        print(f"Found {len(matching_classes)} matching classes for: {search_criteria}")
        for doc in matching_classes:
            class_info = ClassInfo(
                course_name=doc.get("course_name", ""),
                class_index=doc.get("class_index", ""),
                language=doc.get("language", ""),
                field=doc.get("field", ""),
                sub_topic=doc.get("sub_topic", ""),
                teacher=doc.get("teacher", ""),
                day=doc.get("day", ""),
                periods=doc.get("periods", []),
                area=doc.get("area", ""),
                room=doc.get("room", ""),
                class_size=doc.get("class_size", 0)
            )

            courses_data[course_name].append(class_info)

    # Gọi hàm NSGA-II (bạn đã định nghĩa ở nơi khác)
    schedules = run_nsga_ii(courses_data, prompt)

    return jsonify({
        "schedules": schedules,
        "message": "Đã sắp xếp thành công"
    })


@schedule_bp.route("/reschedule", methods=["POST"])
def reschedule():
    """
    API xếp lại lịch - dùng để sửa lỗi đăng ký
    Input:
    - selected_classes: danh sách các lớp đã chọn (format: [{course_name, class_index, ...}])
    - parsed_prompt: ràng buộc đã được parse từ prompt
    - failed_classes: danh sách các lớp bị fail đăng ký (format: [course_name])
    - course_names: danh sách tên các môn học cần query (để lấy tất cả các lớp của môn đó)
    """
    data = request.json
    selected_classes = data.get("selected_classes", [])
    parsed_prompt = data.get("parsed_prompt", {})
    failed_classes = data.get("failed_classes", [])
    course_names = data.get("course_names", [])

    if not selected_classes:
        return jsonify({"error": "Missing selected_classes"}), 400
    if not parsed_prompt:
        return jsonify({"error": "Missing parsed_prompt"}), 400
    if not failed_classes:
        return jsonify({"error": "Missing failed_classes"}), 400

    collection = current_app.db["ly_courses"]
    courses_data: Dict[str, List[ClassInfo]] = defaultdict(list)

    # Lấy tất cả các lớp của các môn bị fail
    for course_name in course_names:
        search_criteria = {"course_name": course_name}
        matching_classes = list(collection.find(search_criteria))
        
        print(f"Found {len(matching_classes)} classes for course: {course_name}")
        for doc in matching_classes:
            class_info = ClassInfo(
                course_name=doc.get("course_name", ""),
                class_index=doc.get("class_index", ""),
                language=doc.get("language", ""),
                field=doc.get("field", ""),
                sub_topic=doc.get("sub_topic", ""),
                teacher=doc.get("teacher", ""),
                day=doc.get("day", ""),
                periods=doc.get("periods", []),
                area=doc.get("area", ""),
                room=doc.get("room", ""),
                class_size=doc.get("class_size", 0)
            )
            courses_data[course_name].append(class_info)

    # Thêm các lớp đã chọn (không bị fail) vào courses_data với chỉ 1 option duy nhất
    for selected_class in selected_classes:
        course_name = selected_class.get("course_name", "")
        # Chỉ thêm nếu không phải là lớp bị fail
        if course_name not in failed_classes:
            class_info = ClassInfo(
                course_name=course_name,
                class_index=selected_class.get("class_index", ""),
                language=selected_class.get("language", ""),
                field=selected_class.get("field", ""),
                sub_topic=selected_class.get("sub_topic", ""),
                teacher=selected_class.get("teacher", ""),
                day=selected_class.get("day", ""),
                periods=selected_class.get("periods", []),
                area=selected_class.get("area", ""),
                room=selected_class.get("room", ""),
                class_size=selected_class.get("class_size", 0)
            )
            # Chỉ có 1 option duy nhất cho môn này (lớp đã chọn)
            courses_data[course_name] = [class_info]

    # Gọi hàm NSGA-II để xếp lại lịch
    schedules = run_nsga_ii(courses_data, parsed_prompt)

    return jsonify({
        "schedules": schedules,
        "message": "Đã xếp lại lịch thành công"
    })
