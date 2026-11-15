"""POST /api/v2/schedule, /api/v2/reschedule (Phần B, task B11), với collection giả thay cho Mongo."""
from dataclasses import asdict

import pytest
from flask import Flask

from app.api.v2.schedule_api import schedule_v2_bp
from app.scheduling.solvers import SOLVERS
from conftest import AUTOMAT, CANDIDATES, CTDL, JAVA, MANG, REVIEW_STATS, TRIET


class FakeCollection:
    """Như Mongo: projection toàn 0 là loại trừ field."""

    def __init__(self, docs):
        self.docs = docs

    def find(self, criteria, projection=None):
        excluded = {key for key, value in (projection or {}).items() if not value}
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in criteria.items()):
                yield {key: value for key, value in doc.items() if key not in excluded}

COURSES = [{"name": name} for name in (AUTOMAT, CTDL, JAVA, MANG, TRIET)]
PREFERENCES = {"version": "2.0", "constraints": [
    {"prefer": {"session": "sáng"}},
    {"avoid": {"day": "thứ 7"}, "level": "must"},
    {"limit": "subjects_per_day", "max": 1},
    {"relation": "different_day", "courses": ["Automat", "Mạng máy tính"]},
    {"prefer": {"review": {"phrase": "giảng viên dạy dễ hiểu", "aspect": "ky_nang_giang_day", "sentiment": "positive"}}},
], "unsupported": ["học cùng bạn Nam"]}


@pytest.fixture
def client():
    docs = [asdict(cls) for classes in CANDIDATES.values() for cls in classes]
    app = Flask(__name__)
    app.db = {"ly_courses": FakeCollection(docs)}
    app.register_blueprint(schedule_v2_bp, url_prefix="/api/v2")
    return app.test_client()


def post(client, path="/api/v2/schedule", **body):
    body.setdefault("courses", COURSES)
    body.setdefault("preferences", PREFERENCES)
    return client.post(path, json=body)


@pytest.mark.parametrize("algorithm", list(SOLVERS))
def test_schedule_returns_conflict_free_schedules(client, algorithm):
    response = post(client, algorithm=algorithm, review_stats=REVIEW_STATS, time_limit=10, budget=1500)
    assert response.status_code == 200
    body = response.get_json()
    assert body["meta"]["algorithm"] == algorithm
    assert 1 <= len(body["schedules"]) <= 5
    for schedule in body["schedules"]:
        assert len(schedule["classes"]) == len(COURSES)
        slots = [(c["day"], p) for c in schedule["classes"] for p in c["periods"] if c["day"] != "Thứ _"]
        assert len(slots) == len(set(slots))
        assert schedule["penalty"] == sum(v["penalty"] for v in schedule["violations"] if not v["hard"])
    assert body["unsupported"][0]["source"] == "học cùng bạn Nam"
    assert [c["id"] for c in body["constraints"]] == [0, 1, 2, 3, 4]


def test_default_algorithm_is_exact_and_ranked(client):
    body = post(client, review_stats=REVIEW_STATS).get_json()
    assert body["meta"]["algorithm"] == "cpsat" and body["meta"]["optimal"] is True
    penalties = [(s["hard_violations"], s["penalty"]) for s in body["schedules"]]
    assert penalties == sorted(penalties)


def test_reschedule_keeps_pinned_classes(client):
    body = post(client, "/api/v2/reschedule", pinned=[{"course": AUTOMAT, "class_index": "4"}]).get_json()
    for schedule in body["schedules"]:
        automat = next(c for c in schedule["classes"] if c["course_name"] == AUTOMAT)
        assert automat["class_index"] == "4"


def test_unsatisfiable_must_is_reported(client):
    preferences = {"constraints": [{"prefer": {"day": "thứ 7"}, "scope": {"course": "Mạng máy tính"}, "level": "must"}]}
    body = post(client, preferences=preferences).get_json()
    assert body["schedules"][0]["hard_violations"] == 1
    assert body["infeasible"][0]["constraint_id"] == 0
    assert "Mạng máy tính" in body["infeasible"][0]["reason"]


@pytest.mark.parametrize("body, message", [
    ({"courses": COURSES}, "Thiếu 'preferences'"),
    ({"courses": [], "preferences": PREFERENCES}, "Thiếu 'courses'"),
    ({"courses": COURSES, "preferences": PREFERENCES, "algorithm": "x"}, "'algorithm'"),
    ({"courses": COURSES, "preferences": PREFERENCES, "k": 0}, "'k'"),
    ({"courses": COURSES, "preferences": {"foo": 1}}, ""),
])
def test_bad_requests(client, body, message):
    response = client.post("/api/v2/schedule", json=body)
    assert response.status_code == 400 and message in response.get_json()["error"]


def test_bad_pin(client):
    response = post(client, "/api/v2/reschedule", pinned=[{"course": AUTOMAT, "class_index": "99"}])
    assert response.status_code == 400


def test_unknown_course_is_a_warning(client):
    body = post(client, courses=COURSES + [{"name": "Môn không có"}]).get_json()
    assert "Không tìm thấy lớp nào của môn 'Môn không có'" in body["warnings"]
    assert body["schedules"]
