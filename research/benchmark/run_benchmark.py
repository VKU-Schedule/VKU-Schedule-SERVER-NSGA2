"""Chạy 6 solver trên mọi instance (docs/specs/algorithms/design.md mục 5.2).

Chạy từ gốc repo:
    python -m research.benchmark.run_benchmark              # đầy đủ
    python -m research.benchmark.run_benchmark --quick      # thử nhanh: 1 seed, ngân sách 1.500
Ghi results/runs.csv (một dòng một lần chạy). Mọi solver tất định theo seed nên chạy lại ra cùng điểm;
chỉ cột thời gian thay đổi.
"""
import argparse
import csv
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from app.scheduling.solvers import EXACT, METAHEURISTICS, SOLVERS
from research.benchmark.common import RESULTS, evaluator, instance_ids, load

# ngân sách số lần đánh giá -> số seed
BUDGETS = {1500: 10, 5000: 30, 20000: 10}
EXACT_TIME_LIMIT = 60.0
COLUMNS = ["instance", "solver", "budget", "seed", "returned", "optimal", "best_hard", "best_p", "mean_p",
           "penalties", "hards", "objectives", "xs", "evaluations", "elapsed_ms"]


def run_one(task):
    instance_id, solver, budget, seed = task
    ev = evaluator(instance_id)
    kwargs = {"k": 5, "seed": seed}
    if solver in EXACT:
        kwargs["time_limit"] = EXACT_TIME_LIMIT
    else:
        kwargs["budget"] = budget
    start = time.perf_counter()
    result = SOLVERS[solver](ev, **kwargs)
    elapsed = (time.perf_counter() - start) * 1000
    schedules = result.schedules
    assert all(s.score.conflicts == 0 for s in schedules)
    best_hard = min((s.score.hard for s in schedules), default=None)
    same = [s.score.soft for s in schedules if s.score.hard == best_hard]
    return {
        "instance": instance_id, "solver": solver, "budget": budget, "seed": seed,
        "returned": len(schedules), "optimal": result.optimal,
        "best_hard": best_hard, "best_p": min(same) if same else None,
        "mean_p": sum(same) / len(same) if same else None,
        "penalties": json.dumps([s.score.soft for s in schedules]),
        "hards": json.dumps([s.score.hard for s in schedules]),
        "objectives": json.dumps([list(s.score.objectives) for s in schedules]),
        "xs": json.dumps([list(s.x) for s in schedules]),
        "evaluations": result.evaluations, "elapsed_ms": round(elapsed, 2),
    }


def tasks(quick: bool, only=None):
    ids = only or instance_ids()
    out = []
    for instance_id in ids:
        for solver in EXACT:
            out.append((instance_id, solver, 0, 0))
        budgets = {1500: 1} if quick else BUDGETS
        for budget, seeds in budgets.items():
            for solver in METAHEURISTICS:
                for seed in range(seeds):
                    out.append((instance_id, solver, budget, seed))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--instances", nargs="*")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--out", default=str(RESULTS / "runs.csv"))
    args = parser.parse_args()
    for instance_id in args.instances or instance_ids():
        load(instance_id)   # báo lỗi sớm nếu instance hỏng
    todo = tasks(args.quick, args.instances)
    # việc dài (chính xác, ngân sách lớn) chạy trước để cân tải
    todo.sort(key=lambda t: (t[1] not in EXACT, -t[2], "synthetic" not in t[0]))
    RESULTS.mkdir(exist_ok=True)
    rows = []
    started = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_one, task) for task in todo]
        for done, future in enumerate(as_completed(futures), 1):
            rows.append(future.result())
            if done % 200 == 0 or done == len(futures):
                print(f"{done}/{len(futures)} lần chạy, {time.time() - started:.0f}s", flush=True)
    rows.sort(key=lambda r: (r["instance"], r["solver"], r["budget"], r["seed"]))
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
