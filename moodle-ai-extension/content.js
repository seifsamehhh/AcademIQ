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

    // --- Moodle identity extraction -----------------------------------------
    // These power the AcademIQ identity mapping (Moodle User ID is the primary
    // key, Student ID the secondary). All are best-effort and null-safe — the
    // fields appear when Moodle exposes them on the current page.

    // Moodle User ID: read from the *user menu* profile link only, so we never
    // pick up another user's id from forum posts / participant lists.
    const parseMoodleUserId = () => {
        const menuLink = document.querySelector(
            '.usermenu a[href*="/user/profile.php"], [data-region="user-menu"] a[href*="/user/profile.php"], #user-menu-toggle ~ * a[href*="/user/profile.php"], .userpicture'
        );
        const href = menuLink?.href || menuLink?.closest("a")?.href || "";
        const fromMenu = href.match(/[?&]id=(\d+)/)?.[1];
        if (fromMenu) return fromMenu;

        // Fallback: the logout link carries the current session's user context
        // in some themes; otherwise the body `data-userid`/`data-user-id`.
        const bodyUserId =
            document.body?.dataset?.userid || document.body?.dataset?.userId;
        return bodyUserId || null;
    };

    const parseFullName = () => {
        const candidates = [
            document.querySelector('[data-region="user-menu"] .usertext')?.textContent,
            document.querySelector(".usermenu .usertext")?.textContent,
            document.querySelector(".usermenu .userbutton")?.textContent,
            document.querySelector(".userpicture")?.getAttribute("title"),
            // On the profile page itself the heading is the user's name.
            (/\/user\/profile\.php/i.test(window.location.href)
                ? document.querySelector(".page-header-headings h1")?.textContent
                : null)
        ];
        const name = candidates.find((value) => cleanText(value));
        return cleanText(name);
    };

    // Full-string match (^…$) — NOT a substring scan. Moodle concatenates
    // adjacent elements without spaces in textContent (e.g.
    // "Hasaballah Studentkhaled@x.eduNotifications"), so a loose substring
    // regex captures the surrounding name/menu glue. We only ever accept text
    // that is *entirely* an email.
    const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
    const looksLikeEmail = (value) => {
        const v = (value || "").trim();
        return v.length > 0 && v.length <= 120 && EMAIL_RE.test(v);
    };

    const parseEmail = () => {
        // 1) mailto: links — the most reliable source (profile "Email address").
        for (const link of document.querySelectorAll('a[href^="mailto:" i]')) {
            const email = (link.getAttribute("href") || "")
                .replace(/^mailto:/i, "")
                .split("?")[0]
                .trim();
            if (looksLikeEmail(email)) return email.toLowerCase();
        }

        // 2) An email input value (edit-profile page).
        const inputVal = document.querySelector('input[type="email"], input[name="email"]')?.value;
        if (looksLikeEmail(inputVal)) return inputVal.trim().toLowerCase();

        // 3) A *leaf* node whose entire trimmed text is exactly an email — the
        //    exact match avoids capturing glued name/menu text around it.
        for (const node of document.querySelectorAll("dd, td, span, a, div, li, p")) {
            if (node.children.length === 0 && looksLikeEmail(node.textContent)) {
                return node.textContent.trim().toLowerCase();
            }
        }

        return null;
    };

    // Institutional Student ID = Moodle's "ID number" (idnumber) field, shown
    // on the user's profile under the user details list.
    const parseStudentIdNumber = () => {
        const labelNodes = document.querySelectorAll("dt, th, .profile-field-label, label");
        for (const node of labelNodes) {
            if (/id\s*number/i.test(node.textContent || "")) {
                const valueNode =
                    node.nextElementSibling ||
                    node.parentElement?.querySelector("dd, td, .profile-field-value");
                const value = cleanText(valueNode?.textContent);
                if (value) return value;
            }
        }
        return null;
    };

    const getStudentIdentity = () => {
        // Restore anything we discovered on earlier pages (the user menu isn't
        // present on every page), so identity stays consistent across a visit.
        let stored = {};
        try {
            stored = JSON.parse(localStorage.getItem(STORAGE_ID_KEY) || "{}") || {};
        } catch {
            stored = {};
        }

        const moodleUserId = parseMoodleUserId() || stored.moodle_user_id || null;
        const idNumber = parseStudentIdNumber() || stored.student_id || null;
        const fullName = parseFullName() || stored.full_name || null;
        const email = parseEmail() || stored.email || null;

        // Anonymous, per-browser fallback so payloads still dedupe to one
        // account when Moodle exposes no real identifier on any visited page.
        const anonId = stored.anon_id || generateHashedId();

        const profileText = document.querySelector(".page-header-headings")?.textContent || "";
        const programMatch = document.body.textContent?.match(/Program(?:me)?\s*:\s*([A-Za-z0-9\s&-]+)/i);
        const enrollmentMatch = document.body.textContent?.match(/Enrollment\s*Year\s*:\s*(\d{4})/i);
        const program =
            programMatch?.[1]?.trim() || stored.program ||
            (profileText.includes("Program") ? profileText.trim() : null);
        const enrollmentYear = enrollmentMatch?.[1] || stored.enrollment_year || null;

        const identity = {
            // Primary linkage keys for AcademIQ ↔ Moodle mapping.
            moodle_user_id: moodleUserId,
            // Prefer the real institutional ID; fall back to the anon id so the
            // backend can still uniquely key/dedupe the account.
            student_id: idNumber || anonId,
            full_name: fullName,
            email,
            program,
            enrollment_year: enrollmentYear,
            anon_id: anonId
        };

        localStorage.setItem(STORAGE_ID_KEY, JSON.stringify(identity));
        return identity;
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

    // Things that look like a course link but aren't a real enrolled course.
    const GENERIC_COURSE_NAMES = /^(my courses|home|dashboard|site home|my moodle|courses|site pages|profile)$/i;
    // Moodle's site front page is course id 1 — never a real course.
    const isRealCourseId = (id) => /^\d+$/.test(String(id || "")) && String(id) !== "1";

    const isBareCourseName = (name, courseId) => {
        const id = String(courseId || "").trim();
        const n = (name || "").trim();
        if (!n) return true;
        if (n === id || n === `Course ${id}`) return true;
        const cleaned = n.replace(/^course\s+/i, "").trim();
        if (cleaned === id || /^\d+$/.test(cleaned)) return true;
        return false;
    };

    const SECTION_GROUP_RE = /:\s*(General|Section|Topic|Group|Week\s*\d+)\s*$/i;
    const isSectionGroupName = (name) => SECTION_GROUP_RE.test((name || "").trim());

    const isTopLevelCourse = (name, courseId) => {
        if (!name || isSectionGroupName(name) || isBareCourseName(name, courseId)) return false;
        return true;
    };

    const pickBetterCourseName = (current, candidate, courseId) => {
        if (!candidate) return current;
        if (isBareCourseName(candidate, courseId)) return current;
        if (isBareCourseName(current, courseId)) return candidate;
        return candidate.length > (current || "").length ? candidate : current;
    };

    const extractCourseTitleFromAnchor = (anchor) => {
        const sources = [];
        const add = (value, source) => {
            const text = cleanText(value);
            if (text) sources.push({ text, source });
        };

        add(anchor.textContent, "anchor_text");
        add(anchor.getAttribute("aria-label"), "aria_label");
        add(anchor.getAttribute("title"), "title_attribute");
        add(anchor.querySelector("img")?.getAttribute("alt"), "image_alt");

        const card = anchor.closest(
            ".coursebox, .course-card, .myc-item, .card, .dashboard-card, .course-list-item, li, [data-courseid], [data-course-id]"
        );
        if (card) {
            const heading = card.querySelector(
                ".coursename, .course-title, .multiline, h3, h4, .card-title, .course-name, .coursefullname"
            );
            add(heading?.textContent, "course_card_heading");
            if (!cleanText(anchor.textContent)) {
                const cardText = cleanText(card.textContent);
                if (cardText && cardText.length <= 180) {
                    add(cardText, "course_card_text");
                }
            }
        }

        return sources;
    };

    const bestCourseTitleFromSources = (sources, courseId) => {
        for (const entry of sources) {
            const { text, source } = entry;
            if (!isBareCourseName(text, courseId) && !GENERIC_COURSE_NAMES.test(text)) {
                return { name: text, source };
            }
        }
        const fallback = sources.find(
            (entry) => entry.text && !GENERIC_COURSE_NAMES.test(entry.text)
        );
        return fallback
            ? { name: fallback.text, source: fallback.source }
            : { name: null, source: null };
    };

    const lookupCourseLinkById = (doc, courseId) => {
        const targetId = String(courseId);
        for (const anchor of doc.querySelectorAll('a[href*="/course/view.php?id="]')) {
            const href = anchor.getAttribute("href") || "";
            const id = href.match(/[?&]id=(\d+)/)?.[1];
            if (id === targetId) return anchor;
        }
        return null;
    };

    const resolveCourseNameFromDocument = (doc, courseId) => {
        const id = String(courseId);

        const pageHeading = cleanText(
            doc.querySelector(".page-header-headings h1")?.textContent ||
                doc.querySelector("#page-header h1")?.textContent ||
                doc.querySelector(".page-context-header h1")?.textContent ||
                doc.querySelector("h1")?.textContent
        );
        if (
            pageHeading &&
            !isBareCourseName(pageHeading, id) &&
            !GENERIC_COURSE_NAMES.test(pageHeading)
        ) {
            return { name: pageHeading, source: "page_heading" };
        }

        const anchor = lookupCourseLinkById(doc, id);
        if (anchor) {
            const resolved = bestCourseTitleFromSources(
                extractCourseTitleFromAnchor(anchor),
                id
            );
            if (resolved.name) {
                return { name: resolved.name, source: resolved.source || "course_link_lookup" };
            }
        }

        const dataEl = doc.querySelector(
            `[data-courseid="${id}"], [data-course-id="${id}"], [data-id="${id}"]`
        );
        if (dataEl) {
            const labelled = cleanText(
                dataEl.getAttribute("aria-label") || dataEl.getAttribute("title") || dataEl.textContent
            );
            if (labelled && !isBareCourseName(labelled, id) && !GENERIC_COURSE_NAMES.test(labelled)) {
                return { name: labelled, source: "data_courseid_element" };
            }
        }

        return { name: null, source: null };
    };

    const getCourseContext = () => {
        const courseId = parseCourseId(window.location.href);
        // Only treat actual course/activity pages as a course. The dashboard,
        // site home (id=1), profile, etc. must NOT be recorded as a course —
        // otherwise we get a bogus "My courses" (id 1) entry.
        const pageType = detectPageType();
        const onCoursePage =
            ["course", "assignment", "quiz", "grades", "resource"].includes(pageType) &&
            isRealCourseId(courseId);

        if (!onCoursePage) {
            return { course_id: null, course_name: null, course_name_source: null };
        }

        const resolved = resolveCourseNameFromDocument(document, courseId);
        const courseName = resolved.name || `Course ${courseId}`;
        return {
            course_id: courseId,
            course_name: courseName,
            course_name_source: resolved.source || (resolved.name ? "page_heading" : "fallback_id")
        };
    };

    const cleanText = (value) => value?.replace(/\s+/g, " ").trim() || null;

    const stableUrlHash = (seed) => {
        const s = String(seed || "").split("#")[0].toLowerCase();
        let hash = 0;
        for (let i = 0; i < s.length; i += 1) {
            hash = ((hash << 5) - hash + s.charCodeAt(i)) | 0;
        }
        return `url_${Math.abs(hash).toString(36)}`;
    };

    const parseMaterialId = (url, activity) => {
        const fromUrl = url?.match(/[?&](?:id|cmid)=([^&#]+)/i)?.[1];
        if (fromUrl) return fromUrl;
        const dataId = activity?.getAttribute("data-id") || activity?.id;
        if (dataId && /^\d+$/.test(String(dataId))) return String(dataId);
        if (url) return stableUrlHash(url);
        const title = cleanText(activity?.textContent || activity?.innerText || "");
        return stableUrlHash(title || "unknown");
    };

    const isEducationalLearningTitle = (title) =>
        /lecture|lec\s*#?\d|\blab\b|revision|review|summary|notes?|tutorial|handout|slides?|chapter|worksheet|problem\s*sheet|exercise\s*sheet/i.test(
            title || ""
        );

    const NESTED_DOWNLOAD_RE = /\.(pdf|pptx?|docx?|txt)(\?|$)/i;
    const PLUGINFILE_RE = /pluginfile\.php/i;

    const isUrlLikeFileType = (fileType) =>
        ["html", "link", "url", "page", "book"].includes(String(fileType || "").toLowerCase());

    const isDirectDownloadUrl = (url) =>
        Boolean(
            url &&
                (/\.(pdf|pptx?|docx?|txt)(\?|$)/i.test(url.split("?")[0]) || PLUGINFILE_RE.test(url))
        );

    const extractReadablePageText = (doc) => {
        const root =
            doc.querySelector("#region-main") ||
            doc.querySelector("[role='main']") ||
            doc.querySelector("#page-content") ||
            doc.querySelector(".no-overflow");
        if (!root) return null;
        const clone = root.cloneNode(true);
        clone
            .querySelectorAll("script, style, nav, .breadcrumb, .activity-header, .navbar, footer")
            .forEach((node) => node.remove());
        const text = cleanText(clone.textContent);
        return text && text.length >= 80 ? text : null;
    };

    const extractDownloadUrlFromHtml = (html, pageUrl, doc) => {
        const candidates = [];
        const pushCandidate = (raw) => {
            if (!raw) return;
            const href = resolveHref({ getAttribute: () => raw }, pageUrl) || raw;
            if (!href || /^javascript:/i.test(href) || /^#/i.test(href)) return;
            const path = href.split("?")[0];
            if (
                PLUGINFILE_RE.test(href) ||
                NESTED_DOWNLOAD_RE.test(path) ||
                /forcedownload=1/i.test(href)
            ) {
                candidates.push(href);
            }
        };

        const urlPatterns = [
            /https?:\/\/[^\s"'<>]+pluginfile\.php[^\s"'<>]*/gi,
            /\/pluginfile\.php[^\s"'<>]*/gi,
            /https?:\/\/[^\s"'<>]+\.(pdf|pptx?|docx?|txt)(?:\?[^\s"'<>]*)?/gi,
        ];
        for (const pattern of urlPatterns) {
            const matches = html.match(pattern) || [];
            for (const match of matches) {
                pushCandidate(match.replace(/&amp;/g, "&"));
            }
        }

        if (doc) {
            doc
                .querySelectorAll(
                    "iframe[src], embed[src], object[data], a[href*='pluginfile.php'], a[href*='forcedownload=1']"
                )
                .forEach((node) => {
                    const src = node.getAttribute("src") || node.getAttribute("data") || node.getAttribute("href");
                    pushCandidate(src);
                });
        }

        return candidates[0] || null;
    };

    const resolveEducationalActivityContent = async (activityUrl) => {
        if (!activityUrl) return { downloadUrl: null, pageText: null, pageUrl: null };
        try {
            const response = await fetch(activityUrl, {
                method: "GET",
                credentials: "include",
                redirect: "follow"
            });
            if (!response.ok) {
                return {
                    downloadUrl: null,
                    pageText: null,
                    pageUrl: null,
                    error: `http_${response.status}`
                };
            }
            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");
            const pageUrl = response.url || activityUrl;
            const anchorSelectors = [
                ".resourceworkaround a[href]",
                ".resourcecontent a[href]",
                ".fileuploadsubmission a[href]",
                "a.resource-wrapped-link[href]",
                "a[href*='pluginfile.php']",
                "a[href*='forcedownload=1']"
            ];
            const anchors = [];
            anchorSelectors.forEach((selector) => {
                doc.querySelectorAll(selector).forEach((node) => anchors.push(node));
            });
            if (!anchors.length) {
                anchors.push(...Array.from(doc.querySelectorAll("a[href]")));
            }
            let downloadUrl = extractDownloadUrlFromHtml(html, pageUrl, doc);
            if (!downloadUrl) {
                for (const anchor of anchors) {
                    const href = resolveHref(anchor, pageUrl);
                    if (!href) continue;
                    if (PLUGINFILE_RE.test(href) || NESTED_DOWNLOAD_RE.test(href.split("?")[0])) {
                        downloadUrl = href;
                        break;
                    }
                    if (/\/mod\/resource\//i.test(href) && !/\/mod\/resource\/view\.php/i.test(href)) {
                        downloadUrl = href;
                        break;
                    }
                }
            }
            const pageText = extractReadablePageText(doc);
            return {
                downloadUrl,
                pageText,
                pageUrl,
                error: downloadUrl ? null : "no_download_link_found_on_resource_page"
            };
        } catch (error) {
            return { downloadUrl: null, pageText: null, pageUrl: null, error: String(error) };
        }
    };

    const isMoodleActivityPageUrl = (url) =>
        /\/mod\/(resource|url|page|book|folder)\/view\.php/i.test(url || "");

    const resolveMoodleFileDownloadUrl = async (material) => {
        const activityUrl = material.url || material.source_url || "";
        let downloadUrl = material.resolvedUrl || material.resolved_url || activityUrl;
        let pageText = material.pageText || material.page_text || null;
        let resolveError = null;

        const needsResolve =
            isMoodleActivityPageUrl(activityUrl) ||
            isMoodleActivityPageUrl(downloadUrl) ||
            !downloadUrl ||
            (!isDirectDownloadUrl(downloadUrl) && !PLUGINFILE_RE.test(downloadUrl));

        if (needsResolve && activityUrl) {
            const resolved = await resolveEducationalActivityContent(activityUrl);
            resolveError = resolved.error || null;
            if (resolved.downloadUrl) {
                downloadUrl = resolved.downloadUrl;
                material.resolvedUrl = resolved.downloadUrl;
                material.resolved_url = resolved.downloadUrl;
                const nestedType = inferFileTypeFromUrl(resolved.downloadUrl);
                if (nestedType) {
                    material.file_type = nestedType;
                    material.fileType = nestedType;
                }
            }
            if (resolved.pageText) {
                pageText = resolved.pageText;
                material.pageText = resolved.pageText;
                material.page_text = resolved.pageText;
            }
        }

        if (
            downloadUrl &&
            (isMoodleActivityPageUrl(downloadUrl) || !isDirectDownloadUrl(downloadUrl))
        ) {
            const head = await fetchHeadMetadata(downloadUrl);
            if (head.finalUrl && (isDirectDownloadUrl(head.finalUrl) || PLUGINFILE_RE.test(head.finalUrl))) {
                downloadUrl = head.finalUrl;
                material.resolvedUrl = head.finalUrl;
                material.resolved_url = head.finalUrl;
            }
            const hintedType = mapMimeTypeToFileType(head.contentType);
            if (hintedType && QUIZ_DOWNLOAD_FILE_TYPES.has(hintedType)) {
                material.file_type = hintedType;
                material.fileType = hintedType;
            }
        }

        return { downloadUrl, pageText, resolveError };
    };

    const findNestedDownloadUrl = async (activityUrl, baseHref) => {
        const resolved = await resolveEducationalActivityContent(activityUrl);
        return resolved.downloadUrl;
    };

    const inferFileTypeFromUrl = (url) => {
        const path = (url || "").split("?")[0];
        const ext = path.match(/\.([a-z0-9]+)$/i)?.[1]?.toLowerCase();
        if (!ext || ext === "php") return null;
        if (ext === "ppt") return "pptx";
        if (ext === "doc") return "docx";
        return ext;
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

    // Resolve an anchor's href to an absolute URL. On the live page `link.href`
    // is already absolute; on a *fetched* (parsed) document it isn't, so we
    // resolve the raw attribute against the course page's URL.
    const resolveHref = (link, baseHref) => {
        const raw = link?.getAttribute("href");
        if (!raw) return null;
        try {
            return new URL(raw, baseHref).href;
        } catch {
            return link.href || null;
        }
    };

    // `doc`/`baseHref` default to the live page, but can be a fetched course
    // document so we can scrape courses that aren't the currently open tab.
    // Moodle activity/material links across versions: each course-content module
    // is a link to /mod/<type>/view.php. Matching these links directly is far
    // more robust than relying on the activity *container* CSS classes, which
    // differ between themes (Boost/Classic) and Moodle versions (3.x vs 4.x).
    const MOD_LINK_RE = /\/mod\/(resource|url|page|folder|book|lesson|scorm|assign|quiz)\//i;

    const extractMaterialsFromCourse = async (course, doc = document, baseHref = window.location.href) => {
        const materials = [];
        const seen = new Set();

        // Find module links, then resolve each one's surrounding activity item
        // (for section name, file-type icon, due date, etc.).
        const links = Array.from(doc.querySelectorAll("a[href]")).filter((anchor) =>
            MOD_LINK_RE.test(anchor.getAttribute("href") || "")
        );

        const collected = links.map(async (link) => {
            const activity =
                link.closest("li.activity, .activity-item, .activity, [data-for='cmitem']") ||
                link.parentElement ||
                link;
            const url = resolveHref(link, baseHref);
            if (!url) return null;
            const title = cleanText(
                activity.querySelector?.(".instancename")?.textContent ||
                link.textContent ||
                link.getAttribute("aria-label")
            );
            if (!title) return null;

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

            const isUrlLike = isUrlLikeFileType(fileType);
            let pageText = null;
            if (
                isEducationalLearningTitle(title) &&
                isUrlLike &&
                !PLUGINFILE_RE.test(url || "")
            ) {
                const resolved = await resolveEducationalActivityContent(url);
                if (resolved.downloadUrl) {
                    resolvedUrl = resolved.downloadUrl;
                    const nestedType = inferFileTypeFromUrl(resolved.downloadUrl);
                    if (nestedType) {
                        fileType = nestedType;
                    } else if (needsHeadProbe(resolved.downloadUrl, null)) {
                        const nestedHead = await fetchHeadMetadata(resolved.downloadUrl);
                        contentType = nestedHead.contentType || contentType;
                        contentDisposition = nestedHead.contentDisposition || contentDisposition;
                        filename = nestedHead.filename || filename;
                        resolvedUrl = nestedHead.finalUrl || resolved.downloadUrl;
                        fileType =
                            mapMimeTypeToFileType(contentType) ||
                            inferFileTypeFromUrl(resolvedUrl) ||
                            fileType;
                    }
                }
                if (resolved.pageText) {
                    pageText = resolved.pageText;
                }
            }

            const materialType = classifyMaterialType(activity, title, fileType, url);
            const downloadable = evaluateDownloadability(activity, materialType, resolvedUrl || url, contentDisposition);
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
                sourcePage: baseHref,
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
                pageText,
                page_text: pageText,
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

    const extractGradesFromTable = (courseId, doc = document) => {
        const grades = [];
        doc.querySelectorAll("table.user-grade tbody tr").forEach((row) => {
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

    // --- Scrape ALL enrolled courses (not only the currently open tab) -------
    // We fetch each course page (and its grade report) with the user's session
    // cookies, parse the HTML off-screen, and reuse the same extractors.
    const fetchDocument = async (url) => {
        const res = await fetch(url, { credentials: "include", redirect: "follow" });
        const html = await res.text();
        return new DOMParser().parseFromString(html, "text/html");
    };

    const getAllCourseLinks = (doc, origin) => {
        const map = new Map();
        doc.querySelectorAll('a[href*="/course/view.php?id="]').forEach((anchor) => {
            const href = anchor.getAttribute("href") || "";
            const id = href.match(/[?&]id=(\d+)/)?.[1];
            if (!isRealCourseId(id) || map.has(id)) return; // skip site home (1) + dups

            const resolved = bestCourseTitleFromSources(extractCourseTitleFromAnchor(anchor), id);
            if (resolved.name && GENERIC_COURSE_NAMES.test(resolved.name)) return;
            if (resolved.name && isSectionGroupName(resolved.name)) return;

            const existing = map.get(id);
            const courseName = pickBetterCourseName(
                existing?.course_name,
                resolved.name || `Course ${id}`,
                id
            );
            if (!isTopLevelCourse(courseName, id)) return;
            map.set(id, {
                course_id: id,
                course_name: courseName,
                course_name_source:
                    resolved.source ||
                    existing?.course_name_source ||
                    (resolved.name ? "anchor_text" : "fallback_id"),
                url: new URL(`/course/view.php?id=${id}`, origin).href
            });
        });
        return Array.from(map.values());
    };

    const scrapeAllCourses = async () => {
        const origin = window.location.origin;
        const titleDebug = [];

        // Discover every enrolled course from the "My courses" listing.
        let courses = [];
        let listingDoc = null;
        for (const path of ["/my/courses.php", "/my/"]) {
            try {
                listingDoc = await fetchDocument(new URL(path, origin).href);
                courses = getAllCourseLinks(listingDoc, origin);
                if (courses.length) break;
            } catch (_error) {
                /* try the next listing */
            }
        }
        // Fallback: course links present on the current page (nav menu, etc.).
        if (!courses.length) {
            listingDoc = document;
            courses = getAllCourseLinks(document, origin);
        }

        // Second pass: resolve bare titles from the listing DOM by course id.
        if (listingDoc) {
            courses = courses.map((course) => {
                const resolved = resolveCourseNameFromDocument(listingDoc, course.course_id);
                const courseName = pickBetterCourseName(
                    course.course_name,
                    resolved.name,
                    course.course_id
                );
                return {
                    ...course,
                    course_name: courseName,
                    course_name_source:
                        resolved.source || course.course_name_source || "listing_lookup"
                };
            });
        }

        let scraped = 0;
        for (const course of courses) {
            try {
                const courseDoc = await fetchDocument(course.url);
                const resolved = resolveCourseNameFromDocument(courseDoc, course.course_id);
                if (resolved.name) {
                    course.course_name = pickBetterCourseName(
                        course.course_name,
                        resolved.name,
                        course.course_id
                    );
                    course.course_name_source = resolved.source;
                }

                titleDebug.push({
                    course_id: course.course_id,
                    course_name: course.course_name,
                    course_name_source: course.course_name_source || "unknown"
                });

                const materials = await extractMaterialsFromCourse(course, courseDoc, course.url);
                if (materials.length) sendMessage("materials", materials);

                // Per-course grades from the user grade report (best-effort).
                try {
                    const gradeUrl = new URL(`/grade/report/user/index.php?id=${course.course_id}`, origin).href;
                    const gradeDoc = await fetchDocument(gradeUrl);
                    const grades = extractGradesFromTable(course.course_id, gradeDoc);
                    if (grades.length) sendMessage("grades", grades);
                } catch (_error) {
                    /* grades are optional */
                }

                scraped += 1;
            } catch (_error) {
                titleDebug.push({
                    course_id: course.course_id,
                    course_name: course.course_name,
                    course_name_source: course.course_name_source || "scrape_failed"
                });
                /* skip a course that fails to load, keep going */
            }
        }

        sendMessage("courses", courses.filter((course) => isTopLevelCourse(course.course_name, course.course_id)));
        sendMessage("course_title_debug", titleDebug);
        sendMessage("identity", getStudentIdentity());
        return { courses: courses.length, scraped };
    };

    const arrayBufferToBase64 = (buf) => {
        const bytes = new Uint8Array(buf);
        let binary = "";
        const chunk = 0x8000;
        for (let i = 0; i < bytes.length; i += chunk) {
            binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
        }
        return btoa(binary);
    };

    const QUIZ_DOWNLOAD_FILE_TYPES = new Set(["pdf", "pptx", "ppt", "docx", "doc", "txt", "text"]);

    const isDownloadableMaterial = (material) => {
        const ft = (material.file_type || material.fileType || "").toLowerCase();
        const url = material.resolvedUrl || material.resolved_url || material.url || "";
        if (QUIZ_DOWNLOAD_FILE_TYPES.has(ft)) return true;
        if (isDirectDownloadUrl(url)) return true;
        if (isEducationalLearningTitle(material.title || "")) {
            if (isUrlLikeFileType(ft) && (material.url || url)) return true;
            if ((material.pageText || material.page_text || "").length >= 80) return true;
        }
        return false;
    };

    const isQuizUploadableMaterial = isDownloadableMaterial;

    const fetchMaterialBytes = async (material, downloadUrlOverride = null) => {
        const url = downloadUrlOverride || material.resolvedUrl || material.resolved_url || material.url;
        if (!url) return { ok: false, error: "missing_url", download_attempted: true };
        try {
            const res = await fetch(url, { credentials: "include", redirect: "follow" });
            const contentType = res.headers.get("content-type") || "";
            if (!res.ok) {
                return {
                    ok: false,
                    error: `http_${res.status}`,
                    httpStatus: res.status,
                    contentType,
                    download_attempted: true
                };
            }
            if (
                /text\/html/i.test(contentType) &&
                !/pdf|powerpoint|presentation|octet-stream/i.test(contentType)
            ) {
                return {
                    ok: false,
                    error: `unexpected_content_type:${contentType}`,
                    httpStatus: res.status,
                    contentType,
                    download_attempted: true
                };
            }
            const buf = await res.arrayBuffer();
            if (!buf || buf.byteLength < 64) {
                return {
                    ok: false,
                    error: "empty_or_tiny_response",
                    httpStatus: res.status,
                    contentType,
                    download_attempted: true
                };
            }
            return {
                ok: true,
                base64: arrayBufferToBase64(buf),
                contentType,
                finalUrl: res.url || url,
                download_attempted: true
            };
        } catch (error) {
            return {
                ok: false,
                error: String(error),
                download_attempted: true
            };
        }
    };

    const buildUploadAuditRow = (material, fetched, backendResult, pageTextUsed = false) => {
        const sourceUrl = material.url || material.source_url || "";
        const resolvedUrl = material.resolvedUrl || material.resolved_url || "";
        const backend = backendResult || {};
        return {
            title: (material.title || "").slice(0, 55),
            file_type: material.file_type || material.fileType || "",
            source_url_present: Boolean(sourceUrl),
            resolved_url_present: Boolean(resolvedUrl),
            download_attempted: Boolean(fetched?.download_attempted || pageTextUsed),
            download_status: fetched?.ok
                ? "ok"
                : pageTextUsed
                    ? "page_text"
                    : fetched?.error || backend.extraction_error || "not_attempted",
            extracted_chars: backend.chars || 0,
            quiz_status: backend.quiz_status || backend.extraction_status || backend.status,
            reason: backend.extraction_error || backend.content_note || fetched?.error || null
        };
    };

    const normalizeUploadFailureReason = (reason) => {
        const value = String(reason || "").trim();
        if (value === "no_download_link_on_page") {
            return "no_download_link_found_on_resource_page";
        }
        return value;
    };

    const buildVerificationAuditRow = (row) => ({
        title: row.title,
        db_id: row.db_id,
        material_id: row.material_id,
        source_url: row.source_url,
        resolved_url: row.resolved_url,
        download_url_used: row.download_url_used || row.verification_audit?.download_url_used,
        attempted: row.attempted,
        backend_called: row.backend_called,
        verified_content_text_length: row.verified_content_text_length,
        verified_quiz_status: row.verified_quiz_status,
        verified_extraction_status: row.verified_extraction_status,
        reason: row.reason || row.error,
        verified_ok: row.verified_ok,
        verified_uploaded: row.verified_uploaded,
        verified_ready: row.verified_ready,
        verified_failed: row.verified_failed,
    });

    const TARGET_VERIFICATION_TITLES =
        /lecture\s*#?\s*2|lecture\s*#?\s*3|lecture\s*#?\s*4|lecture\s*#?\s*6|lecture\s*#?\s*7|lecture\s*#?\s*8|lab\s*#?\s*6|lecture2|lecture3|lecture4/i;

    const countVerifiedUploadResults = (results) => {
        const uploaded = results.filter((row) => row.verified_uploaded).length;
        const ready = results.filter((row) => row.verified_ready).length;
        const failed = results.filter(
            (row) => row.verified_failed || (row.attempted && !row.verified_ok)
        ).length;
        return { uploaded, ready, failed };
    };

    const finalizeUploadBackendResult = (basePayload, workingMaterial, fetched, res, data) => ({
        material_id: data.material_id || basePayload.material_id,
        title: data.title || basePayload.title,
        ok: Boolean(data.verified_ok),
        verified_ok: Boolean(data.verified_ok),
        verified_uploaded: Boolean(data.verified_uploaded),
        verified_ready: Boolean(data.verified_ready),
        verified_failed: Boolean(data.verified_failed),
        attempted: Boolean(data.attempted),
        backend_called: Boolean(data.backend_called),
        ...data,
        audit: buildUploadAuditRow(workingMaterial, fetched, data),
        identity_audit: data.identity_audit || null,
        verification_audit: data.verification_audit || buildVerificationAuditRow({
            title: data.title || basePayload.title,
            db_id: data.db_id || basePayload.db_id,
            material_id: data.material_id || basePayload.material_id,
            source_url: data.source_url || basePayload.source_url,
            resolved_url: data.resolved_url || basePayload.resolved_url,
            download_url_used: data.download_url_used,
            attempted: data.attempted,
            backend_called: data.backend_called,
            verified_content_text_length: data.verified_content_text_length,
            verified_quiz_status: data.verified_quiz_status,
            verified_extraction_status: data.verified_extraction_status,
            reason: data.reason,
            verified_ok: data.verified_ok,
            verified_uploaded: data.verified_uploaded,
            verified_ready: data.verified_ready,
            verified_failed: data.verified_failed,
        }),
    });

    const uploadMaterialToBackend = async (backendUploadUrl, material, identity) => {
        const basePayload = {
            course_id: material.course_id || material.courseId,
            course_name: material.course_name,
            material_id: material.material_id || material.id,
            matched_material_id:
                material.matched_material_id ||
                material.matchedMaterialId ||
                material.matched_db_material_id ||
                material.material_id ||
                material.id,
            db_id: material.db_id || material.dbId || material.matched_db_id || null,
            stable_material_key: material.stable_material_key || null,
            title: material.title,
            material_type: material.material_type || material.type,
            file_type: material.file_type || material.fileType,
            source_url: material.url,
            resolved_url: material.resolvedUrl || material.resolved_url || null,
            user_email: identity?.email || null
        };

        if (!basePayload.db_id) {
            return {
                material_id: basePayload.material_id,
                title: basePayload.title,
                ok: false,
                verified_ok: false,
                verified_uploaded: false,
                verified_ready: false,
                verified_failed: false,
                attempted: true,
                backend_called: false,
                error: "missing_db_id_from_preflight",
                reason: "missing_db_id_from_preflight",
                verification_audit: buildVerificationAuditRow({
                    title: basePayload.title,
                    db_id: null,
                    material_id: basePayload.material_id,
                    source_url: basePayload.source_url,
                    resolved_url: basePayload.resolved_url,
                    attempted: true,
                    backend_called: false,
                    reason: "missing_db_id_from_preflight",
                    verified_ok: false,
                }),
            };
        }

        const postUploadPayload = async (body) => {
            const res = await fetch(backendUploadUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            let data = {};
            try {
                data = await res.json();
            } catch (_error) {
                data = {};
            }
            return { res, data };
        };

        let workingMaterial = { ...material };
        const ft = String(workingMaterial.file_type || workingMaterial.fileType || "").toLowerCase();
        const educational = isEducationalLearningTitle(workingMaterial.title || "");
        const urlLike = isUrlLikeFileType(ft);

        const { downloadUrl, pageText: resolvedPageText, resolveError } = await resolveMoodleFileDownloadUrl(
            workingMaterial
        );
        if (resolvedPageText) {
            workingMaterial.pageText = resolvedPageText;
            workingMaterial.page_text = resolvedPageText;
        }

        const effectiveFt = String(
            workingMaterial.file_type || workingMaterial.fileType || ft
        ).toLowerCase();
        const canFetchFile =
            QUIZ_DOWNLOAD_FILE_TYPES.has(effectiveFt) ||
            isDirectDownloadUrl(downloadUrl) ||
            PLUGINFILE_RE.test(downloadUrl || "");

        let fetched = { ok: false, error: resolveError || "not_attempted", download_attempted: false };
        if (canFetchFile && downloadUrl) {
            fetched = await fetchMaterialBytes(workingMaterial, downloadUrl);
            if (fetched.ok) {
                const { res, data } = await postUploadPayload({
                    ...basePayload,
                    file_type: effectiveFt,
                    resolved_url: workingMaterial.resolvedUrl || workingMaterial.resolved_url || downloadUrl,
                    content_base64: fetched.base64,
                    content_type: fetched.contentType,
                    upload_audit: {
                        download_url_used: downloadUrl,
                        download_status: "ok",
                        was_attempted_by_extension: true,
                        was_in_extension_upload_queue: true,
                    },
                });
                const result = finalizeUploadBackendResult(
                    basePayload,
                    workingMaterial,
                    fetched,
                    res,
                    data
                );
                return result;
            }
        }

        const pageText = String(workingMaterial.pageText || workingMaterial.page_text || "").trim();
        if (pageText.length >= 80) {
            const { res, data } = await postUploadPayload({
                ...basePayload,
                file_type: urlLike ? "html" : effectiveFt,
                content_text: pageText,
                content_type: "text/html",
                upload_audit: {
                    download_url_used: downloadUrl || null,
                    download_status: "page_text",
                    was_attempted_by_extension: true,
                    was_in_extension_upload_queue: true,
                },
            });
            return finalizeUploadBackendResult(
                basePayload,
                workingMaterial,
                { ok: true, download_attempted: true },
                res,
                data
            );
        }

        const failureReason = normalizeUploadFailureReason(
            fetched.error ||
                resolveError ||
                (canFetchFile ? "download_or_page_text_failed" : "no_downloadable_file_or_page_text")
        );
        const { res, data } = await postUploadPayload({
            ...basePayload,
            upload_attempt_failed: true,
            extraction_error: failureReason,
            upload_audit: {
                download_url_used: downloadUrl || null,
                download_status: fetched?.error || resolveError || failureReason,
                was_attempted_by_extension: true,
                was_in_extension_upload_queue: true,
            },
        });
        return finalizeUploadBackendResult(
            basePayload,
            workingMaterial,
            fetched,
            res,
            {
                ...data,
                error: failureReason,
            }
        );
    };

    /**
     * Download and upload course materials.
     *
     * Preflight is now called from popup.js (chrome-extension:// origin) which
     * avoids CORS rejection.  The popup passes the pre-filtered list of
     * material IDs via `message.only_material_ids`.
     *
     * @param {string}        backendUploadUrl  Full URL to /materials/upload-for-quiz
     * @param {string}        courseId          Moodle course ID from the popup dropdown
     * @param {string[]|null} onlyMaterialIds   IDs approved for upload by popup's preflight.
     *                                          null = upload everything (no pre-filtering).
     * @param {object[]|null} preflightItems    Full preflight rows (URLs from DB when scrape misses).
     */
    const uploadMaterialsForQuiz = async (
        backendUploadUrl,
        courseId,
        onlyMaterialIds = null,
        preflightItems = null
    ) => {
        const course = getCourseContext();
        const tabCourseId = course.course_id;
        if (!tabCourseId) {
            return { status: "error", error: "Open a Moodle course page first." };
        }
        if (courseId && String(courseId) !== String(tabCourseId)) {
            return {
                status: "error",
                error:
                    `Course mismatch: dropdown selected ${courseId} but the active Moodle tab is ` +
                    `${tabCourseId} (${course.course_name || "unknown"}). ` +
                    "Open the matching Moodle course page or change the dropdown course.",
                requested_course_id: courseId,
                tab_course_id: tabCourseId,
                tab_course_name: course.course_name,
                backend_endpoint: backendUploadUrl
            };
        }

        // ── 1. Detect all materials on this course page ───────────────────────
        const allMaterials = await extractMaterialsFromCourse(course);
        if (allMaterials.length) {
            sendMessage("materials", allMaterials);
        }

        // ── Build upload queue (preflight-first when popup sent preflight rows) ──
        const cmidFromUrl = (url) => {
            const match = String(url || "").match(/[?&](?:id|cmid)=([^&#]+)/i);
            return match ? String(match[1]) : null;
        };

        const enrichFromPreflight = (material, pf) => {
            if (!pf) return material;
            return {
                ...material,
                material_id: pf.matched_db_material_id || pf.material_id || material.material_id,
                id: pf.matched_db_material_id || pf.material_id || material.id,
                db_id: pf.db_id || pf.matched_db_id || material.db_id,
                matched_material_id:
                    pf.matched_db_material_id || pf.material_id || material.matched_material_id,
                stable_material_key: pf.stable_material_key || material.stable_material_key,
                title: pf.title || pf.matched_db_title || material.title,
                url: pf.db_source_url || material.url,
                source_url: pf.db_source_url || material.source_url || material.url,
                resolvedUrl: pf.db_resolved_url || material.resolvedUrl,
                resolved_url: pf.db_resolved_url || material.resolved_url,
                file_type: pf.file_type || material.file_type || material.fileType,
                fileType: pf.file_type || material.fileType || material.file_type,
            };
        };

        let uploadable = [];
        const pfItems = Array.isArray(preflightItems) ? preflightItems : [];

        if (Array.isArray(onlyMaterialIds)) {
            if (onlyMaterialIds.length === 0) {
                return {
                    status: "done",
                    course_id: String(tabCourseId),
                    course_name: course.course_name,
                    backend_endpoint: backendUploadUrl,
                    detected: allMaterials.length,
                    uploaded: 0,
                    ready: 0,
                    failed: 0,
                    total: 0,
                    results: [],
                    retry_audit: [],
                };
            }

            const allowed = new Set(onlyMaterialIds.map(String));
            const scrapeByMid = new Map();
            const scrapeByCmid = new Map();
            for (const material of allMaterials) {
                const mid = String(material.material_id || material.id || "");
                if (mid) scrapeByMid.set(mid, material);
                const cmid = cmidFromUrl(material.url);
                if (cmid) scrapeByCmid.set(cmid, material);
            }

            const queuedIds = new Set();
            const addToQueue = (material) => {
                const mid = String(material.material_id || material.id || "");
                if (!mid || queuedIds.has(mid)) return;
                queuedIds.add(mid);
                uploadable.push(material);
            };

            if (pfItems.length > 0) {
                for (const item of pfItems) {
                    const mid = String(item.material_id || "");
                    if (!mid || !allowed.has(mid)) continue;
                    const scraped = scrapeByMid.get(mid) || scrapeByCmid.get(mid);
                    if (scraped) {
                        addToQueue(enrichFromPreflight(scraped, item));
                        continue;
                    }
                    const sourceUrl = item.db_source_url || item.source_url || null;
                    if (!sourceUrl) continue;
                    addToQueue({
                        material_id: item.matched_db_material_id || mid,
                        id: item.matched_db_material_id || mid,
                        title: item.title || "Untitled",
                        url: sourceUrl,
                        source_url: sourceUrl,
                        resolvedUrl: item.db_resolved_url || item.resolved_url || null,
                        resolved_url: item.db_resolved_url || item.resolved_url || null,
                        file_type: item.file_type || "unknown",
                        fileType: item.file_type || "unknown",
                        db_id: item.db_id || item.matched_db_id || null,
                        matched_material_id: item.matched_db_material_id || item.material_id || mid,
                        stable_material_key: item.stable_material_key || null,
                        course_id: tabCourseId,
                        courseId: tabCourseId,
                        course_name: course.course_name,
                    });
                }
            } else {
                const materialAllowed = (m) => {
                    const mid = String(m.material_id || m.id || "");
                    if (allowed.has(mid)) return true;
                    const cmid = cmidFromUrl(m.url);
                    return cmid && allowed.has(cmid);
                };
                uploadable = allMaterials.filter(isDownloadableMaterial).filter(materialAllowed);
            }
            console.log(
                `[AcademIQ] Upload: ${uploadable.length}/${allMaterials.length} materials after preflight filter`
            );
        } else {
            uploadable = allMaterials.filter(isDownloadableMaterial);
        }

        const identity = getStudentIdentity();

        // ── 2. Download + upload approved materials ───────────────────────────
        const results = [];
        for (const material of uploadable) {
            results.push(await uploadMaterialToBackend(backendUploadUrl, material, identity));
        }

        const { uploaded, ready, failed } = countVerifiedUploadResults(results);
        const retryAudit = results.map((row) => row.audit).filter(Boolean);
        const verificationAudit = results.map((row) => row.verification_audit).filter(Boolean);
        const targetTitles = /lecture\s*#?\d|lecture\d|lab\s*#?\d|\blab\b/i;
        const targetedAudit = verificationAudit.filter((row) =>
            TARGET_VERIFICATION_TITLES.test(row.title || "")
        );
        const failedOrUnchangedAudit = verificationAudit.filter(
            (row) =>
                !row.verified_ok ||
                row.verified_failed ||
                TARGET_VERIFICATION_TITLES.test(row.title || "")
        );

        return {
            status: "done",
            course_id: String(tabCourseId),
            course_name: course.course_name,
            backend_endpoint: backendUploadUrl,
            detected: allMaterials.length,
            uploaded,
            ready,
            failed,
            total: uploadable.length,
            results,
            retry_audit: retryAudit,
            targeted_retry_audit: targetedAudit,
            verification_audit: verificationAudit,
            failed_or_unchanged_audit: failedOrUnchangedAudit,
        };
    };

    // Allow the popup to trigger a full all-courses scan on demand.
    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
        if (message?.type === "scrape_all_courses") {
            scrapeAllCourses()
                .then((result) => sendResponse({ status: "done", ...result }))
                .catch((error) => sendResponse({ status: "error", error: String(error) }));
            return true;
        }
        if (message?.type === "scrape_current_course") {
            (async () => {
                const course = getCourseContext();
                if (!course.course_id) {
                    sendResponse({ status: "error", error: "Open a Moodle course page first." });
                    return;
                }
                const materials = await extractMaterialsFromCourse(course);
                if (materials.length) sendMessage("materials", materials);
                sendResponse({ status: "done", course, materials });
            })().catch((error) => sendResponse({ status: "error", error: String(error) }));
            return true;
        }
        if (message?.type === "upload_materials_for_quiz") {
            uploadMaterialsForQuiz(
                message.backendUploadUrl,
                message.courseId,
                message.only_material_ids || null,
                message.preflight_items || null
            )
                .then((result) => sendResponse(result))
                .catch((error) => sendResponse({ status: "error", error: String(error) }));
            return true;
        }
        return false;
    });

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
