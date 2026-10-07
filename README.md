# AgentLab

AgentLab is a full-stack AI research assistant that combines a modern frontend, a FastAPI backend, and a multi-agent LangGraph workflow to produce evidence-backed research reports.

## Quick access

- Full project guide: [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md)
- Document upload guide: [docs/document-upload-guide.md](docs/document-upload-guide.md)

## What this project includes

- research topic input and document upload
- multi-stage AI workflow: research → analysis → verification → report
- live progress tracking for each step
- streamed stage progress and report sections
- web search + uploaded document context
- frontend built with Next.js and TypeScript
- backend built with FastAPI and Python

## Run locally

Backend:

```powershell
cd C:\Users\salik\Desktop\AgentLab
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd C:\Users\salik\Desktop\AgentLab\frontend
npm install
npm run dev
```

## CI

GitHub Actions runs backend tests and frontend lint/build checks on every push
and pull request. Run the same checks locally with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm ci
npm run lint
npm run build
```

## Deploy to Vercel and Render

GitHub Actions only runs backend tests and frontend lint/build checks. It does
not deploy either service. After pushing changes, deploy manually:

1. Deploy the backend from the Render dashboard using [render.yaml](render.yaml).
   Set `CORS_ORIGINS` to the production Vercel origin, and configure the
   `TAVILY_API_KEY` plus at least one of `GROQ_API_KEY` or `GEMINI_API_KEY` in
   Render. Do not put secret values in the Blueprint file.
2. Deploy the `frontend` directory from the Vercel dashboard or your local Vercel
   CLI. Set `NEXT_PUBLIC_API_URL` in its production environment to
   `https://agentlab-thst.onrender.com` (no trailing slash), then redeploy so
   the frontend build includes that API URL. Deploy backend changes to Render
   and frontend changes to Vercel independently as needed.

For Vercel preview deployments, add `NEXT_PUBLIC_API_URL` to the Preview
environment as well. Add each Vercel site origin (scheme and hostname only,
without a trailing slash) to Render's comma-separated `CORS_ORIGINS` value.
Vercel deployment protection must allow your users to access the frontend.

## Required environment variables

For web search, add a Tavily API key. For inference, either configure Gemini/Groq
or run a local Ollama model:

```powershell
TAVILY_API_KEY=your_key_here
```

### Automatic LLM routing

AgentLab can route each agent task to the most suitable configured provider:

- Groq for search synthesis, analysis, verification, citations, and follow-up questions.
- Gemini Flash for long-context work and concurrent final-report sections.
- Ollama as a local fallback and for explicitly private content.

In automatic mode it falls back to another available provider if one fails.
Private or explicitly local-only content is never sent to a cloud provider.
For automatic routing, configure any cloud API keys you want available and keep
Ollama running with a model installed:

```powershell
winget install --id Ollama.Ollama --exact
ollama pull qwen3:1.7b
```

Set these values in the backend `.env` file:

```dotenv
LLM_PROVIDER=auto
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:1.7b
```

Keep the Ollama app running while using AgentLab. To pin all tasks to one
provider instead, set `LLM_PROVIDER` to `ollama`, `gemini`, or `groq`.

Optional speed/model settings:

```dotenv
GROQ_FAST_MODEL=openai/gpt-oss-20b
GEMINI_MODEL=gemini-3.8-flash
```

The fast Groq setting applies to analysis and verification; report sections use
Gemini Flash first and fall back to another configured provider if needed.
Provider requests use asynchronous clients, bounded concurrency, per-call
timeouts, and short retries for HTTP 429/5xx responses. Repeated Tavily queries
are cached in memory for five minutes per backend process.
Analysis always tries its preferred cloud provider and the other cloud provider
in sequence. If both fail or return unusable analysis, AgentLab emits a clearly
qualified, evidence-limited analysis from the available research and continues
the pipeline rather than failing that stage.

The frontend uses `POST /research/stream` for Server-Sent Events progress and
completed report sections. The existing `POST /research` JSON response and
`/research/jobs` polling endpoints remain available for existing clients.

## Status

This project is set up for local development, UI polishing, iterating on product flow, and extending into a more complete AI research product.

For the complete architecture and workflow explanation, see [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md).
