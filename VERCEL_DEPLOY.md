# Deploying AcademIQ on Vercel

Two separate Vercel projects: **backend** (FastAPI) and **frontend** (Next.js).

Branch: `production-authentication`

---

## Environment variables

### Backend Vercel project (`backend/` root)

| Variable | Required | Example / notes |
|----------|----------|-----------------|
| `ENVIRONMENT` | Yes | `production` |
| `MONGODB_URI` | Yes | `mongodb+srv://user:pass@cluster.mongodb.net/?appName=Cluster0` |
| `DATABASE_NAME` | Yes | `todo_db` |
| `JWT_SECRET_KEY` | Yes | Long random string — `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_ALGORITHM` | Yes | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | `60` |
| `ALLOWED_ORIGINS` | Yes | `https://your-frontend.vercel.app` (comma-separated for multiple) |
| `BOOTSTRAP_STUDENTS` | Recommended first deploy | `true` — idempotent seed for student1/student2 |

Optional: `BOOTSTRAP_ADMIN`, `SESSION_COOKIE_SECURE`, `APP_LOGIN_URL`, SMTP vars.

### Frontend Vercel project (`front-end/` root)

| Variable | Required | Example / notes |
|----------|----------|-----------------|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | `https://your-backend.vercel.app` (no trailing slash) |
| `NEXT_PUBLIC_USE_MOCK` | Yes | `false` |

**Do not commit** `backend/.env`, `front-end/.env.local`, or any secrets.

---

## Step 1 — MongoDB Atlas

1. Ensure cluster is running.
2. Network Access → allow `0.0.0.0/0` (or Vercel IP ranges if restricted).
3. Copy connection string into backend `MONGODB_URI`.

---

## Step 2 — Deploy backend (FastAPI)

1. Push `production-authentication` to GitHub.
2. [vercel.com/new](https://vercel.com/new) → Import repository.
3. **Root Directory:** `backend`
4. Framework Preset: **Other** (Vercel uses `backend/vercel.json`).
5. Add all **backend environment variables** above.
6. Deploy.
7. Copy the deployment URL, e.g. `https://academiq-api.vercel.app`.
8. Verify:
   ```bash
   curl https://your-backend.vercel.app/health
   ```
   Expected: `{"status":"ok"}`

---

## Step 3 — Deploy frontend (Next.js)

1. New Vercel project → same repo.
2. **Root Directory:** `front-end`
3. Framework: **Next.js** (auto-detected).
4. Environment variables:
   - `NEXT_PUBLIC_API_BASE_URL` = backend URL from Step 2
   - `NEXT_PUBLIC_USE_MOCK` = `false`
5. Deploy.
6. Copy frontend URL, e.g. `https://academiq-frontend.vercel.app`.

---

## Step 4 — Wire CORS

1. Backend project → Settings → Environment Variables.
2. Set `ALLOWED_ORIGINS` to your **frontend** URL:
   ```
   https://academiq-frontend.vercel.app
   ```
3. Redeploy backend.

---

## Step 5 — Smoke test

1. Open `https://your-frontend.vercel.app/signin`
2. Login: `student1` / `password123`
3. Dashboard shows GPA, risk, courses.
4. Logout clears session and returns to sign-in.

---

## Local development

**Backend**
```bash
cd backend
copy .env.example .env
pip install -r requirements.txt
python -m app.scripts.seed_students
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend**
```bash
cd front-end
copy .env.example .env.local
npm install
npm run dev
```

---

## Notes

- ML models are **not** loaded on Vercel auth deploy (`requirements.txt` is slim; ML routes skip mount).
- `/health` always returns `200` with `{"status":"ok"}`.
- `/health/db` checks MongoDB when you need a readiness probe.
- Student auth uses JWT Bearer tokens (no cookie CORS complexity for the dashboard flow).
