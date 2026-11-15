"""Chọn k lịch đa dạng (docs/specs/algorithms/design.md mục 4)."""
from typing import Dict, Iterable, List, Sequence, Tuple

from app.scheduling.constraints import Score
from app.scheduling.model import Problem

DEFAULT_K = 5

Candidate = Tuple[Tuple[int, ...], Score]


def min_distance(problem: Problem) -> int:
    """d = 2 nếu còn ít nhất 3 môn tự do, ngược lại 1."""
    return 2 if problem.free_courses >= 3 else 1


def hamming(a: Sequence[int], b: Sequence[int]) -> int:
    return sum(1 for u, v in zip(a, b) if u != v)


def select_diverse(candidates: Iterable[Candidate], k: int, d: int) -> List[Candidate]:
    """Tham lam theo (conflicts, H, P, x); bỏ lịch trùng lịch. Thiếu thì nới d về 1."""
    pool = sorted(
        {tuple(x): score for x, score in candidates if score.conflicts == 0}.items(),
        key=lambda item: (item[1].key, item[0]),
    )
    chosen: List[Candidate] = []
    for distance in range(d, 0, -1):
        for x, score in pool:
            if len(chosen) >= k:
                break
            if any(x == y for y, _ in chosen):
                continue
            if all(hamming(x, y) >= distance for y, _ in chosen):
                chosen.append((x, score))
        if len(chosen) >= k:
            break
    chosen.sort(key=lambda item: (item[1].key, item[0]))
    return chosen


class Archive:
    """Mọi lời giải đã chấm của một metaheuristic (x -> Score)."""

    def __init__(self):
        self.items: Dict[Tuple[int, ...], Score] = {}

    def add(self, x: Sequence[int], score: Score) -> None:
        self.items[tuple(x)] = score

    def select(self, k: int, d: int) -> List[Candidate]:
        return select_diverse(self.items.items(), k, d)
