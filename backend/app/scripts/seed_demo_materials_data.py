"""
Structured demo lecture content for Quiz Generation.

Course IDs 103–105 store materials for both demo tracks (student1 CV/AI/SE and
student2 Web/DS/ML) because materials are keyed globally by course_id. Each
material uses a distinct material_id so both personas can pick topic-relevant
lectures during a presentation.
"""

from __future__ import annotations

import re


def _quiz_review_line(term: str, definition: str) -> str:
    """Format a short definition sentence the lightweight quiz engine can parse."""
    definition = definition.strip().rstrip(".")
    if re.match(r"^(a|an|the)\s", definition, re.IGNORECASE):
        return f"{term} is {definition}."
    article = "an" if definition[:1].lower() in "aeiou" else "a"
    return f"{term} is {article} {definition}."


def _lecture(title: str, course_name: str, sections: list[tuple[str, list[str]]]) -> str:
    lines = [f"{title} — {course_name} (Seeded Demo Lecture)", ""]
    quiz_review: list[str] = []

    for heading, paragraphs in sections:
        lines.append(heading)
        lines.append("")
        for paragraph in paragraphs:
            lines.append(paragraph)
            lines.append("")
            if heading == "Definitions":
                stripped = paragraph.strip().rstrip(".")
                if " is " in stripped.lower():
                    quiz_review.append(stripped + ".")
                else:
                    match = re.match(
                        r"^(?:A|An|The)\s+(.+?)\s+(checks|verifies|executes|captures|evaluates|stores|removes|adds|modifies|retrieves|translates|writes|groups|partitions|traces|speeds|requires|links|means|combines|halts|updates|trains|predicts|measures)\s+(.+)$",
                        stripped,
                        re.IGNORECASE,
                    )
                    if match:
                        term = match.group(1)
                        verb = match.group(2).lower()
                        rest = match.group(3)
                        quiz_review.append(
                            _quiz_review_line(
                                term,
                                f"process that {verb} {rest}",
                            )
                        )
            elif heading == "Key Concepts":
                stripped = paragraph.strip().rstrip(".")
                match = re.match(
                    r"^([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,4})\s+"
                    r"(groups|stores|allows|uses|converts|speeds|requires|links|partitions|traces|"
                    r"halts|updates|combines|controls|defines|creates|adds|removes|modifies|"
                    r"retrieves|executes|verifies|evaluates|captures|trains|predicts|measures|"
                    r"records|maps|assigns|detects|prevents|enforces|extends|shrinks|expands|"
                    r"fills|closes|isolates|processes|applies|builds|selects|compares|pairs|"
                    r"orders|sorts|filters|joins|reduces|eliminates|separates|inserts|queries|"
                    r"arranges|connects|traverses|visits|explores|estimates|restricts|penalizes|"
                    r"normalizes|partitions|schedules|validates|persists|serves|loads|renders|"
                    r"targets|resolves|determines|describes|models|organizes|partitions)\s+(.+)$",
                    stripped,
                )
                if match:
                    term = match.group(1)
                    verb = match.group(2).lower()
                    rest = match.group(3)
                    quiz_review.append(
                        _quiz_review_line(term, f"concept that {verb} {rest}")
                    )

    if quiz_review:
        lines.extend(["Quiz Review", ""])
        lines.extend(quiz_review)

    return "\n".join(lines).strip()


# Legacy demo material IDs replaced by the entries below (removed on re-seed).
DEPRECATED_DEMO_MATERIAL_IDS = [
    ("101", "prog_lec1"),
    ("102", "db_lec1"),
]


def _programming_materials() -> list[dict]:
    return [
        {
            "course_id": "101",
            "material_id": "prog_intro",
            "title": "Introduction to Programming",
            "file_type": "pdf",
            "course_name": "Programming",
            "content": _lecture(
                "Introduction to Programming",
                "Programming",
                [
                    (
                        "Definitions",
                        [
                            "Programming is the disciplined process of writing precise instructions that a computer executes in order.",
                            "A Program is a complete set of those instructions saved as source code in a file.",
                            "A Programming Language is a formal notation with syntax rules that humans use to express algorithms.",
                            "An Algorithm is a step-by-step procedure that solves a problem and terminates after a finite number of steps.",
                            "Software Development is the broader activity of designing, building, testing, and maintaining programs.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Source Code is human-readable text that must be translated before the machine can run it.",
                            "Compilation converts entire programs into machine code ahead of execution.",
                            "Interpretation executes source code line by line through a runtime engine.",
                            "A Syntax Error is a grammar mistake that prevents the program from starting.",
                            "A Logic Error is a mistake in reasoning that produces incorrect output even when syntax is valid.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "A hello-world program prints a greeting to the console using a single output statement.",
                            "A grade calculator reads a numeric score and prints pass when the score is at least 60.",
                            "A registration script validates that an email contains an at-sign before saving a student record.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Compiled languages such as C++ optimize runtime speed but require a build step before testing.",
                            "Interpreted languages such as Python shorten the edit-run cycle but may run slower on large workloads.",
                            "Low-level languages expose hardware details, while high-level languages emphasize readability and productivity.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Programming combines algorithms, languages, and tools to automate tasks.",
                            "Developers must understand syntax, logic, and the difference between compile-time and runtime errors.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "101",
            "material_id": "prog_variables",
            "title": "Variables and Data Types",
            "file_type": "pdf",
            "course_name": "Programming",
            "content": _lecture(
                "Variables and Data Types",
                "Programming",
                [
                    (
                        "Definitions",
                        [
                            "A Variable is a named storage location that holds a value while a program runs.",
                            "A Data Type is a classification that tells the computer what kind of value a variable stores.",
                            "An Integer is a whole number without a fractional part.",
                            "A Floating Point Number is a numeric value that includes decimal digits.",
                            "A String is an ordered sequence of text characters enclosed in quotes.",
                            "A Boolean is a data type that stores only true or false.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Variable Names should be descriptive so other developers can read the code easily.",
                            "Type Inference allows some languages to choose a data type automatically from an initial value.",
                            "Type Casting converts a value from one data type to another when the conversion is safe.",
                            "Constants are variables whose values must not change after initialization.",
                            "Mutability describes whether a variable's value can be replaced after creation.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "An age variable might store the integer 20 for a university student.",
                            "A gradeAverage variable might store the floating point number 87.5.",
                            "A courseName variable might store the string Programming.",
                            "An isEnrolled variable might store the boolean true when registration is active.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Static typing checks data types at compile time, while dynamic typing checks them at runtime.",
                            "Strong typing rejects implicit unsafe conversions, while weak typing may allow silent coercion.",
                            "Primitive types store simple values directly, while reference types store addresses to larger objects.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Variables name memory locations and data types define what operations are legal on each value.",
                            "Choosing clear names and appropriate types prevents many runtime bugs in introductory programs.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "101",
            "material_id": "prog_loops",
            "title": "Loops and Functions",
            "file_type": "pdf",
            "course_name": "Programming",
            "content": _lecture(
                "Loops and Functions",
                "Programming",
                [
                    (
                        "Definitions",
                        [
                            "A Loop is a control structure that repeats a block of code multiple times.",
                            "A For Loop is used when the number of iterations is known in advance.",
                            "A While Loop repeats code as long as a condition remains true.",
                            "A Function is a reusable block of code that performs a specific task.",
                            "A Parameter is an input value passed into a function when it is called.",
                            "A Return Value is the output a function sends back to the caller.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Loop Iteration means each execution of the loop body.",
                            "An Infinite Loop occurs when the exit condition never becomes false.",
                            "Modular Design divides a program into small functions that each solve one problem.",
                            "Recursion is a technique where a function calls itself on a smaller subproblem.",
                            "Scope determines which variables are visible inside a function versus the global program.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "A for loop can print the numbers 1 through 10 for a attendance counter.",
                            "A while loop can keep reading user input until the user types quit.",
                            "A calculateAverage function accepts a list of scores and returns the mean as a float.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "For loops are ideal for indexed traversal, while while loops fit unknown iteration counts.",
                            "Iterative solutions use explicit loops, while recursive solutions rely on function call stacks.",
                            "Pure functions always return the same output for the same input and avoid side effects.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Loops eliminate duplicated code and functions organize logic into testable units.",
                            "Together they form the backbone of structured programming in every major language.",
                        ],
                    ),
                ],
            ),
        },
    ]


def _database_materials() -> list[dict]:
    return [
        {
            "course_id": "102",
            "material_id": "db_fundamentals",
            "title": "Database Fundamentals",
            "file_type": "pdf",
            "course_name": "Database",
            "content": _lecture(
                "Database Fundamentals",
                "Database",
                [
                    (
                        "Definitions",
                        [
                            "A Database is an organized collection of structured data stored electronically.",
                            "A Database Management System is software that creates, reads, updates, and deletes data safely.",
                            "A Relational Database organizes information into related tables linked by keys.",
                            "A Table is a two-dimensional structure that stores records about one entity type.",
                            "A Row is a single record in a table representing one instance such as one student.",
                            "A Column is a field definition that stores one attribute such as student email.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Database Design models real-world entities so applications can query them efficiently.",
                            "A Table Schema is the set of column names and data types for a table.",
                            "Data Integrity ensures stored values remain accurate and consistent over time.",
                            "Concurrency Control allows multiple users to access data without corrupting each other's work.",
                            "Backup and Recovery protect against hardware failure and accidental deletion.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "A Students table might contain rows for Alice, Bob, and Carol with columns student_id and full_name.",
                            "A Courses table might store course_id, title, and credit_hours for every offering.",
                            "An Enrollments table links students to courses using foreign keys.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "A Spreadsheet suits small datasets but lacks strict integrity rules for multi-user access.",
                            "A Relational Database enforces schemas, constraints, and transactional safety at scale.",
                            "A Flat File stores records sequentially without a declarative query language.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Relational databases use tables, rows, and columns to represent structured information.",
                            "DBMS software is essential for secure, concurrent, and recoverable data storage.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "102",
            "material_id": "db_sql",
            "title": "SQL Basics",
            "file_type": "pdf",
            "course_name": "Database",
            "content": _lecture(
                "SQL Basics",
                "Database",
                [
                    (
                        "Definitions",
                        [
                            "SQL is the standard language for querying and manipulating relational databases.",
                            "A Select Statement retrieves rows and columns from one or more tables.",
                            "An Insert Statement adds new rows into a table.",
                            "An Update Statement modifies existing values in one or more columns.",
                            "A Delete Statement removes rows that match a condition.",
                            "A Where Clause filters rows based on logical conditions.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Projection chooses which columns appear in the result set.",
                            "Selection filters which rows satisfy a predicate expression.",
                            "An Order By Clause sorts results ascending or descending by one or more columns.",
                            "Aggregate Functions such as count, sum, and average summarize groups of rows.",
                            "A Group By Clause partitions rows before applying aggregates.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "Select star from students where enrollment_year equals 2024 returns all first-year students.",
                            "Insert into students values 1001, Dana, 2024 adds a new student record.",
                            "Update students set full_name equals Dana Smith where student_id equals 1001 changes a name.",
                            "Delete from students where student_id equals 1001 removes a row permanently.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "DDL statements such as create table define structure, while DML statements such as insert modify data.",
                            "Inner joins return matching pairs, while outer joins preserve non-matching rows from one side.",
                            "Parameterized queries prevent SQL injection by separating code from user-supplied values.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "SQL select, insert, update, and delete form the daily toolkit of application developers.",
                            "Filtering, sorting, and aggregation turn raw tables into meaningful reports.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "102",
            "material_id": "db_relationships",
            "title": "Relationships and Keys",
            "file_type": "pdf",
            "course_name": "Database",
            "content": _lecture(
                "Relationships and Keys",
                "Database",
                [
                    (
                        "Definitions",
                        [
                            "A Primary Key is a column or combination of columns that uniquely identifies each row.",
                            "A Foreign Key is a column that references the primary key of another table.",
                            "Referential Integrity requires foreign key values to match an existing primary key or be null.",
                            "A One To One relationship links exactly one row in table A to one row in table B.",
                            "A One To Many relationship links one row in table A to many rows in table B.",
                            "A Many To Many relationship requires a junction table holding pairs of foreign keys.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Normalization reduces duplication and update anomalies in relational schemas.",
                            "First Normal Form requires atomic values in every column with no repeating groups.",
                            "Second Normal Form removes partial dependencies on composite keys.",
                            "Third Normal Form removes transitive dependencies among non-key columns.",
                            "An Index is a lookup structure that speeds searches on frequently queried columns.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "One department can employ many instructors, which is a one to many relationship.",
                            "Students and courses are many to many because each student enrolls in multiple courses.",
                            "The Enrollments junction table stores student_id and course_id pairs.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "A Composite Key uses multiple columns together as a primary key for junction tables.",
                            "A Surrogate Key is an artificial identifier such as an auto-increment integer.",
                            "A Natural Key uses a real-world identifier such as a national ID number.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Primary and foreign keys connect tables into coherent relational models.",
                            "Choosing correct relationship types prevents redundant data and orphaned records.",
                        ],
                    ),
                ],
            ),
        },
    ]


def _computer_vision_materials() -> list[dict]:
    return [
        {
            "course_id": "103",
            "material_id": "cv_image_processing",
            "title": "Image Processing Basics",
            "file_type": "pdf",
            "course_name": "Computer Vision",
            "content": _lecture(
                "Image Processing Basics",
                "Computer Vision",
                [
                    (
                        "Definitions",
                        [
                            "Computer Vision is the field that enables machines to interpret images and video.",
                            "A Digital Image is a grid of pixels where each pixel stores intensity or color values.",
                            "Grayscale Intensity measures brightness on a single channel from black to white.",
                            "A Color Channel is one component of a color model such as red, green, or blue in RGB.",
                            "Spatial Resolution is the number of pixels along the width and height of an image.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Image Acquisition captures light with sensors and converts it into numeric arrays.",
                            "Point Operations modify each pixel independently using lookup tables or formulas.",
                            "Histogram Equalization spreads intensity values to improve global contrast.",
                            "Convolution applies a small kernel across the image to emphasize edges or blur noise.",
                            "Noise Reduction filters remove sensor grain without destroying important structure.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "Increasing brightness adds a constant offset to every pixel intensity value.",
                            "A Gaussian blur kernel smooths a noisy campus photo before edge detection.",
                            "Thresholding converts a grayscale scan into a binary document image.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Linear filters use weighted sums of neighbors, while nonlinear filters use rank or median statistics.",
                            "Global contrast adjustment affects the entire image, while adaptive methods use local neighborhoods.",
                            "Spatial domain processing edits pixels directly, while frequency domain methods edit spectral components.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Image processing transforms raw pixel arrays into representations suitable for higher-level vision tasks.",
                            "Filtering, contrast adjustment, and thresholding are foundational operations in every vision pipeline.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "103",
            "material_id": "cv_segmentation",
            "title": "Segmentation and Morphology",
            "file_type": "pdf",
            "course_name": "Computer Vision",
            "content": _lecture(
                "Segmentation and Morphology",
                "Computer Vision",
                [
                    (
                        "Definitions",
                        [
                            "Image Segmentation partitions an image into regions that share meaningful properties.",
                            "Binary Segmentation assigns each pixel to foreground or background.",
                            "Morphology is a set of operations that process images based on shape using structuring elements.",
                            "Erosion shrinks bright regions and removes small protrusions.",
                            "Dilation expands bright regions and closes small gaps.",
                            "Opening applies erosion followed by dilation to remove small bright noise.",
                            "Closing applies dilation followed by erosion to fill small dark holes.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Connected Components Labeling groups adjacent pixels with the same label.",
                            "Region of Interest extraction isolates an object for measurement or classification.",
                            "Watershed Segmentation treats gradients as topographic surfaces that flood from markers.",
                            "Structuring Element size controls how aggressively morphology edits boundaries.",
                            "Contour Finding traces the outer boundary of segmented regions.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "Segmenting blood cells in a microscope image uses thresholding plus morphological opening.",
                            "Closing small gaps in a scanned fingerprint ridge pattern improves minutiae detection.",
                            "Connected components count the number of coins on a tabletop photograph.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Global thresholding is fast but fails under uneven illumination, while adaptive thresholding handles shadows.",
                            "Edge-based segmentation relies on gradients, while region-based methods grow homogeneous neighborhoods.",
                            "Semantic segmentation assigns class labels, while instance segmentation separates individual objects.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Segmentation converts pixels into meaningful regions for measurement and recognition.",
                            "Morphological operators refine binary masks by editing shape at the pixel level.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "103",
            "material_id": "cv_features",
            "title": "Feature Extraction and Matching",
            "file_type": "pdf",
            "course_name": "Computer Vision",
            "content": _lecture(
                "Feature Extraction and Matching",
                "Computer Vision",
                [
                    (
                        "Definitions",
                        [
                            "A Feature is a measurable property of an image that is stable under viewpoint or lighting changes.",
                            "A Corner is a point where intensity changes sharply in multiple directions.",
                            "A Keypoint is a detected location that includes position, scale, and orientation.",
                            "A Descriptor is a numeric vector summarizing appearance around a keypoint.",
                            "Feature Matching compares descriptors across two images to find correspondences.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Harris Corner Detection responds to local intensity gradients in orthogonal directions.",
                            "Scale Invariant Feature Transform builds descriptors that remain stable across zoom levels.",
                            "Bag of Visual Words represents an image as a histogram of clustered descriptors.",
                            "Nearest Neighbor Matching pairs descriptors with minimum distance in feature space.",
                            "RANSAC estimates geometric transforms while rejecting outlier matches.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "Matching keypoints between two photos of the same building estimates camera motion.",
                            "Feature vectors from product images power visual search in e-commerce catalogs.",
                            "Descriptor matching links stereo image pairs for depth reconstruction.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Hand-crafted features rely on engineered gradients, while learned features come from neural networks.",
                            "Brute force matching is exact but slow, while approximate nearest neighbors trade accuracy for speed.",
                            "Local features excel on textured objects, while global descriptors summarize entire scenes.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Feature extraction converts raw pixels into compact signatures suitable for comparison.",
                            "Robust matching underpins object recognition, stitching, and three-dimensional reconstruction.",
                        ],
                    ),
                ],
            ),
        },
    ]


def _web_development_materials() -> list[dict]:
    return [
        {
            "course_id": "103",
            "material_id": "web_html_css",
            "title": "HTML and CSS Basics",
            "file_type": "pdf",
            "course_name": "Web Development",
            "content": _lecture(
                "HTML and CSS Basics",
                "Web Development",
                [
                    (
                        "Definitions",
                        [
                            "HTML is the markup language that defines the structure and semantics of web pages.",
                            "CSS is the stylesheet language that controls layout, color, and typography on the web.",
                            "An HTML Element consists of an opening tag, content, and a closing tag.",
                            "A CSS Selector targets elements in the document object model for styling.",
                            "The Box Model describes how margin, border, padding, and content compose element size.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Semantic HTML uses tags such as header, nav, main, and article to convey meaning to browsers and assistive tech.",
                            "CSS Cascade resolves conflicting rules using specificity, origin, and source order.",
                            "Flexbox arranges items along a primary axis for responsive one-dimensional layouts.",
                            "CSS Grid defines two-dimensional tracks for complex page layouts.",
                            "Responsive Design adapts layouts to different viewport widths using media queries.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "A course syllabus page uses heading levels, unordered lists, and anchor links.",
                            "A card component uses flexbox to align a title, description, and button vertically.",
                            "A media query switches a navigation bar from horizontal to stacked on mobile screens.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Inline styles apply to one element, while external stylesheets reuse rules across many pages.",
                            "Block elements occupy full width by default, while inline elements flow within text lines.",
                            "Fixed layouts use pixel widths, while fluid layouts use percentages or fractional grid units.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "HTML provides structure and CSS provides presentation for every modern web application.",
                            "Semantic markup and responsive layout are essential for accessible, maintainable interfaces.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "103",
            "material_id": "web_javascript",
            "title": "JavaScript Fundamentals",
            "file_type": "pdf",
            "course_name": "Web Development",
            "content": _lecture(
                "JavaScript Fundamentals",
                "Web Development",
                [
                    (
                        "Definitions",
                        [
                            "JavaScript is the programming language of the browser that adds interactivity to web pages.",
                            "The Document Object Model is a tree representation of HTML that scripts can read and modify.",
                            "An Event is a signal such as a click or keypress that triggers handler functions.",
                            "A Promise represents a value that will be available asynchronously in the future.",
                            "JSON is a text format for exchanging structured data between client and server.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Event Listeners attach functions that run when users interact with elements.",
                            "DOM Manipulation creates, updates, or removes nodes to reflect application state.",
                            "Closures allow inner functions to access variables from an enclosing scope.",
                            "Async Await syntax writes asynchronous code in a sequential readable style.",
                            "Fetch API requests resources over HTTP and returns responses for parsing.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "A button click handler toggles visibility of an FAQ answer element.",
                            "Fetch loads quiz questions from an API and renders them into a list.",
                            "Form validation prevents submission when required email fields are empty.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "var has function scope, while let and const use block scope in modern JavaScript.",
                            "Synchronous code blocks execution until each step finishes, while asynchronous code schedules work later.",
                            "Vanilla JavaScript uses platform APIs directly, while frameworks provide component abstractions.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "JavaScript connects user events, DOM updates, and network requests in interactive web apps.",
                            "Understanding async behavior and the DOM is critical before adopting frontend frameworks.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "103",
            "material_id": "web_fullstack",
            "title": "Frontend and Backend Concepts",
            "file_type": "pdf",
            "course_name": "Web Development",
            "content": _lecture(
                "Frontend and Backend Concepts",
                "Web Development",
                [
                    (
                        "Definitions",
                        [
                            "The Frontend is the client-side layer users see in the browser.",
                            "The Backend is the server-side layer that stores data and enforces business rules.",
                            "An API Endpoint is a URL that accepts HTTP requests and returns structured responses.",
                            "REST is an architectural style that uses standard HTTP verbs on resource-oriented URLs.",
                            "Authentication verifies identity, while Authorization determines what an identity may access.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Single Page Applications load one HTML shell and swap views with client-side routing.",
                            "Server Side Rendering generates HTML on the server for faster first paint and SEO.",
                            "Environment Variables store secrets such as database URLs outside source code.",
                            "CORS policies control which origins may call an API from the browser.",
                            "State Management coordinates data shared across many UI components.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "A student dashboard frontend calls GET /student/123/courses to populate a course list.",
                            "A login form posts credentials to POST /auth/login and stores a JWT in memory.",
                            "A backend validates quiz answers and persists scores in MongoDB.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Monolithic backends combine all features in one deployable unit, while microservices split domains into services.",
                            "Session cookies keep state on the server, while JWT tokens carry signed claims on the client.",
                            "SQL databases emphasize relations, while document databases store flexible JSON-like records.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Modern web development coordinates frontend presentation with backend data and security.",
                            "Clear API contracts and separation of concerns keep full-stack systems maintainable.",
                        ],
                    ),
                ],
            ),
        },
    ]


def _ai_materials() -> list[dict]:
    return [
        {
            "course_id": "104",
            "material_id": "ai_fundamentals",
            "title": "AI Fundamentals",
            "file_type": "pdf",
            "course_name": "Artificial Intelligence",
            "content": _lecture(
                "AI Fundamentals",
                "Artificial Intelligence",
                [
                    (
                        "Definitions",
                        [
                            "Artificial Intelligence is the study of agents that perceive environments and act to achieve goals.",
                            "An Agent is an entity that receives percepts and selects actions using a policy.",
                            "Machine Learning is a subset of AI where systems improve performance from experience without explicit rule programming.",
                            "Knowledge Representation stores facts and rules that support reasoning.",
                            "An Intelligent Agent maximizes expected performance based on its percept sequence.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Problem Formulation defines states, actions, transition models, and goal tests.",
                            "Heuristic Functions estimate the cost to reach a goal from a given state.",
                            "Uncertainty arises when sensors are noisy or actions have stochastic outcomes.",
                            "Utility Theory ranks outcomes when multiple goals conflict.",
                            "Ethical AI considers fairness, transparency, and human oversight in automated decisions.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "A vacuum-cleaner agent chooses move or suck actions based on dirt percepts.",
                            "A medical triage assistant ranks patients using vital-sign features and learned risk scores.",
                            "A chatbot maps user utterances to intents using training conversations.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Symbolic AI manipulates explicit rules, while statistical AI learns patterns from data.",
                            "Weak AI solves narrow tasks, while strong AI would match general human cognition.",
                            "Online learning updates models continuously, while batch learning trains on fixed datasets.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "AI combines search, learning, and reasoning to build systems that act intelligently.",
                            "Clear problem definitions and ethical constraints guide every successful AI project.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "104",
            "material_id": "ai_search",
            "title": "Search Algorithms",
            "file_type": "pdf",
            "course_name": "Artificial Intelligence",
            "content": _lecture(
                "Search Algorithms",
                "Artificial Intelligence",
                [
                    (
                        "Definitions",
                        [
                            "State Space Search explores possible world states to find a path to a goal.",
                            "Breadth First Search expands the shallowest node first and is complete if branching is finite.",
                            "Depth First Search expands the deepest node first and uses less memory but may get stuck in deep branches.",
                            "Uniform Cost Search expands the node with lowest path cost when step costs vary.",
                            "A Star Search combines path cost g(n) with heuristic h(n) using f(n) equals g(n) plus h(n).",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Admissibility means a heuristic never overestimates true cost to the goal.",
                            "Consistency means estimated cost between neighbors is no greater than actual step cost plus heuristic difference.",
                            "Frontier Management stores unexplored nodes in a queue or priority queue.",
                            "Explored Set prevents revisiting states and eliminates redundant work.",
                            "Graph Search remembers visited states, while tree search may revisit them.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "Breadth first search finds the shortest number of moves in an unweighted puzzle.",
                            "A star with Manhattan distance solves grid pathfinding efficiently in navigation maps.",
                            "Uniform cost search finds cheapest routes when road segments have different travel times.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Breadth first is optimal for unweighted graphs, while uniform cost is optimal for nonnegative weights.",
                            "Greedy best first search uses only h(n) and may sacrifice optimality for speed.",
                            "A star is optimal with an admissible heuristic and often far faster than uninformed search.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Search algorithms systematically explore state spaces to reach goals efficiently.",
                            "Choosing the right strategy depends on cost structure and quality of heuristics.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "104",
            "material_id": "ai_ml_intro",
            "title": "Machine Learning Introduction",
            "file_type": "pdf",
            "course_name": "Artificial Intelligence",
            "content": _lecture(
                "Machine Learning Introduction",
                "Artificial Intelligence",
                [
                    (
                        "Definitions",
                        [
                            "Supervised Learning trains models on labeled input-output pairs.",
                            "Unsupervised Learning discovers structure in unlabeled data such as clusters.",
                            "A Feature Vector is a numeric representation of an input instance.",
                            "A Label is the target output the model tries to predict.",
                            "Generalization is the ability to perform well on unseen examples.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Training Data teaches model parameters through an optimization procedure.",
                            "Validation Data tunes hyperparameters without biasing final evaluation.",
                            "Test Data estimates performance on fresh examples after model selection.",
                            "Overfitting memorizes training noise instead of learning general patterns.",
                            "Bias Variance Tradeoff balances underfitting simplicity against overfitting complexity.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "Linear regression predicts house prices from square footage and location features.",
                            "Logistic regression classifies emails as spam or not spam using word frequencies.",
                            "K-means clustering groups customers by purchasing behavior without predefined labels.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Classification predicts discrete categories, while regression predicts continuous values.",
                            "Parametric models assume fixed functional form, while nonparametric models grow capacity with data.",
                            "Batch gradient descent uses the full dataset each step, while stochastic methods use mini-batches.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Machine learning converts data into models that generalize to new decisions.",
                            "Proper splits and evaluation metrics prevent overconfident but brittle systems.",
                        ],
                    ),
                ],
            ),
        },
    ]


def _data_structures_materials() -> list[dict]:
    return [
        {
            "course_id": "104",
            "material_id": "ds_arrays_lists",
            "title": "Arrays and Linked Lists",
            "file_type": "pdf",
            "course_name": "Data Structures",
            "content": _lecture(
                "Arrays and Linked Lists",
                "Data Structures",
                [
                    (
                        "Definitions",
                        [
                            "An Array is a contiguous block of memory storing elements of the same type with constant-time indexing.",
                            "A Dynamic Array resizes automatically when capacity is exceeded, amortizing copy cost.",
                            "A Linked List stores elements in nodes where each node points to the next node.",
                            "A Singly Linked List has forward pointers only, while a Doubly Linked List links both directions.",
                            "A Node contains a data payload and one or more references to other nodes.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Random Access means retrieving any element by index in constant time in arrays.",
                            "Sequential Access traverses linked lists from head to tail in linear time.",
                            "Insertion at the head of a linked list is constant time if a head pointer exists.",
                            "Insertion in the middle of an array may require shifting many elements.",
                            "Cache Locality favors arrays because neighboring elements sit in contiguous memory.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "An array stores exam scores indexed from zero to n minus one for fast lookup.",
                            "A linked list implements a playlist where songs are inserted at the front in constant time.",
                            "Dynamic arrays power Python lists and Java ArrayList abstractions.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Arrays excel at indexing speed, while linked lists excel at frequent insertions at known positions.",
                            "Array memory is fixed unless resized, while linked lists allocate nodes scattered in the heap.",
                            "Doubly linked lists support backward traversal at the cost of extra pointer storage.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Arrays and linked lists are foundational sequential containers with complementary tradeoffs.",
                            "Choosing between them depends on access patterns, insertion frequency, and memory constraints.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "104",
            "material_id": "ds_stacks_queues",
            "title": "Stacks and Queues",
            "file_type": "pdf",
            "course_name": "Data Structures",
            "content": _lecture(
                "Stacks and Queues",
                "Data Structures",
                [
                    (
                        "Definitions",
                        [
                            "A Stack is a last-in-first-out collection supporting push and pop at one end.",
                            "A Queue is a first-in-first-out collection supporting enqueue at the rear and dequeue at the front.",
                            "A Deque allows insertion and removal at both ends efficiently.",
                            "The Top of a stack is the most recently pushed element.",
                            "The Front of a queue is the next element to be dequeued.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Stack Frames store local variables and return addresses during recursive function calls.",
                            "Expression Evaluation uses stacks to handle operator precedence in calculators.",
                            "Breadth First Search uses a queue to explore graph layers in order.",
                            "Circular Queues reuse array slots by wrapping indices modulo capacity.",
                            "Amortized Analysis shows that occasional expensive resizes still yield good average performance.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "Undo functionality in a text editor pushes commands onto a stack and pops on undo.",
                            "Printer job scheduling enqueues documents and dequeues them in arrival order.",
                            "Balanced parenthesis checking pushes opening symbols and pops on matching closers.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Stacks model depth-first behavior, while queues model breadth-first fairness.",
                            "Array-based queues offer cache efficiency, while linked queues avoid capacity limits.",
                            "Priority queues order elements by priority rather than strict arrival time.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Stacks and queues restrict insertion order to solve parsing, scheduling, and traversal problems.",
                            "Their simple interfaces hide efficient implementations in arrays or linked structures.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "104",
            "material_id": "ds_trees_graphs",
            "title": "Trees and Graphs",
            "file_type": "pdf",
            "course_name": "Data Structures",
            "content": _lecture(
                "Trees and Graphs",
                "Data Structures",
                [
                    (
                        "Definitions",
                        [
                            "A Tree is a connected acyclic graph with a designated root node and hierarchical edges.",
                            "A Binary Tree is a tree where each node has at most two children labeled left and right.",
                            "A Binary Search Tree orders keys so left descendants are smaller and right descendants are larger.",
                            "A Graph is a set of vertices connected by edges that may contain cycles.",
                            "A Directed Graph edges have direction, while an Undirected Graph edges connect pairs symmetrically.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Tree Height measures the longest path from root to leaf and affects search cost.",
                            "Balanced Trees such as AVL or red-black trees keep height logarithmic in node count.",
                            "Depth First Search explores as far as possible along each branch before backtracking.",
                            "Breadth First Search visits all neighbors at the current depth before going deeper.",
                            "Shortest Path Algorithms such as Dijkstra find minimum cost routes in weighted graphs.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "A file system directory tree stores folders as internal nodes and files as leaves.",
                            "A course prerequisite graph uses directed edges from required courses to advanced courses.",
                            "Social networks model friendships as undirected edges between user vertices.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Trees forbid cycles, while graphs allow cycles and richer connectivity patterns.",
                            "Adjacency lists save memory on sparse graphs, while adjacency matrices speed edge lookup on dense graphs.",
                            "Recursive tree traversals mirror call stacks, while iterative versions use explicit stacks or queues.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Trees organize hierarchical data with efficient search when balanced.",
                            "Graphs represent networks where pathfinding and connectivity algorithms are essential.",
                        ],
                    ),
                ],
            ),
        },
    ]


def _software_engineering_materials() -> list[dict]:
    return [
        {
            "course_id": "105",
            "material_id": "se_sdlc",
            "title": "Software Development Life Cycle",
            "file_type": "pdf",
            "course_name": "Software Engineering",
            "content": _lecture(
                "Software Development Life Cycle",
                "Software Engineering",
                [
                    (
                        "Definitions",
                        [
                            "The Software Development Life Cycle is the structured process of planning, building, deploying, and maintaining software.",
                            "Requirements Engineering is the discipline that captures what stakeholders need the system to do.",
                            "Design is the phase that translates requirements into architectures, modules, and interfaces.",
                            "Implementation is the stage that writes and integrates source code according to the design.",
                            "Maintenance is the ongoing work that fixes defects and adapts software to changing environments.",
                            "DevOps is a practice that integrates development and operations through automated pipelines.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Waterfall executes phases sequentially with formal handoffs between stages.",
                            "Agile delivers working software in short iterations with continuous stakeholder feedback.",
                            "DevOps integrates development and operations through automated pipelines.",
                            "Version Control tracks changes and enables collaborative branching workflows.",
                            "Continuous Integration merges code frequently and runs automated tests on each merge.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "A university portal project starts with user stories from registrars and students.",
                            "Sprint planning selects backlog items for a two-week agile iteration.",
                            "A CI pipeline runs unit tests and lint checks on every pull request.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Waterfall suits stable requirements, while agile suits evolving products with uncertain scope.",
                            "Monolithic releases deploy entire applications, while incremental releases ship features continuously.",
                            "Manual deployment is error prone, while automated deployment improves repeatability.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "The SDLC provides discipline that keeps large software efforts predictable and auditable.",
                            "Modern teams combine agile planning with automated quality gates throughout delivery.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "105",
            "material_id": "se_requirements",
            "title": "Requirements Engineering",
            "file_type": "pdf",
            "course_name": "Software Engineering",
            "content": _lecture(
                "Requirements Engineering",
                "Software Engineering",
                [
                    (
                        "Definitions",
                        [
                            "A Functional Requirement describes a specific behavior the system must provide.",
                            "A Nonfunctional Requirement describes quality attributes such as performance or security.",
                            "A User Story is a short scenario describing value from an end user perspective.",
                            "A Use Case documents interactions between actors and the system to achieve a goal.",
                            "A Requirement Traceability Matrix links requirements to design elements and tests.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Elicitation interviews stakeholders to discover needs, constraints, and priorities.",
                            "Analysis resolves conflicts and detects ambiguous or incomplete statements.",
                            "Specification writes clear, testable requirements in a shared document or tool.",
                            "Validation confirms requirements with stakeholders before implementation begins.",
                            "MoSCoW Prioritization ranks features as must, should, could, or won't for the release.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "The system shall allow students to download lecture PDFs within three seconds on campus Wi-Fi.",
                            "As a student I want to reset my password so that I can regain access after forgetting it.",
                            "A traceability link connects quiz submission requirement QA-12 to test case TC-204.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Functional requirements define what the system does, while nonfunctional requirements define how well it does it.",
                            "Prototypes clarify user interfaces early, while formal specs reduce ambiguity for backend contracts.",
                            "Changing requirements late in waterfall is costly, while agile expects controlled change each sprint.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Requirements engineering prevents building the wrong product efficiently.",
                            "Testable, prioritized requirements are the foundation of reliable estimation and verification.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "105",
            "material_id": "se_testing",
            "title": "Testing and Quality Assurance",
            "file_type": "pdf",
            "course_name": "Software Engineering",
            "content": _lecture(
                "Testing and Quality Assurance",
                "Software Engineering",
                [
                    (
                        "Definitions",
                        [
                            "Software Testing executes a program to find defects and verify expected behavior.",
                            "A Unit Test checks an individual function or class in isolation.",
                            "Integration Testing verifies that modules cooperate correctly through their interfaces.",
                            "System Testing evaluates the complete application against requirements.",
                            "Acceptance Testing confirms the product satisfies stakeholder criteria before release.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Test Driven Development writes failing tests before implementing production code.",
                            "Code Coverage measures which lines or branches tests execute.",
                            "Regression Testing reruns existing tests after changes to detect new failures.",
                            "Defect Tracking logs bugs with steps to reproduce, severity, and owner.",
                            "Quality Assurance encompasses processes and standards that prevent defects proactively.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "A unit test asserts that calculateAverage returns 85.0 for scores 80, 85, and 90.",
                            "An integration test posts login credentials to the API and expects a 200 response with a token.",
                            "A regression suite runs on every commit to catch broken quiz submission endpoints.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Black box testing ignores internal structure, while white box testing exercises specific paths.",
                            "Manual exploratory testing finds unexpected issues, while automated tests guard known behavior.",
                            "Static analysis inspects code without running it, while dynamic testing observes runtime behavior.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Layered testing from units to acceptance reduces risk before users encounter defects.",
                            "Quality assurance combines automated gates with human review of requirements and design.",
                        ],
                    ),
                ],
            ),
        },
    ]


def _machine_learning_materials() -> list[dict]:
    return [
        {
            "course_id": "105",
            "material_id": "ml_supervised",
            "title": "Supervised Learning",
            "file_type": "pdf",
            "course_name": "Machine Learning",
            "content": _lecture(
                "Supervised Learning",
                "Machine Learning",
                [
                    (
                        "Definitions",
                        [
                            "Supervised Learning learns a mapping from inputs to outputs using labeled training examples.",
                            "A Training Example pairs a feature vector with a known label.",
                            "A Hypothesis is a candidate function the algorithm adjusts during training.",
                            "A Loss Function quantifies how wrong predictions are on training data.",
                            "Empirical Risk is average loss computed over the training set.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Gradient Descent updates parameters in the direction that reduces loss.",
                            "Regularization penalizes complex models to improve generalization.",
                            "Cross Validation estimates performance by rotating held-out folds.",
                            "Feature Scaling normalizes magnitudes so optimization converges reliably.",
                            "Class Imbalance occurs when some labels are far less frequent than others.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "Predicting student pass or fail from attendance and quiz scores is binary classification.",
                            "Predicting final exam points from study hours is linear regression.",
                            "Email spam filtering learns word weights from messages labeled spam or ham.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Logistic regression outputs probabilities for classes, while linear regression outputs continuous values.",
                            "Decision trees split features interpretably, while deep networks learn hierarchical representations.",
                            "L1 regularization encourages sparse weights, while L2 regularization shrinks weights smoothly.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Supervised learning optimizes models against labeled data using loss minimization.",
                            "Regularization and validation protect against overfitting noisy training sets.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "105",
            "material_id": "ml_classification_metrics",
            "title": "Classification Metrics",
            "file_type": "pdf",
            "course_name": "Machine Learning",
            "content": _lecture(
                "Classification Metrics",
                "Machine Learning",
                [
                    (
                        "Definitions",
                        [
                            "Accuracy is the fraction of predictions that match the true label.",
                            "Precision is the fraction of positive predictions that are actually positive.",
                            "Recall is the fraction of actual positives that the model correctly identifies.",
                            "F1 Score is the harmonic mean of precision and recall.",
                            "A Confusion Matrix tabulates true positives, false positives, true negatives, and false negatives.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Threshold Selection converts probabilistic scores into hard class decisions.",
                            "ROC Curve plots true positive rate against false positive rate across thresholds.",
                            "AUC summarizes ROC performance as a single number between zero and one.",
                            "Macro Averaging computes metrics per class then averages without weighting by frequency.",
                            "Weighted Averaging accounts for class support when averaging metrics.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "A fraud detector with high precision minimizes false alarms blocking legitimate transactions.",
                            "A medical screening test with high recall minimizes missed disease cases.",
                            "Confusion matrix analysis shows whether a model confuses two similar course labels.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Accuracy misleads on imbalanced data, while F1 balances precision and recall.",
                            "Precision focuses on prediction quality, while recall focuses on coverage of positives.",
                            "Micro averaging aggregates counts globally, while macro averaging treats classes equally.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Classification metrics must align with business costs of false positives and false negatives.",
                            "Confusion matrices and ROC analysis reveal failure modes beyond a single accuracy number.",
                        ],
                    ),
                ],
            ),
        },
        {
            "course_id": "105",
            "material_id": "ml_training_eval",
            "title": "Model Training and Evaluation",
            "file_type": "pdf",
            "course_name": "Machine Learning",
            "content": _lecture(
                "Model Training and Evaluation",
                "Machine Learning",
                [
                    (
                        "Definitions",
                        [
                            "Training is the phase where model parameters are fit to minimize loss on training data.",
                            "Hyperparameters are settings such as learning rate chosen before training begins.",
                            "Early Stopping halts training when validation loss stops improving.",
                            "A Baseline Model provides a simple reference score such as predicting the majority class.",
                            "Model Deployment serves trained parameters in production for live predictions.",
                        ],
                    ),
                    (
                        "Key Concepts",
                        [
                            "Learning Rate controls step size during gradient descent and affects convergence stability.",
                            "Mini Batch Training updates weights using small random subsets for efficiency.",
                            "Data Leakage occurs when information from the test set influences training decisions.",
                            "Model Monitoring tracks prediction drift and performance decay after deployment.",
                            "Reproducibility records seeds, data versions, and library versions for every experiment.",
                        ],
                    ),
                    (
                        "Examples",
                        [
                            "Grid search tries multiple regularization strengths and picks the best validation score.",
                            "Early stopping on validation loss prevents a neural network from overfitting epoch 50 noise.",
                            "Comparing to a majority-class baseline proves a classifier beats random guessing.",
                        ],
                    ),
                    (
                        "Comparisons",
                        [
                            "Holdout evaluation is fast but noisy on small datasets, while k-fold cross validation is more stable.",
                            "Offline metrics evaluate historical logs, while online A/B tests measure live user impact.",
                            "Batch inference scores many rows at once, while online inference scores one request at a time.",
                        ],
                    ),
                    (
                        "Summary",
                        [
                            "Rigorous training and evaluation separate robust models from lucky overfits.",
                            "Baselines, validation discipline, and monitoring keep ML systems trustworthy in production.",
                        ],
                    ),
                ],
            ),
        },
    ]


def all_demo_materials() -> list[dict]:
    """Return every seeded demo material spec (24 lectures across 5 course IDs)."""
    return [
        *_programming_materials(),
        *_database_materials(),
        *_computer_vision_materials(),
        *_web_development_materials(),
        *_ai_materials(),
        *_data_structures_materials(),
        *_software_engineering_materials(),
        *_machine_learning_materials(),
    ]
