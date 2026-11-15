"""Sinh instance benchmark từ dữ liệu thật (docs/specs/algorithms/design.md mục 5.1).

Chạy từ gốc repo: python -m research.benchmark.generate_instances
Đọc data/classes.json (export từ MongoDB), ghi instances/*.json. Seed cố định nên chạy lại ra cùng file.
"""
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from app.scheduling import vocab
from app.scheduling.constraints import Evaluator
from app.scheduling.model import build_problem, class_view
from app.scheduling.normalize import normalize_document
from app.scheduling.solvers import bnb

HERE = Path(__file__).parent
DATA = HERE / "data" / "classes.json"
OUT = HERE / "instances"
SEED = 2026

SIZES = (3, 5, 7, 9)
TIERS = {"small": 0.2, "medium": 0.6, "large": 0.95, "max": 1.0}   # phân vị của log(kích thước không gian)
DENSITIES = {"light": (1, 3), "medium": (4, 6), "heavy": (7, 10)}
DAY_NAMES = {"T2": "thứ 2", "T3": "thứ 3", "T4": "thứ 4", "T5": "thứ 5", "T6": "thứ 6", "T7": "thứ 7"}
ASPECTS = ("ky_nang_giang_day", "hanh_vi", "cham_diem", "bai_tap", "kien_thuc", "noi_chung")
PHRASES = {
    ("ky_nang_giang_day", "positive"): "giảng viên dạy dễ hiểu",
    ("hanh_vi", "negative"): "giảng viên khó tính",
    ("cham_diem", "negative"): "giảng viên chấm điểm khắt khe",
    ("bai_tap", "positive"): "giảng viên giao nhiều bài tập",
    ("kien_thuc", "positive"): "giảng viên có kiến thức sâu",
    ("noi_chung", "positive"): "giảng viên tốt",
}


# ---------------------------------------------------------------------------
# Dữ liệu
# ---------------------------------------------------------------------------


def load_groups():
    """(course_name, sub_topic) -> lớp; chỉ giữ nhóm có ít nhất một lớp có lịch."""
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    groups: Dict[tuple, List[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["course_name"], row["sub_topic"])].append(row)
    usable = {}
    for key, classes in groups.items():
        if any(class_view(key[0], c).scheduled for c in classes):
            usable[key] = classes
    return usable


def field_of(classes):
    fields = [c["field"] for c in classes if c.get("field")]
    return max(set(fields), key=fields.count) if fields else "?"


def candidates_of(keys, groups):
    out = {}
    for name, sub in keys:
        out[name] = [dict(c, course_name=name) for c in groups[(name, sub)]]
    return out


def space(candidates):
    return math.prod(len({class_view(n, c).identity() for c in cls}) for n, cls in candidates.items())


def feasible(candidates):
    doc = normalize_document({"constraints": []}, list(candidates), candidates)
    result = bnb.solve(Evaluator(build_problem(candidates), doc), k=1, time_limit=5)
    return bool(result.schedules)


# ---------------------------------------------------------------------------
# Ràng buộc JSON v2 (như module LLM sinh), giá trị lấy từ chính instance
# ---------------------------------------------------------------------------


def short_teacher(name):
    name = re.sub(vocab.TEACHER_TITLE_PATTERN, "", name).strip()
    words = name.split()
    return " ".join(words[-2:]) if len(words) >= 2 else name


class ConstraintMaker:
    def __init__(self, rng: random.Random, candidates):
        self.rng = rng
        self.candidates = candidates
        self.courses = list(candidates)
        self.views = {n: [class_view(n, c) for c in cls] for n, cls in candidates.items()}

    def _course(self):
        return self.rng.choice(self.courses)

    def _day(self):
        return DAY_NAMES[self.rng.choice(list(DAY_NAMES))]

    def _scope(self, allow_course=True):
        r = self.rng.random()
        if r < 0.15 and allow_course:
            return {"course": self._course()}
        if r < 0.25:
            return {"day": self._day()}
        if r < 0.32:
            return {"session": self.rng.choice(["sáng", "chiều"])}
        return None

    def filter_constraint(self):
        rng = self.rng
        kind = rng.choice(["prefer", "avoid"])
        attr = rng.choice(["teacher", "class_group", "language", "day", "day", "session", "session", "periods",
                           "start_period", "end_period", "start_time", "end_time", "duration", "area", "room",
                           "review"])
        scope = None
        if attr == "teacher":
            course = self._course()
            known = [v.teacher for v in self.views[course] if v.teacher]
            if not known:
                return None
            value, scope = short_teacher(rng.choice(known)), {"course": course}
        elif attr == "class_group":
            course = self._course()
            groups = sorted({v.group for v in self.views[course] if v.group})
            if not groups:
                return None
            value, scope = rng.sample(groups, min(len(groups), rng.choice([1, 2]))), {"course": course}
            value = value[0] if len(value) == 1 else value
        elif attr == "language":
            value = rng.choice(["tiếng Anh", "tiếng Việt"])
        elif attr == "day":
            value = rng.choice([self._day(), [self._day(), self._day()], "cuối tuần"])
        elif attr == "session":
            value = rng.choice(["sáng", "chiều", "sáng sớm", "chiều muộn"])
        elif attr == "periods":
            low = rng.randint(1, 7)
            value = {"min": low, "max": min(10, low + rng.randint(1, 4))}
        elif attr == "start_period":
            value = {"min": rng.randint(2, 7)} if kind == "prefer" else {"max": rng.randint(1, 2)}
        elif attr == "end_period":
            value = {"max": rng.randint(4, 9)}
        elif attr == "start_time":
            value = {"min": f"{rng.randint(8, 14)}:00"}
        elif attr == "end_time":
            value = {"max": f"{rng.randint(11, 17)}:00"}
        elif attr == "duration":
            value = {"min": rng.randint(3, 4)} if kind == "avoid" else {"max": rng.randint(2, 3)}
        elif attr == "area":
            value = rng.choice(["K", "V"])
        elif attr == "room":
            rooms = sorted({v.room for vs in self.views.values() for v in vs if v.room})
            if not rooms:
                return None
            value = rng.choice(rooms)
        else:  # review
            aspect, sentiment = rng.choice(list(PHRASES))
            value = {"phrase": PHRASES[(aspect, sentiment)], "aspect": aspect, "sentiment": sentiment}
            if rng.random() < 0.4:
                scope = {"course": self._course()}
        constraint = {kind: {attr: value}}
        if attr == "day" and kind == "prefer" and rng.random() < 0.3:
            constraint[kind]["session"] = rng.choice(["sáng", "chiều"])
        scope = scope or (self._scope() if attr != "review" else None)
        if scope and not set(scope) & set(constraint[kind]):
            constraint["scope"] = scope
        return constraint

    def limit_constraint(self):
        rng = self.rng
        metric = rng.choice(list(vocab.METRICS))
        if metric == "subjects_per_day":
            bounds = rng.choice([{"max": rng.randint(1, 3)}, {"min": 2}, {"min": 1, "max": 2}])
        elif metric == "subjects_per_session":
            bounds = rng.choice([{"max": 1}, {"max": 2}])
        elif metric == "periods_per_day":
            bounds = rng.choice([{"max": rng.randint(4, 8)}, {"min": 4}])
        elif metric == "gap_periods":
            bounds = rng.choice([{"min": 1}, {"max": 1}, {"max": 0}])
        elif metric == "consecutive_periods":
            bounds = {"max": rng.randint(3, 5)}
        else:
            bounds = rng.choice([{"max": rng.randint(2, 4)}, {"min": 4}, {"max": 1}])
        constraint = {"limit": metric, **bounds}
        if rng.random() < 0.15:
            constraint["scope"] = {"day": [self._day(), self._day()]}
        return constraint

    def relation_constraint(self):
        rng = self.rng
        if len(self.courses) < 2:
            return None
        relation = rng.choice(list(vocab.RELATIONS))
        courses = rng.sample(self.courses, rng.choice([2, 2, 3]) if len(self.courses) >= 3 else 2)
        return {"relation": relation, "courses": courses}

    def make(self, count, force_must):
        constraints = []
        while len(constraints) < count:
            r = self.rng.random()
            c = self.filter_constraint() if r < 0.6 else self.limit_constraint() if r < 0.85 else self.relation_constraint()
            if c is None or c in constraints:
                continue
            level = self.rng.random()
            if level < 0.15:
                c["level"] = "must"
            elif level < 0.30:
                c["level"] = "high"
            constraints.append(c)
        if force_must and not any(c.get("level") == "must" for c in constraints):
            constraints[0]["level"] = "must"
        return constraints

    def review_stats(self):
        rows = []
        for course, views in self.views.items():
            for teacher in sorted({v.teacher for v in views if v.teacher}):
                for aspect in ASPECTS[:-1]:
                    if self.rng.random() < 0.6:
                        total = self.rng.randint(0, 20)
                        positive = self.rng.randint(0, total)
                        negative = self.rng.randint(0, total - positive)
                        rows.append({"subject": course, "lecturer": short_teacher(teacher), "aspect": aspect,
                                     "positive": positive, "negative": negative, "total": total})
        return rows


# ---------------------------------------------------------------------------
# Sinh
# ---------------------------------------------------------------------------


def pick_course_sets(rng, groups, n, samples=400):
    by_field = defaultdict(list)
    for key, classes in groups.items():
        by_field[field_of(classes)].append(key)
    fields = [f for f, keys in by_field.items() if len({k[0] for k in keys}) >= n + 3]
    sets = []
    tries = 0
    while len(sets) < samples and tries < samples * 20:
        tries += 1
        f = rng.choice(fields)
        keys = rng.sample(by_field[f], n)
        if len({k[0] for k in keys}) < n:
            continue
        cands = candidates_of(keys, groups)
        sets.append((math.log10(space(cands)), f, keys))
    sets.sort(key=lambda item: item[0])
    return sets


def write(instance):
    path = OUT / f"{instance['id']}.json"
    path.write_text(json.dumps(instance, ensure_ascii=False, indent=1), encoding="utf-8")


def instance_dict(iid, kind, keys, groups, constraints, maker, field, tier=None, density=None, pinned=None,
                  candidates=None):
    candidates = candidates or candidates_of(keys, groups)
    return {
        "id": iid, "kind": kind, "n": len(candidates), "tier": tier, "density": density, "field": field,
        "space": space(candidates), "courses": candidates,
        "preferences": {"version": "2.0", "constraints": constraints},
        "review_stats": maker.review_stats(), "pinned": pinned or {},
    }


def synthetic(rng, groups, n, per_course):
    """Instance tổng hợp: thứ/tiết/giảng viên/phòng lấy theo phân bố thật."""
    pool = [c for classes in groups.values() for c in classes if class_view("x", c).scheduled]
    candidates = {}
    for i in range(n):
        name = f"Môn tổng hợp {i + 1:02d}"
        base = rng.choice(pool)
        candidates[name] = []
        for g in range(per_course):
            src = rng.choice(pool)
            candidates[name].append({
                "course_name": name, "sub_topic": None, "class_index": str(g + 1),
                "language": base["language"], "field": "SYN", "teacher": rng.choice(pool)["teacher"],
                "day": src["day"], "periods": src["periods"], "area": src["area"], "room": src["room"],
                "class_size": src["class_size"],
            })
    return candidates


def main():
    rng = random.Random(SEED)
    groups = load_groups()
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    count = 0
    keep_for_special = None
    for n in SIZES:
        sets = pick_course_sets(rng, groups, n)
        for tier, q in TIERS.items():
            # lấy bộ môn gần phân vị q mà có lịch không trùng
            index = int(q * (len(sets) - 1))
            for offset in range(len(sets)):
                j = max(0, min(len(sets) - 1, index + (offset // 2 + 1) * (-1) ** offset)) if offset else index
                _, field, keys = sets[j]
                if feasible(candidates_of(keys, groups)):
                    break
            for density, (low, high) in DENSITIES.items():
                maker = ConstraintMaker(random.Random(rng.random()), candidates_of(keys, groups))
                constraints = maker.make(rng.randint(low, high), force_must=density == "heavy")
                iid = f"real_n{n}_{tier}_{density}"
                write(instance_dict(iid, "real", keys, groups, constraints, maker, field, tier, density))
                count += 1
            if n == 7 and tier == "medium":
                keep_for_special = (field, keys)

    # ca đặc biệt
    field, keys = keep_for_special
    candidates = candidates_of(keys, groups)
    maker = ConstraintMaker(random.Random(SEED + 1), candidates)
    # môn mà mọi lớp đều có lịch: bắt buộc bắt đầu sau tiết bắt đầu muộn nhất của nó → không thoả được
    course = next(name for name, _ in keys if all(class_view(name, c).scheduled for c in candidates[name]))
    latest = max(class_view(course, c).start for c in candidates[course])
    constraints = maker.make(4, force_must=False) + [
        {"prefer": {"start_period": {"min": latest + 1}}, "scope": {"course": course}, "level": "must"}]
    write(instance_dict("special_infeasible_must", "special", keys, groups, constraints, maker, field))
    constraints = maker.make(4, force_must=False) + [
        {"prefer": {"session": "sáng"}}, {"avoid": {"session": "sáng"}},
        {"relation": "same_day", "courses": [keys[1][0], keys[2][0]]},
        {"relation": "different_day", "courses": [keys[1][0], keys[2][0]]}]
    write(instance_dict("special_contradiction", "special", keys, groups, constraints, maker, field))
    constraints = maker.make(5, force_must=False)
    doc = normalize_document({"constraints": constraints}, list(candidates), candidates)
    best = bnb.solve(Evaluator(build_problem(candidates), doc), k=1, time_limit=10).schedules[0].x
    problem = build_problem(candidates)
    pinned = {problem.courses[i]: problem.options[i][best[i]].class_index
              for i in range(0, problem.n, 2) if problem.options[i][best[i]].class_index}
    write(instance_dict("special_reschedule", "special", keys, groups, constraints, maker, field, pinned=pinned))
    count += 3

    # tổng hợp lớn
    for n, per_course in ((12, 20), (12, 50), (15, 20), (15, 50)):
        for attempt in range(20):
            cands = synthetic(rng, groups, n, per_course)
            if feasible(cands):
                break
        maker = ConstraintMaker(random.Random(rng.random()), cands)
        constraints = maker.make(rng.randint(5, 8), force_must=True)
        write(instance_dict(f"synthetic_n{n}_c{per_course}", "synthetic", None, groups, constraints, maker, "SYN",
                            density="medium", candidates=cands))
        count += 1
    print(f"{count} instance -> {OUT}")


if __name__ == "__main__":
    main()
