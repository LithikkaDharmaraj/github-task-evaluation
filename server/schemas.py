"""
server/schemas.py — Pydantic models for API request/response validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class _ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub URL or local path to the repository")
    project_title: str = Field(..., description="Title of the hiring task / project")
    project_description: str = Field(..., description="Full description of the expected project requirements")
    stages: str = Field(default="1,2,3,7,8", description="Comma-separated stages to run")
    model: Optional[str] = Field(default=None, description="LLM model ID override")


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class FileScoreResponse(_ORMBase):
    file_path: str
    language: str
    cc_avg: float
    cc_max: float
    mi_score: float
    mi_grade: str
    halstead_vol: float
    loc: int
    lloc: int
    security_findings: int
    complexity_grade: str


class FileEvaluationResponse(_ORMBase):
    file_path: str
    language: str
    purpose: str
    relevance_to_task: str
    strengths: list[str]
    issues: list[str]
    file_score: float


class ParameterScoreResponse(BaseModel):
    key: str
    name: str
    max_score: int
    score: float
    reason: str
    evidence: list[str]
    suggestions: list[str]


class FindingResponse(_ORMBase):
    file_path: str
    rule_id: str
    severity: str
    message: str
    line_start: int
    line_end: int
    cwe: str
    owasp: str


class LLMAnalysisResponse(_ORMBase):
    file_path: str
    summary: str
    quality_assessment: str
    interview_notes: str


class EvaluationResponse(_ORMBase):
    id: str
    repo_url: str
    project_title: str
    project_description: str
    status: str
    created_at: Optional[datetime]
    completed_at: Optional[datetime]
    current_stage: str
    progress: int

    overall_score: float
    overall_grade: str
    total_files: int
    total_findings: int
    error_message: Optional[str]

    hiring_grade: str
    recommendation: str
    summary_feedback: str
    matched_requirements: list[str]
    missing_features: list[str]
    improvement_suggestions: list[str]
    interviewer_notes: str

    head_commit: str
    default_branch: str
    languages: list[str]
    total_commits: int
    contributors: list[str]
    repo_age_days: int


class EvaluationDetailResponse(EvaluationResponse):
    file_scores: list[FileScoreResponse] = []
    file_evaluations: list[FileEvaluationResponse] = []
    findings: list[FindingResponse] = []
    llm_analyses: list[LLMAnalysisResponse] = []
    parameter_scores: list[ParameterScoreResponse] = []


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "2.0.0"
    timestamp: datetime


class EvaluationListResponse(BaseModel):
    evaluations: list[EvaluationResponse]
    total: int
