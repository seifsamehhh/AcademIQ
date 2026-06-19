import type { LearningMaterial } from "@/lib/types";

const COURSE_CODE_RE = /\b[A-Z]{2,6}\s*\d{3,4}\b/gi;
const NOISE_TOKENS_RE =
  /\b(file|moodle|resource|activity|pluginfile|mod|folder|page|url|html|pdf|pptx|docx|ppsx)\b/gi;
const COPY_SUFFIX_RE = /\s*\(\d+\)\s*$/;
const PAREN_NUM_RE = /\s*\(\d+\)/g;

/** Sort: lectures → revision → notes → labs */
const KIND_SORT: Record<string, number> = {
  lecture: 0,
  lecture_link: 0,
  revision: 1,
  notes: 2,
  other_educational: 3,
  lab: 4,
  lab_link: 4,
};

const EDUCATIONAL_KINDS = new Set([
  "lecture",
  "lecture_link",
  "lab",
  "lab_link",
  "revision",
  "notes",
  "other_educational",
]);

const MIN_READY_CHARS = 600;
const MIN_LIMITED_CHARS = 200;

export function isEducationalKind(m: LearningMaterial): boolean {
  if (m.isNonQuizMaterial || m.quizStatus === "not_quiz_material") return false;
  if (m.isEducational === false) return false;
  const kind = (m.materialKind || "").toLowerCase();
  if (kind && EDUCATIONAL_KINDS.has(kind)) return true;
  if (m.isEducational === true) return true;
  return !m.isNonQuizMaterial;
}

export function isReadyMaterial(m: LearningMaterial): boolean {
  const normalized = normalizeMaterialForDisplay(m);
  return (
    normalized.quizStatus === "ready" ||
    normalized.quizStatus === "limited_ready" ||
    (normalized.quizGenerationEligible === true && normalized.readyForQuiz === true)
  );
}

export function isSkippedEducational(m: LearningMaterial): boolean {
  if (!isEducationalKind(m)) return false;
  if (isReadyMaterial(m)) return false;
  return true;
}

function stripNoise(raw: string): string {
  let s = (raw || "").trim();
  s = s.replace(/\.(pdf|pptx?|ppsx|docx?|txt|html?|zip)$/i, "");
  s = s.replace(COURSE_CODE_RE, " ");
  s = s.replace(NOISE_TOKENS_RE, " ");
  s = s.replace(PAREN_NUM_RE, " ");
  s = s.replace(COPY_SUFFIX_RE, "");
  s = s.replace(/[_|]+/g, " ");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

function normalizeTopicLabel(text: string): string {
  let t = text.trim();
  t = t.replace(/\bsqflit\b/gi, "SQFLite");
  t = t.replace(/\bsqflite\b/gi, "SQFLite");
  if (!t) return "";
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function cleanMaterialTitle(raw: string): string {
  const s = stripNoise(raw);
  if (!s) return "Learning material";

  const lecturePart = s.match(
    /\b(?:lecture|lec)\s*#?\s*(\d+)\s+part\s*(\d+)\s*(?:[-–—:]\s*)?(.*)$/i,
  );
  if (lecturePart) {
    const rest = normalizeTopicLabel(lecturePart[3] || "");
    return rest
      ? `Lecture ${lecturePart[1]} Part ${lecturePart[2]} — ${rest}`
      : `Lecture ${lecturePart[1]} Part ${lecturePart[2]}`;
  }

  const lecture = s.match(
    /\b(?:lecture|lec)\s*#?\s*(\d+)\s*(?:[-–—:]\s*)?(.*)$/i,
  );
  if (lecture) {
    const rest = normalizeTopicLabel(lecture[2] || "");
    return rest ? `Lecture ${lecture[1]} — ${rest}` : `Lecture ${lecture[1]}`;
  }

  const lab = s.match(/\blab\s*#?\s*(\d+)\s*(?:[-–—:]\s*)?(.*)$/i);
  if (lab) {
    const rest = normalizeTopicLabel(lab[2] || "");
    return rest ? `Lab ${lab[1]} — ${rest}` : `Lab ${lab[1]}`;
  }

  if (/final\s+revision/i.test(s)) return "Final Revision";
  if (/revision|review/i.test(s)) {
    const rev = s.match(/revision\s*#?\s*(\d+)?/i);
    if (rev?.[1]) return `Revision ${rev[1]}`;
    return normalizeTopicLabel(s);
  }

  return normalizeTopicLabel(s);
}

export function extractMaterialNumber(m: LearningMaterial): number {
  const kind = (m.materialKind || "").toLowerCase();
  const stored = m.materialNumber ?? m.sortNumber;
  if (typeof stored === "number" && stored < 9999) return stored;

  const sources = [m.title, m.originalFilename || ""];
  for (const src of sources) {
    if (!src) continue;
    const cleaned = stripNoise(src);
    if (kind.includes("lecture") || /\blecture|\blec\b/i.test(cleaned)) {
      const match = cleaned.match(/\b(?:lecture|lec)\s*#?\s*(\d+)/i);
      if (match) return parseInt(match[1], 10);
    }
    if (kind.includes("lab") || /\blab\b/i.test(cleaned)) {
      const match = cleaned.match(/\blab\s*#?\s*(\d+)/i);
      if (match) return parseInt(match[1], 10);
    }
    if (kind === "revision" || /revision/i.test(cleaned)) {
      const match = cleaned.match(/\brevision\s*#?\s*(\d+)/i);
      if (match) return parseInt(match[1], 10);
    }
  }
  return 9999;
}

export function normalizeMaterialForDisplay(m: LearningMaterial): LearningMaterial {
  const len = m.contentTextLength ?? 0;
  const imported =
    m.importedContent === true ||
    m.contentSource === "course_material_import";

  let quizStatus = m.quizStatus;
  let quizGenerationEligible = m.quizGenerationEligible;
  let readyForQuiz = m.readyForQuiz;

  if (imported && len > 0) {
    if (len >= MIN_READY_CHARS || m.quizStatus === "ready") {
      quizStatus = "ready";
      readyForQuiz = true;
    } else if (len >= MIN_LIMITED_CHARS) {
      quizStatus = "limited_ready";
      readyForQuiz = false;
    } else {
      quizStatus = "limited_ready";
      readyForQuiz = false;
    }
    quizGenerationEligible = true;
  } else if (len > 0 && quizStatus === "not_uploaded") {
    if (len >= MIN_READY_CHARS) {
      quizStatus = "ready";
      readyForQuiz = true;
      quizGenerationEligible = true;
    } else if (len >= MIN_LIMITED_CHARS) {
      quizStatus = "limited_ready";
      quizGenerationEligible = true;
    }
  }

  return {
    ...m,
    quizStatus,
    quizGenerationEligible,
    readyForQuiz,
  };
}

export function materialSubtitle(m: LearningMaterial): string | null {
  const n = normalizeMaterialForDisplay(m);
  const parts: string[] = [];
  const kind = (n.materialKind || "").toLowerCase();
  const num = extractMaterialNumber(n);
  if (kind && num < 9999) {
    parts.push(`${kind} ${num}`);
  } else if (kind === "revision") {
    parts.push("revision");
  }
  if (typeof n.contentTextLength === "number" && n.contentTextLength > 0) {
    parts.push(`${n.contentTextLength.toLocaleString()} chars`);
  } else if (isReadyMaterial(n)) {
    parts.push("ready");
  }
  return parts.length ? parts.join(" · ") : null;
}

export function sortMaterialsForDisplay(materials: LearningMaterial[]): LearningMaterial[] {
  return [...materials].sort((a, b) => {
    const na = normalizeMaterialForDisplay(a);
    const nb = normalizeMaterialForDisplay(b);
    const ka = KIND_SORT[(na.materialKind || "").toLowerCase()] ?? 9;
    const kb = KIND_SORT[(nb.materialKind || "").toLowerCase()] ?? 9;
    if (ka !== kb) return ka - kb;
    const numA = extractMaterialNumber(na);
    const numB = extractMaterialNumber(nb);
    if (numA !== numB) return numA - numB;
    return cleanMaterialTitle(na.title).localeCompare(cleanMaterialTitle(nb.title));
  });
}

export function displayMaterial(m: LearningMaterial): LearningMaterial {
  return {
    ...normalizeMaterialForDisplay(m),
    title: cleanMaterialTitle(m.title),
  };
}
