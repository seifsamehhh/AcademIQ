# Deploying AcademIQ Live

A complete, honest walkthrough to get the whole project running on the public
internet. Hugging Face is used where it actually fits (the FastAPI **backend**
as a Docker Space, and optionally the **models** on the HF Hub); the Next.js
**frontend** goes on Vercel, the **database** stays on MongoDB Atlas, and the
**Chrome extension** is loaded pointing at the live backend.

```
                         ┌─────────────────────────┐
   Browser ───────────►  │  Frontend (Next.js)      │   Vercel
                         │  academiq-frontend.vercel.app │
                         └───────────┬─────────────┘
                                     │  HTTPS + Bearer token
                                     ▼
                         ┌─────────────────────────┐
   Chrome extension ──►  │  Backend (FastAPI)       │   HF Docker Space
                         │  <you>-academiq.hf.space │   (models baked in)
                         └───────────┬─────────────┘
                                     │  TLS
                                     ▼
                         ┌─────────────────────────┐
                         │  MongoDB Atlas           │   Atlas (free tier)
                         └─────────────────────────┘
```

---

## 0. Blockers to clear first (read this)

These will break a naive deploy — handle them before/while following the steps:

1. **Cross-site auth.** Frontend (Vercel) and backend (HF Space) are different
   domains, so the httpOnly session **cookie is not sent cross-site**. The app
   must authenticate with the **Bearer token** the backend already returns on
   login. → see **Step 6** (a small frontend change is required).
2. **Mongo from the Space.** HF Spaces have **dynamic egress IPs**, so Atlas
   must allowlist `0.0.0.0/0`. → **Step 1**.
3. **ML dependencies.** `backend/requirements.txt` currently lists only the
   auth/web deps. Add the ML stack or the models won't load. → **Step 3**.
4. **Student endpoints require auth + synced data.** The backend exposes
   `/courses`, `/dashboard`, `/courses/{id}/performance|insights|materials|quiz`
   via `student_data.py`. Live student pages need a logged-in session **and**
   at least one extension sync for that user (otherwise lists/charts are empty).

---

## 1. MongoDB Atlas — make it reachable

1. Atlas dashboard → your cluster → **Resume** if it shows *Paused* (free
   clusters auto-pause; this is likely the cause of your current TLS error).
2. **Network Access → Add IP Address → Allow access from anywhere**
   (`0.0.0.0/0`). Required because the Space's IP isn't fixed.
3. **Database Access** → confirm the `mohamed2106404_db` user exists and the
   password matches the URI. Rotate it now if you want (the current one is in
   git history) and update `MONGODB_URI` accordingly.
4. Verify locally (venv active):
   ```powershell
   python -c "import certifi; from pymongo import MongoClient; from pymongo.server_api import ServerApi; MongoClient('YOUR_URI', server_api=ServerApi('1'), tlsCAFile=certifi.where()).admin.command('ping'); print('OK')"
   ```
   If this still fails on your network, try a phone hotspot — university/work
   networks often block port 27017.

---

## 2. (Optional) Models on the Hugging Face Hub

The trained models are only ~17 MB and are already committed, so the simplest
path is to **bake them into the Docker image** (the provided `Dockerfile`
already does `COPY models/`). Skip to Step 3 if that's fine.

If you specifically want the models on Hugging Face (keeps large files out of
git, lets you version models independently):

```powershell
pip install huggingface_hub
huggingface-cli login            # paste a token from huggingface.co/settings/tokens
huggingface-cli upload <you>/academiq-models ./models . --repo-type model
```

Then load them at runtime instead of from disk (sketch — ask me to wire this
into `performance_predict.py` / `grade_risk_predict.py`):

```python
from huggingface_hub import hf_hub_download
path = hf_hub_download(repo_id="<you>/academiq-models",
                       filename="performance_model/model_calibrated.pkl",
                       token=os.environ.get("HF_TOKEN"))
```

---

## 3. Complete the backend requirements

Add the ML stack to `backend/requirements.txt` (the auth deps are already
there). Minimum for the performance model + ingest:

```
scikit-learn
shap
joblib
pandas
```

Add `tensorflow-cpu` **only if** you need the grade/risk model live — it makes
the image large/slow; otherwise that endpoint returns 503 (handled gracefully).

> Ask me to finalise `requirements.txt` with pinned versions if you want.

---

## 4. Backend → Hugging Face Docker Space

1. Create the Space: huggingface.co → **New → Space** → **SDK: Docker** →
   *blank* template → name it e.g. `academiq`.
2. The Space is its own git repo. Put **`Dockerfile` + `backend/` + `models/`**
   at its root. Two easy ways:
   - **Clone & copy:** `git clone https://huggingface.co/spaces/<you>/academiq`,
     copy the repo's `Dockerfile`, `backend/`, `models/` into it, commit, push.
   - **Connect GitHub:** push AcademIQ to GitHub and link the repo in the Space
     settings (the root `Dockerfile` + `.dockerignore` here already trim the
     image to just `backend/` + `models/`).
3. **Space → Settings → Variables and secrets** — add (as *Secrets*):
   ```
   MONGODB_URI            = mongodb+srv://...        # your Atlas URI
   MONGODB_DB_NAME        = todo_db
   ALLOWED_ORIGINS        = https://<your-vercel-app>.vercel.app
   SESSION_COOKIE_SECURE  = true
   SESSION_COOKIE_SAMESITE= none
   APP_LOGIN_URL          = https://<your-vercel-app>.vercel.app/signin
   ADMIN_EMAIL            = admin@academiq.local
   ADMIN_PASSWORD         = <a strong password>
   # SMTP_* if you want real account-creation emails
   ```
4. Push. The Space builds the image and starts uvicorn on **port 7860**. Your
   API is then at `https://<you>-academiq.hf.space` (see `/docs`).

> Note: free Spaces **sleep** when idle and cold-start on the next request, and
> their disk is ephemeral — fine here because all state lives in Atlas.

---

## 5. Seed the admin on the Space (no shell)

Free Spaces don't give you a terminal, so run the seeder **once at startup**.
Ask me to add this env-gated, idempotent hook to `main.py`:

```python
# main.py startup — runs only when BOOTSTRAP_ADMIN=true, safe to leave on
import os
if os.environ.get("BOOTSTRAP_ADMIN", "").lower() == "true":
    from app.scripts.seed_admin import seed_admin
    try: seed_admin()
    except Exception as e: print("admin bootstrap skipped:", e)
```

Set `BOOTSTRAP_ADMIN=true` in the Space secrets, restart once, then log in with
`ADMIN_EMAIL` / `ADMIN_PASSWORD`.

---

## 6. Cross-domain auth — switch the frontend to Bearer (required)

Because the cookie can't travel cross-site, the frontend must send the token
returned by `/api/auth/login` as `Authorization: Bearer <token>`. The backend
**already accepts** this (see `auth.py._extract_token`). The change is on the
frontend:

- on login, store `result.token` (e.g. `localStorage`),
- have `api.ts.request()` attach `Authorization: Bearer <token>` when present,
- clear it on logout.

> This is a focused change to `lib/api.ts` + `UserContext`/`signin`. **Ask me to
> implement it** — it's needed for the live deploy to authenticate at all.

---

## 7. Frontend → Vercel

1. Push AcademIQ to GitHub. In Vercel → **Add New Project** → import the repo.
2. **Root Directory** = `front-end`. Framework auto-detects Next.js.
3. **Environment Variables:**
   ```
   NEXT_PUBLIC_API_BASE_URL = https://<you>-academiq.hf.space
   NEXT_PUBLIC_USE_MOCK     = false
   ```
4. Deploy. You get `https://<your-vercel-app>.vercel.app`.
5. Go back and make sure the Space's `ALLOWED_ORIGINS` / `APP_LOGIN_URL` use this
   exact Vercel URL, then restart the Space.

---

## 8. Chrome extension → point at the live backend

In `moodle-ai-extension/popup.js`, change:
```js
const BACKEND_URL = "https://<you>-academiq.hf.space/raw-moodle-payloads";
```
Reload the unpacked extension. (For real distribution, publish to the Chrome Web
Store; `host_permissions` already allows all URLs.)

---

## 9. Verify the live deployment

1. `GET https://<you>-academiq.hf.space/health` → `{"status":"ok","database":"connected"}`.
2. Open the Vercel URL → `/signin` → log in as the admin → lands on `/admin`,
   and `/admin/users` shows real Atlas users (create/delete persist).
3. From a Moodle page, extension **Sync to Backend** → a `student` account is
   auto-provisioned (check the `users` collection); the credentials email is
   logged in the Space logs (or sent if SMTP is set).
4. Browser devtools → Network → confirm requests carry the `Authorization`
   header and return 200 (not CORS/401 errors).

---

## 10. What's still needed for a *fully* working live app

| Item | Status | Action |
| --- | --- | --- |
| Auth + admin dashboard | ✅ works live | — |
| Bearer-token frontend auth | ⛔ required | ask me to implement (Step 6) |
| `requirements.txt` ML deps | ⛔ required | ask me to finalise (Step 3) |
| Startup admin bootstrap | ⛔ for Spaces | ask me to add (Step 5) |
| Student pages (`/dashboard`, `/performance`, `/insights`, `/quiz`) | ✅ endpoints exist | need live auth + extension sync + ML deps |
| Mongo allowlist + resume | ⚠️ config | Step 1 |

The three ⛔ "ask me to implement" items are quick code changes — say the word
and I'll make them so the deploy actually authenticates and serves models.
