"""
server/worker.py — Background evaluation worker for hiring task evaluation.

Runs the 5-stage pipeline in a thread pool and publishes progress via SSE.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import PipelineConfig, PipelineResult
from core.logger import get_logger
from server.database import (
    SessionLocal, update_evaluation, get_evaluation,
    FileScoreRecord, FindingRecord, LLMAnalysisRecord,
    FileEvaluationRecord, EvaluationScoreRecord,
)

log = get_logger("worker")

_progress_queues: dict[str, asyncio.Queue] = {}
_event_loops: dict[str, asyncio.AbstractEventLoop] = {}


def register_progress_queue(eval_id: str, loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _progress_queues[eval_id] = q
    _event_loops[eval_id] = loop
    return q


def unregister_progress_queue(eval_id: str):
    _progress_queues.pop(eval_id, None)
    _event_loops.pop(eval_id, None)


def _publish(eval_id: str, data: dict):
    q = _progress_queues.get(eval_id)
    loop = _event_loops.get(eval_id)
    if q and loop and loop.is_running():
        try:
            loop.call_soon_threadsafe(q.put_nowait, data)
        except Exception:
            pass


def _json_list(items: list) -> str:
    try:
        return json.dumps(items)
    except Exception:
        return "[]"


def run_evaluation(
    eval_id: str,
    repo_url: str,
    project_title: str,
    project_description: str,
    stages_str: str,
    model: str | None,
):
    db = SessionLocal()
    stages = {int(s.strip()) for s in stages_str.split(",")}

    try:
        update_evaluation(db, eval_id, status="running", current_stage="initialising", progress=5)
        _publish(eval_id, {"stage": "initialising", "progress": 5, "message": "Starting evaluation pipeline…"})

        cfg = PipelineConfig()
        if model:
            cfg.llm_model = model
        elif os.environ.get("GROQ_MODEL"):
            cfg.llm_model = os.environ["GROQ_MODEL"]
        cfg.groq_api_key = os.environ.get("GROQ_API_KEY", "")
        cfg.project_title = project_title
        cfg.project_description = project_description

        result = PipelineResult()

        # ------------------------------------------------------------------
        # Stage 01 — Repo Cloner
        # ------------------------------------------------------------------
        if 1 in stages:
            update_evaluation(db, eval_id, current_stage="cloning", progress=10)
            _publish(eval_id, {"stage": "cloning", "progress": 10, "message": "Cloning repository…"})

            from stages import s01_cloner
            result.repo_meta = s01_cloner.run(repo_url, cfg)

            update_evaluation(
                db, eval_id,
                head_commit=result.repo_meta.head_commit,
                default_branch=result.repo_meta.default_branch,
                languages=json.dumps(result.repo_meta.languages_detected),
                total_commits=result.repo_meta.total_commits,
                contributors=json.dumps(result.repo_meta.contributors),
                repo_age_days=result.repo_meta.repo_age_days,
                total_files=result.repo_meta.total_files,
                progress=25,
            )
            _publish(eval_id, {
                "stage": "cloning", "progress": 25,
                "message": f"Cloned — {result.repo_meta.total_files} files found",
            })
        else:
            from core.config import RepoMeta as CfgRepoMeta
            result.repo_meta = CfgRepoMeta(
                url=repo_url, local_path=repo_url,
                default_branch="HEAD", head_commit="unknown", total_files=0,
            )

        # ------------------------------------------------------------------
        # Stage 02 — Parser
        # ------------------------------------------------------------------
        if 2 in stages:
            update_evaluation(db, eval_id, current_stage="parsing", progress=30)
            _publish(eval_id, {"stage": "parsing", "progress": 30, "message": "Parsing source files…"})

            from stages import s02_parser
            result.parsed_files = s02_parser.run(result.repo_meta, cfg)

            update_evaluation(db, eval_id, progress=45)
            _publish(eval_id, {
                "stage": "parsing", "progress": 45,
                "message": f"Parsed {len(result.parsed_files)} source files",
            })

        # ------------------------------------------------------------------
        # Stage 03 — Static Analysis
        # ------------------------------------------------------------------
        if 3 in stages:
            update_evaluation(db, eval_id, current_stage="static_analysis", progress=50)
            _publish(eval_id, {"stage": "static_analysis", "progress": 50, "message": "Running static analysis…"})

            from stages import s03_static
            result.static_findings = s03_static.run(result.repo_meta, cfg)

            update_evaluation(db, eval_id, total_findings=len(result.static_findings), progress=60)
            _publish(eval_id, {
                "stage": "static_analysis", "progress": 60,
                "message": f"Found {len(result.static_findings)} security/code issues",
            })

        # ------------------------------------------------------------------
        # Stage 07 — LLM Hiring Evaluation
        # ------------------------------------------------------------------
        if 7 in stages and result.parsed_files:
            update_evaluation(db, eval_id, current_stage="llm_analysis", progress=65)
            _publish(eval_id, {"stage": "llm_analysis", "progress": 65, "message": "Running AI hiring evaluation…"})

            from stages import s07_llm
            try:
                result.llm_analyses, result.hiring_analysis = s07_llm.run(
                    result.repo_meta,
                    result.parsed_files,
                    result.static_findings,
                    cfg,
                )
            except Exception as exc:
                log.warning("LLM stage failed: %s", exc)
                _publish(eval_id, {
                    "stage": "llm_analysis", "progress": 75,
                    "message": f"LLM analysis skipped: {exc}",
                })

            update_evaluation(db, eval_id, progress=80)

        # ------------------------------------------------------------------
        # Stage 08 — Scoring + File Evaluations
        # ------------------------------------------------------------------
        if 8 in stages:
            update_evaluation(db, eval_id, current_stage="scoring", progress=85)
            _publish(eval_id, {"stage": "scoring", "progress": 85, "message": "Computing scores and file evaluations…"})

            from stages import s08_scorer
            result = s08_scorer.run(
                result.repo_meta,
                result.parsed_files,
                result.static_findings,
                result.llm_analyses,
                result.hiring_analysis,
                cfg,
            )

        # ------------------------------------------------------------------
        # Persist results
        # ------------------------------------------------------------------
        update_evaluation(db, eval_id, current_stage="saving", progress=95)
        _publish(eval_id, {"stage": "saving", "progress": 95, "message": "Saving results…"})

        def _default(obj):
            if dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj)
            return str(obj)

        report_json = json.dumps(dataclasses.asdict(result), default=_default, indent=2)

        # Serialise parameter scores to JSON for the DB column
        param_scores_json = json.dumps([
            {
                "key": ps.key, "name": ps.name, "max_score": ps.max_score,
                "score": ps.score, "reason": ps.reason,
                "evidence": ps.evidence, "suggestions": ps.suggestions,
            }
            for ps in result.parameter_scores
        ])

        # Extract hiring data from analysis
        ha = result.hiring_analysis

        if not result.file_scores:
            summary_feedback = (
                "This repository contains no source code files that could be analysed. "
                "The repository may be empty, or it may not contain any files in a supported "
                "programming language. All parameters have been scored 0."
            )
            interviewer_notes = (
                "- Repository has no analysable source files.\n"
                "- Verify the candidate submitted the correct repository URL.\n"
                "- Ensure the repository is not empty and contains actual code."
            )
            matched_reqs = []
            missing_features = ["Source code files (none detected)"]
            improvement_suggestions = [
                "Submit a repository that contains source code.",
                "Ensure the repository URL is correct and points to the right project.",
            ]
        else:
            matched_reqs = ha.matched_requirements if ha else []
            missing_features = ha.missing_requirements if ha else []
            improvement_suggestions = ha.improvement_suggestions if ha else []
            summary_feedback = ""
            if ha:
                parts = []
                if ha.project_match:
                    parts.append(ha.project_match)
                if ha.implementation_quality:
                    parts.append(ha.implementation_quality)
                summary_feedback = "\n\n".join(parts)
            interviewer_notes = ha.interviewer_notes if ha else ""

        db.add_all([
            FileScoreRecord(
                evaluation_id=eval_id,
                file_path=fs.file_path,
                language=fs.language,
                cc_avg=fs.cyclomatic_complexity_avg,
                cc_max=fs.cyclomatic_complexity_max,
                mi_score=fs.maintainability_index,
                mi_grade=fs.mi_grade,
                halstead_vol=fs.halstead_volume,
                loc=fs.loc,
                lloc=fs.lloc,
                security_findings=fs.security_findings,
                complexity_grade=fs.complexity_grade,
            ) for fs in result.file_scores
        ])
        db.add_all([
            FindingRecord(
                evaluation_id=eval_id,
                file_path=f.file_path,
                rule_id=f.rule_id,
                severity=f.severity,
                message=f.message,
                line_start=f.line_start,
                line_end=f.line_end,
                cwe=f.cwe,
                owasp=f.owasp,
            ) for f in result.static_findings
        ])
        db.add_all([
            LLMAnalysisRecord(
                evaluation_id=eval_id,
                file_path=a.file_path,
                summary=a.summary,
                quality_assessment=a.quality_assessment,
                interview_notes=a.interview_notes,
            ) for a in result.llm_analyses
        ])
        db.add_all([
            FileEvaluationRecord(
                evaluation_id=eval_id,
                file_path=fe.file_path,
                language=fe.language,
                purpose=fe.purpose,
                relevance_to_task=fe.relevance_to_task,
                strengths=_json_list(fe.strengths),
                issues=_json_list(fe.issues),
                file_score=fe.file_score,
            ) for fe in result.file_evaluations
        ])

        # Persist overall evaluation score
        db.add(EvaluationScoreRecord(
            application_id=eval_id,
            round=1,
            score=result.overall_score,
            max_score=100.0,
            details=json.dumps({
                "hiring_grade": result.hiring_grade,
                "recommendation": result.recommendation,
                "total_files": len(result.file_scores),
                "total_findings": len(result.static_findings),
            }),
        ))

        update_evaluation(
            db, eval_id,
            status="completed",
            current_stage="done",
            progress=100,
            overall_score=result.overall_score,
            overall_grade=result.overall_grade,
            hiring_grade=result.hiring_grade,
            recommendation=result.recommendation,
            summary_feedback=summary_feedback,
            matched_requirements=_json_list(matched_reqs),
            missing_features=_json_list(missing_features),
            improvement_suggestions=_json_list(improvement_suggestions),
            interviewer_notes=interviewer_notes,
            total_files=len(result.file_scores),
            total_findings=len(result.static_findings),
            report_json=report_json,
            parameter_scores=param_scores_json,
            completed_at=datetime.now(timezone.utc),
        )
        db.commit()

        _publish(eval_id, {
            "stage": "done", "progress": 100,
            "message": f"Evaluation complete — {result.hiring_grade} ({result.recommendation}) | Score: {result.overall_score:.0f}/100",
            "done": True,
        })

    except Exception as exc:
        log.exception("Evaluation failed: %s", exc)
        update_evaluation(
            db, eval_id,
            status="failed",
            error_message=str(exc),
            current_stage="error",
            completed_at=datetime.now(timezone.utc),
        )
        db.commit()
        _publish(eval_id, {
            "stage": "error", "progress": 0,
            "message": f"Pipeline failed: {exc}",
            "done": True,
            "error": True,
        })

    finally:
        db.close()
        unregister_progress_queue(eval_id)
