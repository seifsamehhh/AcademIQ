# AcademIQ Backend - Project Overview

## 📋 Project Description

**AcademIQ** is an intelligent student risk prediction and intervention system built as a FastAPI backend service. It analyzes student engagement data from Moodle LMS to identify at-risk students and provide personalized recommendations for intervention.

### Core Purpose
- **Data Collection**: Ingests raw Moodle learning analytics (sessions, assignments, quizzes, grades)
- **Feature Engineering**: Extracts meaningful engagement metrics from raw data
- **Risk Prediction**: Uses machine learning models to classify students into risk clusters
- **Intervention Recommendations**: Provides actionable insights based on risk assessment

---

## 🏗️ Architecture Overview

### Tech Stack
- **Framework**: FastAPI (Python)
- **ML Libraries**: scikit-learn, joblib, numpy
- **Data Validation**: Pydantic
- **CORS**: Enabled for Chrome Extension communication

### Core Components

#### 1. **Backend Application** (`backend.py`)
Main FastAPI application with CORS middleware configured for the Chrome extension.

**Key Features:**
- Loads pre-trained ML models:
  - `pass_fail_model.pkl` - Pass/fail classification
  - `ai_model.pkl` - Risk clustering model
- Provides RESTful API endpoints
- Handles data ingestion and prediction

#### 2. **Feature Extraction** (`backend.py` - `compute_features()`)
Processes raw Moodle data into engineered features:
- **total_time_spent**: Total session duration in milliseconds
- **active_days**: Number of unique days with activity
- **access_frequency**: Average course visits
- **avg_quiz_score**: Mean quiz performance
- **quiz_score_std**: Quiz score variance
- **avg_assignment_score**: Mean assignment grades
- **late_submission_ratio**: Proportion of late submissions
- **avg_final_grade**: Average course final grades

#### 3. **Risk Prediction** (`predict.py`)
ML prediction endpoint that classifies students into risk clusters (0, 1, 2):
- **Cluster 0**: Low risk – Good academic standing
- **Cluster 1**: Medium risk – Needs focus
- **Cluster 2**: High risk – Immediate intervention needed

#### 4. **Results Storage** (`student_results.py`)
In-memory data store for student assessment results with retrieval endpoints.

---

## 🔗 Chrome Extension Integration

### Connection Architecture

```
Chrome Extension (Moodle)
        ↓
  Send raw Moodle data
        ↓
/ingest endpoint
        ↓
Feature Extraction
        ↓
/predict endpoint
        ↓
ML Model Inference
        ↓
Risk Classification + Recommendations
        ↓
/store_result endpoint
        ↓
Display in Extension UI
```

### CORS Configuration
The backend is configured to accept requests from:
- **Chrome Extension**: `chrome-extension://pelgaliljjfhhboggbncepdblmjobgan`
- **Frontend (dev)**: `http://localhost:3000`
- **Backend (dev)**: `http://localhost:8000`

### Communication Flow

#### Step 1: Data Ingestion
**Endpoint**: `POST /ingest`+

The Chrome extension sends raw Moodle data:
```json
{
  "student_id": "12345",
  "clicks": 150,
  "lastActivity": 1675000000,
  "sessions": [...],
  "courses": {...}
}
```

**Response**: Extracted features ready for ML prediction

#### Step 2: Risk Prediction
**Endpoint**: `POST /predict`

Send engineered features to the ML model:
```json
{
  "total_time_spent": 86400000,
  "active_days": 25,
  "access_frequency": 8.5,
  ...
}
```

**Response**: Risk cluster, encoded value, and personalized recommendation

#### Step 3: Store Results
**Endpoint**: `POST /store_result`

Persist the assessment result for later retrieval:
```json
{
  "student_id": "12345",
  "features": {...},
  "risk_cluster": 1,
  "recommendation": "Medium risk – Focus on weak courses."
}
```

#### Step 4: Retrieve Results
**Endpoint**: `GET /student_results?student_id=12345`

Fetch stored results for a specific student.

---

## 📊 Data Flow Diagram

```
Moodle LMS
    ↓
Chrome Extension (content.js)
    ↓
HTTP POST /ingest
    ↓
compute_features() - Extract 8 metrics
    ↓
HTTP POST /predict
    ↓
[Risk Clustering ML Model]
    ↓
Risk Cluster (0, 1, or 2)
    ↓
generate_recommendation()
    ↓
HTTP POST /store_result
    ↓
In-Memory STUDENT_RESULTS Dict
    ↓
Extension displays recommendation to user
```

---

## 🚀 API Endpoints

| Method | Endpoint | Purpose | Input | Output |
|--------|----------|---------|-------|--------|
| GET | `/` | Health check | None | Status message |
| POST | `/ingest` | Process raw Moodle data | RawMoodlePayload | Extracted features |
| POST | `/predict` | ML prediction | FeaturesPayload | Risk cluster + recommendation |
| POST | `/store_result` | Save student result | StoreResultPayload | Confirmation |
| GET | `/student_results` | Retrieve student data | student_id (query param) | Stored result |

---

## 🔧 Running the Project

### Prerequisites
- Python 3.13+
- Virtual environment activated
- Required packages: `fastapi`, `uvicorn`, `pydantic`, `numpy`, `joblib`, `scikit-learn`

### Start Development Server
```bash
cd backend
python -m uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

### Access API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 📁 File Structure

```
backend/
├── backend.py           # Main FastAPI app with CORS & endpoints
├── predict.py           # ML prediction logic (alternative implementation)
├── student_results.py   # Student data storage & retrieval
├── ingest.py           # Data ingestion utilities
├── pass_fail_model.pkl # Trained binary classifier
├── pass_fail_scaler.pkl # Feature scaler
├── logistic_model.pkl  # Additional ML model
├── sample_input.json   # Example request payload
├── test_request.py     # Testing utilities
└── venv/               # Python virtual environment
```

---

## 🤝 Extension-Backend Workflow Example

1. **Extension detects student page loaded in Moodle**
2. **Extracts engagement data** (sessions, grades, assignments, quizzes)
3. **Sends to `/ingest`** → Receives feature engineering
4. **Sends to `/predict`** → Receives risk assessment
5. **Sends to `/store_result`** → Persists for historical tracking
6. **Displays intervention recommendation** in the extension UI

---

## ⚠️ Current Status

### Working Features ✅
- FastAPI server running with auto-reload
- CORS middleware configured
- Feature extraction pipeline functional
- Prediction logic implemented
- Student results storage operational

### Known Issues ⚠️
- `pass_fail_model.pkl` - scikit-learn import required (resolved)
- `ai_model.pkl` - File not found at `backend/models/ai_model.pkl` (expected in future)

---

## 🔐 Security Notes

- CORS restricted to known origins
- Input validation via Pydantic schemas
- Error handling with HTTPException
- Recommend adding authentication for production

---

**Last Updated**: February 2, 2026  
**Version**: 1.0
