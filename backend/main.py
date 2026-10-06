import inspect
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.models.research import DocumentReference, ResearchRequest, ResearchResponse
from backend.services.documents import extract_document_text
from backend.services.harness import StepFailedError
from backend.services.llm import ollama_model_available
from backend.services.research import perform_research

JOB_STORE: dict[str, dict] = {}
JOB_LOCK = threading.Lock()


logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AgentLab")

app.state.rate_limit_window_seconds = 60
app.state.rate_limit_max_requests = 300
app.state.rate_limit_buckets = defaultdict(deque)
app.state.rate_limit_lock = threading.Lock()

allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in {"/health", "/docs", "/openapi.json", "/redoc"}:
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    window = getattr(app.state, "rate_limit_window_seconds", 60)
    max_requests = getattr(app.state, "rate_limit_max_requests", 30)
    now = time.monotonic()

    with app.state.rate_limit_lock:
        bucket = app.state.rate_limit_buckets.setdefault(client_ip, deque())
        while bucket and now - bucket[0] > window:
            bucket.popleft()

        if len(bucket) >= max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": "Too many requests. Please slow down and try again shortly.",
                },
            )

        bucket.append(now)

    return await call_next(request)


@app.exception_handler(StepFailedError)
def step_failed_handler(request: Request, error: StepFailedError):
    return JSONResponse(
        status_code=502,
        content={
            "error": "pipeline_step_failed",
            "step": error.step_name,
            "message": "An agent step failed. Please try again later.",
        },
    )


@app.get("/")
def root():
    return {
        "message": "AgentLab API is running"
    }


def _runtime_checks():
    groq_configured = bool(os.getenv("GROQ_API_KEY"))
    gemini_configured = bool(os.getenv("GEMINI_API_KEY"))
    selected_provider = os.getenv("LLM_PROVIDER", "auto").strip().lower() or "auto"
    tavily_configured = bool(os.getenv("TAVILY_API_KEY"))
    ollama_configured = ollama_model_available()
    if selected_provider == "auto":
        provider = "auto"
        llm_configured = gemini_configured or groq_configured or ollama_configured
    elif selected_provider:
        provider = selected_provider
        llm_configured = (
            selected_provider == "ollama" and ollama_configured
            or selected_provider == "gemini" and gemini_configured
            or selected_provider == "groq" and groq_configured
        )
        if selected_provider not in {"ollama", "gemini", "groq"}:
            provider = "none"
            llm_configured = False
    else:
        provider = "none"
        llm_configured = False
    return {
        "groq": groq_configured,
        "gemini": gemini_configured,
        "ollama": ollama_configured,
        "tavily": tavily_configured,
        "llm": llm_configured,
        "provider": provider,
    }


@app.get("/health")
def health():
    checks = _runtime_checks()
    status = "healthy" if checks["llm"] and checks["tavily"] else "degraded"
    message = "All providers are configured and ready."
    if not checks["llm"]:
        message = (
            "No LLM provider is available. Start Ollama or configure GEMINI_API_KEY "
            "or GROQ_API_KEY, and set LLM_PROVIDER=auto."
        )
    elif not checks["tavily"]:
        message = "Tavily is not configured. Search functionality will be unavailable."
    return {
        "status": status,
        "checks": checks,
        "message": message,
    }


@app.post("/documents/upload")
async def upload_documents(files: list[UploadFile] = File(default_factory=list)):
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    documents: list[DocumentReference] = []

    for file in files:
        if file.filename is None:
            continue

        data = await file.read()
        try:
            content = extract_document_text(file.filename, data)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"{file.filename}: {error}") from error

        documents.append(
            DocumentReference(
                name=file.filename,
                content=content,
                size=len(data),
                type=file.content_type or "application/octet-stream",
            )
        )

    return {"documents": documents}


def _update_job(job_id: str, **changes):
    with JOB_LOCK:
        job = JOB_STORE.setdefault(job_id, {
            "job_id": job_id,
            "status": "queued",
            "current_step": None,
            "completed_steps": [],
            "result": None,
            "error": None,
        })
        for key, value in changes.items():
            job[key] = value
        return job


def _execute_research_job(job_id: str, topic: str, documents: list[DocumentReference]):
    def on_step(step_name: str, step_state: str):
        with JOB_LOCK:
            job = JOB_STORE[job_id]
            if step_state == "processing":
                job["status"] = "running"
                job["current_step"] = step_name
            elif step_state == "completed":
                if step_name not in job["completed_steps"]:
                    job["completed_steps"].append(step_name)
                job["current_step"] = step_name
            elif step_state == "failed":
                job["status"] = "failed"
                job["current_step"] = step_name

    def on_result(step_name: str, value: object):
        if step_name == "research" and isinstance(value, dict):
            updates = {
                "research": value.get("research", ""),
                "sources": value.get("sources", []),
            }
        else:
            result_fields = {
                "analysis": "analysis",
                "verification": "verification",
                "report": "report",
                "citation_linking": "citations",
                "follow_up_questions": "follow_up_questions",
            }
            field = result_fields.get(step_name)
            updates = {field: value} if field else {}

        if updates:
            with JOB_LOCK:
                JOB_STORE[job_id]["partial_result"].update(updates)

    _update_job(job_id, status="running", current_step="research")
    try:
        result = perform_research(
            topic,
            documents,
            on_step=on_step,
            on_result=on_result,
        )
        _update_job(job_id, status="completed", current_step="report", result=result)
    except Exception as error:
        _update_job(job_id, status="failed", current_step=None, error=str(error))


@app.post("/research/jobs")
def create_research_job(request: ResearchRequest):
    job_id = uuid.uuid4().hex
    _update_job(
        job_id,
        status="queued",
        current_step=None,
        completed_steps=[],
        partial_result={
            "topic": request.topic,
            "status": "running",
            "research": "",
            "analysis": "",
            "verification": "",
            "report": "",
            "sources": [],
            "citations": [],
            "follow_up_questions": [],
            "documents": [],
        },
    )
    worker = threading.Thread(
        target=_execute_research_job,
        args=(job_id, request.topic, request.documents),
        daemon=True,
    )
    worker.start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/research/jobs/{job_id}")
def get_research_job(job_id: str):
    with JOB_LOCK:
        job = JOB_STORE.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        payload = {
            "job_id": job["job_id"],
            "status": job["status"],
            "current_step": job["current_step"],
            "completed_steps": job["completed_steps"],
            "partial_result": job.get("partial_result"),
        }
        if job.get("result") is not None:
            payload["result"] = job["result"]
        if job.get("error") is not None:
            payload["error"] = job["error"]
        return payload


@app.post("/research", response_model=ResearchResponse)
def research(request: ResearchRequest):
    if "documents" in inspect.signature(perform_research).parameters:
        return perform_research(request.topic, request.documents)
    return perform_research(request.topic)
