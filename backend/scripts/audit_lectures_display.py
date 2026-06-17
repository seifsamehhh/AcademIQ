"""One-off audit: lecture display status for a course."""
import re
import sys

from app.repositories import material_repository
from app.services.material_quiz_display import _resolve_one_material


def main(course_id: str = "666") -> None:
    lecture_re = re.compile(r"lecture\s*\d|lecture\d", re.I)
    docs = material_repository.list_by_course(course_id)
    rows = []
    for d in docs:
        t = d.get("title") or ""
        if not lecture_re.search(t) and "Lecture" not in t:
            continue
        disp = _resolve_one_material(d)
        rows.append(
            {
                "id": d.get("material_id"),
                "title": t[:55],
                "chars": len((d.get("content_text") or "").strip()),
                "stored": d.get("extraction_status"),
                "quiz_status": disp.get("quiz_status"),
                "probe": disp.get("probe_question_count"),
                "reason": (disp.get("content_note") or disp.get("quiz_reason") or "")[:80],
            }
        )
    rows.sort(key=lambda x: x["title"])
    for r in rows:
        print(
            f"{r['quiz_status']:20} probe={r['probe']} chars={r['chars']:5} | {r['title']}"
        )
        if r["reason"]:
            print(f"  -> {r['reason']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "666")
