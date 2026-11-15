"""Case study: yêu cầu cụ thể của sinh viên, môn thật trong MongoDB (design.md mục 5.5).

Chạy từ gốc repo:
    python -m research.benchmark.case_study --write-instances   # ghi instances/case_*.json
    python -m research.benchmark.case_study                     # chạy 6 solver, ghi results/case_study.md
Các instance case_* cũng được run_benchmark chạy như mọi instance khác.
"""
import argparse
import json
import random

from app.scheduling.solvers import SOLVERS
from research.benchmark.analyze import LABEL, ORDER
from research.benchmark.common import INSTANCES, RESULTS, evaluator, load
from research.benchmark.generate_instances import DATA, ConstraintMaker, space

CSDL, OOP, KTMT, HDH = "Cơ sở dữ liệu", "Lập trình hướng đối tượng", "Kiến trúc máy tính", "Nguyên lý hệ điều hành"
PTTKGT, TRIET, TANC2 = "Phân tích và thiết kế giải thuật", "Triết học Mác - Lênin", "Tiếng Anh nâng cao 2"
WEB, MANG, AI, PTTKHT, KHO, CNXH = ("Công nghệ và lập trình web", "Lập trình mạng", "Trí tuệ nhân tạo",
                                     "Phân tích và thiết kế hệ thống", "Kho dữ liệu", "Chủ nghĩa xã hội khoa học")

CASES = {
    "case_a_year2": {
        "courses": [CSDL, OOP, KTMT, HDH, PTTKGT, TRIET, TANC2],
        "prompt": ("Em muốn học Cơ sở dữ liệu với cô Mai Nga, tránh thầy Nguyễn Văn Lợi. Em thích học buổi sáng, "
                   "riêng thứ 5 thì học chiều. Tuyệt đối không học thứ 7. Mỗi ngày tối đa 2 môn, lên trường tối đa "
                   "4 ngày, không học quá 4 tiết liền. Lập trình hướng đối tượng em muốn học lớp tiếng Việt. Cơ sở "
                   "dữ liệu và Lập trình hướng đối tượng không học chung một ngày. Em muốn học với giảng viên dạy dễ "
                   "hiểu. Em muốn học cùng lớp với bạn Nam."),
        "constraints": [
            {"prefer": {"teacher": "Mai Nga"}, "scope": {"course": CSDL}},
            {"avoid": {"teacher": "Nguyễn Văn Lợi"}, "scope": {"course": CSDL}},
            {"prefer": {"session": "sáng"}},
            {"prefer": {"session": "chiều"}, "scope": {"day": "thứ 5"}},
            {"avoid": {"day": "thứ 7"}, "level": "must"},
            {"limit": "subjects_per_day", "max": 2},
            {"limit": "study_days", "max": 4},
            {"limit": "consecutive_periods", "max": 4},
            {"prefer": {"language": "tiếng Việt"}, "scope": {"course": OOP}},
            {"relation": "different_day", "courses": [CSDL, OOP]},
            {"prefer": {"review": {"phrase": "giảng viên dạy dễ hiểu", "aspect": "ky_nang_giang_day",
                                   "sentiment": "positive"}}},
        ],
        "unsupported": ["muốn học cùng lớp với bạn Nam"],
    },
    "case_b_year3": {
        "courses": [WEB, MANG, AI, PTTKHT, KHO, CNXH],
        "prompt": ("Em chỉ học nếu lớp bắt đầu sau 8 giờ. Em muốn dồn lịch vào ít ngày nhất, nghỉ ít nhất 1 tiết "
                   "giữa các môn, và thích học ở khu K. Hôm nào có cả hai thì em muốn học Trí tuệ nhân tạo trước "
                   "Lập trình mạng. Môn Lập trình mạng em tránh thầy Lê Tân. Em rất không muốn học thứ 2."),
        "constraints": [
            {"prefer": {"start_time": {"min": "8:00"}}, "level": "must"},
            {"limit": "study_days", "max": 1},
            {"limit": "gap_periods", "min": 1},
            {"prefer": {"area": "K"}},
            {"relation": "before", "courses": [AI, MANG]},
            {"avoid": {"teacher": "Lê Tân"}, "scope": {"course": MANG}},
            {"avoid": {"day": "thứ 2"}, "level": "high"},
        ],
        "unsupported": [],
    },
}
# reschedule: case A, đã đăng ký được 3 môn, xếp lại các môn còn lại
RESCHEDULE = ("case_c_reschedule", "case_a_year2", {OOP: "6", TRIET: "9", TANC2: "7"})


def write_instances():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    for case_id, case in CASES.items():
        candidates = {name: [dict(r) for r in rows if r["course_name"] == name and r["sub_topic"] is None]
                      for name in case["courses"]}
        maker = ConstraintMaker(random.Random(case_id), candidates)
        instance = {
            "id": case_id, "kind": "case", "n": len(candidates), "tier": None, "density": None, "field": "IT",
            "space": space(candidates), "prompt": case["prompt"], "courses": candidates,
            "preferences": {"version": "2.0", "constraints": case["constraints"], "unsupported": case["unsupported"]},
            # Số liệu review giả: repo không có dữ liệu Review service
            "review_stats": maker.review_stats(), "pinned": {},
        }
        (INSTANCES / f"{case_id}.json").write_text(json.dumps(instance, ensure_ascii=False, indent=1), encoding="utf-8")
    new_id, base_id, pinned = RESCHEDULE
    instance = json.loads((INSTANCES / f"{base_id}.json").read_text(encoding="utf-8"))
    instance.update(id=new_id, pinned=pinned,
                    prompt="Xếp lại lịch của case A: đã đăng ký được " + ", ".join(f"{c} nhóm {g}" for c, g in pinned.items()))
    (INSTANCES / f"{new_id}.json").write_text(json.dumps(instance, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> instances/case_*.json")


def describe(problem, x):
    parts = []
    for i, l in enumerate(x):
        v = problem.options[i][l]
        when = f"{v.day} t{v.start}-{v.end}" if v.scheduled else "chưa xếp lịch"
        parts.append(f"{problem.courses[i]} nhóm {v.class_index or '?'} ({when}, {v.teacher or '?'})")
    return "; ".join(parts)


def run(budget=5000, seed=0):
    lines = ["# Case study (tự sinh bởi case_study.py)\n",
             f"Metaheuristic: ngân sách {budget} lần đánh giá, seed {seed}. B&B, CP-SAT: giới hạn 60 giây.\n"]
    for case_id in ("case_a_year2", "case_b_year3", "case_c_reschedule"):
        data, document, problem = load(case_id)
        lines.append(f"## {case_id}\n")
        lines.append(f"> {data['prompt']}\n")
        lines.append(f"- {problem.n} môn, {problem.sizes} lớp ứng viên, không gian {problem.space_size():.2e}.")
        if data["pinned"]:
            lines.append(f"- Ghim: {data['pinned']}.")
        lines.append(f"- Unsupported: {[u.source for u in document.unsupported]}; warnings: {document.warnings}.\n")
        lines.append("```json\n" + json.dumps(data["preferences"]["constraints"], ensure_ascii=False) + "\n```\n")
        for name in ORDER:
            ev = evaluator(case_id)
            result = SOLVERS[name](ev, k=5, budget=budget, seed=seed, time_limit=60)
            lines.append(f"### {LABEL[name]}: {len(result.schedules)} lịch, {result.elapsed_ms:.0f} ms, "
                         f"{result.evaluations} lần đánh giá"
                         + (f", tối ưu đã chứng minh: {result.optimal}" if result.optimal is not None else "") + "\n")
            lines.append("| # | H | P | vi phạm (id: số lần → phạt) | lịch |")
            lines.append("|---|---|---|---|---|")
            for rank, s in enumerate(result.schedules, 1):
                violations = ", ".join(f"{v.constraint_id}: {v.amount}→{'cứng' if v.hard else v.penalty}"
                                       for v in ev.explain(s.x)) or "—"
                lines.append(f"| {rank} | {s.score.hard} | {s.score.soft} | {violations} | {describe(problem, s.x)} |")
            lines.append("")
    (RESULTS / "case_study.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"-> {RESULTS / 'case_study.md'}")


def _class_json(v):
    return {"course": v.course, "group": v.class_index, "day": v.day, "periods": list(v.periods),
            "teacher": v.teacher, "language": v.language, "area": v.area, "room": v.room}


def _culprits(ev, x):
    """Ràng buộc prefer/avoid -> các môn có lớp được chọn vi phạm nó."""
    found = {}
    for rule, coeff in ev.filter_rules:
        for i in range(ev.problem.n):
            if coeff[i][x[i]]:
                found.setdefault(rule.constraint.id, []).append(ev.problem.courses[i])
    return found


def export_json(budget=5000, seed=0):
    """Cùng lần chạy như run(), ghi đầy đủ dạng JSON cho report HTML (results/case_study.json)."""
    out = {"budget": budget, "seed": seed, "cases": []}
    for case_id in ("case_a_year2", "case_b_year3", "case_c_reschedule"):
        data, document, problem = load(case_id)
        probe = evaluator(case_id)
        resolved = {}
        for c in probe.constraints:  # ràng buộc review đã quy về giảng viên, theo môn
            if "teacher" in c.condition and "review" in c.source.get(c.kind, {}):
                resolved.setdefault(c.id, []).append(
                    {"course": next(iter(c.scope["course"])), "teachers": sorted(c.condition["teacher"])})
        constraints = [{"id": c.id, "kind": c.kind, "level": c.level, "weight": c.weight, "source": c.source,
                        "review_teachers": resolved.get(c.id)} for c in document.constraints]
        case = {
            "id": case_id, "prompt": data["prompt"], "pinned": data["pinned"],
            "courses": [{"name": name, "classes": size} for name, size in zip(problem.courses, problem.sizes)],
            "space": problem.space_size(), "constraints": constraints,
            "unsupported": [u.source for u in document.unsupported],
            "warnings": list(document.warnings) + probe.warnings, "solvers": {},
        }
        for name in ORDER:
            ev = evaluator(case_id)
            result = SOLVERS[name](ev, k=5, budget=budget, seed=seed, time_limit=60)
            case["solvers"][name] = {
                "elapsed_ms": round(result.elapsed_ms, 1), "evaluations": result.evaluations,
                "optimal": result.optimal,
                "schedules": [{
                    "hard": s.score.hard, "soft": s.score.soft, "objectives": list(s.score.objectives),
                    "violations": [dict(v._asdict(), courses=_culprits(ev, s.x).get(v.constraint_id, []))
                                   for v in ev.explain(s.x)],
                    "classes": [_class_json(v) for v in problem.classes(s.x)],
                } for s in result.schedules],
            }
        out["cases"].append(case)
    path = RESULTS / "case_study.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=sorted), encoding="utf-8")
    print(f"-> {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-instances", action="store_true")
    parser.add_argument("--json", action="store_true", help="ghi results/case_study.json cho report HTML")
    args = parser.parse_args()
    if args.write_instances:
        write_instances()
    elif args.json:
        export_json()
    else:
        run()
