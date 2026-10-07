# AgentLab: Complete Project Guide

This document explains the project end-to-end: what it does, how it works, how to run it locally, how the system is structured, and how to extend it.

## 1) What this project is

AgentLab is an AI-powered research assistant that:

- accepts a research topic from the user,
- optionally uses uploaded documents as supporting context,
- searches the web for sources,
- processes the results through multiple AI stages,
- produces a final research report with evidence,
- shows progress in real time while the work is being executed.

This is not a simple chat app. It is a multi-step AI pipeline with a backend orchestrator, frontend UI, and several agent roles working in sequence.

## 2) High-level architecture

The app is split into three main layers:

1. Frontend
   - built with Next.js and React
   - handles the UI and user interaction
   - sends research requests and uploads files

2. Backend API
   - built with FastAPI
   - exposes routes for health checks, uploads, and research jobs
   - manages job state and progress tracking

3. AI workflow
   - uses LangGraph and named agents
   - conducts research, analysis, verification, and final report generation

The main flow is:

- User enters a topic
- User may attach files
- Frontend sends the request to backend
- Backend starts a research job
- Research graph runs stage by stage
- Progress is reported back to frontend
- Final report and sources are returned to the UI

## 3) Stack used

### Frontend
- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- lucide-react
- sonner for toasts
- motion for transitions

### Backend
- Python
- FastAPI
- Pydantic
- LangGraph
- Async Groq for research, analysis, verification, and constrained tasks
- Gemini Flash for report sections, with configured-provider fallback
- Tavily for web search

### Core idea
The application behaves like an orchestration layer around multiple AI steps. The user sees the workflow, but the technical system behind it is a pipeline of specialized agents.

## 4) Project structure

```text
AgentLab/
├── backend/
│   ├── agents/
│   │   ├── analysis_agent.py
│   │   ├── report_agent.py
│   │   ├── research_agent.py
│   │   └── verification_agent.py
│   ├── models/
│   │   ├── research.py
│   │   └── state.py
│   ├── services/
│   │   ├── documents.py
│   │   ├── harness.py
│   │   ├── llm.py
│   │   ├── research.py
│   │   └── source_context.py
│   ├── graph.py
│   ├── main.py
│   └── tools/
│       └── web_search.py
├── docs/
│   ├── PROJECT_GUIDE.md
│   └── document-upload-guide.md
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── package.json
│   └── ...
├── tests/
│   ├── test_harness.py
│   ├── test_health.py
│   └── test_research.py
├── .gitignore
├── README.md
└── requirements.txt or environment setup notes
```

## 5) How the frontend works

The main frontend page is in:

- [frontend/app/page.tsx](../frontend/app/page.tsx)
- [frontend/components/query-form.tsx](../frontend/components/query-form.tsx)
- [frontend/components/pipeline-tracker.tsx](../frontend/components/pipeline-tracker.tsx)
- [frontend/lib/api.ts](../frontend/lib/api.ts)

### Main responsibilities
- collect the user’s research topic
- allow file upload
- validate the input
- send the request to backend
- consume stage progress and streamed report sections
- display the progress and final data

### Typical frontend flow
1. User types a question.
2. User optionally uploads supporting documents.
3. User clicks the main research action.
4. Frontend opens a Server-Sent Events request to `POST /research/stream`.
5. Stage updates advance the pipeline tracker.
6. Completed report sections are shown as they arrive and assembled in report order.
7. The final response replaces the progressive view when the pipeline completes.

## 6) How the backend works

The API entrypoint is:

- [backend/main.py](../backend/main.py)

### Important backend routes

#### GET /
Returns a basic hello-style API status message.

#### GET /health
Used to verify backend health.

#### POST /documents/upload
Receives uploaded files and extracts their text.

#### POST /research/jobs
Creates an async research job.

#### GET /research/jobs/{job_id}
Returns the current job state, including:
- status
- current_step
- completed_steps
- partial_result, updated after each agent finishes
- result
- error

#### POST /research
Direct research call without job tracking for simple usage.

#### POST /research/stream
Streams stage progress, completed research sections, report sections, and the
final result as Server-Sent Events. The existing JSON and job-polling endpoints
remain available to clients that do not use streaming.

## 7) Research job lifecycle

The backend maintains a job store with a thread-safe dictionary.

Each job tracks:
- job_id
- status
- current_step
- completed_steps
- partial_result
- result
- error

When a research request is created:

1. a new job ID is generated
2. the job is stored in memory
3. a background thread runs the research pipeline
4. the job is updated as each stage progresses
5. the frontend polls the job endpoint to get progress

The frontend polls this state and immediately renders completed research,
analysis, verification, report, source, citation, and follow-up sections while
the remaining agents continue.

## 8) Multi-agent pipeline

The orchestration logic is in:

- [backend/graph.py](../backend/graph.py)

The graph runs its primary stages in sequence:

- research
- analysis
- verification
- report

After the report, citation linking and follow-up question generation run in
parallel. The final result view appears once both branches finish.

Each node runs a specialized agent.

### research agent
Responsible for gathering information and building the initial evidence set.

### analysis agent
Examines the findings and structures what matters.

### verification agent
Checks the quality, correctness, and evidence quality of the claim.

### report agent
Creates the final output that the user sees.

This is the heart of the product: a modular system where each stage has a different purpose.

## 9) Document upload workflow

The uploaded document feature is a major upgrade because it allows the model to use the user’s own knowledge base in addition to web search.

### Upload path

Frontend:
- user selects files
- frontend sends them to `/documents/upload`

Backend:
- files are read
- text is extracted
- content is converted into structured document entries
- response returns extracted text and metadata

The extraction logic lives in:

- [backend/services/documents.py](../backend/services/documents.py)

The data model for documents is defined in:

- [backend/models/research.py](../backend/models/research.py)

The system supports text-heavy files such as `.txt`, `.md`, `.csv`, `.json`, and `.pdf` when PDF support is available.

### Why document context matters
Uploaded documents become part of prompt context. The app does not just research from the internet; it can also reason over internal documents, notes, briefs, or research materials.

## 10) How the real-time progress works

The live stage tracking is handled through a progress callback.

Key file:

- [backend/services/harness.py](../backend/services/harness.py)

The backend uses a callback that captures stage transitions like:
- processing
- completed
- failed

Those callbacks update the job state in the memory store. The frontend then polls the job endpoint and transforms that into a visible step indicator.

This solves one of the biggest UX problems in AI apps: users tend to abandon a workflow when they have no idea whether anything is happening.

## 11) Important service files

### backend/services/llm.py
Handles Language Model configuration and connection.

### backend/tools/web_search.py
Runs web search queries and fetches search results.

### backend/services/source_context.py
Helps prepare the context used for source-driven reasoning.

### backend/services/research.py
Builds the combined research input and invokes the LangGraph pipeline.

This file is especially important because it connects all the moving parts together.

## 12) Required environment variables

Before running the app, create the environment variables needed for the external APIs.

The backend needs a Tavily API key for web search. LLM inference can use Gemini,
Groq, or a local Ollama installation. In automatic mode, AgentLab routes long
context, analysis, and verification to Gemini; research and reports to Groq;
and compact question/citation tasks or private content to Ollama. If a provider
fails, it tries another available provider, except for private/local-only
content, which is never sent to a cloud model.

Install Ollama and pull the default lightweight model:

```powershell
winget install --id Ollama.Ollama --exact
ollama pull qwen3:1.7b
```

Then set these values in the backend `.env` file:

```dotenv
TAVILY_API_KEY=your_key_here
LLM_PROVIDER=auto
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:1.7b
```

Configure `GEMINI_API_KEY` and/or `GROQ_API_KEY` to enable those cloud providers.
Keep the Ollama app running during use. To pin all tasks to one provider, set
`LLM_PROVIDER` to `ollama`, `gemini`, or `groq`.

## 13) Local setup instructions

### Step 1: Open a terminal in the project root

```powershell
cd C:\Users\salik\Desktop\AgentLab
```

### Step 2: Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 3: Start the backend

```powershell
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Start the frontend

Open a second terminal:

```powershell
cd C:\Users\salik\Desktop\AgentLab\frontend
npm install
npm run dev
```

The frontend typically runs on port 3000, and the backend on port 8000.

## 14) How to run the app in one go

If you want both services running at the same time:

Terminal 1:

```powershell
cd C:\Users\salik\Desktop\AgentLab
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2:

```powershell
cd C:\Users\salik\Desktop\AgentLab\frontend
npm run dev
```

## 15) Testing and validation

The project includes tests under:

- [tests/test_health.py](../tests/test_health.py)
- [tests/test_harness.py](../tests/test_harness.py)
- [tests/test_research.py](../tests/test_research.py)

To run backend tests:

```powershell
cd C:\Users\salik\Desktop\AgentLab
.\.venv\Scripts\Activate.ps1
pytest -q
```

To run frontend lint and production build:

```powershell
cd C:\Users\salik\Desktop\AgentLab\frontend
npm run lint
npm run build
```

## 16) Common issues and fixes

### Backend not starting
Check whether:
- the virtual environment is active,
- dependencies are installed,
- your Python version supports the project requirements,
- the API keys are present.

### Research flow fails
Usually caused by missing or invalid env keys, such as:
- `GEMINI_API_KEY`
- `TAVILY_API_KEY`

### Frontend cannot connect to backend
Check the backend port and CORS config. The app is configured to allow localhost:3000 by default.

### Turbopack build issue
Using `next dev --webpack` and `next build --webpack` is the stable way in this setup. This avoids the CSS/Turbopack compatibility issue that can appear during local development.

### Job never completes
Usually this means the step execution hit an exception or one of the external APIs timed out. Check server logs in the backend terminal.

## 17) Important product thought process

This project is a good example of a useful AI product architecture because it separates:

- user interaction,
- orchestration,
- evidence retrieval,
- reasoning stages,
- final synthesis.

That separation is what makes the system extensible. It is easier to change one part of the pipeline without breaking the whole app.

## 18) How to extend the project

### Possible next upgrades
- save research history
- let users reopen previous jobs
- add PDF export
- add Markdown export
- support saved workspaces or topics
- allow multiple documents comparison
- improve source citations and traceability
- add custom model selection
- add user authentication

### Good extension points
- [backend/graph.py](../backend/graph.py) for changing workflow order
- [backend/agents](../backend/agents) for new agent capabilities
- [frontend/components](../frontend/components) for new UI blocks
- [frontend/lib/api.ts](../frontend/lib/api.ts) for new requests

## 19) What the app is best at

This app is strongest for:
- research synthesis,
- evidence-backed reporting,
- document-grounded analysis,
- rapid exploration of unfamiliar topics,
- structured AI work that benefits from step-by-step transparency.

## 20) Recommended learning path

If you want to understand the system deeply, follow this order:

1. Read the frontend entry page and API client.
2. Read the backend main API routes.
3. Read the graph orchestration file.
4. Read each agent file one by one.
5. Read the service files for llm, search, and document extraction.
6. Run the app locally and trace the request flow.
7. Add a small feature, then learn what changes in each layer.

This is the best way to understand how an AI product is built in practice.

## 21) Summary

AgentLab is a full-stack AI research product that combines:
- a polished frontend,
- a FastAPI backend,
- a modular multi-agent LangGraph pipeline,
- document-context support,
- job-based progress tracking,
- external web search and LLM reasoning.

The project is already structured well for learning, iteration, and product expansion.

If you want to keep progressing, the next best move is to create one small feature enhancement, such as:
- saved report history,
- source citation improvements,
- export to Markdown/PDF,
- better document management,
- multi-topic comparison view.

That is where the real product quality comes from.
