// content.js - Moodle data extraction and event tracking
(() => {
    const STORAGE_ID_KEY = "moodle_student_id";

    if (window.__moodleAiExtensionInitialized) {
        return;
    }
    window.__moodleAiExtensionInitialized = true;

    const isMoodlePage = () => {
        if (!document?.body) return false;
        const metaGenerator = document.querySelector('meta[name="generator"]')?.getAttribute("content") || "";
        const bodyClass = document.body.className || "";
        const url = window.location.href;
        return (
            metaGenerator.toLowerCase().includes("moodle") ||
            bodyClass.includes("path-") ||
            url.includes("/course/view.php") ||
            url.includes("/mod/") ||
            url.includes("/my/") ||
            url.includes("/grade/report")
        );
    };

    if (!isMoodlePage()) {
        return;
    }

    const generateHashedId = () => `stu_${Math.random().toString(36).slice(2, 10)}`;

    const getStudentIdentity = () => {
        const storedId = localStorage.getItem(STORAGE_ID_KEY) || generateHashedId();
        localStorage.setItem(STORAGE_ID_KEY, storedId);

        const profileText = document.querySelector(".page-header-headings")?.textContent || "";
        const programMatch = document.body.textContent?.match(/Program(?:me)?\s*:\s*([A-Za-z0-9\s&-]+)/i);
        const enrollmentMatch = document.body.textContent?.match(/Enrollment\s*Year\s*:\s*(\d{4})/i);

        return {
            student_id: storedId,
            program: programMatch?.[1]?.trim() || (profileText.includes("Program") ? profileText.trim() : null),
            enrollment_year: enrollmentMatch?.[1] || null
        };
    };

    const detectPageType = () => {
        const url = window.location.href;
        if (url.includes("/my/") || url.includes("/my/index.php")) return "dashboard";
        if (url.includes("/course/view.php")) return "course";
        if (url.includes("/mod/assign/")) return "assignment";
        if (url.includes("/mod/quiz/")) return "quiz";
        if (url.includes("/grade/report/user")) return "grades";
        if (url.includes("/mod/resource/") || url.includes("/mod/page/") || url.includes("/mod/url/")) return "resource";
        return "resource";
    };

    const parseCourseId = (url) => {
        const match = url.match(/[?&]courseid=(\d+)/i) || url.match(/[?&]id=(\d+)/);
        if (match) return match[1];

        const bodyMatch = document.body.className.match(/\bcourse-(\d+)\b/);
        if (bodyMatch?.[1]) return bodyMatch[1];

        const linkCandidates = [
            ...document.querySelectorAll('a[href*="course/view.php?id="]'),
            ...document.querySelectorAll('a[href*="/course/edit.php?id="]')
        ];
        for (const candidate of linkCandidates) {
            const linkMatch = candidate.href.match(/[?&]id=(\d+)/);
            if (linkMatch?.[1]) return linkMatch[1];
        }

        const pageCourseId = document.body?.dataset?.courseid || document.documentElement?.dataset?.courseid;
        return pageCourseId || null;
    };

    const getCourseContext = () => {
        const url = window.location.href;
        const courseId = parseCourseId(url);
        const courseName =
            document.querySelector("h1")?.textContent?.trim() ||
            document.querySelector(".page-header-headings h1")?.textContent?.trim() ||
            document.querySelector('a[href*="course/view.php"]')?.textContent?.trim();
        return {
            course_id: courseId,
            course_name: courseName || "Unknown Course"
        };
    };

    const cleanText = (value) => value?.replace(/\s+/g, " ").trim() || null;

    const parseMaterialId = (url, activity) => {
        const fromUrl = url?.match(/[?&](?:id|cmid)=([^&#]+)/i)?.[1];
        if (fromUrl) return fromUrl;
        return activity?.getAttribute("data-id") || activity?.id || `material_${Math.random().toString(36).slice(2, 9)}`;
    };

    const MIME_TYPE_MAP = [
        { pattern: /application\/pdf/i, fileType: "pdf" },
        { pattern: /presentation|powerpoint|vnd\.ms-powerpoint/i, fileType: "pptx" },
        { pattern: /wordprocessingml|msword/i, fileType: "docx" },
        { pattern: /spreadsheetml|vnd\.ms-excel/i, fileType: "xlsx" },
        { pattern: /zip|compressed/i, fileType: "zip" },
        { pattern: /text\/plain/i, fileType: "txt" },
        { pattern: /text\/html/i, fileType: "html" }
    ];

    const mapMimeTypeToFileType = (contentType) => {
        if (!contentType) return null;
        const match = MIME_TYPE_MAP.find((item) => item.pattern.test(contentType));
        return match?.fileType || null;
    };

    const parseFileTypeFromDom = (activity, title, url) => {
        const icon = activity?.querySelector("img.activityicon");
        const iconSrc = icon?.getAttribute("src") || "";
        const iconAlt = icon?.getAttribute("alt") || "";
        const dataType = activity?.getAttribute("data-filetype") || "";
        const fileTypeClass = Array.from(activity?.classList || []).find((c) => c.startsWith("filetype-")) || "";
        const fileTypeFromClass = fileTypeClass.replace("filetype-", "");
        const hint = `${iconSrc} ${iconAlt} ${dataType} ${fileTypeFromClass} ${title || ""} ${url || ""}`.toLowerCase();

        if (hint.includes("pdf")) return "pdf";
        if (hint.includes("powerpoint") || hint.includes("ppt")) return "pptx";
        if (hint.includes("word") || hint.includes("doc")) return "docx";
        if (hint.includes("excel") || hint.includes("xlsx") || hint.includes("spreadsheet")) return "xlsx";
        if (hint.includes("link") || hint.includes("url") || hint.includes("external")) return "link";
        if (hint.includes("folder")) return "folder";
        if (hint.includes("book") || hint.includes("page")) return "html";
        return null;
    };

    const needsHeadProbe = (url, fileType) => Boolean(url && !fileType && (/pluginfile\.php/i.test(url) || /\/mod\/resource\//i.test(url)));

    // Moodle often serves files via pluginfile.php without a reliable extension, so HEAD is used as a fallback.
    const fetchHeadMetadata = async (url) => {
        if (!url) return {};
        try {
            const response = await fetch(url, {
                method: "HEAD",
                credentials: "include",
                redirect: "follow"
            });
            const contentType = response.headers.get("content-type") || "";
            const disposition = response.headers.get("content-disposition") || "";
            const filenameMatch = disposition.match(/filename\*?=(?:UTF-8''|\")?([^\";]+)/i);
            const filename = filenameMatch?.[1] ? decodeURIComponent(filenameMatch[1].replace(/"/g, "").trim()) : null;
            return {
                contentType,
                contentDisposition: disposition,
                filename,
                finalUrl: response.url || url
            };
        } catch (_error) {
            return {};
        }
    };

    const classifyMaterialType = (activity, title, fileType, url) => {
        const classList = activity?.className || "";
        const text = `${title || ""} ${url || ""}`.toLowerCase();

        if (classList.includes("folder") || text.includes("lab") || text.includes("tutorial") || text.includes("practical")) return "lab";
        if (classList.includes("resource") || classList.includes("page") || text.includes("lecture") || fileType === "pdf") return "lecture";
        if (classList.includes("url") || fileType === "link" || text.includes("resource")) return "resource";
        return "unknown";
    };

    const parseSectionName = (activity) => {
        const section = activity?.closest("li.section, .course-section, .topics .section, section.course-section");
        const heading = section?.querySelector(".sectionname, h3.sectionname, .section-title, .course-section-header h3");
        return cleanText(heading?.textContent) || "General";
    };

    const parseAvailabilityStatus = (activity) => {
        const availability = cleanText(activity?.querySelector(".availabilityinfo")?.textContent);
        if (availability) return availability;

        const restricted = activity?.classList.contains("dimmed") || activity?.classList.contains("hidden") || activity?.classList.contains("stealth");
        return restricted ? "restricted" : "available";
    };

    const parseDueDate = (activity) => {
        const explicitDate = cleanText(activity?.querySelector(".activitydate")?.textContent);
        if (explicitDate) return explicitDate;

        const text = cleanText(activity?.textContent);
        const dueMatch = text?.match(/(?:due\s*(?:date|on)?\s*:?\s*)([^\n|]+)/i);
        return dueMatch?.[1]?.trim() || null;
    };

    const parseFileSize = (activity) => {
        const text = cleanText(activity?.textContent) || "";
        const sizeMatch = text.match(/\b(\d+(?:\.\d+)?)\s?(KB|MB|GB)\b/i);
        return sizeMatch ? `${sizeMatch[1]} ${sizeMatch[2].toUpperCase()}` : null;
    };

    const inferSemanticTags = ({ title, sectionName, materialType }) => {
        const source = `${title || ""} ${sectionName || ""} ${materialType || ""}`.toLowerCase();
        const tags = new Set();

        if (/lecture|slides|week\s*\d+|topic/i.test(source)) tags.add("lecture");
        if (/revision|review|summary|recap|past\s*paper/i.test(source)) tags.add("revision");
        if (/exam|midterm|final|test|mock/i.test(source)) tags.add("exam");
        if (/quiz|mcq/i.test(source) || materialType === "quiz") tags.add("quiz");
        if (/lab|practical|workshop|exercise|practice|tutorial/i.test(source) || materialType === "lab") tags.add("practice");
        if (/assignment|coursework|submission/i.test(source) || materialType === "assignment") tags.add("assignment");

        if (tags.size === 0) {
            tags.add(materialType === "link" ? "reference" : "general");
        }

        return Array.from(tags);
    };

    const evaluateDownloadability = (activity, materialType, url, contentDisposition) => {
        const classList = activity?.className || "";
        const isMoodleResource = classList.includes("modtype_resource") || classList.includes("resource");
        const isResourceType = ["pdf", "lecture", "lab", "document"].includes(materialType);
        return Boolean(
            isMoodleResource ||
                isResourceType ||
                /\/mod\/resource\//i.test(url || "") ||
                /pluginfile\.php/i.test(url || "") ||
                /attachment/i.test(contentDisposition || "")
        );
    };

    const extractMaterialsFromCourse = async (course) => {
        const materials = [];
        const seen = new Set();
        const activities = document.querySelectorAll(".activity, li.activity, .modtype_resource, .course-section .activity-item");

        const collected = Array.from(activities).map(async (activity) => {
            const link = activity.querySelector("a.aalink, .activityname a, a[href]");
            const title = cleanText(activity.querySelector(".instancename")?.textContent || link?.textContent);
            const url = link?.href;
            if (!title || !url) return null;

            const materialId = parseMaterialId(url, activity);
            let fileType = parseFileTypeFromDom(activity, title, url);
            let contentType = null;
            let contentDisposition = null;
            let filename = null;
            let resolvedUrl = url;

            if (needsHeadProbe(url, fileType)) {
                const headMetadata = await fetchHeadMetadata(url);
                contentType = headMetadata.contentType || null;
                contentDisposition = headMetadata.contentDisposition || null;
                filename = headMetadata.filename || null;
                resolvedUrl = headMetadata.finalUrl || url;
                fileType = fileType || mapMimeTypeToFileType(contentType) || null;
            }

            if (!fileType) {
                const pathExtension = (url.split("?")[0].match(/\.([a-z0-9]+)$/i)?.[1] || "").toLowerCase();
                fileType = pathExtension && pathExtension !== "php" ? pathExtension : "html";
            }

            const materialType = classifyMaterialType(activity, title, fileType, url);
            const downloadable = evaluateDownloadability(activity, materialType, url, contentDisposition);
            const dedupeKey = `${course.course_id || "unknown"}-${materialId}-${url}`;

            if (seen.has(dedupeKey)) return null;
            seen.add(dedupeKey);

            return {
                id: materialId,
                courseId: course.course_id,
                title,
                type: materialType,
                url,
                fileType: fileType || "unknown",
                sourcePage: window.location.href,
                course_id: course.course_id,
                course_name: course.course_name,
                section_name: parseSectionName(activity),
                material_id: materialId,
                material_type: materialType,
                file_type: fileType,
                file_size: parseFileSize(activity),
                downloadable,
                original_filename: filename,
                content_type: contentType,
                resolvedUrl,
                due_date: parseDueDate(activity),
                availability_status: parseAvailabilityStatus(activity),
                semantic_tags: inferSemanticTags({ title, sectionName: parseSectionName(activity), materialType }),
                extracted_at: new Date().toISOString()
            };
        });

        const resolved = await Promise.all(collected);
        resolved.filter(Boolean).forEach((item) => materials.push(item));

        return materials;
    };

    const extractGradesFromTable = (courseId) => {
        const grades = [];
        document.querySelectorAll("table.user-grade tbody tr").forEach((row) => {
            const itemName = cleanText(row.querySelector("th.column-itemname")?.textContent);
            const gradeText = cleanText(row.querySelector("td.column-grade")?.textContent);
            const rangeText = cleanText(row.querySelector("td.column-range")?.textContent);
            if (!itemName || !gradeText) return;

            const [gradeValue] = gradeText.split("/");
            const maxGrade = rangeText?.split("/")[1] || rangeText;
            const gradeNumber = parseFloat(gradeValue);
            const maxNumber = parseFloat(maxGrade);
            const percentage =
                Number.isFinite(gradeNumber) && Number.isFinite(maxNumber) && maxNumber > 0
                    ? Math.round((gradeNumber / maxNumber) * 100)
                    : null;

            grades.push({
                course_id: courseId,
                item_name: itemName,
                item_type: itemName.toLowerCase().includes("quiz") ? "quiz" : "assignment",
                grade: gradeText,
                max_grade: rangeText,
                percentage,
                submission_status: cleanText(row.querySelector("td.column-status")?.textContent),
                submission_time: cleanText(row.querySelector("td.column-lastaccess")?.textContent)
            });
        });
        return grades;
    };

    const extractAssignmentDetails = (courseId) => {
        const title = cleanText(document.querySelector("h1")?.textContent);
        const status = cleanText(document.querySelector(".submissionstatustable")?.textContent);
        const grade = cleanText(document.querySelector(".gradingtable .grade")?.textContent);
        return title
            ? [
                  {
                      course_id: courseId,
                      item_name: title,
                      item_type: "assignment",
                      grade,
                      max_grade: null,
                      percentage: null,
                      submission_status: status,
                      submission_time: null
                  }
              ]
            : [];
    };

    const extractQuizDetails = (courseId) => {
        const title = cleanText(document.querySelector("h1")?.textContent);
        const gradeSummary = cleanText(document.querySelector(".quizgradefeedback")?.textContent);
        const gradeInfo = cleanText(document.querySelector(".quizinfo")?.textContent);
        return title
            ? [
                  {
                      course_id: courseId,
                      item_name: title,
                      item_type: "quiz",
                      grade: gradeSummary,
                      max_grade: gradeInfo,
                      percentage: null,
                      submission_status: null,
                      submission_time: null
                  }
              ]
            : [];
    };

    const sendMessage = (type, payload) => {
        chrome.runtime.sendMessage({ type, payload }, () => {});
    };

    const getNavigationType = () => {
        const nav = performance.getEntriesByType("navigation")[0];
        return nav?.type || "navigate";
    };

    const getPageSignals = () => {
        const url = window.location.href;
        const pageText = `${document.body?.innerText || ""} ${url}`.toLowerCase();
        const isAssignmentSubmission =
            /\/mod\/assign\/view\.php/i.test(url) &&
            (/submitted for grading|submission status|submission statement|submitted/i.test(pageText) ||
                document.querySelector('form[action*="assign"] button[name="submitbutton"]'));

        const isQuizAttempt =
            /\/mod\/quiz\/(attempt|review|summary|view)\.php/i.test(url) &&
            (/attempt|review|finished|quiz navigation|state: finished/i.test(pageText) ||
                document.querySelector(".quizattempt, .quizsummaryofattempt, .qn_buttons"));

        return {
            assignment_submission: Boolean(isAssignmentSubmission),
            quiz_attempt: Boolean(isQuizAttempt)
        };
    };

    const sendPageView = (pageType, course) => {
        const navType = getNavigationType();
        sendMessage("page_view", {
            page_type: pageType,
            course_id: course.course_id,
            course_name: course.course_name,
            url: window.location.href,
            navigation_type: navType,
            ...getPageSignals(),
            timestamp: Date.now()
        });
    };

    const handleScrape = async () => {
        const pageType = detectPageType();
        const course = getCourseContext();

        sendMessage("identity", getStudentIdentity());
        sendPageView(pageType, course);

        if (pageType === "course") {
            const materials = await extractMaterialsFromCourse(course);
            if (materials.length) {
                sendMessage("materials", materials);
            }
        }

        if (pageType === "grades") {
            const grades = extractGradesFromTable(course.course_id);
            if (grades.length) {
                sendMessage("grades", grades);
            }
        }

        if (pageType === "assignment") {
            const grades = extractAssignmentDetails(course.course_id);
            if (grades.length) {
                sendMessage("grades", grades);
            }
        }

        if (pageType === "quiz") {
            const grades = extractQuizDetails(course.course_id);
            if (grades.length) {
                sendMessage("grades", grades);
            }
        }
    };

    const classifyClickAction = (target) => {
        const link = target.closest("a");
        if (!link) return "click";

        const href = link.href || "";
        if (/\/mod\/resource\//i.test(href) || /pluginfile\.php/i.test(href) || /\/mod\/(page|url)\//i.test(href)) {
            return "material_click";
        }
        if (/\/mod\/assign\//i.test(href)) {
            return "assignment_view";
        }
        if (/\/mod\/quiz\//i.test(href)) {
            return "quiz_view";
        }
        return "click";
    };

    document.addEventListener(
        "click",
        (event) => {
            const pageType = detectPageType();
            const course = getCourseContext();
            const action = classifyClickAction(event.target);
            sendMessage("interaction", {
                page_type: pageType,
                course_id: course.course_id,
                action_type: action,
                url: window.location.href,
                timestamp: Date.now()
            });
        },
        { passive: true }
    );

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") {
            sendMessage("page_hidden", { timestamp: Date.now() });
        } else if (document.visibilityState === "visible") {
            const course = getCourseContext();
            sendMessage("page_visible", {
                course_id: course.course_id,
                course_name: course.course_name,
                page_type: detectPageType(),
                timestamp: Date.now()
            });
        }
    });

    window.addEventListener("beforeunload", () => {
        sendMessage("page_hidden", { timestamp: Date.now() });
    });

    const bootstrap = () => {
        handleScrape();
        setTimeout(handleScrape, 1200);
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bootstrap, { once: true });
    } else {
        bootstrap();
    }
})();
