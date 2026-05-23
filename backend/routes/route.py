from fastapi import APIRouter, HTTPException
from models.todos import Todo
from models.assignments import Assignment
from models.sessions import Session
from models.quizzes import Quiz
from models.courses import Course
from models.raw_moodle_payload import RawMoodlePayload
from config.database import collection_name, assignments_collection, sessions_collection, quizzes_collection, courses_collection, raw_moodle_payload_collection
from schema.schemas import list_serial, list_assignment_serial, list_session_serial, list_quiz_serial, list_course_serial, list_raw_moodle_payload_serial
from bson import ObjectId

router = APIRouter()


# Get request method
@router.get("/todos")
async def get_todos():
    try:
        todos = list_serial(collection_name.find())
        return todos
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)  # Log to terminal
        raise HTTPException(status_code=500, detail=error_msg)


# Post request method
@router.post("/todos")
async def post_todo(todo: Todo):
    try:
        result = collection_name.insert_one(todo.dict())
        return {"inserted_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")

# Put Request Method
@router.put("/todos/{id}")
async def put_todo(id: str, todo: Todo):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = collection_name.update_one({"_id": oid}, {"$set": todo.dict()})
        return {"matched_count": result.matched_count, "modified_count": result.modified_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")

# Delete Request Method
@router.delete("/todos/{id}")
async def delete_todo(id: str):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = collection_name.delete_one({"_id": oid})
        return {"deleted_count": result.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")




# Get all assignments
@router.get("/assignments")
async def get_assignments():
    try:
        assignments = list_assignment_serial(assignments_collection.find())
        return assignments
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


# Create assignment
@router.post("/assignments")
async def post_assignment(assignment: Assignment):
    try:
        result = assignments_collection.insert_one(assignment.dict())
        return {"inserted_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# Update assignment
@router.put("/assignments/{id}")
async def put_assignment(id: str, assignment: Assignment):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = assignments_collection.update_one({"_id": oid}, {"$set": assignment.dict()})
        return {"matched_count": result.matched_count, "modified_count": result.modified_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# Delete assignment
@router.delete("/assignments/{id}")
async def delete_assignment(id: str):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = assignments_collection.delete_one({"_id": oid})
        return {"deleted_count": result.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# ===========================
# SESSIONS CRUD ENDPOINTS
# ===========================

# Get all sessions
@router.get("/sessions")
async def get_sessions():
    try:
        sessions = list_session_serial(sessions_collection.find())
        return sessions
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


# Create session
@router.post("/sessions")
async def post_session(session: Session):
    try:
        result = sessions_collection.insert_one(session.dict())
        return {"inserted_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# Update session
@router.put("/sessions/{id}")
async def put_session(id: str, session: Session):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = sessions_collection.update_one({"_id": oid}, {"$set": session.dict()})
        return {"matched_count": result.matched_count, "modified_count": result.modified_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# Delete session
@router.delete("/sessions/{id}")
async def delete_session(id: str):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = sessions_collection.delete_one({"_id": oid})
        return {"deleted_count": result.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# ===========================
# QUIZZES CRUD ENDPOINTS
# ===========================

# Get all quizzes
@router.get("/quizzes")
async def get_quizzes():
    try:
        quizzes = list_quiz_serial(quizzes_collection.find())
        return quizzes
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


# Create quiz
@router.post("/quizzes")
async def post_quiz(quiz: Quiz):
    try:
        result = quizzes_collection.insert_one(quiz.dict())
        return {"inserted_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# Update quiz
@router.put("/quizzes/{id}")
async def put_quiz(id: str, quiz: Quiz):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = quizzes_collection.update_one({"_id": oid}, {"$set": quiz.dict()})
        return {"matched_count": result.matched_count, "modified_count": result.modified_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# Delete quiz
@router.delete("/quizzes/{id}")
async def delete_quiz(id: str):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = quizzes_collection.delete_one({"_id": oid})
        return {"deleted_count": result.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# ===========================
# COURSES CRUD ENDPOINTS
# ===========================

# Get all courses
@router.get("/courses")
async def get_courses():
    try:
        courses = list_course_serial(courses_collection.find())
        return courses
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


# Create course
@router.post("/courses")
async def post_course(course: Course):
    try:
        result = courses_collection.insert_one(course.dict())
        return {"inserted_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# Update course
@router.put("/courses/{id}")
async def put_course(id: str, course: Course):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = courses_collection.update_one({"_id": oid}, {"$set": course.dict()})
        return {"matched_count": result.matched_count, "modified_count": result.modified_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# Delete course
@router.delete("/courses/{id}")
async def delete_course(id: str):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = courses_collection.delete_one({"_id": oid})
        return {"deleted_count": result.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")



# RAW MOODLE PAYLOAD CRUD ENDPOINTS


# Get all raw moodle payloads
@router.get("/raw-moodle-payloads")
async def get_raw_moodle_payloads():
    try:
        payloads = list_raw_moodle_payload_serial(raw_moodle_payload_collection.find())
        return payloads
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


# Create raw moodle payload
@router.post("/raw-moodle-payloads")
async def post_raw_moodle_payload(payload: RawMoodlePayload):
    try:
        result = raw_moodle_payload_collection.insert_one(payload.dict())
        return {"inserted_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# Update raw moodle payload
@router.put("/raw-moodle-payloads/{id}")
async def put_raw_moodle_payload(id: str, payload: RawMoodlePayload):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = raw_moodle_payload_collection.update_one({"_id": oid}, {"$set": payload.dict()})
        return {"matched_count": result.matched_count, "modified_count": result.modified_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# Delete raw moodle payload
@router.delete("/raw-moodle-payloads/{id}")
async def delete_raw_moodle_payload(id: str):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")
    
    try:
        result = raw_moodle_payload_collection.delete_one({"_id": oid})
        return {"deleted_count": result.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")