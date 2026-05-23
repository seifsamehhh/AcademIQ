def individual_serial(todo)->dict:
    return {
        "id": str(todo.get("_id", "")),
        "name": todo.get("name", ""),
        "description": todo.get("description", ""),
        "complete": todo.get("complete", False)
    }

def list_serial(todos)->list:
    return [individual_serial(todo) for todo in todos]

def individual_assignment_serial(assignment)->dict:
    return {
        "id": str(assignment.get("_id", "")),
        "title": assignment.get("title", ""),
        "due_date": assignment.get("due_date", ""),
        "submitted": assignment.get("submitted", False),
        "grade": assignment.get("grade", None)
    }

def list_assignment_serial(assignments)->list:
    return [individual_assignment_serial(assignment) for assignment in assignments]

def individual_session_serial(session)->dict:
    return {
        "id": str(session.get("_id", "")),
        "start": session.get("start", 0),
        "end": session.get("end", 0),
        "duration_ms": session.get("duration_ms", 0)
    }

def list_session_serial(sessions)->list:
    return [individual_session_serial(session) for session in sessions]

def individual_quiz_serial(quiz)->dict:
    return {
        "id": str(quiz.get("_id", "")),
        "title": quiz.get("title", ""),
        "attempts": quiz.get("attempts", None),
        "score": quiz.get("score", None),
        "time_spent_ms": quiz.get("time_spent_ms", None)
    }

def list_quiz_serial(quizzes)->list:
    return [individual_quiz_serial(quiz) for quiz in quizzes]

def individual_course_serial(course)->dict:
    return {
        "id": str(course.get("_id", "")),
        "course_id": course.get("course_id", ""),
        "name": course.get("name", ""),
        "visits": course.get("visits", 0),
        "time_spent_ms": course.get("time_spent_ms", 0),
        "final_grade": course.get("final_grade", None)
    }

def list_course_serial(courses)->list:
    return [individual_course_serial(course) for course in courses]

def individual_raw_moodle_payload_serial(payload)->dict:
    return {
        "id": str(payload.get("_id", "")),
        "student_id": payload.get("student_id", None),
        "clicks": payload.get("clicks", 0),
        "lastActivity": payload.get("lastActivity", 0),
        "sessions": payload.get("sessions", []),
        "courses": payload.get("courses", {})
    }

def list_raw_moodle_payload_serial(payloads)->list:
    return [individual_raw_moodle_payload_serial(payload) for payload in payloads]
