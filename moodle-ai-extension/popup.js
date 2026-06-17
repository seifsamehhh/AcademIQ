const PRODUCTION_SIGNIN_URL = "https://academiq-frontend.vercel.app/signin";
const STORAGE_KEY = "moodleData";
const PRODUCTION_API_BASE = "https://academiq-backend.vercel.app";
const SYNC_PATH = "/raw-moodle-payloads";
const UPLOAD_QUIZ_PATH = "/materials/upload-for-quiz";
const CONTENT_PATH = "/materials/content";
const PREFLIGHT_PATH = "/materials/preflight";
const SAVE_DETECTED_PATH = "/materials/save-detected";

/** Strip any known API paths from the end so we always have a clean base URL. */
const normalizeApiBase = (url) => {
    const raw = (url || PRODUCTION_API_BASE).trim().replace(/\/$/, "");
    return raw
        .replace(/\/raw-moodle-payloads\/?$/, "")
        .replace(/\/materials\/upload-for-quiz\/?$/, "")
        .replace(/\/materials\/preflight\/?$/, "")
        .replace(/\/materials\/save-detected\/?$/, "")
        .replace(/\/materials\/content\/?$/, "");
};

const buildBackendUrls = (apiBase) => {
    const base = normalizeApiBase(apiBase);
    return {
        sync: `${base}${SYNC_PATH}`,
        uploadQuiz: `${base}${UPLOAD_QUIZ_PATH}`,
        preflight: `${base}${PREFLIGHT_PATH}`,
        saveDetected: `${base}${SAVE_DETECTED_PATH}`,
        content: `${base}${CONTENT_PATH}`,
        base,
    };
};

let BACKEND_URL = buildBackendUrls(PRODUCTION_API_BASE).sync;
let UPLOAD_QUIZ_URL = buildBackendUrls(PRODUCTION_API_BASE).uploadQuiz;
let PREFLIGHT_URL = buildBackendUrls(PRODUCTION_API_BASE).preflight;
let SAVE_DETECTED_URL = buildBackendUrls(PRODUCTION_API_BASE).saveDetected;
let CONTENT_URL = buildBackendUrls(PRODUCTION_API_BASE).content;

/** Load saved API base URL, update all globals, and fill the settings input. */
const loadBackendConfig = () =>
    new Promise((resolve) => {
        chrome.storage.local.get(["backendUrl"], (res) => {
            const base = res.backendUrl || PRODUCTION_API_BASE;
            const urls = buildBackendUrls(base);
            BACKEND_URL = urls.sync;
            UPLOAD_QUIZ_URL = urls.uploadQuiz;
            PREFLIGHT_URL = urls.preflight;
            SAVE_DETECTED_URL = urls.saveDetected;
            CONTENT_URL = urls.content;
            // Populate the settings input if it exists in the DOM
            const input = document.getElementById("backendUrlInput");
            if (input) input.value = urls.base;
            resolve();
        });
    });

/**
 * Normalize a scraped Moodle material for backend API payloads.
 */
const normalizeMaterialForApi = (m) => ({
    material_id: m.material_id || m.id,
    title: m.title || "Untitled",
    source_url: m.url || m.source_url || null,
    resolved_url: m.resolvedUrl || m.resolved_url || null,
    file_type: m.fileType || m.file_type || "unknown",
    material_type: m.type || m.material_type || null,
    db_id: m.db_id || m.dbId || m.matched_db_id || null,
    matched_material_id:
        m.matched_material_id || m.matchedMaterialId || m.matched_db_material_id || null,
    stable_material_key: m.stable_material_key || null,
});

const logSaveDetectedAudit = (saveData, courseId) => {
    const audit = saveData?.audit || [];
    const lectureAudit = saveData?.lecture_audit || audit.filter((row) =>
        /lecture/i.test(row?.title || "") || /lecture/i.test(row?.saved_title || "")
    );
    console.group(`[AcademIQ] Save-detected audit — course ${courseId}`);
    console.log(
        "detected:", saveData?.detected_total,
        "| upsert ops:", saveData?.metadata_saved_total,
        "| unique DB rows:", saveData?.db_materials_found_for_course
    );
    if (lectureAudit.length) {
        console.table(
            lectureAudit.map((row) => ({
                idx: row.detected_index,
                title: row.title,
                cmid: row.cmid,
                file_type: row.file_type,
                key: row.key_strategy,
                saved: row.was_saved_in_db,
                saved_id: row.saved_material_id,
                status: row.saved_status,
                reason: row.reason_if_not_saved,
            }))
        );
    } else {
        console.log("No lecture rows in audit payload.");
    }
    console.groupEnd();
};

/**
 * Call POST /materials/save-detected — metadata-only upsert for all detected items.
 */
const callSaveDetectedFromPopup = async (courseId, materials, identity, courseName) => {
    const saveUrl = SAVE_DETECTED_URL;
    const body = {
        course_id: String(courseId),
        course_name: courseName || null,
        user_email: identity?.email || null,
        materials: materials.map(normalizeMaterialForApi),
    };
    try {
        const res = await fetch(saveUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            let errText = "";
            try { errText = await res.text(); } catch (_) {}
            return {
                ok: false,
                httpStatus: res.status,
                error: `HTTP ${res.status}${errText ? `: ${errText.slice(0, 160)}` : ""}`,
                saveUrl,
            };
        }
        const data = await res.json();
        return { ok: true, data, saveUrl };
    } catch (err) {
        return {
            ok: false,
            httpStatus: 0,
            error: String(err.message || err),
            saveUrl,
        };
    }
};

/**
 * Call POST /materials/preflight from the POPUP context (chrome-extension:// origin).
 *
 * Running the fetch here rather than in content.js ensures the request carries
 * "Origin: chrome-extension://…" which is explicitly allowed by the backend CORS
 * middleware.  Content-script fetches carry the Moodle page's origin and may be
 * blocked by the CORS policy.
 *
 * Returns { ok: true, data, preflightUrl } or { ok: false, error, httpStatus, preflightUrl }.
 */
const callPreflightFromPopup = async (courseId, materials, identity) => {
    const preflightUrl = PREFLIGHT_URL;

    const body = {
        course_id: String(courseId),
        user_email: identity?.email || null,
        materials: materials.map(normalizeMaterialForApi),
    };

    try {
        const res = await fetch(preflightUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        if (!res.ok) {
            let errText = "";
            try { errText = await res.text(); } catch (_) {}
            return {
                ok: false,
                httpStatus: res.status,
                error: `HTTP ${res.status}${errText ? `: ${errText.slice(0, 160)}` : ""}`,
                preflightUrl
            };
        }
        const data = await res.json();
        return { ok: true, data, preflightUrl };
    } catch (err) {
        return {
            ok: false,
            httpStatus: 0,
            error: String(err.message || err),
            preflightUrl
        };
    }
};

const refs = {
    refreshBtn: document.getElementById("refreshBtn"),
    downloadJsonBtn: document.getElementById("downloadJsonBtn"),
    clearDataBtn: document.getElementById("clearDataBtn"),
    downloadAllPdfsBtn: document.getElementById("downloadAllPdfsBtn"),
    uploadQuizBtn: document.getElementById("uploadQuizBtn"),
    manualQuizFileInput: document.getElementById("manualQuizFileInput"),
    uploadMeta: document.getElementById("uploadMeta"),
    emptyState: document.getElementById("emptyState"),
    dashboard: document.getElementById("dashboard"),
    courseSelector: document.getElementById("courseSelector"),
    performanceStats: document.getElementById("performanceStats"),
    materialsList: document.getElementById("materialsList"),
    downloadMeta: document.getElementById("downloadMeta"),
    lastUpdated: document.getElementById("lastUpdated"),
    // Settings
    backendUrlInput: document.getElementById("backendUrlInput"),
    saveBackendUrlBtn: document.getElementById("saveBackendUrlBtn"),
    backendUrlStatus: document.getElementById("backendUrlStatus"),
};

let currentData = null;
let currentCourseId = null;

const sanitizePayload = (data) => {
    if (!data) return null;
    const { events, grades, materials, courses, behavior, student, metricsByCourse } = data;
    return {
        student,
        courses,
        behavior,
        metricsByCourse,
        events: (events || []).map(({ _id, ...event }) => event),
        grades: (grades || []).map(({ _key, ...grade }) => grade),
        // Single canonical materials array — no duplicated learning_materials /
        // materialsByCourse / knowledge_base structures are sent any more.
        materials: (materials || []).map(({ _key, ...material }) => material)
    };
};

const getStorageData = () =>
    new Promise((resolve) => {
        chrome.storage.local.get(STORAGE_KEY, (res) => {
            resolve(res[STORAGE_KEY] || null);
        });
    });

const syncToBackend = async (data) => {
    if (!data) {
        alert("No data to sync.");
        return null;
    }
    const payload = sanitizePayload(data);
    try {
        const response = await fetch(BACKEND_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        const result = await response.json();
        console.log("Sync successful:", result);
        return result;
    } catch (error) {
        console.error("Sync failed:", error);
        alert(`Sync failed: ${error.message}`);
        return null;
    }
};

const createStatCard = (label, value) => {
    const el = document.createElement("div");
    el.className = "stat";
    el.innerHTML = `<div class="label">${label}</div><div class="value">${value}</div>`;
    return el;
};

const normalizeMaterial = (material, courseId) => ({
    id: material.id || material.material_id,
    courseId: material.courseId || material.course_id || courseId,
    title: material.title || "Untitled Material",
    type: material.type || material.material_type || "unknown",
    url: material.url || "",
    fileType: material.fileType || material.file_type || "unknown",
    sourcePage: material.sourcePage || null,
    downloadable: Boolean(material.downloadable)
});

const getCourseMaterials = (data, courseId) => {
    // Read from the single canonical materials array, filtered by course.
    const all = Array.isArray(data?.materials) ? data.materials : [];
    return all
        .filter((item) => (item.courseId || item.course_id) === courseId)
        .map((m) => normalizeMaterial(m, courseId));
};

const getMaterialDownloadLabel = (material) => {
    if (material.downloadStatus === "No downloadable files") return "No downloadable files";
    if ((material.fileType || "").toLowerCase() === "folder" && !material.downloadable) return "No downloadable files";
    return null;
};

const isMaterialDownloadable = (material) => {
    const fileType = (material.fileType || "").toLowerCase();
    if (fileType === "folder") return false;
    if (fileType === "html") return false;
    if (material.downloadStatus === "No downloadable files") return false;
    const hasDirectExt = /\.(pdf|doc|docx|ppt|pptx|xls|xlsx|zip)(\?|$)/i.test(material.url || "");
    return /^https?:/i.test(material.url || "") && (material.downloadable || hasDirectExt || (fileType !== "link" && fileType !== "unknown"));
};

const startDownload = (material, index = 0) =>
    new Promise((resolve) => {
        const fallbackName = `${(material.title || `material_${index + 1}`).replace(/[\\/:*?"<>|]+/g, "_")}.${(material.fileType || "bin").replace(/[^a-z0-9]/gi, "") || "bin"}`;
        chrome.downloads.download(
            {
                url: material.url,
                filename: fallbackName,
                conflictAction: "uniquify",
                saveAs: false
            },
            (downloadId) => {
                if (downloadId) {
                    resolve({ ok: true, method: "download" });
                    return;
                }
                chrome.tabs.create({ url: material.url }, (tab) => {
                    resolve({ ok: Boolean(tab?.id), method: tab?.id ? "tab" : "failed" });
                });
            }
        );
    });

const fileTypeIcon = (fileType) => {
    const ft = (fileType || "").toLowerCase();
    if (ft === "pdf") return "📄";
    if (["doc", "docx", "ppt", "pptx", "xls", "xlsx"].includes(ft)) return "📝";
    if (ft === "link") return "🔗";
    return "📁";
};

const renderPerformance = (metrics = {}) => {
    refs.performanceStats.innerHTML = "";
    refs.performanceStats.appendChild(createStatCard("Total Visits", metrics.total_visits || 0));
    refs.performanceStats.appendChild(createStatCard("Time Spent (min)", Math.round((metrics.total_time_spent_seconds || 0) / 60)));
    refs.performanceStats.appendChild(createStatCard("Resource Clicks", metrics.number_of_resources_clicked || 0));
    refs.performanceStats.appendChild(createStatCard("Assignments Viewed", metrics.number_of_assignments_viewed || 0));
    refs.performanceStats.appendChild(createStatCard("Quiz Attempts", metrics.quiz_attempts || 0));
    refs.performanceStats.appendChild(createStatCard("Assignment Submissions", metrics.assignment_submissions || 0));
    refs.performanceStats.appendChild(createStatCard("Active Days", metrics.active_days_count || 0));
    refs.performanceStats.appendChild(createStatCard("Clicks", metrics.click_count || 0));
};

const groupMaterials = (materials) => {
    const groups = { lecture: [], lab: [], other: [] };
    materials.forEach((material) => {
        const type = (material.type || "unknown").toLowerCase();
        if (type === "lecture") groups.lecture.push(material);
        else if (type === "lab") groups.lab.push(material);
        else groups.other.push(material);
    });
    return groups;
};

const renderMaterialsList = (materials) => {
    refs.materialsList.innerHTML = "";
    const groups = groupMaterials(materials);
    const orderedGroups = [
        ["Lecture", groups.lecture],
        ["Lab", groups.lab],
        ["Other", groups.other]
    ];
    orderedGroups.forEach(([label, items]) => {
        const section = document.createElement("section");
        section.className = "material-group";
        section.innerHTML = `<h3>${label} (${items.length})</h3>`;
        if (!items.length) {
            const empty = document.createElement("p");
            empty.className = "subtle";
            empty.textContent = "No materials in this group.";
            section.appendChild(empty);
            refs.materialsList.appendChild(section);
            return;
        }
        items.forEach((material, index) => {
            const item = document.createElement("article");
            item.className = "material-item";
            const canDownload = isMaterialDownloadable(material);
            item.innerHTML = `
                <div class="row"><strong>${fileTypeIcon(material.fileType)} ${material.title}</strong></div>
                <div class="material-meta">Type: ${material.type} · File: ${(material.fileType || "unknown").toUpperCase()}</div>
            `;
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = canDownload ? "Download" : "View on Moodle";
            button.disabled = !material.url;
            button.addEventListener("click", async () => {
                if (!canDownload) {
                    chrome.tabs.create({ url: material.url });
                    return;
                }
                const result = await startDownload(material, index);
                button.textContent = result.ok ? (result.method === "download" ? "Downloaded" : "Opened") : "Failed";
            });
            item.appendChild(button);
            section.appendChild(item);
        });
        refs.materialsList.appendChild(section);
    });
};

const renderCourseSelector = (courseIds) => {
    refs.courseSelector.innerHTML = "";
    courseIds.forEach((courseId) => {
        const metrics = currentData.metricsByCourse?.[courseId] || {};
        const option = document.createElement("option");
        option.value = courseId;
        option.textContent = metrics.course_name || `Course ${courseId}`;
        refs.courseSelector.appendChild(option);
    });
    if (!currentCourseId || !courseIds.includes(currentCourseId)) {
        currentCourseId = courseIds[0] || null;
    }
    refs.courseSelector.value = currentCourseId || "";
};

const renderDashboard = () => {
    const data = currentData;
    const courseIds = Object.keys(data?.metricsByCourse || {});
    const isEmpty = courseIds.length === 0;
    refs.lastUpdated.textContent = `Last refreshed: ${new Date().toLocaleString()}`;
    refs.emptyState.classList.toggle("hidden", !isEmpty);
    refs.dashboard.classList.toggle("hidden", isEmpty);
    if (isEmpty) {
        refs.downloadAllPdfsBtn.disabled = true;
        return;
    }
    renderCourseSelector(courseIds);
    const metrics = data.metricsByCourse?.[currentCourseId] || {};
    metrics.active_days_count = data.behavior?.active_days_count || metrics.active_days_count || 0;
    renderPerformance(metrics);
    const courseMaterials = getCourseMaterials(data, currentCourseId);
    const downloadableCount = courseMaterials.filter(isMaterialDownloadable).length;
    refs.downloadMeta.textContent = `Total materials: ${courseMaterials.length} · Download-ready: ${downloadableCount}`;
    refs.downloadAllPdfsBtn.disabled = downloadableCount === 0;
    renderMaterialsList(courseMaterials);
};

const refreshData = async () => {
    currentData = await getStorageData();
    renderDashboard();
};

// Add Sync button dynamically
const addSyncButton = () => {
    const syncBtn = document.createElement("button");
    syncBtn.id = "syncBackendBtn";
    syncBtn.textContent = "Sync to Backend";
    syncBtn.style.marginLeft = "10px";
    refs.downloadJsonBtn.parentNode.insertBefore(syncBtn, refs.downloadJsonBtn.nextSibling);
    syncBtn.addEventListener("click", async () => {
        const data = await getStorageData();
        if (data) {
            syncBtn.disabled = true;
            syncBtn.textContent = "Syncing...";
            const result = await syncToBackend(data);
            if (result) {
                const email = result.login_email || "your AcademIQ email";
                const signinUrl = result.signin_url || PRODUCTION_SIGNIN_URL;
                syncBtn.textContent = "Synced!";
                const passwordLine = result.temporary_password
                    ? `Temporary password: ${result.temporary_password}\n\n`
                    : "";
                const accountLine = result.account_created
                    ? "A new AcademIQ account was created.\n\n"
                    : result.password_reset_for_demo
                        ? "Your AcademIQ account already existed. A new temporary password was generated for demo sign-in.\n\n"
                        : "";
                alert(
                    `Synced to deployed backend:\nhttps://academiq-backend.vercel.app\n\n` +
                    accountLine +
                    `Login email: ${email}\n` +
                    passwordLine +
                    `Sign in: ${signinUrl}\n\n` +
                    `Optional: click "Upload materials for quiz" in this popup to send course files to the backend for quiz generation.`
                );
            } else {
                syncBtn.textContent = "Sync Failed";
            }
            setTimeout(() => {
                syncBtn.disabled = false;
                syncBtn.textContent = "Sync to Backend";
            }, 2000);
        } else {
            alert("No data to sync.");
        }
    });
};

// Add "Scan all courses" button — asks the content script on the active Moodle
// tab to fetch + scrape every enrolled course (not just the open one).
const addScanAllButton = () => {
    const btn = document.createElement("button");
    btn.id = "scanAllBtn";
    btn.textContent = "Scan all courses";
    btn.style.marginLeft = "10px";
    refs.refreshBtn.parentNode.insertBefore(btn, refs.refreshBtn.nextSibling);
    btn.addEventListener("click", () => {
        chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
            if (!tab?.id) return;
            btn.disabled = true;
            btn.textContent = "Scanning all courses...";
            chrome.tabs.sendMessage(tab.id, { type: "scrape_all_courses" }, (response) => {
                if (chrome.runtime.lastError || !response) {
                    btn.textContent = "Open a Moodle tab first";
                } else if (response.status === "done") {
                    btn.textContent = `Scanned ${response.scraped}/${response.courses} courses`;
                    refreshData();
                } else {
                    btn.textContent = "Scan failed";
                }
                setTimeout(() => {
                    btn.disabled = false;
                    btn.textContent = "Scan all courses";
                }, 2500);
            });
        });
    });
};

const QUIZ_DOWNLOAD_FILE_TYPES = new Set(["pdf", "pptx", "ppt", "docx", "doc", "txt", "text"]);
const URL_LIKE_FILE_TYPES = new Set(["html", "link", "url", "page", "book"]);
const PLUGINFILE_RE = /pluginfile\.php/i;

const isEducationalLearningTitle = (title) =>
    /lecture|lec\s*#?\d|\blab\b|revision|review|summary|notes?|tutorial|handout|slides?|chapter|worksheet|problem\s*sheet|exercise\s*sheet/i.test(
        title || ""
    );

const isDirectDownloadUrl = (url) =>
    Boolean(
        url &&
            (/\.(pdf|pptx?|docx?|txt)(\?|$)/i.test(url.split("?")[0]) || PLUGINFILE_RE.test(url))
    );

/** True when the extension can download bytes or upload HTML page text for quiz extraction. */
const isDownloadableMaterial = (material) => {
    const ft = (material.fileType || material.file_type || "").toLowerCase();
    const url = material.resolvedUrl || material.resolved_url || material.url || "";
    if (QUIZ_DOWNLOAD_FILE_TYPES.has(ft)) return true;
    if (isDirectDownloadUrl(url)) return true;
    if (isEducationalLearningTitle(material.title || "")) {
        if (URL_LIKE_FILE_TYPES.has(ft) && (material.url || url)) return true;
        if ((material.pageText || material.page_text || "").length >= 80) return true;
    }
    return false;
};

/** Legacy alias — only use for download/upload filtering, not metadata save. */
const isQuizUploadableMaterial = isDownloadableMaterial;

/** Preflight statuses that must never trigger a file download/upload. */
const PREFLIGHT_SKIP_STATUSES = new Set([
    "already_saved",
    "already_ready",
    "already_classified",
    "already_processed",
    "not_quiz_material",
    "extraction_failed",
    "metadata_only",
    "extraction_too_short",
    "insufficient_text",
    "unsupported",
    "failed_download",
]);

const isPreflightUploadAllowed = (item) => {
    if (!item || item.should_upload !== true) return false;
    if (PREFLIGHT_SKIP_STATUSES.has(item.status)) return false;
    return true;
};

const getActiveMoodleTab = () =>
    new Promise((resolve) => {
        chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => resolve(tab || null));
    });

const scrapeCurrentCourseOnActiveTab = (courseId) =>
    new Promise((resolve) => {
        getActiveMoodleTab().then((tab) => {
            if (!tab?.id) {
                resolve({ status: "error", error: "Open a Moodle course tab first." });
                return;
            }
            chrome.tabs.sendMessage(
                tab.id,
                { type: "scrape_current_course", courseId },
                (response) => {
                    if (chrome.runtime.lastError) {
                        resolve({ status: "error", error: chrome.runtime.lastError.message });
                        return;
                    }
                    resolve(response || { status: "error", error: "No response from Moodle page." });
                }
            );
        });
    });

/**
 * Ask content.js to upload materials for quiz.
 *
 * @param {string} courseId
 * @param {string[]|null} onlyMaterialIds  When provided, content.js only
 *   downloads and uploads materials whose id is in this list.  Pass null to
 *   upload everything (no pre-filtering).
 */
const uploadMaterialsOnActiveTab = (courseId, onlyMaterialIds = null, preflightItems = null) =>
    new Promise((resolve) => {
        getActiveMoodleTab().then((tab) => {
            if (!tab?.id) {
                resolve({ status: "error", error: "Open a Moodle course tab first." });
                return;
            }
            chrome.tabs.sendMessage(
                tab.id,
                {
                    type: "upload_materials_for_quiz",
                    backendUploadUrl: UPLOAD_QUIZ_URL,
                    courseId,
                    // Pre-filtered list from popup's preflight call.
                    // content.js skips any material not in this set.
                    only_material_ids: onlyMaterialIds,
                    preflight_items: preflightItems
                },
                (response) => {
                    if (chrome.runtime.lastError) {
                        resolve({ status: "error", error: chrome.runtime.lastError.message });
                        return;
                    }
                    resolve(response || { status: "error", error: "No response from Moodle page." });
                }
            );
        });
    });

// Upload materials to the backend for quiz generation (uses Moodle session in the active tab).
const arrayBufferToBase64 = (buf) => {
    const bytes = new Uint8Array(buf);
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
};

const uploadMaterialPayload = async (payload) => {
    const response = await fetch(UPLOAD_QUIZ_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    let data = {};
    try {
        data = await response.json();
    } catch (_error) {
        data = {};
    }
    return { ok: response.ok, ...data };
};

const uploadStoredMaterial = async (material, identity) => {
    const materialId = material.id || material.material_id;
    const url = material.url;
    if (!materialId || !url) return { ok: false, error: "missing_id_or_url" };
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) return { ok: false, error: `http_${res.status}` };
    return uploadMaterialPayload({
        course_id: material.courseId || currentCourseId,
        course_name: currentData?.metricsByCourse?.[currentCourseId]?.course_name,
        material_id: materialId,
        title: material.title,
        material_type: material.type,
        file_type: material.fileType,
        source_url: url,
        content_base64: arrayBufferToBase64(await res.arrayBuffer()),
        content_type: res.headers.get("content-type") || "",
        user_email: identity?.email || null
    });
};

const uploadPickedFiles = async (files, courseId, identity) => {
    const results = [];
    for (const file of files) {
        const ext = (file.name.split(".").pop() || "").toLowerCase();
        const materialId = `manual_${ext}_${file.name.replace(/[^a-z0-9._-]+/gi, "_")}`;
        const buf = await file.arrayBuffer();
        const result = await uploadMaterialPayload({
            course_id: courseId,
            course_name: currentData?.metricsByCourse?.[courseId]?.course_name,
            material_id: materialId,
            title: file.name,
            material_type: "resource",
            file_type: ext || "unknown",
            source_url: null,
            content_base64: arrayBufferToBase64(buf),
            content_type: file.type || "",
            user_email: identity?.email || null
        });
        results.push(result);
    }
    return results;
};

const formatQuizUploadSummary = ({
    courseId,
    courseName,
    detected = 0,
    metadataSaved = 0,
    preflightChecked = 0,
    dbFound = 0,
    uploadAttempted = 0,
    uploaded = 0,
    ready = 0,
    failed = 0,
    total = 0,
    skippedExisting = 0,
    alreadyReady = 0,
    alreadyClassified = 0,
    skippedExtractionFailed = 0,
    reprocessing = 0,
    excludedFromDownload = 0,
    excludedReason = "",
    endpoint,
    extra = ""
}) => {
    const parts = [
        `Course ${courseId}${courseName ? ` · ${courseName}` : ""}`,
        `Detected ${detected}`,
    ];
    if (metadataSaved > 0 || detected > 0) {
        parts.push(`Saved metadata ${metadataSaved || detected}`);
    }
    if (dbFound > 0) {
        parts.push(`DB has ${dbFound} unique rows`);
    }
    if (preflightChecked > 0) {
        parts.push(`Preflight checked ${preflightChecked}`);
        if (dbFound > 0) parts.push(`DB has ${dbFound} for course`);
    }
    if (uploadAttempted > 0 || total > 0) {
        parts.push(`Downloadable/upload attempted ${uploadAttempted || total}`);
    }
    if (excludedFromDownload > 0) {
        parts.push(
            `Excluded ${excludedFromDownload}${excludedReason ? ` (${excludedReason})` : " (not downloadable)"}`
        );
    }
    if (skippedExisting > 0) {
        const detail = [];
        if (alreadyReady > 0) detail.push(`${alreadyReady} already ready`);
        if (alreadyClassified > 0) detail.push(`${alreadyClassified} already classified`);
        if (skippedExtractionFailed > 0) detail.push(`${skippedExtractionFailed} extraction failed`);
        const rest = skippedExisting - alreadyReady - alreadyClassified - skippedExtractionFailed;
        if (rest > 0) detail.push(`${rest} other`);
        parts.push(`Skipped existing ${skippedExisting}${detail.length ? ` (${detail.join(", ")})` : ""}`);
    }
    if (reprocessing > 0) {
        parts.push(`Re-extracting ${reprocessing} educational (too short)`);
    }
    if (uploaded > 0 || total > 0) {
        parts.push(`Uploaded ${uploaded}/${total}`);
    }
    if (ready > 0) parts.push(`Ready ${ready}`);
    if (failed > 0) parts.push(`Failed ${failed}`);
    parts.push(`API ${endpoint || UPLOAD_QUIZ_URL}`);
    if (extra) parts.push(extra);
    parts.push("Open Quiz Generation for the same course in AcademIQ.");
    return parts.join(" · ");
};

const syncPopupCourseToTab = async () => {
    const scrape = await scrapeCurrentCourseOnActiveTab();
    if (scrape.status !== "done" || !scrape.course?.course_id) {
        return {
            ok: false,
            error: scrape.error || "Open a Moodle course page in the active tab first."
        };
    }
    const tabId = String(scrape.course.course_id);
    const tabName = scrape.course.course_name || null;
    if (currentCourseId !== tabId) {
        currentCourseId = tabId;
        if (refs.courseSelector.querySelector(`option[value="${tabId}"]`)) {
            refs.courseSelector.value = tabId;
        }
        renderDashboard();
    }
    // Return scraped materials so the popup can run preflight without
    // a second round-trip to the Moodle tab.
    return { ok: true, courseId: tabId, courseName: tabName, materials: scrape.materials || [] };
};

const logRetryExtractionAudit = (tabResult, courseId) => {
    const identityRows = (tabResult?.results || [])
        .map((row) => row.identity_audit)
        .filter(Boolean);
    if (identityRows.length) {
        console.group(`[AcademIQ] Upload identity audit — course ${courseId}`);
        console.table(identityRows);
        console.groupEnd();
    }
    const audit =
        tabResult?.targeted_retry_audit ||
        tabResult?.retry_audit ||
        (tabResult?.results || []).map((row) => row.audit).filter(Boolean);
    if (!audit.length) return;
    console.group(`[AcademIQ] Not-uploaded extraction audit — course ${courseId}`);
    console.table(
        audit.map((row) => ({
            title: row.title,
            file_type: row.file_type,
            source_url: row.source_url_present,
            resolved_url: row.resolved_url_present,
            download_attempted: row.download_attempted,
            download_status: row.download_status,
            extracted_chars: row.extracted_chars,
            quiz_status: row.quiz_status,
            reason: row.reason,
        }))
    );
    console.groupEnd();
};

const runQuizMaterialUpload = async () => {
    const btn = refs.uploadQuizBtn;
    if (!currentCourseId) {
        refs.uploadMeta.textContent = "Select a course first.";
        return;
    }

    btn.disabled = true;
    refs.uploadMeta.textContent = "Scanning Moodle course page...";

    // ── Step 1: scrape material list from the active Moodle tab ──────────────
    const tabSync = await syncPopupCourseToTab();
    if (!tabSync.ok) {
        refs.uploadMeta.textContent = tabSync.error;
        btn.disabled = false;
        return;
    }

    const courseId = tabSync.courseId;
    const courseName = tabSync.courseName;
    const identity = currentData?.student || {};

    // All materials visible on the page (metadata only, no downloads yet)
    const scrapedMaterials = tabSync.materials || [];
    const detected = scrapedMaterials.length;
    const downloadable = scrapedMaterials.filter(isDownloadableMaterial);
    const excludedFromDownload = detected - downloadable.length;

    let metadataSaved = 0;
    let dbFound = 0;

    // ── Step 2: save metadata for EVERY detected material ───────────────────
    refs.uploadMeta.textContent =
        `Saving metadata for ${detected} detected materials...`;

    if (detected > 0) {
        const saveRes = await callSaveDetectedFromPopup(
            courseId,
            scrapedMaterials,
            identity,
            courseName
        );
        if (!saveRes.ok) {
            const httpNote =
                saveRes.httpStatus === 404
                    ? " — endpoint not found (backend may need redeployment)"
                    : saveRes.httpStatus === 0
                        ? " — network error"
                        : ` — HTTP ${saveRes.httpStatus}`;
            refs.uploadMeta.textContent =
                `Save metadata failed at ${saveRes.saveUrl}${httpNote}: ${saveRes.error}. ` +
                `Check the backend URL in Settings below and try again.`;
            btn.disabled = false;
            btn.textContent = "Upload materials for quiz";
            return;
        }
        metadataSaved =
            saveRes.data.metadata_saved_total ||
            saveRes.data.saved_total ||
            detected;
        logSaveDetectedAudit(saveRes.data, courseId);
        dbFound = saveRes.data.db_materials_found_for_course || dbFound;
    }

    // ── Step 3: preflight — runs from popup context (chrome-extension:// origin) ──
    refs.uploadMeta.textContent =
        `Preflight check: ${PREFLIGHT_URL} (${detected} materials)...`;

    let skippedExisting = 0;
    let alreadyReady = 0;
    let alreadyClassified = 0;
    let skippedExtractionFailed = 0;
    let reprocessing = 0;
    let preflightChecked = 0;
    let onlyMaterialIds = null;
    let preflightItems = null;

    if (detected > 0) {
        const pf = await callPreflightFromPopup(courseId, scrapedMaterials, identity);

        if (!pf.ok) {
            const httpNote =
                pf.httpStatus === 404
                    ? " — endpoint not found (backend may need redeployment)"
                    : pf.httpStatus === 0
                        ? " — network error"
                        : ` — HTTP ${pf.httpStatus}`;
            refs.uploadMeta.textContent =
                `Preflight failed at ${pf.preflightUrl}${httpNote}: ${pf.error}. ` +
                `Metadata was saved (${metadataSaved}). Check backend URL and try again.`;
            btn.disabled = false;
            btn.textContent = "Upload materials for quiz";
            return;
        }

        preflightChecked = (pf.data.materials || []).length;
        dbFound = pf.data.db_materials_found_for_course || 0;

        console.group(`[AcademIQ] Preflight response — course ${courseId}`);
        console.log(
            "checked:", pf.data.checked,
            "| should_upload:", pf.data.should_upload_count,
            "| matched:", pf.data.matched_count,
            "| no_match:", pf.data.no_match_count
        );
        console.log("metadata_saved:", metadataSaved, "| downloadable:", downloadable.length);
        console.groupEnd();

        preflightItems = pf.data.materials || [];
        onlyMaterialIds = [];
        for (const item of preflightItems) {
            const mid = String(item.material_id);
            if (isPreflightUploadAllowed(item)) {
                onlyMaterialIds.push(mid);
            } else {
                if (item.status === "already_ready") {
                    alreadyReady += 1;
                } else if (
                    ["already_saved", "already_classified", "already_processed", "not_quiz_material"].includes(
                        item.status
                    )
                ) {
                    alreadyClassified += 1;
                } else if (item.status === "extraction_failed") {
                    skippedExtractionFailed += 1;
                }
                skippedExisting += 1;
            }
        }

        if (onlyMaterialIds.length === 0) {
            await refreshData();
            btn.textContent = "Upload materials for quiz";
            btn.disabled = false;
            refs.uploadMeta.textContent = formatQuizUploadSummary({
                courseId,
                courseName,
                detected,
                metadataSaved,
                preflightChecked,
                dbFound,
                uploadAttempted: 0,
                uploaded: 0,
                ready: 0,
                failed: 0,
                total: 0,
                skippedExisting,
                alreadyReady,
                alreadyClassified,
                skippedExtractionFailed,
                reprocessing,
                excludedFromDownload,
                excludedReason: "url/html/link — metadata saved only",
                endpoint: UPLOAD_QUIZ_URL,
            });
            return;
        }

        refs.uploadMeta.textContent =
            `DB: ${dbFound} saved · Skipped ${skippedExisting} · Uploading ${onlyMaterialIds.length} new file(s)...`;
    }

    if (!onlyMaterialIds || onlyMaterialIds.length === 0) {
        await refreshData();
        btn.textContent = "Upload materials for quiz";
        btn.disabled = false;
        refs.uploadMeta.textContent = formatQuizUploadSummary({
            courseId,
            courseName,
            detected,
            metadataSaved,
            preflightChecked,
            dbFound,
            uploadAttempted: 0,
            uploaded: 0,
            ready: 0,
            failed: 0,
            total: 0,
            skippedExisting,
            alreadyReady,
            alreadyClassified,
            skippedExtractionFailed,
            reprocessing: 0,
            excludedFromDownload,
            excludedReason: "url/html/link — metadata saved only",
            endpoint: UPLOAD_QUIZ_URL,
        });
        return;
    }

    // ── Step 4: download + upload only brand-new unmatched downloadable materials ──
    const tabResult = await uploadMaterialsOnActiveTab(courseId, onlyMaterialIds, preflightItems);

    if (tabResult.status === "done") {
        logRetryExtractionAudit(tabResult, courseId);
        const uploaded = tabResult.uploaded || 0;
        const ready = tabResult.ready || 0;
        const failed = tabResult.failed ?? Math.max(0, (tabResult.total || 0) - uploaded);
        const total = tabResult.total || 0;
        await refreshData();
        btn.textContent = "Upload materials for quiz";
        btn.disabled = false;
        refs.uploadMeta.textContent = formatQuizUploadSummary({
            courseId,
            courseName: tabResult.course_name || courseName,
            detected,
            metadataSaved,
            preflightChecked,
            dbFound,
            uploadAttempted: total,
            uploaded,
            ready,
            failed,
            total,
            skippedExisting,
            alreadyReady,
            alreadyClassified,
            skippedExtractionFailed,
            reprocessing,
            excludedFromDownload,
            excludedReason: "url/html/link — metadata saved only",
            endpoint: tabResult.backend_endpoint || UPLOAD_QUIZ_URL,
        });
        return;
    }

    if (tabResult.tab_course_id && String(tabResult.tab_course_id) !== String(courseId)) {
        refs.uploadMeta.textContent =
            tabResult.error ||
            `Course mismatch: tab is ${tabResult.tab_course_id}, dropdown is ${courseId}.`;
        btn.disabled = false;
        btn.textContent = "Upload materials for quiz";
        return;
    }

    // Final fallback — content script failed; try stored materials from popup context
    const stored = getCourseMaterials(currentData, courseId).filter(isDownloadableMaterial);
    if (stored.length) {
        refs.uploadMeta.textContent = `Falling back to ${stored.length} stored material(s)...`;
        let uploaded = 0; let ready = 0; let failed = 0;
        for (let i = 0; i < stored.length; i += 1) {
            btn.textContent = `Uploading ${i + 1}/${stored.length}...`;
            try {
                const result = await uploadStoredMaterial(stored[i], identity);
                if (result.ok) uploaded += 1; else failed += 1;
                if (result.ready_for_quiz) ready += 1;
            } catch (_error) {
                failed += 1;
            }
        }
        btn.textContent = "Upload materials for quiz";
        btn.disabled = false;
        refs.uploadMeta.textContent = formatQuizUploadSummary({
            courseId,
            courseName,
            detected,
            metadataSaved,
            preflightChecked,
            uploaded,
            ready,
            failed,
            total: stored.length,
            uploadAttempted: stored.length,
            skippedExisting,
            alreadyReady,
            alreadyClassified,
            skippedExtractionFailed,
            reprocessing,
            endpoint: UPLOAD_QUIZ_URL,
            extra: "Fallback: stored materials",
        });
    } else {
        refs.uploadMeta.textContent =
            `${tabResult.error || "Could not reach Moodle tab."} ` +
            `Open the course page, refresh, or pick files manually.`;
        btn.disabled = false;
        btn.textContent = "Upload materials for quiz";
        refs.manualQuizFileInput.click();
    }
};

const bindQuizUploadControls = () => {
    refs.uploadQuizBtn.addEventListener("click", () => {
        runQuizMaterialUpload().catch((error) => {
            refs.uploadMeta.textContent = `Upload failed: ${error.message || error}`;
            refs.uploadQuizBtn.disabled = false;
            refs.uploadQuizBtn.textContent = "Upload materials for quiz";
        });
    });

    refs.manualQuizFileInput.addEventListener("change", async (event) => {
        const files = Array.from(event.target.files || []);
        event.target.value = "";
        if (!files.length || !currentCourseId) return;
        refs.uploadMeta.textContent = `Uploading ${files.length} picked file(s)...`;
        refs.uploadQuizBtn.disabled = true;
        const identity = currentData?.student || {};
        const results = await uploadPickedFiles(files, currentCourseId, identity);
        const uploaded = results.filter((row) => row.ok).length;
        const ready = results.filter((row) => row.ready_for_quiz).length;
        const failed = results.length - uploaded;
        refs.uploadQuizBtn.disabled = false;
        refs.uploadMeta.textContent = formatQuizUploadSummary({
            courseId: currentCourseId,
            courseName: currentData?.metricsByCourse?.[currentCourseId]?.course_name,
            uploaded,
            ready,
            failed,
            total: files.length,
            endpoint: UPLOAD_QUIZ_URL,
            extra: "Manual file picker"
        });
    });
};

refs.courseSelector.addEventListener("change", () => {
    currentCourseId = refs.courseSelector.value;
    renderDashboard();
});

refs.downloadAllPdfsBtn.addEventListener("click", async () => {
    const materials = getCourseMaterials(currentData, currentCourseId).filter(isMaterialDownloadable);
    let successCount = 0;
    for (let i = 0; i < materials.length; i += 1) {
        const result = await startDownload(materials[i], i);
        if (result.ok) successCount += 1;
    }
    refs.downloadMeta.textContent = `Total materials: ${materials.length} · Started: ${successCount}`;
});

refs.downloadJsonBtn.addEventListener("click", async () => {
    const data = await getStorageData();
    if (!data) return;
    const payload = sanitizePayload(data);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "moodle_student_data.json";
    a.click();
    URL.revokeObjectURL(url);
});

refs.clearDataBtn.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "clear_data" }, () => {
        currentData = null;
        currentCourseId = null;
        renderDashboard();
        refs.lastUpdated.textContent = "Data cleared";
    });
});

refs.refreshBtn.addEventListener("click", refreshData);

const bindSettingsControls = () => {
    if (!refs.saveBackendUrlBtn) return;
    refs.saveBackendUrlBtn.addEventListener("click", () => {
        const raw = (refs.backendUrlInput?.value || "").trim();
        if (!raw) return;
        const normalized = normalizeApiBase(raw);
        chrome.storage.local.set({ backendUrl: normalized }, () => {
            const urls = buildBackendUrls(normalized);
            BACKEND_URL = urls.sync;
            UPLOAD_QUIZ_URL = urls.uploadQuiz;
            PREFLIGHT_URL = urls.preflight;
            SAVE_DETECTED_URL = urls.saveDetected;
            CONTENT_URL = urls.content;
            if (refs.backendUrlStatus) {
                refs.backendUrlStatus.textContent = `Saved. Preflight: ${urls.preflight}`;
                setTimeout(() => { refs.backendUrlStatus.textContent = ""; }, 4000);
            }
        });
    });
};

document.addEventListener("DOMContentLoaded", () => {
    loadBackendConfig().then(() => {
        refreshData();
        addSyncButton();
        addScanAllButton();
        bindQuizUploadControls();
        bindSettingsControls();
    });
});