const STORAGE_KEY = "moodleData";

const refs = {
    refreshBtn: document.getElementById("refreshBtn"),
    downloadJsonBtn: document.getElementById("downloadJsonBtn"),
    clearDataBtn: document.getElementById("clearDataBtn"),
    downloadAllPdfsBtn: document.getElementById("downloadAllPdfsBtn"),
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
    const { _meta, events, grades, learning_materials, courses, behavior, student, knowledge_base, metricsByCourse, materialsByCourse } = data;
    return {
        student,
        courses,
        behavior,
        knowledge_base,
        metricsByCourse,
        materialsByCourse,
        events: (events || []).map(({ _id, ...event }) => event),
        grades: (grades || []).map(({ _key, ...grade }) => grade),
        learning_materials: (learning_materials || []).map(({ _key, ...material }) => material)
    };
};

const getStorageData = () =>
    new Promise((resolve) => {
        chrome.storage.local.get(STORAGE_KEY, (res) => {
            resolve(res[STORAGE_KEY] || null);
        });
    });

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
    const fromScoped = Array.isArray(data?.materialsByCourse?.[courseId]) ? data.materialsByCourse[courseId].map((m) => normalizeMaterial(m, courseId)) : [];
    if (fromScoped.length) return fromScoped;

    const fromLegacy = Array.isArray(data?.learning_materials)
        ? data.learning_materials.filter((item) => (item.courseId || item.course_id) === courseId).map((m) => normalizeMaterial(m, courseId))
        : [];
    return fromLegacy;
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
document.addEventListener("DOMContentLoaded", refreshData);

// ── Sync to AcademIQ Dashboard ──────────────────────────────────────────────

const BACKEND_URL = "http://localhost:8000";

const syncRefs = {
    tokenInput: document.getElementById("syncTokenInput"),
    syncBtn:    document.getElementById("syncBtn"),
    syncStatus: document.getElementById("syncStatus"),
};

/**
 * POST the collected Moodle data to /api/extension/sync using the user's
 * Bearer token.  On success the dashboard will show data_source="live".
 */
const syncToDashboard = async () => {
    const token = (syncRefs.tokenInput?.value || "").trim();
    if (!token) {
        syncRefs.syncStatus.textContent = "⚠ Paste your dashboard token first.";
        return;
    }

    const data = await getStorageData();
    if (!data) {
        syncRefs.syncStatus.textContent = "⚠ No Moodle data collected yet.";
        return;
    }

    syncRefs.syncBtn.disabled = true;
    syncRefs.syncStatus.textContent = "Syncing…";

    const payload = sanitizePayload(data);

    try {
        const res = await fetch(`${BACKEND_URL}/api/extension/sync`, {
            method:  "POST",
            headers: {
                "Content-Type":  "application/json",
                "Authorization": `Bearer ${token}`,
            },
            body: JSON.stringify(payload),
        });

        if (res.ok) {
            const json = await res.json();
            syncRefs.syncStatus.textContent =
                `✓ Synced! Open your dashboard to see live data. (student: ${json.student_id})`;
        } else {
            const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
            syncRefs.syncStatus.textContent = `✗ ${err.detail || "Sync failed"}`;
        }
    } catch (e) {
        syncRefs.syncStatus.textContent = "✗ Backend not reachable. Make sure it is running on port 8000.";
    } finally {
        syncRefs.syncBtn.disabled = false;
    }
};

if (syncRefs.syncBtn) {
    syncRefs.syncBtn.addEventListener("click", syncToDashboard);
}
