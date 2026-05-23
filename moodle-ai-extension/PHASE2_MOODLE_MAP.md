## Dashboard
URL: /my/
Key Elements:
- Course cards container
- Course title
- Course link

- Course link selector: a[href*="course/view.php"]
- Course container (optional): .myc-item.course-card


## Course Page
URL: /course/view.php
Key Elements:
- Course name
- Sections
- Activity list
const courseName = document.querySelector("h1")?.innerText.trim();
document.querySelectorAll(".activity.assign");


## Assignments Page
URL: /mod/assign/
Key Elements:
- Assignment title
- Due date
- Submission status

- Link selector: a[href*="/mod/assign/view.php"]
- Container: .activity.assign
- Due date: extracted from container text (regex-based)


## Grades Page
URL: /grade/report/user/
Key Elements:
- Item name
- Grade value
- Max grade

- Grade rows: table.user-grade tbody tr
- Item name: th.column-itemname
- Grade value: td.column-grade
- Max grade: td.column-range

