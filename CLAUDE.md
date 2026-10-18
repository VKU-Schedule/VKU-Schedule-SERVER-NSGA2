# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Flask backend for the VKU timetable optimizer. A student picks courses and gives preferences; this service fetches every class of those courses from MongoDB and runs a DEAP-based NSGA-II search to return the top 5 class combinations. The LLM (VIT5) that turns the student's natural-language prompt into structured JSON is **not** in this repo. `/api/schedule` and `/api/reschedule` receive that already-parsed preference JSON as `prompt` / `parsed_prompt`.

Code comments, docstrings, log output and data (course names, days like "Thứ Sáu") are in Vietnamese.

## Research roadmap (read first)

This repo is being redesigned for a graduation thesis. **Read `docs/specs/README.md` before starting any work.** It holds the decisions already made, the status of each part, and the full plan:
- **Part A:** JSON Structure v2 for constraints. Spec in `docs/specs/json_v2/`; branch `feature/new_json_structure`.
- **Part B:** algorithm comparison. Planned in README section 7; gets its own branch after Part A is approved.

The rules:
- Each part follows `requirements.md` → `design.md` → `tasks.md`. Don't write code for a part until its spec is approved.
- Commit each finished piece with Conventional Commits, e.g. `docs(specs): …`, `feat(scheduling): …`.
- Everything described below documents the old (v1) preference JSON and will be replaced.

## Commands

Run everything from the repo root. Imports are absolute (`from app...`), so the root must be on `PYTHONPATH`.

```bash
pip install -r app/requirements.txt     # runtime deps used by the app and Docker
python -m app.main                      # dev server, Flask debug mode, port 5001
# Swagger UI: http://localhost:5001/api-docs
python test_db_connection.py            # check the Mongo connection and the ly_courses contents
python -m app.demo                      # standalone NSGA-II run on the hard-coded fixtures in app/constant/constant_input_test.py
docker compose up --build               # uses .env, maps 8001:8001
```

- The root `requirements.txt` is an older pip freeze (torch/CUDA). Use `app/requirements.txt`.
- Port mismatch: `app/main.py` binds 5001, but the Dockerfile and compose file expose 8001. As written, the container won't answer on 8001 until the two agree.
- There is no test suite, linter or formatter configured.
- `database/embedding/embedding_data.py` re-imports `data/input/Final_Dataset.xlsx` into Mongo. It **wipes `ly_courses` first** (`delete_many({})`), uses a relative path to the xlsx (run it from `database/embedding/`), and needs the repo root on `PYTHONPATH`.

## Environment

`.env` (gitignored) must set `MONGO_URI`. The DB is `university_db` and the collection is `ly_courses`, both hard-coded in the API modules. When the app starts it connects to Mongo and loads the `all-MiniLM-L6-v2` SentenceTransformer onto `app.db` / `app.model`. Today the model is only used by the commented-out vector-search code in `schedule_api.py`.

## Architecture

- `app/main.py`: builds the Flask app, sets up Swagger (flasgger reads the YAML in each route's docstring, so keep those docstrings in sync when you change a request or response), and registers the blueprints under `/api`.
- `app/api/`
  - `search_api.py`: `POST /search-recommend` does a case-insensitive regex match on `course_name` / `sub_topic`.
  - `schedule_api.py`:
    - `POST /schedule`: each query is `"course_name @ sub_topic"`, and `@ sub_topic` is optional. Every query becomes an exact-match Mongo find, and the matching docs become `ClassInfo` objects grouped by course.
    - `POST /reschedule`: loads every class of `course_names`, then pins each non-failed course in `selected_classes` to its single chosen class, so NSGA-II only re-picks the failed courses.
  - `list_all_api.py`: debug dump of the whole collection.
- `app/model/Class_Info.py`: the `ClassInfo` dataclass. Mongo fields are English (`course_name`, `class_index`, `day`, `periods`, `area`, `room`, ...), mapped from the Vietnamese Excel columns in `embedding_data.py`.
- `app/service/constraints_service.py`: the optimizer.
  - **Encoding:** an individual is a list of ints, one gene per course. Each gene is the index of the chosen class in that course's list.
  - **Objective:** `evaluate` returns a single objective, `weights=(-1.0,)`, so lower is better. Even though it uses `selNSGA2` / `sortNondominated`, it is effectively single-objective.
  - **Hard constraint:** any `(day, period)` overlap returns `inf`.
  - **Soft constraints:** each preference key maps to a scorer in `CONSTRAINT_FUNCTIONS`. Scorers return negative values for liked matches (`like: true`) and positive values for disliked ones. The magnitude is scaled by `PRIORITY_WEIGHTS` in `app/constant/constant_of_schedule.py`.
  - **Preference JSON shape:** `{"defaults": {...}, "periods": [{"day": {"value": "Thứ Sáu", ...}, <constraint keys>...}]}`.
    - Each `periods` entry applies only to classes on its day ("Cả tuần" or no day means all days), and its score is multiplied by 2.
    - `defaults` apply only to (course, day) pairs that no period entry has already handled for the same key.
    - See `app/constant/constant_input_test.py` for a full example.
  - **Keys:** some differ from their function names. `"period"` maps to `periods()` and `"class"` maps to `class_name()`. `class_name` handles teacher (via `fuzzy_name_match`) and class-group preferences, optionally scoped to one course by `name`.
  - **Missing scorer:** `subject_count` has a scorer and a weight but no entry in `CONSTRAINT_FUNCTIONS`, so the key is currently ignored.
  - **GA settings:** fixed seed (`random.seed(42)`), population 30, 50 generations, `eaMuPlusLambda`. A single-course request skips the GA and scores every class directly.
  - **Module-level DEAP state:** `creator.create(...)` and the shared `toolbox` live at module scope. `run_nsga_ii` re-registers the toolbox on every request. That is not safe under concurrent requests.
- `app/demo.py`: an older standalone copy of the constraint logic, run against the fixtures. It is not used by the API, so edits to `constraints_service.py` don't carry over to it.
- `validation/` and `data/`: offline scripts and datasets (Excel cleaning, VIT5 training-data generation, a Gemini translation script). They are not part of the server or the Docker image.
- `app/mock/docs/`: API and UI/UX notes for the frontend. `app/mock/mock_*` hold sample responses.
