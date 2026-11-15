"""Export lớp học thật từ MongoDB (chỉ đọc) ra data/classes.json để benchmark tái lập được.

Chạy từ gốc repo: python -m research.benchmark.export_classes
Cần MONGO_URI trong .env. DB `university_db`, collection `ly_courses`.
"""
import json
import math
from pathlib import Path

from app.config.database_configuration import get_database

OUT = Path(__file__).with_name("data") / "classes.json"
FIELDS = ("course_name", "sub_topic", "class_index", "language", "field", "teacher", "day", "periods",
          "area", "room", "class_size")


def clean(value):
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def main():
    collection = get_database()["ly_courses"]
    docs = collection.find({}, {"_id": 0, "embedding": 0})
    rows = [{name: clean(doc.get(name)) for name in FIELDS} for doc in docs]
    for row in rows:
        row["periods"] = [int(p) for p in (row["periods"] or [])]
        row["class_index"] = "" if row["class_index"] is None else str(row["class_index"])
    rows.sort(key=lambda r: (r["course_name"] or "", r["sub_topic"] or "", r["class_index"], r["day"] or "",
                             r["periods"], r["teacher"] or ""))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(rows)} lớp -> {OUT}")


if __name__ == "__main__":
    main()
