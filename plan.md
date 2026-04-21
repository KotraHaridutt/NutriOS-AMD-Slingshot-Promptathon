# NutriOS — Promptathon Build Plan
> **Swap model:** Change `gemini-2.0-flash` or `gemini-2.5-flash` everywhere you see `MODEL_NAME` below.

---

## SYSTEM PROMPT FOR BUILDER

You are building **NutriOS** — a *context-aware food intelligence system* deployed on **Google Cloud Run**. This is NOT a calorie tracker. The core insight is: **most food apps help you log what you ate. NutriOS helps you decide what you're about to eat — based on your schedule, location, activity, and past patterns.**

**Stack:** Python (FastAPI) · Gemini API (`MODEL_NAME`) · Google Maps Places API · Google Calendar API · Firestore · Cloud Run · Docker

> 🔁 **Replace `MODEL_NAME` with:**
> - `gemini-2.0-flash` — faster, cost-efficient
> - `gemini-2.5-flash` — best reasoning + vision quality

---

## WHAT TO BUILD

### Core Feature 1 — Contextual Nudge Engine
At lunchtime, NutriOS doesn't ask "what did you eat?" It proactively checks:
- What the user has on their Google Calendar next (a workout? a meeting? a flight?)
- Their GPS-approximate location (office district? home?)
- Their activity from the past 24h (sedentary vs active)
- Their last 7 days of meals from Firestore

Then Gemini generates a single, specific, actionable food nudge.

**Example output:** *"You have a 3pm back-to-back. High-protein, low-carb lunch now — try the salad at [Place X] 200m away."*

### Core Feature 2 — Vision Food Logging
User takes a photo of their meal. Gemini Vision identifies it, estimates macros, logs to Firestore. No manual entry.

### Core Feature 3 — Conversational Food Coach
Multi-turn chat powered by Gemini. Context window includes user's meal history, goals, and today's schedule. The coach gives advice that is specific to *this person, today* — not generic.

### Core Feature 4 — Habit Scoring & Weekly Report
A behavioral scoring algorithm that rewards consistency, variety, and timing — not just calories. Streak tracking. Weekly PDF/HTML report auto-generated.

---

## SYSTEM DESIGN

### Architecture Flow

```
User HTTP Request
  → FastAPI (Cloud Run) — Auth middleware (JWT), rate limiting
    → Context Aggregator — parallel fetch:
        Calendar API + Firestore meal log + user profile
      → Gemini MODEL_NAME — system prompt includes aggregated context
        → Response streamed back to user
          → Firestore write (async, non-blocking)
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   USER CONTEXT LAYER                    │
│  Location    Schedule    Activity    Meal Log    Goals   │
│ (Maps API) (Calendar) (Google Fit) (Firestore) (Profile)│
└────────────────────────┬────────────────────────────────┘
                         │ asyncio.gather()
                         ▼
┌─────────────────────────────────────────────────────────┐
│           BACKEND — FastAPI on Cloud Run                │
│         JWT Auth · Rate Limit · Context Builder         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              AI ENGINE — Gemini MODEL_NAME              │
│   ┌──────────────┐ ┌─────────────┐ ┌────────────────┐  │
│   │Vision Logging│ │Habit Scoring│ │ Geo-Nudge Eng. │  │
│   │Photo→Macros  │ │Streak·Trend │ │Nearby options  │  │
│   └──────────────┘ └─────────────┘ └────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│               GOOGLE SERVICES LAYER                     │
│  Maps Platform  Firestore  Calendar API  Cloud Run      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│               OUTPUT — BEHAVIORAL NUDGES                │
│  Proactive Nudge   Chat Coach   Weekly Report           │
│ "Lunch in 30min"  Conversational  Habit trends·score   │
└────────────────────────┬────────────────────────────────┘
                         │ feedback loop
                         └──────────────────────────────┐
                                                        │
                         ┌──────────────────────────────┘
                         ▼
              [Back to Context Aggregator]
```

### Key Design Decisions

- All Google API calls are made in **parallel** using `asyncio.gather()` — never sequential
- Gemini **system prompt is dynamically assembled** at request time from user context
- Firestore document structure: `users/{uid}/meals/{date}/{mealId}` + `users/{uid}/profile`
- Environment config via `.env` — never hardcode keys
- **Multi-stage Dockerfile** (build stage + slim runtime stage)
- `cloudbuild.yaml` for CI/CD to Cloud Run

---

## FILE STRUCTURE

```
nutrios/
├── main.py                    # FastAPI app entrypoint
├── routers/
│   ├── nudge.py               # POST /nudge — contextual food advice
│   ├── log.py                 # POST /log/photo + POST /log/manual
│   ├── coach.py               # POST /coach — multi-turn chat
│   └── report.py              # GET /report/weekly
├── services/
│   ├── gemini.py              # All Gemini API calls + prompt assembly
│   ├── context.py             # Async context aggregator
│   ├── maps.py                # Google Maps Places nearby search
│   ├── calendar_svc.py        # Google Calendar — next 3 events
│   └── firestore_svc.py       # DB reads/writes
├── models/
│   └── schemas.py             # Pydantic models for all request/response
├── middleware/
│   └── auth.py                # JWT verification middleware
├── tests/
│   ├── test_nudge.py
│   ├── test_log.py
│   └── test_coach.py
├── Dockerfile                 # Multi-stage build
├── cloudbuild.yaml            # Cloud Run deploy pipeline
├── .env.example               # Template — never .env itself
├── requirements.txt
└── README.md                  # GitHub Codespaces setup instructions
```

---

## CODE REQUIREMENTS

### Code Quality
- Type hints on all functions
- Pydantic schemas for all inputs/outputs
- Docstrings on all service functions
- Separation of concerns: routers call services, services call external APIs

### Security
- JWT middleware on all routes except `/health`
- All secrets via `os.getenv()` + `.env.example` committed, never `.env`
- CORS restricted to known origins
- Input validation via Pydantic

### Efficiency
- `asyncio.gather()` for all parallel Google API calls
- Gemini streaming responses (`stream=True`) for chat
- Firestore writes are fire-and-forget (non-blocking)

### Testing
- pytest with `httpx.AsyncClient` for route tests
- Mock Gemini and Firestore in unit tests
- At least one test per router

### Accessibility
- All API responses include human-readable `message` field
- HTML report uses semantic HTML with ARIA labels
- Error messages are plain English, not stack traces

### Google Services Integration (mandatory for judging)
- **Gemini MODEL_NAME**: nudge generation, vision logging, chat coach
- **Google Maps Places API**: nearby healthy restaurant lookup
- **Google Calendar API**: schedule context for nudges
- **Firestore**: all persistent storage
- **Cloud Run**: deployment target

---

## GEMINI MODEL SWAP GUIDE

In `services/gemini.py`, find this line and update it:

```python
# Change this:
MODEL_NAME = "gemini-1.5-pro"

# To one of these:
MODEL_NAME = "gemini-2.0-flash"       # Fast, cost-efficient, great for nudges
MODEL_NAME = "gemini-2.5-flash"       # Best reasoning + vision quality
```

Also update in `requirements.txt` to ensure you're on the latest SDK:

```
google-generativeai>=0.8.0
```

And update the Gemini client call in `services/gemini.py`:

```python
import google.generativeai as genai
import os

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Use whichever model you chose:
model = genai.GenerativeModel("gemini-2.0-flash")
# or
model = genai.GenerativeModel("gemini-2.5-flash")
```

For vision/multimodal (photo food logging), the call stays the same — both 2.0 flash and 2.5 flash support vision:

```python
response = model.generate_content([
    "Identify this food, estimate macros (calories, protein, carbs, fat), and return JSON.",
    image_part  # PIL Image or base64 bytes
])
```

---

## KEY API ROUTES

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/health` | Health check (no auth) |
| POST | `/nudge` | Get contextual food nudge for right now |
| POST | `/log/photo` | Upload meal photo → auto-logged |
| POST | `/log/manual` | Log meal by text description |
| POST | `/coach` | Multi-turn food coaching chat |
| GET | `/report/weekly` | Get weekly habit report (HTML/JSON) |
| GET | `/profile` | Get user profile + goals |
| PUT | `/profile` | Update user goals |

---

## GEMINI PROMPT TEMPLATE

This is how `services/gemini.py` assembles the dynamic nudge prompt:

```python
NUDGE_SYSTEM_PROMPT = """
You are NutriOS, a personal food intelligence assistant.
You have access to the user's full context below.
Generate ONE specific, actionable food recommendation for right now.
Be direct. Include a nearby place if available. Max 2 sentences.

USER CONTEXT:
- Name: {name}
- Goals: {goals}
- Next calendar event: {next_event} (in {time_until} minutes)
- Location: {location_description}
- Nearby healthy options: {nearby_places}
- Last meal logged: {last_meal} ({hours_since}h ago)
- Today's activity: {activity_summary}
- Weekly pattern: {pattern_summary}

Respond with a nudge that accounts for their upcoming schedule and energy needs.
"""
```

---

## WHAT MAKES THIS DIFFERENT FROM EVERY OTHER SUBMISSION

| Axis | Common submission | NutriOS |
|------|-------------------|---------|
| Trigger | User opens app | Time-aware proactive nudge |
| Intelligence | Static meal database | Gemini context window = YOUR schedule + location + history |
| Logging | Manual text entry | Gemini Vision — photo to macros |
| Advice | Generic "eat more veggies" | "You have a run at 6pm, eat carbs now, here's what's nearby" |
| Scoring | Calories only | Behavioral habit score — timing, variety, consistency |

---

## ENVIRONMENT FILE TEMPLATE (.env.example)

```env
# Gemini
GEMINI_API_KEY=your_gemini_api_key_here

# Google Maps
MAPS_API_KEY=your_maps_api_key_here

# Google Calendar + Firestore (service account)
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json

# Firebase / Firestore
FIRESTORE_PROJECT_ID=your_gcp_project_id

# Auth
JWT_SECRET=your_jwt_secret_here
JWT_ALGORITHM=HS256

# App
PORT=8080
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000,https://your-frontend.com
```

---

## DOCKERFILE (Multi-stage)

```dockerfile
# Stage 1: Build
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## CLOUD RUN DEPLOY CHECKLIST

```bash
# 1. Build container locally and test
docker build -t nutrios .
docker run -p 8080:8080 --env-file .env nutrios
curl http://localhost:8080/health

# 2. Authenticate with GCP
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 3. Push to Artifact Registry
gcloud auth configure-docker
docker tag nutrios gcr.io/YOUR_PROJECT_ID/nutrios
docker push gcr.io/YOUR_PROJECT_ID/nutrios

# 4. Deploy to Cloud Run
gcloud run deploy nutrios \
  --image gcr.io/YOUR_PROJECT_ID/nutrios \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=xxx \
  --set-env-vars MAPS_API_KEY=xxx \
  --set-env-vars FIRESTORE_PROJECT_ID=xxx \
  --set-env-vars JWT_SECRET=xxx

# 5. Verify deployment
curl https://YOUR_CLOUD_RUN_URL/health
```

---

## GITHUB CODESPACES SETUP

Add this to your repo as `.devcontainer/devcontainer.json`:

```json
{
  "name": "NutriOS Dev",
  "image": "mcr.microsoft.com/devcontainers/python:3.11",
  "postCreateCommand": "pip install -r requirements.txt",
  "forwardPorts": [8080],
  "remoteEnv": {
    "PORT": "8080"
  }
}
```

Then in Codespaces:
```bash
cp .env.example .env
# Fill in your API keys in .env
uvicorn main:app --reload --port 8080
```

---

## JUDGING CRITERIA CHECKLIST

- [x] **Code Quality** — Type hints, Pydantic, docstrings, clean separation of concerns
- [x] **Security** — JWT middleware, env secrets, CORS, input validation
- [x] **Efficiency** — Async parallel API calls, Gemini streaming, non-blocking DB writes
- [x] **Testing** — pytest suite with mocked external services
- [x] **Accessibility** — Semantic HTML report, plain-English errors, human-readable responses
- [x] **Google Services** — Gemini (AI), Maps (geo-nudge), Calendar (schedule), Firestore (storage), Cloud Run (deploy)
- [x] **Problem Alignment** — Context-aware food decisions, behavioral habit building, real-world usability

---

## BUILD ORDER FOR AI BUILDER

Tell your AI builder to generate files in this exact order:

1. `models/schemas.py` — all Pydantic models first
2. `services/firestore_svc.py` — base DB layer
3. `services/gemini.py` — AI service with `MODEL_NAME` set to your chosen model
4. `services/maps.py` — Places API integration
5. `services/calendar_svc.py` — Calendar API integration
6. `services/context.py` — async aggregator calling all above services
7. `middleware/auth.py` — JWT middleware
8. `routers/nudge.py` — main nudge route
9. `routers/log.py` — photo + manual logging
10. `routers/coach.py` — multi-turn chat
11. `routers/report.py` — weekly report
12. `main.py` — FastAPI app wiring everything together
13. `tests/` — one test file per router
14. `Dockerfile` — multi-stage build
15. `cloudbuild.yaml` — CI/CD pipeline
16. `.env.example` — secrets template
17. `README.md` — full setup + deploy guide
