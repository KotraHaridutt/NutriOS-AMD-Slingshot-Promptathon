# 🍎 NutriOS — Context-Aware Food Intelligence System

> **NutriOS doesn't ask "what did you eat?" It tells you what to eat RIGHT NOW — based on your schedule, location, activity, and past patterns.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini-2.0_Flash-purple.svg)](https://ai.google.dev)
[![Cloud Run](https://img.shields.io/badge/Deploy-Cloud_Run-orange.svg)](https://cloud.google.com/run)

---

## 🚀 What Makes NutriOS Different

| Feature | Typical Food App | NutriOS |
|---------|-----------------|---------|
| **Trigger** | User opens app | Proactive, time-aware nudge |
| **Intelligence** | Static meal database | Gemini AI + your schedule + location + history |
| **Logging** | Manual text entry | 📸 Photo → auto-identified macros (Gemini Vision) |
| **Advice** | Generic "eat more veggies" | "You have a run at 6pm, eat carbs now, here's what's nearby" |
| **Scoring** | Calories only | Behavioral habit score — timing, variety, consistency |

---

## 📋 Table of Contents

1. [Quick Start (GitHub Codespaces)](#-quick-start-github-codespaces)
2. [Frontend UI](#-frontend-ui)
3. [Local Development Setup](#-local-development-setup)
4. [API Keys Setup](#-api-keys-setup)
5. [API Endpoints](#-api-endpoints)
6. [Architecture](#-architecture)
7. [Testing](#-testing)
8. [Cloud Run Deployment (Step-by-Step)](#-cloud-run-deployment-step-by-step)
9. [Gemini Model Configuration](#-gemini-model-configuration)
10. [Project Structure](#-project-structure)

---

## ⚡ Quick Start (GitHub Codespaces)

The fastest way to run NutriOS — zero local setup required.

### Step 1: Create Codespace
1. Push this repo to GitHub
2. Click **Code → Codespaces → Create codespace on main**
3. Wait for the devcontainer to build (~2 min — auto-installs everything)

### Step 2: Configure API Key
```bash
# .env is auto-created from .env.example
# Edit and add your Gemini key:
nano .env
```

Add **only this one line** (everything else has demo fallbacks):
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

> 🔑 **Get your key:** [Google AI Studio](https://aistudio.google.com/apikey) → Create API Key (free)

### Step 3: Run the Server
```bash
uvicorn main:app --reload --port 8080
```

### Step 4: Open the UI
- Click the **"Open in Browser"** button when VS Code shows the port notification
- Or go to: `https://YOUR-CODESPACE-NAME-8080.app.github.dev/`
- The app opens with a **beautiful dark-themed UI** — enter your name and click **Get Started**

### Step 5: Try It!
1. **Dashboard** → Click **"Get Nudge"** → get a personalized food recommendation
2. **Log Meal** → Describe a meal or upload a photo → Gemini analyzes it
3. **Coach** → Chat with your AI food coach → personalized advice
4. **Report** → View your weekly habit score and nutrition trends

---

## 🎨 Frontend UI

NutriOS includes a **premium single-page application** served directly from FastAPI:

- **Auth Screen** — Glassmorphism card with gradient animations
- **Dashboard** — Contextual food nudge, nearby places, schedule, quick stats
- **Log Meal** — Photo upload with drag-and-drop + manual text entry
- **Coach** — Real-time chat interface with conversation history
- **Weekly Report** — Habit scores, daily breakdown table, AI insights
- **Profile** — Manage dietary goals, restrictions, calorie targets

**Design features:**
- Dark mode with Inter font
- Glassmorphism effects & gradient accents
- Smooth micro-animations
- Mobile responsive
- Toast notifications
- No external JS dependencies (vanilla JS)

---

## 🛠 Local Development Setup

### Prerequisites
- Python 3.11+
- pip

### Installation
```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/nutrios.git
cd nutrios

# 2. Create virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env — add at minimum: GEMINI_API_KEY

# 5. Run the server
uvicorn main:app --reload --port 8080

# 6. Open in browser
# → http://localhost:8080
```

---

## 🔑 API Keys Setup

| Key | Required? | Where to get it |
|-----|-----------|----------------|
| `GEMINI_API_KEY` | ✅ **Yes** | [Google AI Studio](https://aistudio.google.com/apikey) |
| `MAPS_API_KEY` | ❌ Optional | [Google Cloud Console](https://console.cloud.google.com/apis) → Enable "Places API (New)" |
| `FIRESTORE_PROJECT_ID` | ❌ Optional | [Firebase Console](https://console.firebase.google.com) |
| `GOOGLE_CALENDAR_ENABLED` | ❌ Optional | Requires OAuth2 setup |

> **Without optional keys:** The app uses demo data (mock nearby places, in-memory DB, demo calendar events). Everything works — just not with real data.

---

## 📡 API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/` | ❌ | **Frontend web UI** |
| `GET` | `/health` | ❌ | Health check |
| `GET` | `/docs` | ❌ | Interactive Swagger API docs |
| `POST` | `/auth/demo-token` | ❌ | Generate JWT token for testing |
| `POST` | `/nudge` | ✅ | Contextual food nudge |
| `POST` | `/log/photo` | ✅ | Upload meal photo → auto-log |
| `POST` | `/log/manual` | ✅ | Log meal by text description |
| `POST` | `/coach` | ✅ | Multi-turn food coaching chat |
| `POST` | `/coach?stream=true` | ✅ | Streaming coach (SSE) |
| `GET` | `/report/weekly` | ✅ | Weekly habit report (JSON) |
| `GET` | `/report/weekly?format=html` | ✅ | Weekly habit report (HTML) |
| `GET` | `/profile` | ✅ | Get user profile |
| `PUT` | `/profile` | ✅ | Update user goals |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (SPA)                        │
│  Auth · Dashboard · Log Meal · Coach · Report · Profile  │
│         HTML + CSS + Vanilla JS (served by FastAPI)      │
└────────────────────────┬────────────────────────────────┘
                         │ fetch() API calls
                         ▼
┌─────────────────────────────────────────────────────────┐
│           BACKEND — FastAPI on Cloud Run                 │
│      JWT Auth · Static Files · Context Builder           │
└────────────────────────┬────────────────────────────────┘
                         │ asyncio.gather()
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 GOOGLE SERVICES LAYER                    │
│  Gemini AI    Maps Places    Calendar    Firestore       │
│  (Nudge,      (Nearby        (Schedule   (Meals,        │
│   Vision,      healthy        context)    Profiles)      │
│   Coach)       places)                                   │
└─────────────────────────────────────────────────────────┘
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_nudge.py -v
```

---

## ☁️ Cloud Run Deployment (Step-by-Step)

### Prerequisites
- [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install) installed
- A GCP project with billing enabled
- Your `GEMINI_API_KEY` ready

### Step 1: Authenticate
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Step 2: Enable required APIs
```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  containerregistry.googleapis.com \
  artifactregistry.googleapis.com
```

### Step 3: Build and push Docker image
```bash
# Option A: Build locally and push
docker build -t gcr.io/YOUR_PROJECT_ID/nutrios .
docker push gcr.io/YOUR_PROJECT_ID/nutrios

# Option B: Build in the cloud (no Docker needed locally)
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/nutrios
```

### Step 4: Deploy to Cloud Run
```bash
gcloud run deploy nutrios \
  --image gcr.io/YOUR_PROJECT_ID/nutrios \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "GEMINI_API_KEY=YOUR_GEMINI_KEY" \
  --set-env-vars "GEMINI_MODEL=gemini-2.0-flash" \
  --set-env-vars "ENVIRONMENT=production" \
  --set-env-vars "JWT_SECRET=YOUR_PRODUCTION_SECRET"
```

> **Optional env vars** — add these if you have the keys:
> ```bash
> --set-env-vars "MAPS_API_KEY=YOUR_MAPS_KEY" \
> --set-env-vars "FIRESTORE_PROJECT_ID=YOUR_PROJECT_ID"
> ```

### Step 5: Verify deployment
```bash
# Get your Cloud Run URL
gcloud run services describe nutrios --region us-central1 --format='value(status.url)'

# Test health check
curl https://YOUR_CLOUD_RUN_URL/health

# Open the UI in your browser
open https://YOUR_CLOUD_RUN_URL/
```

### Step 6: Set up CI/CD (automatic deploys)
The included `cloudbuild.yaml` auto-deploys on every push:
```bash
# Connect your GitHub repo to Cloud Build:
# 1. Go to https://console.cloud.google.com/cloud-build/triggers
# 2. Click "Connect Repository" → select GitHub
# 3. Create trigger → set branch to "main"
# 4. Set build config to "cloudbuild.yaml"

# Set secrets as substitution variables:
gcloud builds submit --config cloudbuild.yaml \
  --substitutions _GEMINI_API_KEY="your_key"
```

### Deployment Checklist
- [ ] `gcloud auth login` authenticated
- [ ] GCP project selected with billing enabled
- [ ] Required APIs enabled (Cloud Build, Cloud Run, Container Registry)
- [ ] Docker image built and pushed
- [ ] Cloud Run service deployed with env vars
- [ ] Health check passing at `/health`
- [ ] Frontend UI loading at root URL `/`
- [ ] Demo token working at `/auth/demo-token`

---

## 🤖 Gemini Model Configuration

Change the model in `.env` or Cloud Run env vars:

```env
# Fast, cost-efficient (recommended)
GEMINI_MODEL=gemini-2.0-flash

# Best reasoning + vision quality
GEMINI_MODEL=gemini-2.5-flash
```

---

## 📂 Project Structure

```
├── main.py                        # FastAPI app + static file serving
├── config.py                      # pydantic-settings config
├── static/                        # Frontend UI (SPA)
│   ├── index.html                 # Main HTML page
│   ├── css/style.css              # Premium dark theme
│   └── js/app.js                  # All frontend logic
├── routers/
│   ├── nudge.py                   # POST /nudge
│   ├── log.py                     # POST /log/photo + /log/manual
│   ├── coach.py                   # POST /coach (+ SSE streaming)
│   └── report.py                  # GET /report/weekly
├── services/
│   ├── gemini.py                  # Gemini AI (google-genai SDK)
│   ├── context.py                 # Async parallel context aggregator
│   ├── maps.py                    # Google Maps Places API v2
│   ├── calendar_svc.py            # Calendar + demo fallback
│   └── firestore_svc.py           # Firestore + in-memory fallback
├── models/schemas.py              # All Pydantic v2 models
├── middleware/auth.py             # JWT authentication
├── tests/                         # pytest suite
├── .devcontainer/devcontainer.json # Codespaces config
├── Dockerfile                     # Multi-stage production build
├── cloudbuild.yaml                # Cloud Run CI/CD
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # pytest config
├── .env.example                   # Environment template
└── .gitignore
```

---

## 🏆 Google Services Integration

| Service | Usage | Status |
|---------|-------|--------|
| **Gemini AI** | Nudge generation, Vision food logging, Chat coach, Weekly insights | ✅ Core |
| **Google Maps Places API** | Nearby healthy restaurant lookup | ✅ Integrated (demo fallback) |
| **Google Calendar API** | Schedule-aware context for nudges | ✅ Integrated (demo fallback) |
| **Firestore** | User profiles, meal logs, persistent storage | ✅ Integrated (in-memory fallback) |
| **Cloud Run** | Production deployment target | ✅ Dockerfile + cloudbuild.yaml |

---

Built for the **AMD Slingshot Hackathon Promptathon** · Powered by **Google Gemini AI**
