"""Interface chung của các solver (docs/specs/algorithms/design.md mục 3)."""
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.scheduling.constraints import Evaluator, Score

DEFAULT_BUDGET = 5000          # số lần đánh giá cho metaheuristic
DEFAULT_TIME_LIMIT = 60.0      # giây, cho solver chính xác


@dataclass
class Schedule:
    x: Tuple[int, ...]
    score: Score


@dataclass
class SolveResult:
    algorithm: str
    schedules: List[Schedule]
    evaluations: int
    elapsed_ms: float
    optimal: Optional[bool] = None       # solver chính xác: đã chứng minh tối ưu chưa
    meta: Dict[str, Any] = field(default_factory=dict)


class Timer:
    def __init__(self):
        self.start = time.perf_counter()

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.start

    @property
    def ms(self) -> float:
        return self.elapsed * 1000


def result_from(algorithm: str, candidates: Sequence[Tuple[Sequence[int], Score]], evaluator: Evaluator,
                timer: Timer, **kwargs) -> SolveResult:
    return SolveResult(
        algorithm=algorithm,
        schedules=[Schedule(tuple(x), score) for x, score in candidates],
        evaluations=evaluator.evaluations,
        elapsed_ms=timer.ms,
        **kwargs,
    )


def random_solution(rng: random.Random, sizes: Sequence[int]) -> List[int]:
    return [rng.randrange(size) for size in sizes]


def repair(evaluator: Evaluator, x: List[int], rng: random.Random) -> List[int]:
    """Gán lại lớp không trùng lịch cho các môn đang trùng (thứ tự môn ngẫu nhiên).

    Chỉ dùng bitmask (thứ, tiết), không gọi hàm chấm nên không tính vào số lần đánh giá.
    """
    slots = evaluator.slots
    n = len(x)
    order = list(range(n))
    rng.shuffle(order)
    occupied = 0
    clash = []
    for i in order:
        mask = slots[i][x[i]]
        if mask & occupied:
            clash.append(i)
        else:
            occupied |= mask
    for i in clash:
        choices = [l for l in range(len(slots[i])) if not slots[i][l] & occupied]
        if choices:
            # ưu tiên lớp có phạt unary nhỏ, giữ chút ngẫu nhiên
            choices.sort(key=lambda l: (evaluator.unary_scalar[i][l], rng.random()))
            x[i] = choices[0] if rng.random() < 0.7 else rng.choice(choices)
        occupied |= slots[i][x[i]]
    return x
