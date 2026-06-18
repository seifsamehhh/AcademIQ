const STORAGE_KEY = "moodleData";
const SESSION_TIMEOUT_MS = 30 * 60 * 1000; // session end after 3 mins of inactivity

const activeTabs = new Map();
const pageViewsByTab = new Map();
let storageWriteQueue = Promise.resolve();

const defaultData = () => ({
    student: {
        // Identity used by AcademIQ to map Moodle data to the right account.
        // Priority: moodle_user_id, then student_id (see backend provisioning).
        moodle_user_id: null,
        student_id: null,
        full_name: null,
        email: null,
        program: null,
        enrollment_year: null
    },
    metricsByCourse: {},
    courses: [], // export flexibity (ashan aamel export brahty)
    behavior: { // bgahez lel ml models
        total_time_spent_on_moodle: 0,
        active_days_count: 0,
        session_count: 0,
        average_session_duration: 0,
        clicks_per_session: 0,
        peak_activity_hours: []
    },
    events: [],
    grades: [],
    // Single canonical list of materials (deduped by course_id + material id).
    // Categorisation (lecture/quiz/assignment/…) lives in each material's
    // `semantic_tags`/`type` — we no longer keep duplicate per-category or
    // per-course copies (learning_materials / materialsByCourse / knowledge_base).
    materials: [],
    _meta: {
        activeDays: [],
        hourCounts: {},
        lastActivity: null,
        sessionStart: null,
        sessionClicks: 0
    }
});

const createDefaultCourseMetrics = (course) => ({ // mapping el data ely gebtaha mn el content.js ashan adeha lel ml model later
    course_id: course.course_id,
    course_name: course.course_name || "Unknown Course",
    course_name_source: course.course_name_source || null,
    total_visits: 0,
    last_access_time: null,
    total_time_spent_seconds: 0,
    number_of_resources_clicked: 0,
    number_of_assignments_viewed: 0,
    number_of_quizzes_viewed: 0,
    active_days_count: 0,
    click_count: 0,
    quiz_attempts: 0,
    assignment_submissions: 0
});

const getStoredData = async () => {
    const result = await chrome.storage.local.get(STORAGE_KEY);
    const data = result[STORAGE_KEY] || defaultData();

    if (!data.metricsByCourse) data.metricsByCourse = {};
    if (!Array.isArray(data.materials)) data.materials = [];

    return data;
};

const saveStoredData = async (data) => {
    await chrome.storage.local.set({ [STORAGE_KEY]: data });
};

const queueStorageUpdate = (updater) => {
    storageWriteQueue = storageWriteQueue.then(async () => {
        const data = await getStoredData();
        await updater(data);
        await saveStoredData(data);
    });
    return storageWriteQueue;
};

const toCourseMap = (courses) => {
    const map = new Map();
    courses.forEach((course) => {
        if (course.course_id) {
            map.set(course.course_id, { ...course });
        }
    });
    return map;
};

const isBareCourseName = (name, courseId) => {
    const id = String(courseId || "").trim();
    const value = (name || "").trim();
    if (!value) return true;
    if (value === id || value === `Course ${id}`) return true;
    const cleaned = value.replace(/^course\s+/i, "").trim();
    if (cleaned === id || /^\d+$/.test(cleaned)) return true;
    return false;
};

const preferCourseName = (existingName, incomingName, courseId) => {
    if (!incomingName) return existingName;
    if (isBareCourseName(incomingName, courseId)) return existingName;
    if (isBareCourseName(existingName, courseId)) return incomingName;
    return incomingName.length > (existingName || "").length ? incomingName : existingName;
};

const mergeCourse = (data, coursesMap, course) => {
    if (!course?.course_id) return;

    const existing = coursesMap.get(course.course_id);
    const preferredName = preferCourseName(existing?.course_name, course.course_name, course.course_id);
    const preferredSource = course.course_name_source || existing?.course_name_source || null;

    if (!existing) {
        coursesMap.set(course.course_id, {
            ...createDefaultCourseMetrics(course),
            course_name: preferredName,
            course_name_source: preferredSource
        });
    } else {
        existing.course_name = preferredName;
        if (preferredSource) existing.course_name_source = preferredSource;
        coursesMap.set(course.course_id, existing);
    }

    if (!data.metricsByCourse[course.course_id]) {
        data.metricsByCourse[course.course_id] = {
            ...createDefaultCourseMetrics(course),
            course_name: preferredName,
            course_name_source: preferredSource
        };
    } else {
        data.metricsByCourse[course.course_id].course_name = preferCourseName(
            data.metricsByCourse[course.course_id].course_name,
            course.course_name,
            course.course_id
        );
        if (preferredSource) {
            data.metricsByCourse[course.course_id].course_name_source = preferredSource;
        }
    }
};

const syncMetricsByCourse = (data, coursesMap) => {
    data.courses = Array.from(coursesMap.values());
    data.courses.forEach((course) => {
        if (course.course_id) {
            data.metricsByCourse[course.course_id] = { ...course };
        }
    });
};

const updateSessionMetrics = (data, timestamp, isClick) => { // bupadate el sessions
    const meta = data._meta || defaultData()._meta;
    const behavior = data.behavior;
    const lastActivity = meta.lastActivity;

    const startNewSession = () => {
        meta.sessionStart = timestamp;
        meta.sessionClicks = 0;
        behavior.session_count += 1;
    };

    if (!meta.sessionStart) {
        startNewSession();
    } else if (lastActivity && timestamp - lastActivity > SESSION_TIMEOUT_MS) {
        const duration = Math.max(0, lastActivity - meta.sessionStart);
        if (duration > 0) {
            behavior.average_session_duration =
                (behavior.average_session_duration * (behavior.session_count - 1) + duration / 1000) /
                behavior.session_count;
            behavior.clicks_per_session =
                (behavior.clicks_per_session * (behavior.session_count - 1) + meta.sessionClicks) /
                behavior.session_count;
        }
        startNewSession();
    }

    if (isClick) {
        meta.sessionClicks += 1;
    }

    meta.lastActivity = timestamp;
    data._meta = meta;
};

const updateActiveDayAndHours = (data, timestamp) => {
    const meta = data._meta || defaultData()._meta;
    const dayKey = new Date(timestamp).toISOString().slice(0, 10);
    if (!meta.activeDays.includes(dayKey)) {
        meta.activeDays.push(dayKey);
    }
    data.behavior.active_days_count = meta.activeDays.length;

    const hour = new Date(timestamp).getHours();
    meta.hourCounts[hour] = (meta.hourCounts[hour] || 0) + 1;
    const sortedHours = Object.entries(meta.hourCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([hourKey]) => Number(hourKey));
    data.behavior.peak_activity_hours = sortedHours;
    data._meta = meta;
};

const addEvent = (data, event) => {
    const eventId = `${event.timestamp}-${event.page_type}-${event.action_type}-${event.course_id || "unknown"}`;
    const exists = data.events.some((item) => item._id === eventId);
    if (!exists) {
        data.events.push({ ...event, _id: eventId });
    }
};

const mergeGrades = (data, grades) => {
    grades.forEach((grade) => {
        const key = `${grade.course_id}-${grade.item_name}-${grade.item_type}-${grade.source_url || grade.submission_time || ""}`;
        const existingIndex = data.grades.findIndex((existing) => existing._key === key);
        const isNewGrade = existingIndex === -1;
        if (isNewGrade) {
            data.grades.push({ ...grade, _key: key });
        } else {
            const existing = data.grades[existingIndex];
            if (grade.percentage != null && existing.percentage == null) {
                data.grades[existingIndex] = { ...existing, ...grade, _key: key };
            }
        }

        if (!grade.course_id || !data.metricsByCourse[grade.course_id]) return;
        const courseMetrics = data.metricsByCourse[grade.course_id];
        const itemType = (grade.item_type || "").toLowerCase();
        if (!isNewGrade) return;

        if (itemType.includes("quiz")) {
            incrementCourseMetric(courseMetrics, "quiz_attempts", grade.course_id, "grades_merge");
        }

        if (itemType.includes("assignment")) {
            const isSubmitted = /submitted|submitted for grading|graded|done/i.test(grade.submission_status || "");
            if (isSubmitted) {
                incrementCourseMetric(courseMetrics, "assignment_submissions", grade.course_id, "grades_merge");
            }
        }
    });
};

// Merge scraped materials into the SINGLE canonical `data.materials` array,
// deduped by course_id + material id. No per-course or per-category copies are
// created — categorisation is derived later from each material's metadata
// (`semantic_tags` / `type`), so a material is stored exactly once.
const mergeMaterials = (data, materials) => {
    if (!Array.isArray(data.materials)) data.materials = [];
    const coursesMap = toCourseMap(data.courses);

    materials.forEach((material) => {
        const courseId = material.courseId || material.course_id || null;
        const materialId = material.id || material.material_id || material.url || material.title || "unknown";
        const key = `${courseId || "unknown"}-${materialId}`;

        if (courseId && material.course_name) {
            mergeCourse(data, coursesMap, {
                course_id: courseId,
                course_name: material.course_name,
                course_name_source: material.course_name_source || "material_scrape"
            });
        }

        const existingIndex = data.materials.findIndex((m) => m._key === key);
        const record = {
            ...material,
            course_id: courseId,
            material_id: materialId,
            _key: key
        };

        if (existingIndex === -1) {
            data.materials.push(record);
        } else {
            // Refresh in place (e.g. a later page resolved more metadata).
            data.materials[existingIndex] = { ...data.materials[existingIndex], ...record };
        }
    });

    syncMetricsByCourse(data, coursesMap);
};

const finalizeActiveTab = async (tabId, endTime) => { // time gets tracked by tap msh ay haga etfathet w khalas
    const active = activeTabs.get(tabId);
    if (!active) return;
    const durationMs = Math.max(0, endTime - active.startTime);
    if (durationMs <= 0) {
        activeTabs.delete(tabId);
        return;
    }
    await queueStorageUpdate(async (data) => {
        const coursesMap = toCourseMap(data.courses);
        mergeCourse(data, coursesMap, { course_id: active.courseId, course_name: active.courseName });

        const course = coursesMap.get(active.courseId);
        if (course) {
            course.total_time_spent_seconds += Math.round(durationMs / 1000);
            course.last_access_time = new Date(endTime).toISOString();
            coursesMap.set(active.courseId, course);
            console.log(`[moodle-ai] metric increment total_time_spent_seconds +${Math.round(durationMs / 1000)} course=${active.courseId} source=tab_hidden`);
        }

        data.behavior.total_time_spent_on_moodle += Math.round(durationMs / 1000);
        updateSessionMetrics(data, endTime, false);
        updateActiveDayAndHours(data, endTime);

        syncMetricsByCourse(data, coursesMap);
    });
    activeTabs.delete(tabId);
};

const shouldCountVisit = (tabId, payload) => { // ashan el bug bta3 el refresh. visits is counted lama ye3ml visit fe3lan bas.
    if (typeof tabId !== "number" || !payload?.course_id) return false;
    if (payload.navigation_type === "reload") return false;

    const previous = pageViewsByTab.get(tabId);
    const key = `${payload.course_id}-${payload.url || ""}`;
    if (previous?.key === key) {
        return false;
    }
    pageViewsByTab.set(tabId, { key, timestamp: payload.timestamp || Date.now() });
    return true;
};

const incrementCourseMetric = (course, metricName, courseId, source) => { 
    if (!course || typeof course[metricName] !== "number") return;
    course[metricName] += 1;
    console.log(`[moodle-ai] metric increment ${metricName} +1 course=${courseId} source=${source}`);
};

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const tabId = sender.tab?.id;

    if (message.type === "get_data") {
        chrome.storage.local.get(STORAGE_KEY, (result) => {
            sendResponse({ data: result[STORAGE_KEY] || null });
        });
        return true;
    }

    if (message.type === "clear_data") {
        chrome.storage.local.remove(STORAGE_KEY, () => {
            sendResponse({ status: "cleared" });
        });
        return true;
    }

    if (message.type === "page_view") {
        (async () => {
            const payload = message.payload;
            const timestamp = payload.timestamp || Date.now();
            const countVisit = shouldCountVisit(tabId, payload);
            if (typeof tabId === "number") {
                await finalizeActiveTab(tabId, timestamp);
                if (payload.course_id) {
                    activeTabs.set(tabId, {
                        startTime: timestamp,
                        courseId: payload.course_id,
                        courseName: payload.course_name,
                        pageType: payload.page_type
                    });
                }
            }

            await queueStorageUpdate(async (data) => {
                const coursesMap = toCourseMap(data.courses);
                mergeCourse(data, coursesMap, { course_id: payload.course_id, course_name: payload.course_name });
                const course = coursesMap.get(payload.course_id);
                if (course) {
                    if (countVisit) {
                        incrementCourseMetric(course, "total_visits", payload.course_id, `navigation:${payload.navigation_type || "navigate"}`);
                    }
                    course.last_access_time = new Date(timestamp).toISOString();
                    if (payload.page_type === "assignment") {
                        incrementCourseMetric(course, "number_of_assignments_viewed", payload.course_id, "page_view");
                    } else if (payload.page_type === "quiz") {
                        incrementCourseMetric(course, "number_of_quizzes_viewed", payload.course_id, "page_view");
                    }
                    if (payload.assignment_submission) {
                        incrementCourseMetric(course, "assignment_submissions", payload.course_id, "assignment_submission_detected");
                    }
                    if (payload.quiz_attempt) {
                        incrementCourseMetric(course, "quiz_attempts", payload.course_id, "quiz_attempt_detected");
                    }
                    coursesMap.set(payload.course_id, course);
                }

                updateSessionMetrics(data, timestamp, false);
                updateActiveDayAndHours(data, timestamp);
                addEvent(data, {
                    timestamp,
                    course_id: payload.course_id,
                    page_type: payload.page_type,
                    action_type: "view"
                });

                syncMetricsByCourse(data, coursesMap);
            });
            sendResponse({ status: "ok" });
        })();
        return true;
    }

    if (message.type === "page_hidden") {
        (async () => {
            const timestamp = message.payload?.timestamp || Date.now();
            if (typeof tabId === "number") {
                await finalizeActiveTab(tabId, timestamp);
            }
            sendResponse({ status: "ok" });
        })();
        return true;
    }

    if (message.type === "interaction") {
        (async () => {
            const payload = message.payload;
            const timestamp = payload.timestamp || Date.now();
            await queueStorageUpdate(async (data) => {
                const coursesMap = toCourseMap(data.courses);
                mergeCourse(data, coursesMap, { course_id: payload.course_id, course_name: null });
                const course = payload.course_id ? coursesMap.get(payload.course_id) : null;

                updateSessionMetrics(data, timestamp, true);
                updateActiveDayAndHours(data, timestamp);
                addEvent(data, {
                    timestamp,
                    course_id: payload.course_id,
                    page_type: payload.page_type,
                    action_type: payload.action_type
                });

                if (course) {
                    incrementCourseMetric(course, "click_count", payload.course_id, payload.action_type || "interaction");
                    if (payload.action_type === "material_click") {
                        incrementCourseMetric(course, "number_of_resources_clicked", payload.course_id, "click");
                    }
                    if (payload.action_type === "assignment_view") {
                        incrementCourseMetric(course, "number_of_assignments_viewed", payload.course_id, "click");
                    }
                    if (payload.action_type === "quiz_view") {
                        incrementCourseMetric(course, "number_of_quizzes_viewed", payload.course_id, "click");
                    }
                    coursesMap.set(payload.course_id, course);
                }

                syncMetricsByCourse(data, coursesMap);
            });
            sendResponse({ status: "ok" });
        })();
        return true;
    }

    if (message.type === "page_visible") {
        (async () => {
            const payload = message.payload || {};
            const timestamp = payload.timestamp || Date.now();
            if (typeof tabId === "number" && payload.course_id) {
                activeTabs.set(tabId, {
                    startTime: timestamp,
                    courseId: payload.course_id,
                    courseName: payload.course_name,
                    pageType: payload.page_type
                });
            }
            sendResponse({ status: "ok" });
        })();
        return true;
    }

    if (message.type === "identity") {
        (async () => {
            await queueStorageUpdate(async (data) => {
                const prev = data.student || {};
                const next = message.payload || {};
                // Merge so an identifier discovered on one page isn't lost on
                // the next page that happens not to expose it.
                data.student = {
                    moodle_user_id: next.moodle_user_id || prev.moodle_user_id || null,
                    student_id: next.student_id || prev.student_id || null,
                    full_name: next.full_name || prev.full_name || null,
                    email: next.email || prev.email || null,
                    program: next.program || prev.program || null,
                    enrollment_year: next.enrollment_year || prev.enrollment_year || null
                };
            });
            sendResponse({ status: "ok" });
        })();
        return true;
    }

    if (message.type === "grades") {
        (async () => {
            await queueStorageUpdate(async (data) => {
                mergeGrades(data, message.payload || []);
            });
            sendResponse({ status: "ok" });
        })();
        return true;
    }

    if (message.type === "materials") {
        (async () => {
            await queueStorageUpdate(async (data) => {
                mergeMaterials(data, message.payload || []);
            });
            sendResponse({ status: "ok" });
        })();
        return true;
    }

    if (message.type === "courses") {
        (async () => {
            await queueStorageUpdate(async (data) => {
                const coursesMap = toCourseMap(data.courses);
                (message.payload || []).forEach((course) => mergeCourse(data, coursesMap, course));
                syncMetricsByCourse(data, coursesMap);
            });
            sendResponse({ status: "ok" });
        })();
        return true;
    }

    if (message.type === "course_title_debug") {
        (async () => {
            await queueStorageUpdate(async (data) => {
                data._meta = data._meta || {};
                data._meta.courseTitleDebug = message.payload || [];
            });
            sendResponse({ status: "ok" });
        })();
        return true;
    }

    return false;
});

chrome.tabs.onRemoved.addListener((tabId) => {
    finalizeActiveTab(tabId, Date.now());
    pageViewsByTab.delete(tabId);
});
