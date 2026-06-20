import type { LearningMaterial } from "@/lib/types";

const COURSE_CODE_RE = /\b[A-Z]{2,6}\s*\d{3,4}\b/gi;
const NOISE_TOKENS_RE =
  /\b(file|moodle|resource|activity|pluginfile|mod|folder|page|url|html)\b/gi;
const COPY_SUFFIX_RE = /\s*\(\d+\)\s*$/;
const PAREN_NUM_RE = /\s*\(\d+\)/g;
const COPY_WORD_RE = /\b-?\s*copy\b/gi;

/** Sort: lectures → revision → labs */
const KIND_SORT: Record<string, number> = {
  lecture: 0,
  lecture_link: 0,
  revision: 1,
  notes: 9,
  other_educational: 9,
  lab: 2,
  lab_link: 2,
};

const MIN_READY_CHARS = 301;
const MIN_LIMITED_CHARS = 100;
const MIN_STANDALONE_NOTE_CHARS = 1000;

const STANDALONE_EXERCISE_RE = /^(?:meal\s+)?exercise\s*#?\s*\d+\s*$/i;
const EXERCISE_PHRASE_RE =
  /(?:smart\s+home|triple-island|meal)\s+exercise/i;
const EXERCISE_PREFIX_RE = /^exercise\s*#?\s*\d+/i;

const LAB_TOPIC_HINTS: Array<{ re: RegExp; label: string }> = [
  { re: /adaboost/i, label: "AdaBoost" },
  { re: /naive\s*bayes/i, label: "Naive Bayes" },
  { re: /sqflit/i, label: "SQFLite" },
  { re: /layout\s*widgets/i, label: "Layout Widgets" },
  { re: /svm/i, label: "SVM" },
  { re: /knn/i, label: "KNN" },
  { re: /decision\s*tree/i, label: "Decision Tree" },
];

export function isDemoHiddenTitle(m: LearningMaterial): boolean {
  const title = stripNoise(m.title).trim();
  const fn = m.originalFilename ? stripNoise(m.originalFilename).trim() : "";
  const combined = `${title} ${fn}`;
  if (/^test\s+notes/i.test(title) || /^test\s+notes/i.test(fn)) return true;
  if (/^summary$/i.test(title) || /^summary$/i.test(fn)) return true;
  if (
    (/^summary\b/i.test(title) || /^summary\b/i.test(fn)) &&
    !/revision/i.test(combined)
  ) {
    return true;
  }
  if (/algorithm\s+steps/i.test(combined)) return true;
  if (/^multi\s+class\s+classification/i.test(combined)) return true;
  return false;
}

export function isStandaloneExercise(m: LearningMaterial): boolean {
  const title = stripNoise(m.title).trim();
  const fn = m.originalFilename ? stripNoise(m.originalFilename).trim() : "";
  const combined = `${title} ${fn}`;
  if (STANDALONE_EXERCISE_RE.test(title) || STANDALONE_EXERCISE_RE.test(fn)) {
    return true;
  }
  if (EXERCISE_PHRASE_RE.test(combined)) return true;
  if (
    EXERCISE_PREFIX_RE.test(title) &&
    !/\blab\s*-?\s*\d/i.test(combined)
  ) {
    return true;
  }
  return false;
}

export function isCoreDemoKind(m: LearningMaterial): boolean {
  if (isStandaloneExercise(m) || isDemoHiddenTitle(m)) return false;
  const kind = (m.materialKind || "").toLowerCase();
  const title = stripNoise(m.title);
  if (kind.includes("lecture") || kind.includes("lab") || kind === "revision") {
    return true;
  }
  if (/final\s+revision/i.test(title)) return true;
  if (
    /\b(?:lecture|lec)\s*-?\s*\d/i.test(title) ||
    /\blab\s*-?\s*\d/i.test(title) ||
    /_LAB\d/i.test(title)
  ) {
    return true;
  }
  if (/^revision/i.test(title)) return true;
  return false;
}

export function isEducationalKind(m: LearningMaterial): boolean {
  if (isStandaloneExercise(m) || isDemoHiddenTitle(m)) return false;
  if (m.isNonQuizMaterial || m.quizStatus === "not_quiz_material") return false;
  if (m.isEducational === false) return false;
  if (isCoreDemoKind(m)) return true;
  const kind = (m.materialKind || "").toLowerCase();
  if (kind === "notes" || kind === "other_educational") return true;
  if (m.isEducational === true) return true;
  return !m.isNonQuizMaterial;
}

export function isReadyMaterial(m: LearningMaterial): boolean {
  const normalized = normalizeMaterialForDisplay(m);
  return (
    normalized.quizStatus === "ready" ||
    normalized.quizStatus === "limited_ready" ||
    (normalized.quizGenerationEligible === true &&
      (normalized.readyForQuiz === true || normalized.quizStatus === "limited_ready"))
  );
}

export function isSkippedEducational(m: LearningMaterial): boolean {
  if (!isEducationalKind(m)) return false;
  if (isMainListLearningMaterial(m)) return false;
  return true;
}

function stripNoise(raw: string): string {
  let s = (raw || "").trim();
  s = s.replace(/\.(pdf|pptx?|ppsx|docx?|txt|html?|zip)$/i, "");
  s = s.replace(COURSE_CODE_RE, " ");
  s = s.replace(NOISE_TOKENS_RE, " ");
  s = s.replace(PAREN_NUM_RE, " ");
  s = s.replace(COPY_SUFFIX_RE, "");
  s = s.replace(COPY_WORD_RE, " ");
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

function inferLabTopic(raw: string): string | null {
  for (const hint of LAB_TOPIC_HINTS) {
    if (hint.re.test(raw)) return hint.label;
  }
  return null;
}

function extractLabNumberFromText(text: string): string | null {
  const m =
    text.match(/\blab\s*-?\s*(\d+)/i) || text.match(/_LAB(\d+)/i);
  return m ? m[1] : null;
}

export function cleanMaterialTitle(raw: string): string {
  const s = stripNoise(raw);
  if (!s) return "Learning material";

  if (/final\s+revision/i.test(s)) return "Final Revision";

  const prefixedLecture = s.match(
    /^\d+\s+(?:lecture|lec)\s*#?\s*(\d+)\s*(?:[-–—:]\s*)?(.*)$/i,
  );
  if (prefixedLecture) {
    const rest = normalizeTopicLabel(prefixedLecture[2] || "");
    return rest
      ? `Lecture ${prefixedLecture[1]} — ${rest}`
      : `Lecture ${prefixedLecture[1]}`;
  }

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

  const labNum = extractLabNumberFromText(s);
  if (labNum) {
    const topic = inferLabTopic(s);
    if (topic) return `Lab ${labNum} — ${topic}`;
    const restMatch = s.match(
      new RegExp(`lab\\s*-?\\s*${labNum}\\s*(?:[-–—:]\\s*)?(.*)$`, "i"),
    );
    const rest = normalizeTopicLabel((restMatch?.[1] || "").trim());
    if (rest && !/^lab$/i.test(rest)) return `Lab ${labNum} — ${rest}`;
    return `Lab ${labNum}`;
  }

  if (/^lab\s*-?\s*(\d+)\s*$/i.test(s)) {
    const n = s.match(/^lab\s*-?\s*(\d+)/i)?.[1];
    return n ? `Lab ${n}` : s;
  }

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
    const prefixed = cleaned.match(/^\d+\s+(?:lecture|lec)\s*-?\s*(\d+)/i);
    if (prefixed) return parseInt(prefixed[1], 10);
    if (kind.includes("lecture") || /\blecture|\blec\b/i.test(cleaned)) {
      const match = cleaned.match(/\b(?:lecture|lec)\s*-?\s*#?\s*(\d+)/i);
      if (match) return parseInt(match[1], 10);
    }
    if (kind.includes("lab") || /\blab\b/i.test(cleaned)) {
      const match =
        cleaned.match(/\blab\s*-?\s*(\d+)/i) ||
        cleaned.match(/_LAB(\d+)/i);
      if (match) return parseInt(match[1], 10);
    }
    if (kind === "revision" || /revision/i.test(cleaned)) {
      const match = cleaned.match(/\brevision\s*#?\s*(\d+)/i);
      if (match) return parseInt(match[1], 10);
    }
    const labAny =
      cleaned.match(/\blab\s*-?\s*(\d+)/i) || cleaned.match(/_LAB(\d+)/i);
    if (labAny) return parseInt(labAny[1], 10);
    const lecAny = cleaned.match(/\b(?:lecture|lec)\s*-?\s*(\d+)/i);
    if (lecAny) return parseInt(lecAny[1], 10);
  }
  return 9999;
}

export function normalizeMaterialForDisplay(m: LearningMaterial): LearningMaterial {
  const len = m.contentTextLength ?? 0;
  const imported =
    m.importedContent === true ||
    m.contentSource === "course_material_import";
  const core = isCoreDemoKind(m);

  let quizStatus = m.quizStatus;
  let quizGenerationEligible = m.quizGenerationEligible;
  let readyForQuiz = m.readyForQuiz;

  if (len > 0 && (imported || core)) {
    if (len >= MIN_READY_CHARS) {
      quizStatus = "ready";
      readyForQuiz = true;
      quizGenerationEligible = true;
    } else if (len >= MIN_LIMITED_CHARS) {
      quizStatus = "limited_ready";
      readyForQuiz = false;
      quizGenerationEligible = true;
    }
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

export function isMainListLearningMaterial(m: LearningMaterial): boolean {
  if (!isCoreDemoKind(m)) return false;
  const n = normalizeMaterialForDisplay(m);
  if (!isReadyMaterial(n)) return false;

  const len = n.contentTextLength ?? 0;
  if (len < MIN_LIMITED_CHARS) return false;

  if (n.visibleInMainList === false) return false;
  return true;
}

function dedupeKey(m: LearningMaterial): string {
  const n = normalizeMaterialForDisplay(m);
  const kind = (n.materialKind || "").toLowerCase();
  const num = extractMaterialNumber(n);
  const title = cleanMaterialTitle(m.title).toLowerCase();

  if (/final revision/.test(title)) return "revision:final";
  if (kind.includes("lecture") && num < 9999) return `lecture:${num}`;
  if (kind.includes("lab") && num < 9999) return `lab:${num}`;
  if (kind === "revision") {
    return title.includes("final") ? "revision:final" : `revision:${num}`;
  }
  if (num < 9999) {
    if (/\blecture|\blec\b/i.test(title)) return `lecture:${num}`;
    if (/\blab\b/i.test(title)) return `lab:${num}`;
  }
  return `${kind}:${title}`;
}

function dedupeScore(m: LearningMaterial): number {
  const n = normalizeMaterialForDisplay(m);
  let score = n.contentTextLength ?? 0;
  if (n.importedContent || n.contentSource === "course_material_import") {
    score += 100000;
  }
  if (n.quizStatus === "ready") score += 5000;
  else if (n.quizStatus === "limited_ready") score += 2000;
  if (n.readyForQuiz) score += 500;
  if (!n.isLinkWrapper) score += 100;
  return score;
}

export function deduplicateMaterials(
  materials: LearningMaterial[],
): LearningMaterial[] {
  const best: Record<string, { score: number; id: string }> = {};
  const hiddenIds = new Set<string>();

  for (const m of materials) {
    const key = dedupeKey(m);
    const score = dedupeScore(m);
    const prev = best[key];
    if (!prev || score > prev.score) {
      if (prev) hiddenIds.add(prev.id);
      best[key] = { score, id: m.id };
    } else {
      hiddenIds.add(m.id);
    }
  }

  return materials.map((m) => {
    if (!hiddenIds.has(m.id)) return m;
    return {
      ...m,
      visibleInMainList: false,
      visibleInOtherItems: true,
      quizGenerationEligible: false,
    };
  });
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
