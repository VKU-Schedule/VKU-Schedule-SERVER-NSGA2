"""Đọc instance và dựng Evaluator, dùng chung cho run_benchmark, case_study, analyze."""
import json
from functools import lru_cache
from pathlib import Path

from app.scheduling.constraints import Evaluator
from app.scheduling.model import build_problem
from app.scheduling.normalize import normalize_document

HERE = Path(__file__).parent
INSTANCES = HERE / "instances"
RESULTS = HERE / "results"


def instance_ids():
    return sorted(path.stem for path in INSTANCES.glob("*.json"))


@lru_cache(maxsize=None)
def load(instance_id: str):
    data = json.loads((INSTANCES / f"{instance_id}.json").read_text(encoding="utf-8"))
    candidates = data["courses"]
    document = normalize_document(data["preferences"], list(candidates), candidates, data.get("review_stats"))
    problem = build_problem(candidates, data.get("pinned") or None)
    return data, document, problem


def evaluator(instance_id: str) -> Evaluator:
    """Evaluator mới (bộ đếm số lần đánh giá về 0) cho mỗi lần chạy."""
    _, document, problem = load(instance_id)
    return Evaluator(problem, document)
