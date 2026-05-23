// Mock data for courses and performance

export interface Course {
  id: string;
  name: string;
  code: string;
  instructor: string;
  chapters: string[];
}

export interface PerformanceData {
  date: string;
  score: number;
}

export interface CourseStats {
  submittedAssignments: number;
  totalAssignments: number;
  avgAssignmentGrade: number;
  completedQuizzes: number;
  totalQuizzes: number;
  avgQuizGrade: number;
  timeSpentHours: number;
}

export const courses: Course[] = [
  { id: "cs101", name: "Introduction to Programming", code: "CS101", instructor: "Dr. Traggy", chapters: ["Variables & Data Types", "Control Flow", "Functions", "Arrays & Lists", "OOP Basics"] },
  { id: "cs201", name: "Data Structures", code: "CS201", instructor: "Dr. Ashraf", chapters: ["Arrays & Linked Lists", "Stacks & Queues", "Trees", "Graphs", "Hashing"] },
  { id: "cs301", name: "Database", code: "CS301", instructor: "Dr. Fatma", chapters: ["ER Modeling", "Relational Model", "SQL Basics", "Normalization", "Transactions"] },
  { id: "cs401", name: "Software Engineering", code: "CS401", instructor: "Dr. Yasmin", chapters: ["SDLC Models", "Requirements Engineering", "Design Patterns", "Testing", "Agile Methods"] },
  { id: "math201", name: "Linear Algebra", code: "MATH201", instructor: "Dr. Emad", chapters: ["Vectors", "Matrices", "Determinants", "Eigenvalues", "Linear Transformations"] },
  { id: "eng101", name: "English", code: "ENG101", instructor: "Dr. Rahma", chapters: ["Grammar Review", "Academic Writing", "Report Writing", "Presentation Skills", "Research Methods"] },
];

export const weeklyPerformanceData: PerformanceData[] = [
  { date: "Mon", score: 72 },
  { date: "Tue", score: 78 },
  { date: "Wed", score: 85 },
  { date: "Thu", score: 82 },
  { date: "Fri", score: 88 },
  { date: "Sat", score: 90 },
  { date: "Sun", score: 85 },
];

export const coursePerformanceData: Record<string, PerformanceData[]> = {
  cs101: [
    { date: "Week 1", score: 85 },
    { date: "Week 2", score: 88 },
    { date: "Week 3", score: 82 },
    { date: "Week 4", score: 90 },
    { date: "Week 5", score: 92 },
    { date: "Week 6", score: 88 },
  ],
  cs201: [
    { date: "Week 1", score: 78 },
    { date: "Week 2", score: 72 },
    { date: "Week 3", score: 75 },
    { date: "Week 4", score: 80 },
    { date: "Week 5", score: 82 },
    { date: "Week 6", score: 85 },
  ],
  cs301: [
    { date: "Week 1", score: 65 },
    { date: "Week 2", score: 68 },
    { date: "Week 3", score: 62 },
    { date: "Week 4", score: 70 },
    { date: "Week 5", score: 72 },
    { date: "Week 6", score: 68 },
  ],
  cs401: [
    { date: "Week 1", score: 90 },
    { date: "Week 2", score: 92 },
    { date: "Week 3", score: 88 },
    { date: "Week 4", score: 95 },
    { date: "Week 5", score: 93 },
    { date: "Week 6", score: 91 },
  ],
  math201: [
    { date: "Week 1", score: 75 },
    { date: "Week 2", score: 78 },
    { date: "Week 3", score: 80 },
    { date: "Week 4", score: 82 },
    { date: "Week 5", score: 85 },
    { date: "Week 6", score: 88 },
  ],
  eng101: [
    { date: "Week 1", score: 88 },
    { date: "Week 2", score: 85 },
    { date: "Week 3", score: 90 },
    { date: "Week 4", score: 88 },
    { date: "Week 5", score: 92 },
    { date: "Week 6", score: 90 },
  ],
};

export const courseStats: Record<string, CourseStats> = {
  cs101: {
    submittedAssignments: 8,
    totalAssignments: 10,
    avgAssignmentGrade: 87,
    completedQuizzes: 5,
    totalQuizzes: 6,
    avgQuizGrade: 85,
    timeSpentHours: 42,
  },
  cs201: {
    submittedAssignments: 6,
    totalAssignments: 8,
    avgAssignmentGrade: 78,
    completedQuizzes: 4,
    totalQuizzes: 5,
    avgQuizGrade: 76,
    timeSpentHours: 38,
  },
  cs301: {
    submittedAssignments: 5,
    totalAssignments: 8,
    avgAssignmentGrade: 68,
    completedQuizzes: 3,
    totalQuizzes: 5,
    avgQuizGrade: 65,
    timeSpentHours: 28,
  },
  cs401: {
    submittedAssignments: 9,
    totalAssignments: 10,
    avgAssignmentGrade: 92,
    completedQuizzes: 6,
    totalQuizzes: 6,
    avgQuizGrade: 94,
    timeSpentHours: 55,
  },
  math201: {
    submittedAssignments: 7,
    totalAssignments: 8,
    avgAssignmentGrade: 82,
    completedQuizzes: 4,
    totalQuizzes: 5,
    avgQuizGrade: 80,
    timeSpentHours: 35,
  },
  eng101: {
    submittedAssignments: 8,
    totalAssignments: 8,
    avgAssignmentGrade: 89,
    completedQuizzes: 5,
    totalQuizzes: 5,
    avgQuizGrade: 88,
    timeSpentHours: 30,
  },
};

export const getOverallStatus = (avgScore: number): "At Risk" | "Good" | "Perfect" => {
  if (avgScore < 70) return "At Risk";
  if (avgScore < 85) return "Good";
  return "Perfect";
};

export const getCourseStatus = (avgScore: number): "Bad" | "Average" | "Good" => {
  if (avgScore < 70) return "Bad";
  if (avgScore < 85) return "Average";
  return "Good";
};

// Schedule data
export interface ScheduleEntry {
  day: string;
  time: string;
  courseCode: string;
  courseName: string;
  room: string;
}

export const scheduleData: ScheduleEntry[] = [
  { day: "Sunday", time: "08:00 - 09:30", courseCode: "CS101", courseName: "Introduction to Programming", room: "Hall A1" },
  { day: "Sunday", time: "10:00 - 11:30", courseCode: "MATH201", courseName: "Linear Algebra", room: "Hall B2" },
  { day: "Monday", time: "08:00 - 09:30", courseCode: "CS201", courseName: "Data Structures", room: "Lab 3" },
  { day: "Monday", time: "12:00 - 13:30", courseCode: "ENG101", courseName: "English", room: "Hall C1" },
  { day: "Tuesday", time: "09:00 - 10:30", courseCode: "CS301", courseName: "Database", room: "Lab 1" },
  { day: "Tuesday", time: "11:00 - 12:30", courseCode: "CS401", courseName: "Software Engineering", room: "Hall A2" },
  { day: "Wednesday", time: "08:00 - 09:30", courseCode: "CS101", courseName: "Introduction to Programming", room: "Lab 2" },
  { day: "Wednesday", time: "10:00 - 11:30", courseCode: "MATH201", courseName: "Linear Algebra", room: "Hall B2" },
  { day: "Thursday", time: "09:00 - 10:30", courseCode: "CS201", courseName: "Data Structures", room: "Hall A1" },
  { day: "Thursday", time: "11:00 - 12:30", courseCode: "CS401", courseName: "Software Engineering", room: "Lab 3" },
];

// Quiz grades data
export interface QuizGrade {
  quizName: string;
  score: number;
  totalMarks: number;
  date: string;
}

export const quizGrades: Record<string, QuizGrade[]> = {
  cs101: [
    { quizName: "Quiz 1", score: 18, totalMarks: 20, date: "2026-01-10" },
    { quizName: "Quiz 2", score: 16, totalMarks: 20, date: "2026-01-24" },
    { quizName: "Quiz 3", score: 19, totalMarks: 20, date: "2026-02-07" },
  ],
  cs201: [
    { quizName: "Quiz 1", score: 14, totalMarks: 20, date: "2026-01-12" },
    { quizName: "Quiz 2", score: 15, totalMarks: 20, date: "2026-01-26" },
    { quizName: "Quiz 3", score: 17, totalMarks: 20, date: "2026-02-09" },
  ],
  cs301: [
    { quizName: "Quiz 1", score: 12, totalMarks: 20, date: "2026-01-11" },
    { quizName: "Quiz 2", score: 13, totalMarks: 20, date: "2026-01-25" },
    { quizName: "Quiz 3", score: 14, totalMarks: 20, date: "2026-02-08" },
  ],
  cs401: [
    { quizName: "Quiz 1", score: 19, totalMarks: 20, date: "2026-01-13" },
    { quizName: "Quiz 2", score: 18, totalMarks: 20, date: "2026-01-27" },
    { quizName: "Quiz 3", score: 20, totalMarks: 20, date: "2026-02-10" },
  ],
  math201: [
    { quizName: "Quiz 1", score: 15, totalMarks: 20, date: "2026-01-14" },
    { quizName: "Quiz 2", score: 16, totalMarks: 20, date: "2026-01-28" },
    { quizName: "Quiz 3", score: 17, totalMarks: 20, date: "2026-02-11" },
  ],
  eng101: [
    { quizName: "Quiz 1", score: 17, totalMarks: 20, date: "2026-01-15" },
    { quizName: "Quiz 2", score: 18, totalMarks: 20, date: "2026-01-29" },
    { quizName: "Quiz 3", score: 19, totalMarks: 20, date: "2026-02-12" },
  ],
};

// AI generated quizzes
export type Difficulty = "Easy" | "Medium" | "Hard";
export type QuizType = "Multiple Choice" | "True/False" | "Mixed";

export interface GeneratedQuiz {
  id: string;
  title: string;
  courseId: string;
  courseName: string;
  difficulty: Difficulty;
  type: QuizType;
  questions: number;
  durationMin: number;
  createdAt: string;
}

export const generatedQuizzes: GeneratedQuiz[] = [
  { id: "q1", title: "Variables & Control Flow Drill", courseId: "cs101", courseName: "Introduction to Programming", difficulty: "Easy", type: "Multiple Choice", questions: 10, durationMin: 15, createdAt: "2026-05-09" },
  { id: "q2", title: "Trees & Graph Traversals", courseId: "cs201", courseName: "Data Structures", difficulty: "Hard", type: "Mixed", questions: 15, durationMin: 30, createdAt: "2026-05-08" },
  { id: "q3", title: "SQL Joins & Normalization", courseId: "cs301", courseName: "Database", difficulty: "Medium", type: "Multiple Choice", questions: 12, durationMin: 20, createdAt: "2026-05-07" },
  { id: "q4", title: "Agile vs Waterfall", courseId: "cs401", courseName: "Software Engineering", difficulty: "Easy", type: "True/False", questions: 8, durationMin: 10, createdAt: "2026-05-06" },
  { id: "q5", title: "Eigenvalues Practice Set", courseId: "math201", courseName: "Linear Algebra", difficulty: "Hard", type: "Mixed", questions: 14, durationMin: 35, createdAt: "2026-05-05" },
  { id: "q6", title: "Academic Writing Essentials", courseId: "eng101", courseName: "English", difficulty: "Medium", type: "Multiple Choice", questions: 10, durationMin: 18, createdAt: "2026-05-04" },
];

// AI generated notes
export interface GeneratedNote {
  id: string;
  title: string;
  courseId: string;
  courseName: string;
  summary: string;
  createdAt: string;
}

export const generatedNotes: GeneratedNote[] = [
  { id: "n1", title: "OOP Fundamentals — Cheat Sheet", courseId: "cs101", courseName: "Introduction to Programming", summary: "Concise overview of classes, objects, inheritance, polymorphism and encapsulation with quick examples.", createdAt: "2026-05-10" },
  { id: "n2", title: "Graph Algorithms Summary", courseId: "cs201", courseName: "Data Structures", summary: "BFS, DFS, Dijkstra and topological sorting with complexity comparisons and pseudocode.", createdAt: "2026-05-09" },
  { id: "n3", title: "Normalization (1NF–BCNF)", courseId: "cs301", courseName: "Database", summary: "Step-by-step decomposition examples and anomaly elimination guide for relational schemas.", createdAt: "2026-05-08" },
  { id: "n4", title: "Common Design Patterns", courseId: "cs401", courseName: "Software Engineering", summary: "Singleton, Factory, Observer and Strategy patterns with TypeScript-style examples.", createdAt: "2026-05-07" },
  { id: "n5", title: "Matrix Operations Recap", courseId: "math201", courseName: "Linear Algebra", summary: "Multiplication, inverse, determinant and rank with worked numerical examples.", createdAt: "2026-05-06" },
  { id: "n6", title: "Report Writing Guide", courseId: "eng101", courseName: "English", summary: "Structure, tone and citation tips for producing strong academic reports.", createdAt: "2026-05-05" },
];

// Per-course predicted grades
export type PredictedStatus = "Excellent" | "Good" | "Average" | "At Risk";
export type Trend = "up" | "down" | "flat";

export interface CoursePrediction {
  courseId: string;
  courseName: string;
  score: number; // 0-100
  trend: Trend;
}

export const coursePredictions: CoursePrediction[] = [
  { courseId: "cs101", courseName: "Introduction to Programming", score: 89, trend: "up" },
  { courseId: "cs201", courseName: "Data Structures", score: 78, trend: "up" },
  { courseId: "cs301", courseName: "Database", score: 66, trend: "down" },
  { courseId: "cs401", courseName: "Software Engineering", score: 92, trend: "up" },
  { courseId: "math201", courseName: "Linear Algebra", score: 81, trend: "flat" },
  { courseId: "eng101", courseName: "English", score: 88, trend: "up" },
];

export const getPredictedStatus = (s: number): PredictedStatus => {
  if (s >= 85) return "Excellent";
  if (s >= 75) return "Good";
  if (s >= 65) return "Average";
  return "At Risk";
};

// Interactive quiz questions (mock) per course
export interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  correctIndex: number;
}

export const quizQuestionBank: Record<string, QuizQuestion[]> = {
  cs101: [
    { id: "1", question: "Which keyword declares a constant in JavaScript?", options: ["var", "let", "const", "static"], correctIndex: 2 },
    { id: "2", question: "Which of these is NOT a primitive data type?", options: ["string", "number", "object", "boolean"], correctIndex: 2 },
    { id: "3", question: "What does a function return by default if no return statement is present?", options: ["null", "0", "undefined", "false"], correctIndex: 2 },
    { id: "4", question: "Which loop is guaranteed to execute at least once?", options: ["for", "while", "do...while", "foreach"], correctIndex: 2 },
    { id: "5", question: "OOP stands for?", options: ["Open Object Programming", "Object-Oriented Programming", "Operational Output Process", "Optimal Order Pattern"], correctIndex: 1 },
  ],
  cs201: [
    { id: "1", question: "Which data structure uses LIFO order?", options: ["Queue", "Stack", "Heap", "Tree"], correctIndex: 1 },
    { id: "2", question: "Average time complexity of HashMap lookup?", options: ["O(1)", "O(log n)", "O(n)", "O(n log n)"], correctIndex: 0 },
    { id: "3", question: "Which traversal visits root first?", options: ["Inorder", "Preorder", "Postorder", "Level-order"], correctIndex: 1 },
    { id: "4", question: "BFS uses which structure?", options: ["Stack", "Queue", "Heap", "Set"], correctIndex: 1 },
    { id: "5", question: "Best case for QuickSort?", options: ["O(n^2)", "O(n log n)", "O(n)", "O(log n)"], correctIndex: 1 },
  ],
  cs301: [
    { id: "1", question: "Which normal form removes transitive dependencies?", options: ["1NF", "2NF", "3NF", "BCNF"], correctIndex: 2 },
    { id: "2", question: "SQL keyword to remove duplicates?", options: ["UNIQUE", "DISTINCT", "DEDUP", "ONLY"], correctIndex: 1 },
    { id: "3", question: "Which JOIN returns only matching rows?", options: ["LEFT", "RIGHT", "INNER", "FULL"], correctIndex: 2 },
    { id: "4", question: "ACID 'I' stands for?", options: ["Integrity", "Isolation", "Indexing", "Inheritance"], correctIndex: 1 },
    { id: "5", question: "Primary key cannot be?", options: ["Unique", "Indexed", "Null", "Numeric"], correctIndex: 2 },
  ],
  cs401: [
    { id: "1", question: "Agile values working software over?", options: ["Documentation", "People", "Tools", "Code"], correctIndex: 0 },
    { id: "2", question: "Singleton ensures?", options: ["Many instances", "One instance", "No instance", "Lazy load only"], correctIndex: 1 },
    { id: "3", question: "Which is a black-box testing technique?", options: ["Path coverage", "Equivalence partitioning", "Branch coverage", "Statement coverage"], correctIndex: 1 },
    { id: "4", question: "Sprint length in Scrum is typically?", options: ["1 day", "1-4 weeks", "3 months", "6 months"], correctIndex: 1 },
    { id: "5", question: "UML class diagrams show?", options: ["Sequences", "States", "Structure", "Activities"], correctIndex: 2 },
  ],
  math201: [
    { id: "1", question: "Determinant of identity matrix In is?", options: ["0", "1", "n", "n!"], correctIndex: 1 },
    { id: "2", question: "Eigenvalues are roots of?", options: ["Trace polynomial", "Characteristic polynomial", "Minimal polynomial only", "Hessian"], correctIndex: 1 },
    { id: "3", question: "Rank of a 3x3 invertible matrix?", options: ["1", "2", "3", "0"], correctIndex: 2 },
    { id: "4", question: "Dot product of orthogonal vectors equals?", options: ["1", "-1", "0", "Undefined"], correctIndex: 2 },
    { id: "5", question: "A linear transformation preserves?", options: ["Only addition", "Addition & scalar multiplication", "Only scalars", "Norms always"], correctIndex: 1 },
  ],
  eng101: [
    { id: "1", question: "Which is a coordinating conjunction?", options: ["because", "although", "but", "since"], correctIndex: 2 },
    { id: "2", question: "An abstract in a research paper should be?", options: ["Long & detailed", "A concise summary", "Only references", "A figure"], correctIndex: 1 },
    { id: "3", question: "Active voice example?", options: ["The ball was kicked", "Kicked was the ball", "She kicked the ball", "Being kicked"], correctIndex: 2 },
    { id: "4", question: "Citations primarily aim to?", options: ["Add length", "Credit sources", "Show vocabulary", "Confuse readers"], correctIndex: 1 },
    { id: "5", question: "A thesis statement appears typically in?", options: ["Conclusion", "Introduction", "Appendix", "Footnote"], correctIndex: 1 },
  ],
};

// Detailed AI-generated note content per course
export interface NoteContent {
  courseId: string;
  title: string;
  summary: string;
  keyPoints: string[];
  sections: { heading: string; body: string }[];
}

export const noteContentBank: Record<string, NoteContent> = {
  cs101: {
    courseId: "cs101",
    title: "Introduction to Programming — Study Notes",
    summary:
      "A consolidated overview of programming fundamentals: variables, control flow, functions, collections, and an introduction to object-oriented thinking.",
    keyPoints: [
      "Variables store typed values; prefer immutability when possible.",
      "Conditionals and loops control program flow.",
      "Functions encapsulate reusable behavior with clear inputs and outputs.",
      "Lists, arrays, and maps are core collection types.",
      "OOP organizes data and behavior around objects.",
    ],
    sections: [
      { heading: "Variables & Data Types", body: "Variables hold values of a given type. Most languages distinguish primitive types (numbers, booleans, strings) from reference types (objects, arrays). Prefer constants when a value should not change." },
      { heading: "Control Flow", body: "if/else statements branch execution. Loops (for, while, do-while) repeat a block until a condition is met. Use break and continue carefully to keep code readable." },
      { heading: "Functions", body: "Functions take parameters, do work, and return a value. Pure functions (no side effects) are easier to test. Prefer small focused functions over large ones." },
      { heading: "OOP Basics", body: "Classes describe the shape and behavior of objects. The four pillars are encapsulation, inheritance, polymorphism, and abstraction." },
    ],
  },
  cs201: {
    courseId: "cs201",
    title: "Data Structures — Study Notes",
    summary:
      "Core data structures and their trade-offs: arrays, linked lists, stacks, queues, trees, graphs, and hashing.",
    keyPoints: [
      "Arrays give O(1) random access; linked lists give O(1) insertion at known nodes.",
      "Stacks are LIFO; queues are FIFO.",
      "Binary trees power many search and traversal algorithms.",
      "Graphs model relationships; BFS/DFS are foundational traversals.",
      "Hashing offers near-constant average lookup.",
    ],
    sections: [
      { heading: "Linear Structures", body: "Arrays store contiguous elements; linked lists chain nodes together. Stacks and queues are restricted-access linear structures used in parsing, scheduling, and traversal." },
      { heading: "Trees", body: "Trees are hierarchical. Binary search trees support ordered operations; balanced variants (AVL, Red-Black) keep operations logarithmic." },
      { heading: "Graphs", body: "Graphs are vertices and edges. BFS explores by layers; DFS dives deep first. Dijkstra finds shortest paths with non-negative weights." },
      { heading: "Hashing", body: "Hash maps map keys to buckets via a hash function. Good hash functions distribute keys uniformly to avoid collisions." },
    ],
  },
  cs301: {
    courseId: "cs301",
    title: "Database — Study Notes",
    summary: "Relational databases, SQL essentials, normalization, and transactions.",
    keyPoints: [
      "ER diagrams model entities and relationships.",
      "Primary keys uniquely identify rows; foreign keys link tables.",
      "Normalization reduces redundancy.",
      "ACID guarantees correct concurrent execution.",
      "Indexes speed up queries at the cost of writes.",
    ],
    sections: [
      { heading: "Relational Model", body: "Data is represented as relations (tables) with attributes (columns) and tuples (rows). Operations follow relational algebra." },
      { heading: "SQL", body: "SQL queries combine SELECT, FROM, WHERE, GROUP BY and JOIN clauses. Use INNER JOIN for matched rows and LEFT/RIGHT JOIN to keep one side." },
      { heading: "Normalization", body: "1NF removes repeating groups, 2NF removes partial dependencies, 3NF removes transitive dependencies, BCNF tightens 3NF." },
      { heading: "Transactions", body: "Transactions group statements that must succeed or fail together, providing Atomicity, Consistency, Isolation, and Durability." },
    ],
  },
  cs401: {
    courseId: "cs401",
    title: "Software Engineering — Study Notes",
    summary: "Methodologies, design, testing, and the software development lifecycle.",
    keyPoints: [
      "SDLC defines stages from requirements to maintenance.",
      "Agile values iteration and feedback over rigid plans.",
      "Design patterns capture proven solutions.",
      "Testing pyramid: unit > integration > end-to-end.",
      "Version control underpins collaboration.",
    ],
    sections: [
      { heading: "SDLC", body: "Common phases: requirements, design, implementation, testing, deployment, maintenance. Different models (Waterfall, Spiral, Agile) sequence them differently." },
      { heading: "Design Patterns", body: "Creational (Singleton, Factory), Structural (Adapter, Decorator) and Behavioral (Observer, Strategy) patterns each address recurring design problems." },
      { heading: "Testing", body: "Unit tests validate small pieces in isolation. Integration tests check combined behavior. End-to-end tests validate user flows." },
      { heading: "Agile", body: "Short iterations, continuous feedback and incremental delivery emphasize working software and customer collaboration." },
    ],
  },
  math201: {
    courseId: "math201",
    title: "Linear Algebra — Study Notes",
    summary: "Vectors, matrices, determinants, eigenvalues, and linear transformations.",
    keyPoints: [
      "Matrices represent linear transformations.",
      "Determinant indicates invertibility and scaling.",
      "Eigenvectors keep direction under transformation.",
      "Rank measures independent dimensions.",
      "Orthogonality simplifies projections and decompositions.",
    ],
    sections: [
      { heading: "Vectors & Spaces", body: "Vectors live in vector spaces with addition and scalar multiplication. Linear combinations span subspaces." },
      { heading: "Matrices", body: "Matrices encode systems of linear equations and linear maps. Multiplication composes transformations." },
      { heading: "Determinants & Inverses", body: "A square matrix is invertible iff its determinant is non-zero. Determinants also describe how transformations scale volume." },
      { heading: "Eigenvalues", body: "Eigenvalues λ satisfy Av = λv. Diagonalization simplifies repeated matrix application." },
    ],
  },
  eng101: {
    courseId: "eng101",
    title: "English — Study Notes",
    summary: "Grammar, academic writing, and research/presentation skills.",
    keyPoints: [
      "Use active voice for clarity.",
      "Strong thesis statements guide essays.",
      "Cite sources to credit original authors.",
      "Reports follow predictable structures.",
      "Practice drives presentation confidence.",
    ],
    sections: [
      { heading: "Grammar Review", body: "Master subject-verb agreement, tense consistency, and punctuation. Read your work aloud to catch awkward constructions." },
      { heading: "Academic Writing", body: "Begin with a clear thesis. Use evidence to support claims. Conclude by restating significance, not just summarizing." },
      { heading: "Citations", body: "Use a consistent citation style (APA, MLA, IEEE). Quote sparingly; paraphrase and credit sources." },
      { heading: "Presentations", body: "Open with a hook, structure around 3 main ideas, and close with a memorable takeaway. Rehearse out loud." },
    ],
  },
};
