# AgentLab document upload guide

This document explains how the uploaded document feature works in AgentLab, from the frontend UI to the backend pipeline, and how to extend it safely.

## Overview

The platform now supports uploading supporting documents before starting a research run. The user can add text-based files such as `.txt`, `.md`, `.csv`, `.json`, and `.pdf` (if `pypdf` is installed), and those files are extracted into plain text and sent along with the research request.

The uploaded content is then:

1. extracted into text on the backend,
2. included as `document_context` in the research flow,
3. passed through the `research -> analysis -> verification -> report` chain,
4. surfaced back to the frontend as metadata alongside the final research result.

## Architecture

### Backend

Key pieces:

- `backend/main.py` exposes the API routes.
- `backend/services/documents.py` handles extraction and validation.
- `backend/models/research.py` defines `DocumentReference`, `ResearchRequest`, and `ResearchResponse`.
- `backend/services/research.py` combines the topic and the optional uploaded docs into the graph input.
- `backend/graph.py` passes `document_context` through each agent.

### Frontend

Key pieces:

- `frontend/components/query-form.tsx` includes the file picker and document chips.
- `frontend/lib/api.ts` defines the upload and research API calls.
- `frontend/app/page.tsx` stores uploaded docs in local state and sends them with the research request.

## API contract

### Upload endpoint

`POST /documents/upload`

Request:

- form-data with one or more files under `files`

Response:

```json
{
  "documents": [
    {
      "name": "notes.txt",
      "content": "AI is a broad field of computer science.",
      "size": 42,
      "type": "text/plain"
    }
  ]
}
```

### Research endpoint

`POST /research`

Request:

```json
{
  "topic": "Artificial Intelligence",
  "documents": [
    {
      "name": "brief.txt",
      "content": "AI is a broad field of computer science.",
      "size": 42,
      "type": "text/plain"
    }
  ]
}
```

## How the document context flows through the research graph

The graph state now includes:

- `document_context`: a combined plain-text string built from all uploaded docs.
- `documents`: the list of document names for bookkeeping.

Each agent receives `document_context` as an optional parameter and adds it to the prompt when present. This allows the research agent to ground the web search in the user’s material, and the analysis/report agents to reason about it in context.

## Supported file types

The upload layer currently supports:

- `.txt`
- `.md`
- `.csv`
- `.json`
- `.pdf` when `pypdf` is installed

If a file type is unsupported, the API returns a `400` error with a clear message.

## Product behaviour

On the frontend, the flow is:

1. User clicks `Add documents`.
2. User picks one or more supported files.
3. UI posts them to `/documents/upload`.
4. Uploaded file text is returned and shown as document chips.
5. User submits a research topic.
6. The app sends the topic and the document metadata to `/research`.
7. The backend includes those documents in the prompt context.

## Extending further

The clean next extension points are:

- support `.docx` and `.pptx` via `python-docx` or `pypandoc`,
- save uploaded files to disk or object storage for long-term access,
- allow users to remove or reorder uploaded docs before running,
- summarize uploaded documents separately before retrieval,
- enable multi-document comparison and citation grounding.

## Local development

Backend:

```powershell
cd C:\Users\salik\Desktop\AgentLab
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd C:\Users\salik\Desktop\AgentLab\frontend
npm install
npx next dev --webpack --hostname 0.0.0.0 --port 3000
```

## Verification status

The current project is verified with:

- backend tests: `pytest -q` → all passing
- frontend lint/build: `npm run lint && npm run build` → passing with webpack

This keeps the app stable without the Turbopack CSS incompatibility that affected the earlier setup.
