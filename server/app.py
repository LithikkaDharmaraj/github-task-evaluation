"""
server/app.py — FastAPI application for the Hiring Task Evaluator.

Endpoints:
  POST /api/evaluate            — submit repo + task description
  GET  /api/evaluate/{id}       — evaluation detail
  GET  /api/evaluate/{id}/stream — SSE progress stream
  GET  /api/evaluations          — paginated history
  DELETE /api/evaluations/{id}   — delete an evaluation
  GET  /api/health               — health check
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from server.database import (
    init_db, get_db, SessionLocal,
    create_evaluation, get_evaluation, list_evaluations,
    update_evaluation, delete_evaluation, EvaluationRecord,
)
from server.schemas import (
    EvaluateRequest, EvaluationResponse, EvaluationDetailResponse,
    EvaluationListResponse, HealthResponse,
    FileScoreResponse, FileEvaluationResponse, FindingResponse,
    LLMAnalysisResponse, ParameterScoreResponse,
)
from server.worker import run_evaluation, register_progress_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Hiring Task Evaluator",
    description="AI pipeline for evaluating candidate GitHub submissions against task requirements",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_FRONTEND_DIST = _ROOT / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")


# ---------------------------------------------------------------------------
# ORM → Pydantic helpers
# ---------------------------------------------------------------------------

def _to_response(record: EvaluationRecord) -> EvaluationResponse:
    return EvaluationResponse(
        id=record.id,
        repo_url=record.repo_url,
        project_title=record.project_title or "",
        project_description=record.project_description or "",
        status=record.status,
        created_at=record.created_at,
        completed_at=record.completed_at,
        current_stage=record.current_stage,
        progress=record.progress,
        overall_score=record.overall_score,
        overall_grade=record.overall_grade,
        total_files=record.total_files,
        total_findings=record.total_findings,
        error_message=record.error_message,
        hiring_grade=record.hiring_grade or "N/A",
        recommendation=record.recommendation or "needs_review",
        summary_feedback=record.summary_feedback or "",
        matched_requirements=record.matched_requirements or "[]",
        missing_features=record.missing_features or "[]",
        improvement_suggestions=record.improvement_suggestions or "[]",
        interviewer_notes=record.interviewer_notes or "",
        head_commit=record.head_commit,
        default_branch=record.default_branch,
        languages=record.languages,
        total_commits=record.total_commits,
        contributors=record.contributors,
        repo_age_days=record.repo_age_days,
    )


def _to_detail_response(record: EvaluationRecord) -> EvaluationDetailResponse:
    import json as _json

    def _parse_json_list(text: str) -> list:
        try:
            return _json.loads(text or "[]")
        except Exception:
            return []

    return EvaluationDetailResponse(
        id=record.id,
        repo_url=record.repo_url,
        project_title=record.project_title or "",
        project_description=record.project_description or "",
        status=record.status,
        created_at=record.created_at,
        completed_at=record.completed_at,
        current_stage=record.current_stage,
        progress=record.progress,
        overall_score=record.overall_score,
        overall_grade=record.overall_grade,
        total_files=record.total_files,
        total_findings=record.total_findings,
        error_message=record.error_message,
        hiring_grade=record.hiring_grade or "N/A",
        recommendation=record.recommendation or "needs_review",
        summary_feedback=record.summary_feedback or "",
        matched_requirements=record.matched_requirements or "[]",
        missing_features=record.missing_features or "[]",
        improvement_suggestions=record.improvement_suggestions or "[]",
        interviewer_notes=record.interviewer_notes or "",
        head_commit=record.head_commit,
        default_branch=record.default_branch,
        languages=record.languages,
        total_commits=record.total_commits,
        contributors=record.contributors,
        repo_age_days=record.repo_age_days,
        file_scores=[
            FileScoreResponse(
                file_path=fs.file_path,
                language=fs.language,
                cc_avg=fs.cc_avg,
                cc_max=fs.cc_max,
                mi_score=fs.mi_score,
                mi_grade=fs.mi_grade,
                halstead_vol=fs.halstead_vol,
                loc=fs.loc,
                lloc=fs.lloc,
                security_findings=fs.security_findings,
                complexity_grade=fs.complexity_grade,
            ) for fs in record.file_scores
        ],
        file_evaluations=[
            FileEvaluationResponse(
                file_path=fe.file_path,
                language=fe.language,
                purpose=fe.purpose,
                relevance_to_task=fe.relevance_to_task,
                strengths=_parse_json_list(fe.strengths),
                issues=_parse_json_list(fe.issues),
                file_score=fe.file_score,
            ) for fe in record.file_evaluations
        ],
        findings=[
            FindingResponse(
                file_path=f.file_path,
                rule_id=f.rule_id,
                severity=f.severity,
                message=f.message,
                line_start=f.line_start,
                line_end=f.line_end,
                cwe=f.cwe,
                owasp=f.owasp,
            ) for f in record.findings
        ],
        llm_analyses=[
            LLMAnalysisResponse(
                file_path=a.file_path,
                summary=a.summary,
                quality_assessment=a.quality_assessment,
                interview_notes=a.interview_notes,
            ) for a in record.llm_analyses
        ],
        parameter_scores=_parse_parameter_scores_json(record.parameter_scores),
    )


def _parse_parameter_scores_json(raw: str | None) -> list[ParameterScoreResponse]:
    import json as _json
    try:
        items = _json.loads(raw or "[]")
        return [
            ParameterScoreResponse(
                key=it.get("key", ""),
                name=it.get("name", ""),
                max_score=int(it.get("max_score", 0)),
                score=float(it.get("score", 0)),
                reason=it.get("reason", ""),
                evidence=it.get("evidence", []),
                suggestions=it.get("suggestions", []),
            )
            for it in items
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        version="2.0.0",
        timestamp=datetime.now(timezone.utc),
    )


@app.post("/api/evaluate", response_model=EvaluationResponse, status_code=202)
async def start_evaluation(req: EvaluateRequest, db: Session = Depends(get_db)):
    record = create_evaluation(
        db,
        repo_url=req.repo_url,
        project_title=req.project_title,
        project_description=req.project_description,
    )

    loop = asyncio.get_running_loop()
    register_progress_queue(record.id, loop)

    loop.run_in_executor(
        None,
        run_evaluation,
        record.id,
        req.repo_url,
        req.project_title,
        req.project_description,
        req.stages,
        req.model,
        req.use_4bit,
    )

    return _to_response(record)


@app.get("/api/evaluate/{eval_id}", response_model=EvaluationDetailResponse)
def get_evaluation_detail(eval_id: str, db: Session = Depends(get_db)):
    record = get_evaluation(db, eval_id)
    if not record:
        raise HTTPException(404, "Evaluation not found")
    return _to_detail_response(record)


@app.get("/api/evaluate/{eval_id}/stream")
async def stream_evaluation(eval_id: str):
    from server.worker import _progress_queues

    queue = _progress_queues.get(eval_id)

    async def event_generator():
        if not queue:
            yield {"event": "error", "data": json.dumps({"message": "No active evaluation found"})}
            return

        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=120)
                yield {"event": "progress", "data": json.dumps(data)}
                if data.get("done"):
                    break
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(event_generator())


@app.get("/api/evaluations", response_model=EvaluationListResponse)
def list_evals(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    records = list_evaluations(db, limit=limit, offset=offset)
    total = db.query(EvaluationRecord).count()
    return EvaluationListResponse(
        evaluations=[_to_response(r) for r in records],
        total=total,
    )


@app.delete("/api/evaluations/{eval_id}", status_code=204)
def delete_eval(eval_id: str, db: Session = Depends(get_db)):
    if not delete_evaluation(db, eval_id):
        raise HTTPException(404, "Evaluation not found")


@app.get("/{path:path}")
async def serve_spa(path: str):
    index_path = _FRONTEND_DIST / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse(
        "<h1>Frontend not built</h1>"
        "<p>Run <code>cd frontend && npm run build</code> to build the frontend.</p>",
        status_code=200,
    )
