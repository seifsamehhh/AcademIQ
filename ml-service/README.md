# AcademIQ ML Service

Independent FastAPI service for **Performance Model v4** inference.  
Designed for **Hugging Face Docker Space** (not Gradio, not Streamlit).

This service is **not** connected to the Vercel API backend yet.

---

## Model inventory

| Item | Location |
|------|----------|
| Purpose | High-performer classification → `predictedGrade`, `status`, `probability` |
| Artifacts | `models/performance_model/*.pkl` (monorepo root) or `ml-service/models/performance_model/` |
| Loader | `ml-service/app/performance_model.py` |
| Training reference | `ai/Performance Model/PerformanceModel_v4.ipynb` |

### Required artifacts (~12 MB total)

- `model_calibrated.pkl` — primary classifier
- `model_raw.pkl` — raw model (loaded for parity with training pipeline)
- `shap_explainer.pkl` — SHAP explainer (loaded; not exposed in MVP API response)
- `features_behavioral.pkl` — feature column list
- `train_medians.pkl`, `hp_train_medians.pkl` — engineering medians

### Required Python packages

See `ml-service/requirements.txt`:

- `fastapi`, `uvicorn`
- `scikit-learn`, `joblib`, `pandas`, `numpy`
- `lightgbm`, `shap`

---

## API

### `GET /health`

```json
{
  "status": "ok",
  "service": "academiq-ml",
  "model": "performance_model_v4",
  "mlAvailable": true,
  "engine": "ml",
  "modelDir": "/app/models/performance_model",
  "message": null
}
```

When artifacts are missing, `mlAvailable` is `false` and `message` explains why.

### `POST /predict/performance`

Request:

```json
{
  "features": {
    "all_clicks": 120,
    "active_days": 15,
    "access_frequency": 2.5,
    "material_clicks": 40,
    "quiz_attempts": 5,
    "assignment_submissions": 3,
    "total_time_spent": 7200,
    "procrastination_index": 1.2,
    "late_submission_count": 0
  }
}
```

Response (model loaded):

```json
{
  "mlAvailable": true,
  "engine": "ml",
  "predictedGrade": 72,
  "status": "Good",
  "probability": 0.72,
  "confidence": 72.0,
  "message": null,
  "classification": "High Performer"
}
```

Response (placeholder — artifacts not loaded):

```json
{
  "mlAvailable": false,
  "engine": "placeholder",
  "predictedGrade": null,
  "status": null,
  "probability": null,
  "confidence": null,
  "message": "Performance Model v4 artifacts are not loaded...",
  "classification": null
}
```

---

## Run locally

```bash
cd ml-service
pip install -r requirements.txt

# Option A: point at monorepo artifacts (no copy)
set MODEL_DIR=..\models\performance_model        # Windows
# export MODEL_DIR=../models/performance_model   # macOS/Linux

uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

```bash
# Option B: copy artifacts into ml-service/models/performance_model/ first (see models/README.md)
uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

Open http://127.0.0.1:7860/docs for Swagger UI.

---

## Local tests

```bash
# Import check
python -c "from app.main import app; print('import ok', app.title)"

# Health
curl http://127.0.0.1:7860/health

# Predict (sample features)
curl -X POST http://127.0.0.1:7860/predict/performance \
  -H "Content-Type: application/json" \
  -d "{\"features\":{\"all_clicks\":120,\"active_days\":15,\"access_frequency\":2.5,\"material_clicks\":40,\"quiz_attempts\":5,\"assignment_submissions\":3,\"total_time_spent\":7200,\"procrastination_index\":1.2,\"late_submission_count\":0}}"
```

---

## Docker (local)

From **monorepo root** (copies `models/performance_model` into the image):

```bash
docker build -f ml-service/Dockerfile -t academiq-ml .
docker run --rm -p 7860:7860 academiq-ml
curl http://127.0.0.1:7860/health
```

---

## Deploy to Hugging Face Docker Space

### 1. Prepare a deployable tree

HF Docker Space needs the Dockerfile, app, requirements, and model artifacts in one repo.

**Option A — deploy `ml-service/` as its own HF repo**

1. Create a new Hugging Face model/space repo (type: **Docker**).
2. Copy into that repo:
   - `ml-service/Dockerfile` (adjust `COPY` paths if root is `ml-service/`)
   - `ml-service/app/`
   - `ml-service/requirements.txt`
   - `ml-service/models/performance_model/*.pkl` (all six `.pkl` files)

Standalone Dockerfile (if repo root is `ml-service/`):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV MODEL_DIR=/app/models/performance_model PORT=7860
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY models/performance_model ./models/performance_model
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

**Option B — monorepo subfolder**

Push only `ml-service/` plus copied `models/performance_model/` to the Space repo.

### 2. Create the Space

1. Go to https://huggingface.co/new-space
2. Name: e.g. `academiq-ml`
3. SDK: **Docker** (not Gradio / Streamlit)
4. Visibility: Public or Private
5. Clone the empty repo and push your prepared files.

### 3. HF Space settings

- Default port **7860** is required (already set in Dockerfile `CMD`).
- No `app_port` override needed if CMD uses 7860.
- Optional Space secret: `MODEL_DIR=/app/models/performance_model` (default in image).

### 4. Build and verify

1. Wait for HF to build the Docker image.
2. Open `https://<your-space>.hf.space/health`
3. Expect `mlAvailable: true` if artifacts were copied correctly.
4. Test `POST https://<your-space>.hf.space/predict/performance` with the sample JSON above.

### 5. Do not connect Vercel yet

The Vercel backend will call this service in a later phase via `ML_SERVICE_URL` + API key.  
Until then, this Space is standalone for ML validation only.

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MODEL_DIR` | `/app/models/performance_model` | Artifact directory |
| `PORT` | `7860` | HF Space HTTP port (set by CMD) |

No MongoDB. No JWT. Stateless inference only.
