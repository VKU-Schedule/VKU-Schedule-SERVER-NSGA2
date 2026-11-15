"""API xếp lịch v2: JSON Structure v2 + solver của Phần B (docs/specs/algorithms/design.md mục 6).

Request / response: docs/specs/json_v2/design.md mục 10. API v1 (`/api/schedule`) giữ nguyên.
"""
import math

from flask import Blueprint, current_app, jsonify, request

from app.api.preferences_api import _parse_courses
from app.scheduling.constraints import Evaluator, infeasible_report
from app.scheduling.model import build_problem
from app.scheduling.normalize import normalize_document
from app.scheduling.schema import DocumentError
from app.scheduling.solvers import SOLVERS

schedule_v2_bp = Blueprint("schedule_v2", __name__)

# Thuật toán mặc định, chọn theo docs/algorithm-comparison.md
DEFAULT_ALGORITHM = "cpsat"
DEFAULT_TIME_LIMIT = 10.0      # giây
MAX_TIME_LIMIT = 60.0
DEFAULT_BUDGET = 5000          # số lần đánh giá cho metaheuristic
MAX_K = 10
CPSAT_WORKERS = 4

_CLASS_FIELDS = ("course_name", "sub_topic", "class_index", "teacher", "day", "periods", "area", "room",
                 "language", "class_size")


def _clean(value):
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            return int(value)
    return value


def _load_classes(collection, courses):
    """Môn -> lớp (dict). Hai môn cùng tên khác sub_topic được đặt tên "tên @ sub_topic"."""
    candidates, warnings, labels = {}, [], {}
    for course in courses:
        criteria = {"course_name": course["name"]}
        if course.get("sub_topic"):
            criteria["sub_topic"] = course["sub_topic"]
        label = course["name"]
        if label in candidates:
            label = f"{course['name']} @ {course.get('sub_topic') or len(candidates)}"
        docs = [dict(doc) for doc in collection.find(criteria, {"_id": 0, "embedding": 0})]
        if not docs:
            warnings.append(f"Không tìm thấy lớp nào của môn '{course['name']}'")
            continue
        for doc in docs:
            doc["display_name"] = doc.get("course_name")
            doc["course_name"] = label
        candidates[label] = docs
        labels[(course["name"], course.get("sub_topic"))] = label
    return candidates, warnings, labels


def _class_json(view):
    raw = view.raw
    data = {name: _clean(raw.get(name)) for name in _CLASS_FIELDS}
    data["course_name"] = raw.get("display_name") or raw.get("course_name")
    data["class_index"] = view.class_index
    data["periods"] = list(view.periods) if view.scheduled else list(raw.get("periods") or [])
    return data


def _parse_options(data):
    k = data.get("k", 5)
    if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= MAX_K:
        raise ValueError(f"'k' phải là số nguyên từ 1 đến {MAX_K}")
    algorithm = data.get("algorithm") or DEFAULT_ALGORITHM
    if algorithm not in SOLVERS:
        raise ValueError(f"'algorithm' phải là một trong {', '.join(SOLVERS)}")
    time_limit = data.get("time_limit", DEFAULT_TIME_LIMIT)
    if not isinstance(time_limit, (int, float)) or isinstance(time_limit, bool) or not 0 < time_limit <= MAX_TIME_LIMIT:
        raise ValueError(f"'time_limit' phải là số giây trong (0, {MAX_TIME_LIMIT:g}]")
    return k, algorithm, float(time_limit)


def _parse_pinned(raw, courses, labels):
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise ValueError("'pinned' phải là mảng")
    pinned = {}
    by_name = {}
    for (name, sub_topic), label in labels.items():
        by_name.setdefault(name, label)
        by_name[f"{name} @ {sub_topic}"] = label
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("course"), str) or item.get("class_index") in (None, ""):
            raise ValueError("Mỗi phần tử của 'pinned' cần 'course' và 'class_index'")
        label = by_name.get(item["course"].strip())
        if label is None:
            raise ValueError(f"Môn ghim '{item['course']}' không có trong 'courses'")
        pinned[label] = str(item["class_index"])
    return pinned


def _solve(data, with_pinned):
    if not isinstance(data, dict):
        return {"error": "Body phải là JSON object"}, 400
    if "preferences" not in data:
        return {"error": "Thiếu 'preferences'"}, 400
    try:
        courses = _parse_courses(data.get("courses"))
        if not courses:
            raise ValueError("Thiếu 'courses'")
        k, algorithm, time_limit = _parse_options(data)
    except ValueError as exc:
        return {"error": str(exc)}, 400

    candidates, warnings, labels = _load_classes(current_app.db["ly_courses"], courses)
    try:
        pinned = _parse_pinned(data.get("pinned"), courses, labels) if with_pinned else {}
        document = normalize_document(data["preferences"], list(candidates), candidates, data.get("review_stats"))
        problem = build_problem(candidates, pinned)
    except DocumentError as exc:
        return {"error": str(exc)}, 400
    except ValueError as exc:
        return {"error": str(exc)}, 400

    body = {
        "version": document.version,
        "schedules": [],
        "constraints": [{key: c.to_dict()[key] for key in ("id", "kind", "level", "weight", "source")}
                        for c in document.constraints],
        "unsupported": [item.to_dict() for item in document.unsupported],
        "warnings": warnings + document.warnings,
        "infeasible": [],
        "meta": {"algorithm": algorithm},
    }
    if not candidates:
        return body, 200

    evaluator = Evaluator(problem, document)
    body["warnings"] += evaluator.warnings
    result = SOLVERS[algorithm](evaluator, k=k, budget=data.get("budget", DEFAULT_BUDGET), seed=0,
                                time_limit=time_limit, workers=CPSAT_WORKERS)
    for rank, schedule in enumerate(result.schedules, 1):
        body["schedules"].append({
            "rank": rank,
            "classes": [_class_json(view) for view in problem.classes(schedule.x)],
            "hard_violations": schedule.score.hard,
            "penalty": schedule.score.soft,
            "objectives": dict(zip(("time", "people_place", "shape"), schedule.score.objectives)),
            "violations": [v._asdict() for v in evaluator.explain(schedule.x)],
        })
    if not result.schedules:
        body["infeasible"].append({"constraint_id": None, "amount": None,
                                   "reason": "Không có lịch nào không trùng lịch với các môn đã chọn"})
    elif result.schedules[0].score.hard:
        body["infeasible"] = infeasible_report(evaluator, result.schedules[0].x)
    body["meta"].update({
        "elapsed_ms": round(result.elapsed_ms, 1),
        "optimal": result.optimal,
        "evaluations": result.evaluations,
        "search_space": problem.space_size(),
    })
    return body, 200


_DOC = """
    ---
    tags:
      - Schedule v2
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - courses
            - preferences
          properties:
            courses:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  sub_topic:
                    type: string
              example:
                - name: "Cơ sở dữ liệu"
                - name: "Lập trình hướng đối tượng"
                - name: "Kiến trúc máy tính"
            preferences:
              type: object
              description: Tài liệu ưu tiên v2 (docs/specs/json_v2/schema.json); v1 được chuyển sang v2
              example:
                version: "2.0"
                constraints:
                  - prefer: {session: "sáng"}
                  - avoid: {day: "thứ 7"}
                    level: "must"
                  - limit: "subjects_per_day"
                    max: 2
                  - relation: "different_day"
                    courses: ["Cơ sở dữ liệu", "Lập trình hướng đối tượng"]
            review_stats:
              type: array
              description: Số review theo (môn, giảng viên, aspect); cần khi có ràng buộc review
              items:
                type: object
            k:
              type: integer
              description: Số lịch trả về (1–10, mặc định 5)
            algorithm:
              type: string
              enum: [cpsat, bnb, sa, ga, nsga2, nsga2_legacy]
              description: Thuật toán (mặc định cpsat, theo docs/algorithm-comparison.md)
            time_limit:
              type: number
              description: Giới hạn thời gian, giây (mặc định 10, tối đa 60)
            budget:
              type: integer
              description: Số lần đánh giá cho metaheuristic (mặc định 5000)
    responses:
      200:
        description: "schedules (rank, classes, hard_violations, penalty, objectives, violations), constraints, unsupported, warnings, infeasible, meta"
      400:
        description: Lỗi request hoặc lỗi của cả tài liệu ưu tiên
"""


@schedule_v2_bp.route("/schedule", methods=["POST"])
def schedule_v2():
    body, status = _solve(request.get_json(silent=True), with_pinned=False)
    return jsonify(body), status


@schedule_v2_bp.route("/reschedule", methods=["POST"])
def reschedule_v2():
    body, status = _solve(request.get_json(silent=True), with_pinned=True)
    return jsonify(body), status


schedule_v2.__doc__ = "Xếp lịch theo JSON v2, trả k lịch đa dạng (design.md mục 10)\n" + _DOC
reschedule_v2.__doc__ = (
    "Xếp lại lịch: các môn trong 'pinned' giữ lớp đã đăng ký, các môn còn lại được xếp lại\n"
    + _DOC.replace("            budget:", """            pinned:
              type: array
              description: Lớp đã đăng ký thành công
              items:
                type: object
                properties:
                  course:
                    type: string
                  class_index:
                    type: string
              example:
                - {course: "Cơ sở dữ liệu", class_index: "5"}
            budget:""")
)
