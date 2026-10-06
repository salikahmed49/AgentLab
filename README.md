# AgentLab

AgentLab is a full-stack AI research assistant that combines a modern frontend, a FastAPI backend, and a multi-agent LangGraph workflow to produce evidence-backed research reports.

## Quick access

- Full project guide: [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md)
- Document upload guide: [docs/document-upload-guide.md](docs/document-upload-guide.md)

## What this project includes

- research topic input and document upload
- multi-stage AI workflow: research → analysis → verification → report
- live progress tracking for each step
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

The GitHub Actions workflow deploys on pushes to `main`, after both CI jobs pass.
To enable production deployments:

1. Create a Render Blueprint from this repository using [render.yaml](render.yaml).
   Set `CORS_ORIGINS` to the production Vercel origin, and configure the
   `TAVILY_API_KEY` plus at least one of `GROQ_API_KEY` or `GEMINI_API_KEY` in
   Render. Do not put secret values in the Blueprint file.
2. Create/import the `frontend` directory as a Vercel project. Set
   `NEXT_PUBLIC_API_URL` in its production environment to the Render service URL,
   then redeploy once so the frontend build includes that API URL.
3. Add these repository secrets under **Settings → Secrets and variables →
   Actions**:
   - `RENDER_DEPLOY_HOOK_URL` — the Render service's deploy hook URL.
   - `VERCEL_TOKEN` — a Vercel access token.
   - `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` — the IDs from Vercel project settings.

After setup, each successful push to `main` triggers the Render backend deploy
and builds/deploys the frontend to Vercel. Pull requests run CI only.

## Required environment variables

For web search, add a Tavily API key. For inference, either configure Gemini/Groq
or run a local Ollama model:

```powershell
TAVILY_API_KEY=your_key_here
```

### Automatic LLM routing

AgentLab can route each agent task to the most suitable configured provider:

- Gemini for long-context, analysis, and verification tasks.
- Groq for research synthesis and report drafting.
- Ollama for compact citation/question tasks and explicitly private content.

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

## Status

This project is set up for local development, UI polishing, iterating on product flow, and extending into a more complete AI research product.

For the complete architecture and workflow explanation, see [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md).
