"""
Seed demo learning materials for test student courses (Quiz Generation).

Materials are stored in course_materials — course-scoped, not Moodle sync.
Re-running always refreshes metadata and content_text (no skip on existing content).

Run from backend/:

    python -m app.scripts.seed_demo_materials

Also invoked automatically by seed_students() / BOOTSTRAP_STUDENTS.
"""

from app.config.database import ensure_indexes
from app.repositories import material_repository

# Seeded test materials for demo course IDs (see seed_students.DEMO_COURSE_METRICS).
DEMO_MATERIALS = [
    {
        "course_id": "101",
        "material_id": "prog_lec1",
        "title": "Programming Lecture 1",
        "file_type": "pdf",
        "course_name": "Programming",
        "content": """
Programming Lecture 1 — Seeded Demo Material (AcademIQ Test Content)

Introduction to Programming Fundamentals

Programming is the process of writing instructions that a computer executes in a
precise order. A Program is a complete set of those instructions saved as source
code. Software Developers use programming languages to translate human logic into
machine-readable commands.

Variables and Data Types

A Variable is a named storage location that holds a value while a program runs.
Variable Names should be descriptive so other developers can read the code easily.
Data Types are classifications that tell the computer what kind of value a variable
stores. An Integer is a whole number without a decimal point. A Floating Point
Number is a numeric value that includes fractional digits. A String is a sequence
of text characters enclosed in quotes. A Boolean is a data type that stores only
true or false.

For example, a student age variable might store the integer 20. A grade average
variable might store the floating point number 87.5. A course name variable might
store the string "Programming". An enrollment status variable might store the
boolean true when the student is active.

Control Structures and Conditionals

Control Structures are programming constructs that determine which lines of code
execute and in what order. A Conditional Statement is a control structure that
runs code only when a logical test is true. An If Else Block compares a condition
and chooses between two different paths. Comparison Operators such as equal to,
greater than, and less than produce boolean results used by conditionals.

For example, if a score is greater than or equal to 60, the program prints pass.
Otherwise the program prints fail. Conditionals are essential because real
programs must respond differently to different inputs.

Loops and Iteration

A Loop is a control structure that repeats a block of code multiple times. A For
Loop is used when the number of iterations is known in advance. A While Loop
repeats code as long as a condition remains true. Loop Iteration means each
execution of the loop body. An Infinite Loop occurs when the exit condition never
becomes false and the program never stops.

For example, a for loop can print the numbers 1 through 10. A while loop can keep
reading user input until the user types quit. Loops reduce duplication and make
programs shorter and easier to maintain.

Functions and Modular Design

A Function is a reusable block of code that performs a specific task. A Function
Parameter is an input value passed into a function when it is called. A Return
Value is the output a function sends back to the caller. Modular Design is the
practice of dividing a program into small functions that each solve one problem.

For example, a calculateAverage function accepts a list of scores and returns the
mean. A printReceipt function formats output for the user. Functions improve
readability and make testing easier because each function can be checked alone.

Arrays and Collections

An Array is a fixed-size ordered collection of elements stored in contiguous
memory. A List is a flexible collection that can grow or shrink during execution.
An Index is the numeric position of an element inside an array or list. The First
Element in most languages is stored at index zero.

For example, an array of exam scores might contain 85, 90, and 78. Programs
iterate across arrays with loops to process every value. Arrays and lists are
fundamental for storing multiple grades, names, or sensor readings.

Input and Output

Program Input is data received from the user, a file, or another system. Program
Output is data displayed on a screen, written to a file, or sent across a network.
Standard Input is the default stream where keyboards provide data. Standard Output
is the default stream where text appears in the console. Formatted Output uses
templates to combine variables and labels in readable messages.

For example, a program can ask the user to enter their name and then print a
welcome message. Input validation checks that numbers are numeric and strings are
not empty before processing continues.

Comparisons and Best Practices

Compiled Languages translate source code into machine code before execution.
Interpreted Languages execute source code line by line through a runtime engine.
A Syntax Error is a mistake in grammar that prevents compilation or interpretation.
A Logic Error is a mistake in reasoning that produces incorrect results even when
the syntax is valid.

Good Programming Practice includes choosing meaningful variable names, writing
comments that explain why code exists, testing edge cases, and keeping functions
small. These habits help teams build reliable software that is easier to debug.

Summary

Variables store data. Data Types classify values. Conditionals branch execution.
Loops repeat work. Functions organize logic. Arrays hold collections. Input and
Output connect programs to users. Together these ideas form the foundation of
every programming language students will study this term.
""".strip(),
    },
    {
        "course_id": "102",
        "material_id": "db_lec1",
        "title": "Database Lecture 1",
        "file_type": "pdf",
        "course_name": "Database",
        "content": """
Database Lecture 1 — Seeded Demo Material (AcademIQ Test Content)

Introduction to Database Systems

A Database is an organized collection of structured data stored electronically.
A Database Management System is software that creates, reads, updates, and deletes
data safely. Relational Databases organize information into related tables linked
by keys. Database Design is the process of modeling real-world entities so
applications can query them efficiently.

Tables, Rows, and Columns

A Table is a two-dimensional structure that stores records about one entity type.
A Row is a single record in a table representing one instance, such as one student.
A Column is a field definition that stores one attribute, such as student name or
email. A Table Schema is the set of column names and data types for a table.

For example, a Students table might contain rows for Alice, Bob, and Carol. Each
row shares the same columns: student_id, full_name, and enrollment_year. Columns
enforce consistent structure so queries remain predictable.

Primary Keys and Foreign Keys

A Primary Key is a column or combination of columns that uniquely identifies each
row in a table. A Foreign Key is a column that references the primary key of
another table to create a relationship. Referential Integrity is the rule that
foreign key values must match an existing primary key or be null.

For example, a Courses table might use course_id as its primary key. An Enrollments
table might include course_id as a foreign key pointing to Courses. This design
prevents orphan enrollment records that reference nonexistent classes.

SQL Fundamentals

SQL is the standard language for querying and manipulating relational databases.
A SQL Select statement retrieves rows and columns from one or more tables. A SQL
Insert statement adds new rows into a table. A SQL Update statement modifies
existing values in one or more columns. A SQL Delete statement removes rows that
match a condition.

For example, select star from students where enrollment_year equals 2024 returns
all first-year students. Insert into students values 1001, Dana, 2024 adds a new
record. Update students set full_name equals Dana Smith where student_id equals
1001 changes a name. Delete from students where student_id equals 1001 removes a
row permanently.

Filtering, Sorting, and Joins

A Where Clause filters rows based on conditions such as equality or range tests.
An Order By Clause sorts results ascending or descending by one or more columns.
A Table Join combines rows from two tables using matching key columns. An Inner
Join returns only rows that have partners in both tables.

For example, joining Students and Enrollments on student_id lists every student
with the courses they take. Joins are how relational databases reconstruct
connected information without duplicating entire tables.

Relationship Types

A One To One relationship means each row in table A links to exactly one row in
table B. A One To Many relationship means one row in table A can link to many
rows in table B. A Many To Many relationship requires a junction table that holds
pairs of foreign keys. Relationship Types guide normalization and prevent redundant
data storage.

For example, one department can employ many instructors, which is one to many.
Students and courses are many to many because each student enrolls in multiple
courses and each course contains multiple students. The Enrollments junction table
stores student_id and course_id pairs.

Normalization and Data Quality

First Normal Form requires atomic values in every column with no repeating groups.
Second Normal Form removes partial dependencies on composite keys. Third Normal
Form removes transitive dependencies where non-key columns depend on other non-key
columns. Normalization reduces duplication and update anomalies.

A Duplicate Record is a second row that repeats the same real-world entity.
A Null Value represents missing or unknown data and must be handled carefully in
queries. Data Validation at the database layer enforces types, required fields,
and acceptable ranges.

Indexes and Performance

An Index is a lookup structure that speeds searches on frequently queried columns.
A Primary Key Index is created automatically for primary key columns. A Composite
Index spans multiple columns used together in where clauses. Query Performance
improves when indexes match common filter patterns.

For example, indexing last_name accelerates searches for students by surname.
However, excessive indexes slow insert and update operations because each change
must update index structures as well as table data.

Transactions and ACID Properties

A Transaction is a group of SQL operations that succeed or fail as one unit.
Atomicity means all statements commit together or none do. Consistency means
constraints remain valid after a transaction. Isolation means concurrent
transactions do not corrupt each other's partial results. Durability means
committed data survives system failures.

For example, transferring funds between accounts requires debiting one row and
crediting another inside a single transaction. If either step fails, the database
rolls back both changes.

Comparisons and Practical Examples

A Spreadsheet can store small tables but lacks strict integrity rules and concurrent
access controls. A Relational Database is better for multi-user applications with
complex relationships. A Flat File stores records sequentially without declarative
query language support.

Database Lecture 1 prepares students to model entities, write SQL select insert
update delete statements, identify primary and foreign keys, and recognize one to
many and many to many relationship types in real schemas.
""".strip(),
    },
]


def seed_demo_materials() -> None:
    """Upsert demo materials and refresh content_text for courses 101 and 102."""
    ensure_indexes()

    for spec in DEMO_MATERIALS:
        course_id = spec["course_id"]
        material_id = spec["material_id"]
        text = spec["content"]

        material_repository.upsert(
            {
                "course_id": course_id,
                "material_id": material_id,
                "title": spec["title"],
                "course_name": spec["course_name"],
                "file_type": spec["file_type"],
                "material_type": "lecture",
                "semantic_tags": ["lecture", "seeded_demo"],
                "category": "lecture",
                "seed_source": "demo_test",
            }
        )
        material_repository.set_content(course_id, material_id, text)
        word_count = len(text.split())
        print(
            f"Seeded demo material: course {course_id} / {material_id} "
            f"({spec['title']}, {len(text)} chars, ~{word_count} words, ready for quiz)."
        )


if __name__ == "__main__":
    seed_demo_materials()
