"""POST /api/preferences/validate (task T10), chạy với collection giả thay cho Mongo."""
import pytest
from flask import Flask

from app.api.preferences_api import preferences_bp
from conftest import CANDIDATES, REVIEW_STATS, design_examples, load_examples


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, criteria, projection=None):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in criteria.items()):
                yield {key: doc.get(key) for key in projection if key != "_id"} if projection else dict(doc)


@pytest.fixture
def client():
    docs = [
        {"course_name": cls.course_name, "sub_topic": cls.sub_topic, "teacher": cls.teacher, "class_index": cls.class_index}
        for classes in CANDIDATES.values() for cls in classes
    ]
    app = Flask(__name__)
    app.db = {"ly_courses": FakeCollection(docs)}
    app.register_blueprint(preferences_bp, url_prefix="/api")
    return app.test_client()


COURSES = [{"name": name} for name in CANDIDATES]


EXPECTED = {example["id"]: example["expected"] for example in load_examples()}


@pytest.mark.parametrize("example_id, raw", [(eid, raw) for eid, _, raw in design_examples()])
def test_every_design_example_validates(client, example_id, raw):
    response = client.post("/api/preferences/validate",
                           json={"courses": COURSES, "preferences": raw, "review_stats": REVIEW_STATS})
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["constraints"]) == len(EXPECTED[example_id]["constraints"])


def test_review_without_review_stats_is_unsupported(client):
    raw = {"constraints": [{"prefer": {"review": {"phrase": "giảng viên dạy dễ hiểu", "aspect": "ky_nang_giang_day",
                                                  "sentiment": "positive"}}}]}
    body = client.post("/api/preferences/validate", json={"courses": COURSES, "preferences": raw}).get_json()
    assert body["constraints"] == []
    assert "thiếu dữ liệu review" in body["unsupported"][0]["reason"]


def test_bad_review_stats_row_is_a_warning(client):
    body = client.post("/api/preferences/validate", json={
        "courses": COURSES, "preferences": {"constraints": []}, "review_stats": [REVIEW_STATS[0], {"subject": "x"}],
    }).get_json()
    assert body["warnings"] == ["Bỏ qua dòng 1 của 'review_stats': 'lecturer' phải là chuỗi không rỗng"]


def test_response_shape(client):
    response = client.post("/api/preferences/validate", json={
        "courses": [{"name": "Automat và ngôn ngữ hình thức"}, "Lập trình Java"],
        "preferences": {"constraints": [
            {"prefer": {"teacher": "Mai Nga"}, "scope": {"course": "Automat"}},
            {"prefer": {"weather": "nắng"}},
        ], "unsupported": ["muốn học cùng lớp với bạn Nam"]},
    })
    assert response.status_code == 200
    body = response.get_json()
    assert body["constraints"][0]["condition"] == {"teacher": ["ThS.Dương Thị Mai Nga"]}
    assert [item["index"] for item in body["unsupported"]] == [1, None]
    assert body["warnings"] == []


def test_course_without_classes_warns(client):
    response = client.post("/api/preferences/validate", json={
        "courses": [{"name": "Kinh tế vĩ mô"}], "preferences": {"constraints": []},
    })
    assert response.get_json()["warnings"] == ["Không tìm thấy lớp nào của môn 'Kinh tế vĩ mô'"]


def test_v1_document_is_converted(client):
    response = client.post("/api/preferences/validate", json={
        "preferences": {"defaults": {"area": {"value": "K", "like": True}}},
    })
    body = response.get_json()
    assert body["constraints"][0]["condition"] == {"area": ["K"]}
    assert body["warnings"] == ["Tài liệu đã được chuyển từ v1 sang v2"]


@pytest.mark.parametrize("payload", [
    {"courses": []},                                            # thiếu preferences
    {"preferences": {}},                                        # V9
    {"preferences": {"version": "1.0", "constraints": []}},     # V11
    {"courses": "Java", "preferences": {"constraints": []}},
    {"courses": [{"sub_topic": "x"}], "preferences": {"constraints": []}},
])
def test_bad_requests(client, payload):
    response = client.post("/api/preferences/validate", json=payload)
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_non_json_body(client):
    response = client.post("/api/preferences/validate", data="x", content_type="text/plain")
    assert response.status_code == 400
