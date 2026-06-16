const PRODUCTION_SIGNIN_URL = "https://academiq-frontend.vercel.app/signin";
const STORAGE_KEY = "moodleData";
const PRODUCTION_API_BASE = "https://academiq-backend.vercel.app";
const SYNC_PATH = "/raw-moodle-payloads";
const UPLOAD_QUIZ_PATH = "/materials/upload-for-quiz";
const CONTENT_PATH = "/materials/content";

/** Always POST to {base}/raw-moodle-payloads even if storage holds base URL only. */
const normalizeApiBase = (url) => {
    const raw = (url || PRODUCTION_API_BASE).trim().replace(/\/$/, "");
    return raw
        .replace(/\/raw-moodle-payloads\/?$/, "")
        .replace(/\/materials\/upload-for-quiz\/?$/, "")
        .replace(/\/materials\/content\/?$/, "");
};

const buildBackendUrls = (apiBase) => {
    const base = normalizeApiBase(apiBase);
    return {
        sync: `${base}${SYNC_PATH}`,
        uploadQuiz: `${base}${UPLOAD_QUIZ_PATH}`,
        content: `${base}${CONTENT_PATH}`,
    };
};

let BACKEND_URL = buildBackendUrls(PRODUCTION_API_BASE).sync;
let UPLOAD_QUIZ_URL = buildBackendUrls(PRODUCTION_API_BASE).uploadQuiz;
let CONTENT_URL = buildBackendUrls(PRODUCTION_API_BASE).content;

const loadBackendConfig = () =>
    new Promise((resolve) => {
        chrome.storage.local.get(["backendUrl"], (res) => {
            const urls = buildBackendUrls(res.backendUrl || PRODUCTION_API_BASE);
            BACKEND_URL = urls.sync;
            UPLOAD_QUIZ_URL = urls.uploadQuiz;
            CONTENT_URL = urls.content;
            resolve();
        });
    });

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
    lastUpdated: document.getElementById("lastUpdated")
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

const QUIZ_UPLOAD_FILE_TYPES = new Set(["pdf", "pptx", "ppt", "docx", "doc", "txt", "text"]);

const isQuizUploadableMaterial = (material) => {
    const ft = (material.fileType || "").toLowerCase();
    const url = material.url || "";
    if (QUIZ_UPLOAD_FILE_TYPES.has(ft)) return true;
    return /\.(pdf|pptx?|docx?|txt)(\?|$)/i.test(url);
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

const uploadMaterialsOnActiveTab = (courseId) =>
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
                    courseId
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
    uploaded,
    ready,
    failed,
    total,
    endpoint,
    extra = ""
}) => {
    const parts = [
        `Course ${courseId}${courseName ? ` · ${courseName}` : ""}`,
        `Uploaded ${uploaded}/${total}`,
        `Ready ${ready}`,
        `Failed ${failed}`,
        `API ${endpoint || UPLOAD_QUIZ_URL}`
    ];
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
    return { ok: true, courseId: tabId, courseName: tabName };
};

const runQuizMaterialUpload = async () => {
    const btn = refs.uploadQuizBtn;
    if (!currentCourseId) {
        refs.uploadMeta.textContent = "Select a course first.";
        return;
    }

    btn.disabled = true;
    refs.uploadMeta.textContent = "Aligning with active Moodle tab...";

    const tabSync = await syncPopupCourseToTab();
    if (!tabSync.ok) {
        refs.uploadMeta.textContent = tabSync.error;
        btn.disabled = false;
        return;
    }

    const courseId = tabSync.courseId;
    const courseName = tabSync.courseName;
    refs.uploadMeta.textContent = `Uploading materials for course ${courseId}...`;

    const identity = currentData?.student || {};
    let uploaded = 0;
    let ready = 0;
    let failed = 0;
    let total = 0;
    let endpoint = UPLOAD_QUIZ_URL;

    const tabResult = await uploadMaterialsOnActiveTab(courseId);
    if (tabResult.status === "done") {
        uploaded = tabResult.uploaded || 0;
        ready = tabResult.ready || 0;
        failed = tabResult.failed ?? Math.max(0, (tabResult.total || 0) - uploaded);
        total = tabResult.total || 0;
        endpoint = tabResult.backend_endpoint || endpoint;
        await refreshData();
    } else if (tabResult.tab_course_id && String(tabResult.tab_course_id) !== String(courseId)) {
        refs.uploadMeta.textContent =
            tabResult.error ||
            `Course mismatch: tab is ${tabResult.tab_course_id}, dropdown is ${courseId}.`;
        btn.disabled = false;
        btn.textContent = "Upload materials for quiz";
        return;
    } else {
        const stored = getCourseMaterials(currentData, courseId).filter(isQuizUploadableMaterial);
        if (stored.length) {
            refs.uploadMeta.textContent = `Falling back to ${stored.length} stored material(s)...`;
            for (let i = 0; i < stored.length; i += 1) {
                btn.textContent = `Uploading ${i + 1}/${stored.length}...`;
                try {
                    const result = await uploadStoredMaterial(stored[i], identity);
                    if (result.ok) uploaded += 1;
                    else failed += 1;
                    if (result.ready_for_quiz) ready += 1;
                } catch (_error) {
                    failed += 1;
                }
            }
            total = stored.length;
        } else {
            refs.uploadMeta.textContent =
                `${tabResult.error || "Could not upload from Moodle tab."} Open the course page, refresh, or pick files manually.`;
            btn.disabled = false;
            btn.textContent = "Upload materials for quiz";
            refs.manualQuizFileInput.click();
            return;
        }
    }

    btn.textContent = "Upload materials for quiz";
    btn.disabled = false;
    refs.uploadMeta.textContent = formatQuizUploadSummary({
        courseId,
        courseName: tabResult.course_name || courseName,
        uploaded,
        ready,
        failed,
        total,
        endpoint
    });
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
document.addEventListener("DOMContentLoaded", () => {
    loadBackendConfig().then(() => {
        refreshData();
        addSyncButton();
        addScanAllButton();
        bindQuizUploadControls();
    });
});