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
2. [Local Development Setup](#-local-development-setup)
3. [API Keys Setup](#-api-keys-setup)
4. [API Endpoints](#-api-endpoints)
5. [Architecture](#-architecture)
6. [Testing](#-testing)
7. [Docker & Cloud Run Deployment](#-docker--cloud-run-deployment)
8. [Gemini Model Configuration](#-gemini-model-configuration)
9. [Project Structure](#-project-structure)

---

## ⚡ Quick Start (GitHub Codespaces)

The fastest way to run NutriOS — zero local setup required.

### Step 1: Create Codespace
1. Push this repo to GitHub
2. Click **Code → Codespaces → Create codespace on main**
3. Wait for the devcontainer to build (~2 min)

### Step 2: Configure Environment
```bash
# The devcontainer auto-copies .env.example to .env
# Edit .env and add your API keys:
nano .env
```

**Minimum required key** (the app works in demo mode without the others):
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### Step 3: Run the Server
```bash
uvicorn main:app --reload --port 8080
```

### Step 4: Test It
```bash
# Health check
curl http://localhost:8080/health

# Get a demo JWT token
curl -X POST "http://localhost:8080/auth/demo-token?user_id=demo&name=YourName"

# Copy the access_token from the response, then:
export TOKEN="paste_your_token_here"

# Get a contextual food nudge
curl -X POST http://localhost:8080/nudge \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"latitude": 37.7749, "longitude": -122.4194, "activity_level": "moderate"}'
```

### Step 5: Explore the API Docs
Open `http://localhost:8080/docs` in your browser for the interactive Swagger UI.

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

# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env with your API keys (see next section)

# 5. Run the server
uvicorn main:app --reload --port 8080
```

The API is now live at **http://localhost:8080** and docs at **http://localhost:8080/docs**

---

## 🔑 API Keys Setup

### Required: Gemini API Key
1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Click **"Create API Key"**
3. Copy the key and add to `.env`:
   ```env
   GEMINI_API_KEY=AIza...
   ```

### Optional: Google Maps API Key
1. Go to [Google Cloud Console → APIs & Services](https://console.cloud.google.com/apis)
2. Enable **"Places API (New)"**
3. Create an API key → Restrict to Places API
4. Add to `.env`:
   ```env
   MAPS_API_KEY=AIza...
   ```

> **Without Maps API:** The app returns demo nearby-place results.

### Optional: Firestore
1. Create a [Firebase project](https://console.firebase.google.com)
2. Enable **Firestore** in Native mode
3. Generate a service account key (JSON)
4. Add to `.env`:
   ```env
   FIRESTORE_PROJECT_ID=your-project-id
   GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
   ```

> **Without Firestore:** The app uses an in-memory database (data resets on restart).

### Optional: Google Calendar
1. Enable [Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com)
2. Set up domain-wide delegation for the service account
3. Add to `.env`:
   ```env
   GOOGLE_CALENDAR_ENABLED=true
   ```

> **Without Calendar:** The app returns realistic time-aware demo events.

---

## 📡 API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | ❌ | Health check for load balancers |
| `GET` | `/docs` | ❌ | Interactive Swagger API docs |
| `POST` | `/auth/demo-token` | ❌ | Generate a JWT token for testing |
| `POST` | `/nudge` | ✅ | Get a contextual food nudge |
| `POST` | `/log/photo` | ✅ | Upload meal photo → auto-log |
| `POST` | `/log/manual` | ✅ | Log meal by text description |
| `POST` | `/coach` | ✅ | Multi-turn food coaching chat |
| `POST` | `/coach?stream=true` | ✅ | Streaming coach (SSE) |
| `GET` | `/report/weekly` | ✅ | Weekly habit report (JSON) |
| `GET` | `/report/weekly?format=html` | ✅ | Weekly habit report (HTML) |
| `GET` | `/profile` | ✅ | Get user profile |
| `PUT` | `/profile` | ✅ | Update user goals |

### Example: Full Demo Flow
```bash
# 1. Get a token
TOKEN=$(curl -s -X POST "http://localhost:8080/auth/demo-token?user_id=alice&name=Alice" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Get a nudge
curl -X POST http://localhost:8080/nudge \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"latitude": 37.7749, "longitude": -122.4194}'

# 3. Log a meal manually
curl -X POST http://localhost:8080/log/manual \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"food_description": "Grilled chicken salad with quinoa", "meal_type": "lunch"}'

# 4. Chat with the coach
curl -X POST http://localhost:8080/coach \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Was my lunch a good choice?", "conversation_history": []}'

# 5. Get weekly report (HTML)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/report/weekly?format=html" > report.html
open report.html
```

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   USER CONTEXT LAYER                     │
│  Location    Schedule    Activity    Meal Log    Goals    │
│ (Maps API) (Calendar) (Reported)  (Firestore) (Profile) │
└────────────────────────┬────────────────────────────────┘
                         │ asyncio.gather()
                         ▼
┌─────────────────────────────────────────────────────────┐
│           BACKEND — FastAPI on Cloud Run                 │
│         JWT Auth · Rate Limit · Context Builder          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              AI ENGINE — Gemini 2.0 Flash                │
│   ┌──────────────┐ ┌─────────────┐ ┌────────────────┐  │
│   │Vision Logging│ │Habit Scoring│ │ Geo-Nudge Eng. │  │
│   │Photo→Macros  │ │Streak·Trend │ │Nearby options  │  │
│   └──────────────┘ └─────────────┘ └────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Key Design Decisions
- **All API calls in parallel** — `asyncio.gather()`, never sequential
- **Dynamic system prompts** — assembled at request time from user context
- **Graceful degradation** — every external service has a demo fallback
- **Fire-and-forget writes** — Firestore meal logs are non-blocking
- **New Gemini SDK** — uses `google-genai` (not the deprecated `google-generativeai`)

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_nudge.py -v

# Run with coverage
pytest tests/ -v --tb=short
```

> **Note:** Tests that call Gemini API require `GEMINI_API_KEY` to be set. Tests that validate input/auth work without any API keys.

---

## 🐳 Docker & Cloud Run Deployment

### Local Docker
```bash
# Build
docker build -t nutrios .

# Run
docker run -p 8080:8080 --env-file .env nutrios

# Test
curl http://localhost:8080/health
```

### Deploy to Cloud Run
```bash
# 1. Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. Build & push
gcloud auth configure-docker
docker tag nutrios gcr.io/YOUR_PROJECT_ID/nutrios
docker push gcr.io/YOUR_PROJECT_ID/nutrios

# 3. Deploy
gcloud run deploy nutrios \
  --image gcr.io/YOUR_PROJECT_ID/nutrios \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key \
  --set-env-vars MAPS_API_KEY=your_key \
  --set-env-vars FIRESTORE_PROJECT_ID=your_project \
  --set-env-vars JWT_SECRET=your_secret

# 4. Verify
curl https://YOUR_CLOUD_RUN_URL/health
```

### CI/CD with Cloud Build
The included `cloudbuild.yaml` auto-deploys on push:
```bash
gcloud builds submit --config cloudbuild.yaml
```

---

## 🤖 Gemini Model Configuration

Change the model in your `.env` file:

```env
# Fast, cost-efficient (recommended for hackathon)
GEMINI_MODEL=gemini-2.0-flash

# Best reasoning + vision quality
GEMINI_MODEL=gemini-2.5-flash
```

Both models support all NutriOS features including vision (photo food logging).

---

## 📂 Project Structure

```
├── main.py                    # FastAPI app entrypoint
├── config.py                  # Centralized settings (pydantic-settings)
├── routers/
│   ├── nudge.py               # POST /nudge — contextual food advice
│   ├── log.py                 # POST /log/photo + /log/manual
│   ├── coach.py               # POST /coach — multi-turn chat
│   └── report.py              # GET /report/weekly
├── services/
│   ├── gemini.py              # Gemini AI (new google-genai SDK)
│   ├── context.py             # Async context aggregator
│   ├── maps.py                # Google Maps Places API v2
│   ├── calendar_svc.py        # Google Calendar + demo fallback
│   └── firestore_svc.py       # Firestore + in-memory fallback
├── models/
│   └── schemas.py             # All Pydantic v2 models
├── middleware/
│   └── auth.py                # JWT authentication
├── tests/
│   ├── conftest.py            # Shared test fixtures
│   ├── test_nudge.py
│   ├── test_log.py
│   └── test_coach.py
├── .devcontainer/
│   └── devcontainer.json      # GitHub Codespaces config
├── Dockerfile                 # Multi-stage production build
├── cloudbuild.yaml            # Cloud Run CI/CD
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
└── .gitignore
```

---

## 📜 License

Built for the AMD Slingshot Hackathon Promptathon. Powered by Google Gemini AI.
