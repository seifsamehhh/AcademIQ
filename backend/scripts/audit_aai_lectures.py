"""Audit AAI lectures - writes JSON."""
import json
import re
from app.repositories import material_repository
from app.services.material_quiz_display import resolve_quiz_material_display

docs = material_repository.list_by_course("666")
lectures = [
    d for d in docs
    if re.search(r"lecture|lec\s*\d", (d.get("title") or ""), re.I)
]
lectures.sort(key=lambda x: x.get("title", ""))

out = []
for d in lectures:
    title = d.get("title") or ""
    disp = resolve_quiz_material_display([d])[0][0]
    out.append({
        "title": title,
        "material_id": d.get("material_id"),
        "file_type": d.get("file_type"),
        "url": (d.get("url") or "")[:120],
        "resolved_url": (d.get("resolved_url") or "")[:120],
        "chars": len(d.get("content_text") or ""),
        "stored_status": d.get("extraction_status"),
        "quiz_status": disp.get("quiz_status"),
        "probe": disp.get("probe_question_count"),
        "main": disp.get("visible_in_main_list"),
        "non_quiz": disp.get("is_non_quiz_material"),
        "reason": disp.get("why_not_ready") or disp.get("quiz_status_reason"),
    })

with open("scripts/audit_out.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(f"written {len(out)} rows")
