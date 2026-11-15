"""Các solver của Phần B. `SOLVERS[name](evaluator, k=..., budget=..., seed=..., time_limit=...)`."""
from app.scheduling.solvers import bnb, cpsat, ga, nsga2, nsga2_legacy, sa

SOLVERS = {
    bnb.NAME: bnb.solve,
    cpsat.NAME: cpsat.solve,
    sa.NAME: sa.solve,
    ga.NAME: ga.solve,
    nsga2_legacy.NAME: nsga2_legacy.solve,
    nsga2.NAME: nsga2.solve,
}
EXACT = (bnb.NAME, cpsat.NAME)
METAHEURISTICS = (sa.NAME, ga.NAME, nsga2_legacy.NAME, nsga2.NAME)
