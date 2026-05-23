# AcademIQ

AI-assisted learning analytics for Moodle: a **Chrome extension** captures activity, a **FastAPI** backend engineers features and runs **risk prediction**, data can live in **MongoDB**, and the **React** dashboard reads live ML results.

## Architecture

```
Moodle (browser)
    → Chrome extension (content + popup)
        → POST /analyze (or /ingest/extension) — FastAPI
            → features → ML model (or heuristic) → /student_results store
    → React web app (VITE_API_URL) — GET /student_results, GET /courses, GET /
```

## Prerequisites

- **Python 3.11+** with `pip`
- **Node.js 18+** and `npm` (for the web UI)
- **MongoDB** locally (`mongodb://127.0.0.1:27017`) or **MongoDB Atlas** URI
- **Chrome** (for the extension)

## 1. Clone and configure

```bash
cd AcademIQ-main
copy .env.example .env
# Edit .env: MONGODB_URI, MONGODB_DB_NAME, CORS_* as needed
```

### Train the risk model (if `backend/models/risk_model.pkl` is missing)

```bash
python backend/scripts/train_risk_model.py
```

## 2. Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.backend:app --reload --host 127.0.0.1 --port 8000
```

- **Swagger UI:** http://127.0.0.1:8000/docs  
- Health: `GET /`  
- Extension pipeline: `POST /analyze` (JSON body = extension export)  
- ML + store: uses same flow as extension **Sync to AcademIQ** button  

## 3. React web app

```bash
cd "grad's front-end"
copy .env.example .env
npm install
npm run dev
```

Open the URL Vite prints (default **http://localhost:8080** per `vite.config.ts`).

- Set **`VITE_API_URL`** in `grad's front-end/.env` to match the API (default `http://127.0.0.1:8000`).
- **Sign in:** use any demo password (6+ chars). The form checks that the **API is reachable** (`GET /`).
- **Student ID:** enter the same ID as in the extension (e.g. `stu_…`). After you **Sync** from the extension, the **Dashboard** and **Grades** show **risk cluster** and **recommendation** from `GET /student_results`.
- **My Courses** menu loads **`GET /courses`** (Mongo). If empty, the UI falls back to demo courses.

## 4. Chrome extension

1. Open `chrome://extensions` → **Load unpacked** → select the folder **`moodle-ai-extension`**.
2. Browse your Moodle site; open the extension popup.
3. Set **API base URL** to `http://127.0.0.1:8000` (or your host).
4. Click **Sync to AcademIQ** — optional **Save snapshot to MongoDB**.

Ensure the backend allows your extension origin (`CORS_ORIGIN_REGEX=chrome-extension://.*` in `.env`).

**Risk line in the popup** shows the result of the **last** “Sync to AcademIQ” call to the API — it is **not** tied to signing in on the website. The web app and extension both talk to the same backend.

**After reloading the extension** in `chrome://extensions`, **refresh any localhost sign-in tab** once. Otherwise `signin-bridge.js` can log `Extension context invalidated` (old page + new extension).

## 5. End-to-end demo (thesis)

1. Start **MongoDB** and the **backend**.
2. Start the **React** app; confirm **Sign in** succeeds (API ping).
3. Use the **extension** on Moodle → **Sync** (same **Student ID** as in Sign in).
4. Refresh the **Dashboard** — risk and features appear.
5. Optional: **MongoDB Compass** → database `todo_db` → collections `raw_moodle_payload_collection`, etc.

## Project layout

| Path | Role |
|------|------|
| `backend/app/backend.py` | Main FastAPI app |
| `backend/app/extension_ingest.py` | Extension JSON → features |
| `backend/models/risk_model.pkl` | Trained classifier (regenerate with `scripts/train_risk_model.py`) |
| `config/database.py` | MongoDB connection |
| `moodle-ai-extension/` | MV3 extension |
| `grad's front-end/` | Vite + React + shadcn UI |

## Security note

This repo is intended for **academic demos**. Do not commit real **`.env`** secrets. Use Atlas IP allowlists and rotate any credentials that were ever exposed.

## Disclaimer

For academic research and demonstration only
