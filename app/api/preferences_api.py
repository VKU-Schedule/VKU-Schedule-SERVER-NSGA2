from flask import Blueprint, current_app, jsonify, request

from app.scheduling.normalize import normalize_document
from app.scheduling.schema import DocumentError

preferences_bp = Blueprint("preferences", __name__)

_CLASS_FIELDS = {"_id": 0, "course_name": 1, "sub_topic": 1, "teacher": 1, "class_index": 1}


def _load_candidates(collection, courses):
    """Các lớp của từng môn trong request (chỉ các field cần cho chuẩn hoá)."""
    candidates, warnings = [], []
    for course in courses:
        criteria = {"course_name": course["name"]}
        if course.get("sub_topic"):
            criteria["sub_topic"] = course["sub_topic"]
        classes = list(collection.find(criteria, _CLASS_FIELDS))
        if not classes:
            warnings.append(f"Không tìm thấy lớp nào của môn '{course['name']}'")
        candidates.extend(classes)
    return candidates, warnings


def _parse_courses(raw):
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("'courses' phải là mảng")
    courses = []
    for item in raw:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ValueError("Mỗi phần tử của 'courses' cần 'name' là chuỗi")
        courses.append({"name": item["name"].strip(), "sub_topic": item.get("sub_topic")})
    return courses


@preferences_bp.route("/preferences/validate", methods=["POST"])
def validate_preferences():
    """
    Kiểm tra và chuẩn hoá tài liệu ưu tiên v2, không xếp lịch
    Dùng cho module LLM tự kiểm tra output. Tài liệu v1 (defaults / periods) được chuyển sang v2.
    Ràng buộc `review` cần `aspect` / `sentiment` (gateway điền từ SA) và `review_stats` trong request.
    Spec: docs/specs/json_v2/design.md mục 3–9, 17.
    ---
    tags:
      - Preferences
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - preferences
          properties:
            courses:
              type: array
              description: Các môn sinh viên đã chọn; dùng để khớp tên môn và tên giảng viên
              items:
                type: object
                properties:
                  name:
                    type: string
                  sub_topic:
                    type: string
              example:
                - name: "Automat và ngôn ngữ hình thức"
                - name: "Cấu trúc dữ liệu và giải thuật"
            preferences:
              type: object
              description: Tài liệu ưu tiên v2 (docs/specs/json_v2/schema.json)
              example:
                version: "2.0"
                constraints:
                  - prefer: {session: "sáng"}
                  - prefer: {session: "chiều"}
                    scope: {day: "thứ 2"}
                  - prefer: {teacher: "Mai Nga"}
                    scope: {course: "Automat"}
                  - limit: "study_days"
                    max: 3
                    level: "high"
                  - relation: "different_day"
                    courses: ["Automat", "Cấu trúc dữ liệu và giải thuật"]
                  - prefer:
                      review: {phrase: "giảng viên dạy dễ hiểu", aspect: "ky_nang_giang_day", sentiment: "positive"}
                unsupported:
                  - "muốn học cùng lớp với bạn Nam"
            review_stats:
              type: array
              description: "Số review theo (môn, giảng viên, aspect), gateway lấy từ Review service. Cần khi có ràng buộc review; dòng sai bị bỏ kèm warning"
              items:
                type: object
                properties:
                  subject:
                    type: string
                  lecturer:
                    type: string
                  aspect:
                    type: string
                  positive:
                    type: integer
                  negative:
                    type: integer
                  total:
                    type: integer
              example:
                - {subject: "Automat và ngôn ngữ hình thức", lecturer: "Dương Thị Mai Nga", aspect: "ky_nang_giang_day", positive: 12, negative: 1, total: 15}
    responses:
      200:
        description: Ràng buộc đã chuẩn hoá, kèm unsupported và warnings
        schema:
          type: object
          properties:
            version:
              type: string
            constraints:
              type: array
              description: "NormalizedConstraint: id, kind, condition hoặc metric/min/max hoặc relation/courses, scope, exclude, level, weight, source"
              items:
                type: object
            unsupported:
              type: array
              description: "Phần tử {index, source, reason}"
              items:
                type: object
            warnings:
              type: array
              items:
                type: string
      400:
        description: Lỗi của cả tài liệu (thiếu constraints, sai phiên bản, tài liệu v1 hỏng) hoặc courses sai dạng
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Body phải là JSON object"}), 400
    if "preferences" not in data:
        return jsonify({"error": "Thiếu 'preferences'"}), 400
    try:
        courses = _parse_courses(data.get("courses"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    candidates, warnings = _load_candidates(current_app.db["ly_courses"], courses)
    try:
        result = normalize_document(data["preferences"], [course["name"] for course in courses], candidates,
                                    data.get("review_stats"))
    except DocumentError as exc:
        return jsonify({"error": str(exc)}), 400

    body = result.to_dict()
    body["warnings"] = warnings + body["warnings"]
    return jsonify(body)
