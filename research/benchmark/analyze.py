"""Phân tích results/runs.csv (docs/specs/algorithms/design.md mục 5.3, 5.4).

Chạy từ gốc repo: python -m research.benchmark.analyze
Ghi results/metrics.csv, results/reference.csv, results/summary.md và các biểu đồ results/*.png.
"""
import itertools
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from research.benchmark.common import RESULTS, load  # noqa: E402

MAIN_BUDGET = 5000
ORDER = ["bnb", "cpsat", "sa", "ga", "nsga2_legacy", "nsga2"]
LABEL = {"bnb": "B&B", "cpsat": "CP-SAT", "sa": "SA", "ga": "GA", "nsga2_legacy": "NSGA-II gốc",
         "nsga2": "NSGA-II cải tiến"}


def hypervolume(points, ref):
    """HV chính xác bằng bao hàm–loại trừ (≤ 5 điểm), điểm lý tưởng là gốc toạ độ."""
    points = [p for p in points if all(v < r for v, r in zip(p, ref))]
    total = 0.0
    for size in range(1, len(points) + 1):
        for subset in itertools.combinations(points, size):
            corner = [max(p[d] for p in subset) for d in range(3)]
            total += (-1) ** (size + 1) * math.prod(r - c for r, c in zip(ref, corner))
    return total / math.prod(ref)


def reference_table(runs):
    rows = []
    for instance, group in runs.groupby("instance"):
        exact = group[group.solver.isin(["bnb", "cpsat"])]
        proven = exact[exact.optimal == True]  # noqa: E712
        pool = proven if len(proven) else group[group.returned > 0]
        best_hard = pool.best_hard.min()
        pool = pool[pool.best_hard == best_hard]
        # top-5 chuẩn: lời giải chính xác đã chứng minh có trung bình nhỏ nhất (hai solver có thể chọn khác nhau khi hoà)
        pool = pool.assign(_mean=pool.apply(lambda r: np.mean(json.loads(r.penalties)), axis=1))
        best = pool.sort_values(["best_p", "_mean"]).iloc[0]
        penalties = sorted(p for p, h in zip(json.loads(best.penalties), json.loads(best.hards)) if h == best_hard)
        data, _, problem = load(instance)
        rows.append({
            "instance": instance, "kind": data["kind"], "n": data["n"], "tier": data["tier"],
            "density": data["density"], "log10_space": math.log10(problem.space_size()),
            "constraints": len(data["preferences"]["constraints"]),
            "ref_proven": bool(len(proven)), "ref_hard": int(best_hard), "ref_best": int(min(penalties)),
            "ref_penalties": json.dumps(penalties), "ref_mean": float(np.mean(penalties)),
            "ref_count": len(penalties), "ref_solver": best.solver,
        })
    return pd.DataFrame(rows).set_index("instance")


def metrics(runs, ref):
    # điểm tham chiếu HV chung cho mỗi instance: lớn nhất của mọi lịch trả về + 1
    hv_ref = {}
    for instance, group in runs.groupby("instance"):
        objs = [o for cell in group.objectives for o in json.loads(cell)]
        hv_ref[instance] = [max([o[d] for o in objs] + [0]) + 1 for d in range(3)]
    out = []
    for row in runs.itertuples():
        r = ref.loc[row.instance]
        penalties = json.loads(row.penalties)
        hards = json.loads(row.hards)
        objs = json.loads(row.objectives)
        xs = json.loads(row.xs)
        good = sorted(p for p, h in zip(penalties, hards) if h == r.ref_hard)
        feasible = bool(good) and row.best_hard == r.ref_hard
        ref_pen = json.loads(r.ref_penalties)
        padded = (good + [max(ref_pen) + 1] * r.ref_count)[:r.ref_count]
        n = r.n
        pairs = list(itertools.combinations(xs, 2))
        diversity = np.mean([sum(a != b for a, b in zip(p, q)) / n for p, q in pairs]) if pairs else 0.0
        hv = hypervolume([o for o, h in zip(objs, hards) if h == r.ref_hard], hv_ref[row.instance])
        out.append({
            "instance": row.instance, "solver": row.solver, "budget": row.budget, "seed": row.seed,
            "kind": r.kind, "n": n, "tier": r.tier, "density": r.density, "log10_space": r.log10_space,
            "returned": row.returned, "full": row.returned >= r.ref_count,
            "feasible": feasible, "hit": feasible and good[0] == r.ref_best,
            "gap_best": (good[0] - r.ref_best) if feasible else np.nan,
            "gap_mean": float(np.mean(padded) - r.ref_mean) if feasible else np.nan,
            "diversity": diversity, "hv": hv, "elapsed_ms": row.elapsed_ms, "evaluations": row.evaluations,
            "optimal": row.optimal,
        })
    return pd.DataFrame(out)


def main_rows(m):
    """Solver chính xác (1 lần chạy) và metaheuristic ở ngân sách chính."""
    return m[(m.solver.isin(["bnb", "cpsat"])) | (m.budget == MAIN_BUDGET)]


def summary_table(m):
    g = m.groupby("solver")
    table = pd.DataFrame({
        "lần chạy": g.size(),
        "khả thi %": 100 * g.feasible.mean(),
        "đạt tối ưu %": 100 * g.hit.mean(),
        "đủ 5 lịch %": 100 * g.full.mean(),
        "gap_best TB": g.gap_best.mean(),
        "gap_mean TB": g.gap_mean.mean(),
        "đa dạng": g.diversity.mean(),
        "HV": g.hv.mean(),
        "thời gian trung vị (ms)": g.elapsed_ms.median(),
        "thời gian p95 (ms)": g.elapsed_ms.quantile(0.95),
        "thời gian max (ms)": g.elapsed_ms.max(),
        "số lần đánh giá TB": g.evaluations.mean(),
    })
    return table.reindex([s for s in ORDER if s in table.index]).rename(index=LABEL)


def stability_table(m):
    """Độ lệch chuẩn giữa các seed của gap_mean, trung bình qua instance (metaheuristic)."""
    meta = m[~m.solver.isin(["bnb", "cpsat"])]
    std = meta.groupby(["solver", "instance"]).gap_mean.std().groupby("solver").mean()
    hit = meta.groupby(["solver", "instance"]).hit.mean()
    all_hit = (hit == 1).groupby("solver").mean() * 100
    return pd.DataFrame({"độ lệch chuẩn gap_mean": std, "instance đạt tối ưu ở mọi seed %": all_hit}) \
        .reindex([s for s in ORDER if s in std.index]).rename(index=LABEL)


def friedman(m, value, lower_better=True):
    per = main_rows(m).groupby(["instance", "solver"])[value].median().unstack()
    per = per[[s for s in ORDER if s in per.columns]].dropna()
    if lower_better is False:
        per = -per
    statistic, p = stats.friedmanchisquare(*[per[c] for c in per.columns])
    ranks = per.rank(axis=1).mean().rename(index=LABEL)
    pairs = []
    for a, b in itertools.combinations(per.columns, 2):
        diff = per[a] - per[b]
        if (diff == 0).all():
            pairs.append((a, b, 1.0))
            continue
        pairs.append((a, b, stats.wilcoxon(per[a], per[b], zero_method="zsplit").pvalue))
    # Holm
    ordered = sorted(range(len(pairs)), key=lambda i: pairs[i][2])
    adjusted = [None] * len(pairs)
    running = 0.0
    for rank, i in enumerate(ordered):
        running = max(running, min(1.0, (len(pairs) - rank) * pairs[i][2]))
        adjusted[i] = running
    post = pd.DataFrame([{"A": LABEL[a], "B": LABEL[b], "p (Wilcoxon)": p, "p (Holm)": adj,
                          "trung vị A − B": float((per[a] - per[b]).median())}
                         for (a, b, p), adj in zip(pairs, adjusted)])
    return statistic, p, ranks, post, len(per)


def plots(m):
    main = main_rows(m)
    real = main[main.kind != "synthetic"]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for solver in ORDER:
        part = real[real.solver == solver].groupby("instance").agg(x=("log10_space", "first"), y=("elapsed_ms", "median"))
        ax.scatter(part.x, part.y.clip(lower=0.1), s=14, label=LABEL[solver])
    ax.set_yscale("log")
    ax.set_xlabel("log10 kích thước không gian tìm kiếm")
    ax.set_ylabel("thời gian trung vị (ms, log)")
    ax.set_title("Thời gian chạy trên instance thật")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(RESULTS / "time_vs_space.png", dpi=130)
    plt.close(fig)

    meta = m[~m.solver.isin(["bnb", "cpsat"])]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for solver in [s for s in ORDER if s in meta.solver.unique()]:
        part = meta[meta.solver == solver].groupby("budget")
        axes[0].plot(part.hit.mean().index, 100 * part.hit.mean().values, marker="o", label=LABEL[solver])
        axes[1].plot(part.gap_mean.mean().index, part.gap_mean.mean().values, marker="o", label=LABEL[solver])
    for ax, title in zip(axes, ("đạt tối ưu (%)", "gap_mean trung bình")):
        ax.set_xscale("log")
        ax.set_xlabel("ngân sách (số lần đánh giá)")
        ax.set_title(title)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(RESULTS / "convergence.png", dpi=130)
    plt.close(fig)


def md(df, floatfmt=".2f"):
    return df.to_markdown(floatfmt=floatfmt)


def main():
    runs = pd.concat([pd.read_csv(path) for path in sorted(RESULTS.glob("runs*.csv"))], ignore_index=True)
    ref = reference_table(runs)
    ref.to_csv(RESULTS / "reference.csv")
    m = metrics(runs, ref)
    m.to_csv(RESULTS / "metrics.csv", index=False)
    main = main_rows(m)

    parts = ["# Kết quả benchmark (tự sinh bởi analyze.py)\n"]
    parts.append(f"- {runs.instance.nunique()} instance, {len(runs)} lần chạy.")
    parts.append(f"- Chuẩn chứng minh tối ưu ở {int(ref.ref_proven.sum())}/{len(ref)} instance "
                 f"(không chứng minh được: {', '.join(ref.index[~ref.ref_proven]) or 'không có'}).")
    parts.append(f"- Ngân sách chính của metaheuristic: {MAIN_BUDGET} lần đánh giá.\n")

    for title, subset in (("Instance thật (dữ liệu MongoDB, gồm ca đặc biệt)", main[main.kind != "synthetic"]),
                          ("Instance tổng hợp lớn", main[main.kind == "synthetic"])):
        parts.append(f"## {title}\n")
        parts.append(md(summary_table(subset)) + "\n")

    parts.append("## Theo tầng không gian (instance thật, gap_mean TB / thời gian trung vị ms)\n")
    real = main[main.kind == "real"]
    gap = real.pivot_table(index="tier", columns="solver", values="gap_mean", aggfunc="mean")
    time_ = real.pivot_table(index="tier", columns="solver", values="elapsed_ms", aggfunc="median")
    tiers = ["small", "medium", "large", "max"]
    parts.append(md(gap.reindex(tiers)[[s for s in ORDER if s in gap]].rename(columns=LABEL)) + "\n")
    parts.append(md(time_.reindex(tiers)[[s for s in ORDER if s in time_]].rename(columns=LABEL), ".1f") + "\n")

    parts.append("## Theo số môn n (instance thật, thời gian max ms)\n")
    tmax = real.pivot_table(index="n", columns="solver", values="elapsed_ms", aggfunc="max")
    parts.append(md(tmax[[s for s in ORDER if s in tmax]].rename(columns=LABEL), ".0f") + "\n")

    parts.append("## Ca đặc biệt\n")
    special = main[main.kind == "special"].pivot_table(index="instance", columns="solver",
                                                       values=["gap_mean", "returned"], aggfunc="mean")
    parts.append(md(special) + "\n")

    parts.append("## Theo ngân sách (metaheuristic, mọi instance)\n")
    meta = m[~m.solver.isin(["bnb", "cpsat"])]
    conv = meta.groupby(["solver", "budget"]).agg(hit=("hit", "mean"), gap_mean=("gap_mean", "mean"),
                                                   feasible=("feasible", "mean"), ms=("elapsed_ms", "median"))
    parts.append(md(conv) + "\n")

    parts.append("## Độ ổn định giữa các seed (ngân sách chính)\n")
    parts.append(md(stability_table(main)) + "\n")

    for value, label in (("gap_mean", "chất lượng (gap_mean, nhỏ hơn tốt hơn)"),
                         ("elapsed_ms", "thời gian (nhỏ hơn tốt hơn)")):
        for kind_label, subset in (("instance thật", m[m.kind != "synthetic"]), ("mọi instance", m)):
            stat, p, ranks, post, blocks = friedman(subset, value)
            parts.append(f"## Friedman: {label}, {kind_label}\n")
            parts.append(f"χ² = {stat:.2f}, p = {p:.3g}, {blocks} instance.\n")
            parts.append("Hạng trung bình (1 là tốt nhất):\n")
            parts.append(md(ranks.to_frame("hạng TB")) + "\n")
            parts.append(md(post.set_index(["A", "B"]), ".3g") + "\n")

    (RESULTS / "summary.md").write_text("\n".join(parts), encoding="utf-8")
    plots(m)
    print(f"-> {RESULTS / 'summary.md'}")


if __name__ == "__main__":
    main()
