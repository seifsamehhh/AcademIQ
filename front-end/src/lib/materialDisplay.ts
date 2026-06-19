import type { LearningMaterial } from "@/lib/types";

const COURSE_CODE_RE = /\b[A-Z]{2,6}\s*\d{3,4}\b/gi;
const NOISE_TOKENS_RE =
  /\b(file|moodle|resource|activity|pluginfile|mod|folder|page|url|html|pdf|pptx|docx)\b/gi;

/** Sort group: lectures → revision → labs */
const KIND_SORT: Record<string, number> = {
  lecture: 0,
  lecture_link: 0,
  revision: 1,
  notes: 2,
  lab: 3,
  lab_link: 3,
  other_educational: 4,
};

const EDUCATIONAL_KINDS = new Set([
  "lecture",
  "lecture_link",
  "lab",
  "lab_link",
  "revision",
  "notes",
]);

export function isEducationalKind(m: LearningMaterial): boolean {
  if (m.isNonQuizMaterial || m.quizStatus === "not_quiz_material") return false;
  if (m.isEducational === false) return false;
  const kind = (m.materialKind || "").toLowerCase();
  if (kind && EDUCATIONAL_KINDS.has(kind)) return true;
  if (m.isEducational === true) return true;
  return !m.isNonQuizMaterial;
}

export function isReadyMaterial(m: LearningMaterial): boolean {
  return (
    m.quizStatus === "ready" ||
    m.quizStatus === "limited_ready" ||
    (m.quizGenerationEligible === true && m.readyForQuiz === true)
  );
}

export function isSkippedEducational(m: LearningMaterial): boolean {
  if (!isEducationalKind(m)) return false;
  if (isReadyMaterial(m)) return false;
  return true;
}

export function cleanMaterialTitle(raw: string): string {
  let s = (raw || "").trim();
  if (!s) return "Learning material";

  s = s.replace(/\.(pdf|pptx?|ppsx|docx?|txt|html?)$/i, "");
  s = s.replace(COURSE_CODE_RE, " ");
  s = s.replace(NOISE_TOKENS_RE, " ");
  s = s.replace(/[_|]+/g, " ");
  s = s.replace(/\s+/g, " ").trim();

  const lecture = s.match(
    /\b(?:lecture|lec)\s*#?\s*(\d+)\s*(?:[-–—:]\s*)?(.*)$/i,
  );
  if (lecture) {
    const num = lecture[1];
    const rest = (lecture[2] || "").trim();
    return rest
      ? `Lecture ${num} — ${capitalizeTopic(rest)}`
      : `Lecture ${num}`;
  }

  const lab = s.match(/\blab\s*#?\s*(\d+)\s*(?:[-–—:]\s*)?(.*)$/i);
  if (lab) {
    const num = lab[1];
    const rest = (lab[2] || "").trim();
    return rest ? `Lab ${num} — ${capitalizeTopic(rest)}` : `Lab ${num}`;
  }

  if (/final\s+revision/i.test(s)) return "Final Revision";
  if (/revision|review/i.test(s)) {
    const rev = s.match(/revision\s*#?\s*(\d+)?/i);
    if (rev?.[1]) return `Revision ${rev[1]}`;
    return capitalizeTopic(s);
  }

  return capitalizeTopic(s);
}

function capitalizeTopic(text: string): string {
  const t = text.trim();
  if (!t) return "Learning material";
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function materialSubtitle(m: LearningMaterial): string {
  const parts: string[] = [];
  const kind = (m.materialKind || "").toLowerCase();
  if (kind && m.materialNumber != null && m.materialNumber < 9999) {
    parts.push(`${kind} ${m.materialNumber}`);
  } else if (kind === "revision") {
    parts.push("revision");
  }
  if (typeof m.contentTextLength === "number" && m.contentTextLength > 0) {
    parts.push(`${m.contentTextLength.toLocaleString()} chars`);
  } else if (isReadyMaterial(m)) {
    parts.push("ready");
  }
  return parts.join(" · ");
}

export function sortMaterialsForDisplay(materials: LearningMaterial[]): LearningMaterial[] {
  return [...materials].sort((a, b) => {
    const ka = KIND_SORT[(a.materialKind || "").toLowerCase()] ?? 9;
    const kb = KIND_SORT[(b.materialKind || "").toLowerCase()] ?? 9;
    if (ka !== kb) return ka - kb;
    const na = a.materialNumber ?? a.sortNumber ?? 9999;
    const nb = b.materialNumber ?? b.sortNumber ?? 9999;
    if (na !== nb) return na - nb;
    return cleanMaterialTitle(a.title).localeCompare(cleanMaterialTitle(b.title));
  });
}

export function displayMaterial(m: LearningMaterial): LearningMaterial {
  return { ...m, title: cleanMaterialTitle(m.title) };
}
