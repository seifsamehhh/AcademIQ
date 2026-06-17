"""Run material processing audit and print summary."""
import json
import sys

from app.config.database import users_collection
from app.services.material_processing_audit import debug_material_processing_audit

TARGET_COURSES = ("AAI", "DIA", "KRA", "ML", "MDP", "SPI")


def _find_material(courses, course_key, title_fragment):
    for c in courses:
        name = (c.get("course_name") or "").upper()
        if course_key not in name:
            continue
        for m in c.get("educational_materials") or []:
            t = (m.get("title") or "").lower()
            if title_fragment.lower() in t:
                return c["course_id"], m
    return None, None


def main():
    email = sys.argv[1] if len(sys.argv) > 1 else None
    if not email:
        users = list(users_collection.find({}, {"email": 1}).limit(20))
        emails = [u.get("email") for u in users if u.get("email")]
        email = emails[0] if emails else None
    if not email:
        print("No users found")
        return

    r = debug_material_processing_audit(email)
    out_path = "scripts/audit_processing_out.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2, default=str)

    print("email:", email)
    print("courses:", r.get("synced_courses_count"))
    print("global_status:", r.get("global_status_counts"))
    print("issue_counts:", r.get("problem_summary", {}).get("counts_by_issue_type"))
    print("written:", out_path)

    courses = r.get("courses") or []
    for label in TARGET_COURSES:
        c = next((x for x in courses if label in (x.get("course_name") or "").upper()), None)
        if not c:
            print(f"\n{label}: not in synced list")
            continue
        print(
            f"\n{label} ({c['course_id']}): educ={c['educational_count']} "
            f"ready={c['ready_count']} not_uploaded={c['not_uploaded_count']} "
            f"failed={c['extraction_failed_count']}"
        )

    for lecture in ["Lecture2", "Lecture3", "Lecture4", "Lecture 6", "Lecture 7", "Lecture 8"]:
        cid, m = _find_material(courses, "ADVANCED ARTIFICIAL", lecture)
        if not m:
            cid, m = _find_material(courses, "666", lecture)
        if m:
            print(
                f"AAI {lecture}: {m['quiz_status']} issue={m['issue_type']} "
                f"chars={m['content_text_length']} attempted={m.get('last_attempted_at')}"
            )
            flags = m.get("flags") or {}
            active_flags = [k for k, v in flags.items() if v]
            print("  flags:", ", ".join(active_flags))

    course_map = {
        "666": "AAI",
        "808": "DIA",
        "478": "KRA",
        "670": "ML",
        "462": "MDP",
        "669": "SPI",
    }
    for cid, label in course_map.items():
        c = next((x for x in courses if x["course_id"] == cid), None)
        if not c:
            continue
        print(f"\n--- {label} summary ---")
        for m in c.get("educational_materials") or []:
            t = (m.get("title") or "").lower()
            if not any(k in t for k in ("lecture", "lab", "revision", "review")):
                continue
            print(
                f"  {m['issue_type'][:20]:20} {m['quiz_status']:18} "
                f"chars={m['content_text_length']:5} {m['title'][:50]}"
            )


if __name__ == "__main__":
    main()
