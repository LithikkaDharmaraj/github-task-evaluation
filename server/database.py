"""
server/database.py — PostgreSQL database layer for hiring evaluation persistence.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import (
    Column, String, Float, Integer, Text, DateTime,
    create_engine, ForeignKey, text,
)
from sqlalchemy.orm import (
    declarative_base, sessionmaker, relationship, Session,
)

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/hiring_evaluator",
)

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class EvaluationRecord(Base):
    __tablename__ = "evaluations"

    id            = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_url      = Column(String(512), nullable=False)
    project_title = Column(String(255), default="")
    project_description = Column(Text, default="")
    status        = Column(String(20), default="pending")
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at  = Column(DateTime, nullable=True)
    current_stage = Column(String(50), default="")
    progress      = Column(Integer, default=0)

    # Code quality scores
    overall_score  = Column(Float, default=0.0)
    overall_grade  = Column(String(5), default="N/A")
    total_files    = Column(Integer, default=0)
    total_findings = Column(Integer, default=0)
    error_message  = Column(Text, nullable=True)
    report_json    = Column(Text, nullable=True)

    # Hiring evaluation results
    hiring_grade   = Column(String(20), default="N/A")  # Strong | Good | Average | Weak
    recommendation = Column(String(20), default="needs_review")  # shortlisted | needs_review | rejected
    summary_feedback       = Column(Text, default="")
    matched_requirements   = Column(Text, default="[]")   # JSON array
    missing_features       = Column(Text, default="[]")   # JSON array
    improvement_suggestions = Column(Text, default="[]")  # JSON array
    interviewer_notes      = Column(Text, default="")

    # Git metadata
    head_commit    = Column(String(40), default="")
    default_branch = Column(String(100), default="")
    languages      = Column(Text, default="[]")
    total_commits  = Column(Integer, default=0)
    contributors   = Column(Text, default="[]")
    repo_age_days  = Column(Integer, default=0)

    # 10-parameter scoring breakdown (JSON array)
    parameter_scores = Column(Text, default="[]")

    file_scores      = relationship("FileScoreRecord", back_populates="evaluation", cascade="all, delete-orphan")
    findings         = relationship("FindingRecord", back_populates="evaluation", cascade="all, delete-orphan")
    llm_analyses     = relationship("LLMAnalysisRecord", back_populates="evaluation", cascade="all, delete-orphan")
    file_evaluations = relationship("FileEvaluationRecord", back_populates="evaluation", cascade="all, delete-orphan")
    evaluation_scores = relationship("EvaluationScoreRecord", back_populates="evaluation", cascade="all, delete-orphan")


class FileScoreRecord(Base):
    __tablename__ = "file_scores"

    id            = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id = Column(String(36), ForeignKey("evaluations.id"), nullable=False)
    file_path     = Column(String(512), nullable=False)
    language      = Column(String(50), default="")
    cc_avg        = Column(Float, default=0.0)
    cc_max        = Column(Float, default=0.0)
    mi_score      = Column(Float, default=0.0)
    mi_grade      = Column(String(2), default="")
    halstead_vol  = Column(Float, default=0.0)
    loc           = Column(Integer, default=0)
    lloc          = Column(Integer, default=0)
    security_findings = Column(Integer, default=0)
    complexity_grade  = Column(String(2), default="")

    evaluation = relationship("EvaluationRecord", back_populates="file_scores")


class FindingRecord(Base):
    __tablename__ = "findings"

    id            = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id = Column(String(36), ForeignKey("evaluations.id"), nullable=False)
    file_path     = Column(String(512), default="")
    rule_id       = Column(String(200), default="")
    severity      = Column(String(20), default="INFO")
    message       = Column(Text, default="")
    line_start    = Column(Integer, default=0)
    line_end      = Column(Integer, default=0)
    cwe           = Column(String(50), default="")
    owasp         = Column(String(50), default="")

    evaluation = relationship("EvaluationRecord", back_populates="findings")


class LLMAnalysisRecord(Base):
    __tablename__ = "llm_analyses"

    id            = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id = Column(String(36), ForeignKey("evaluations.id"), nullable=False)
    file_path     = Column(String(512), default="")
    summary       = Column(Text, default="")
    quality_assessment = Column(Text, default="")
    interview_notes    = Column(Text, default="")

    evaluation = relationship("EvaluationRecord", back_populates="llm_analyses")


class FileEvaluationRecord(Base):
    """Per-file hiring assessment."""
    __tablename__ = "file_evaluations"

    id            = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id = Column(String(36), ForeignKey("evaluations.id"), nullable=False)
    file_path     = Column(String(512), default="")
    language      = Column(String(50), default="")
    purpose       = Column(Text, default="")
    relevance_to_task = Column(Text, default="")
    strengths     = Column(Text, default="[]")  # JSON array
    issues        = Column(Text, default="[]")   # JSON array
    file_score    = Column(Float, default=0.0)

    evaluation = relationship("EvaluationRecord", back_populates="file_evaluations")


class EvaluationScoreRecord(Base):
    __tablename__ = "evaluation_scores"

    id             = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String(36), ForeignKey("evaluations.id"), nullable=False)
    round          = Column(Integer, nullable=False, default=1)
    score          = Column(Float, nullable=False, default=0.0)
    max_score      = Column(Float, nullable=False, default=100.0)
    details        = Column(Text, nullable=True)
    evaluated_at   = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    evaluation = relationship("EvaluationRecord", back_populates="evaluation_scores")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def init_db():
    Base.metadata.create_all(bind=engine)
    # Add parameter_scores column to existing deployments
    with engine.connect() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS parameter_scores TEXT DEFAULT '[]'"
            ))
            conn.commit()
        except Exception:
            pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def create_evaluation(db: Session, repo_url: str, project_title: str = "", project_description: str = "") -> EvaluationRecord:
    record = EvaluationRecord(
        repo_url=repo_url,
        project_title=project_title,
        project_description=project_description,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_evaluation(db: Session, eval_id: str) -> Optional[EvaluationRecord]:
    return db.query(EvaluationRecord).filter(EvaluationRecord.id == eval_id).first()


def list_evaluations(db: Session, limit: int = 50, offset: int = 0):
    return (
        db.query(EvaluationRecord)
        .order_by(EvaluationRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def update_evaluation(db: Session, eval_id: str, **kwargs):
    record = get_evaluation(db, eval_id)
    if record:
        for key, value in kwargs.items():
            setattr(record, key, value)
        db.commit()
        db.refresh(record)
    return record


def delete_evaluation(db: Session, eval_id: str) -> bool:
    record = get_evaluation(db, eval_id)
    if record:
        db.delete(record)
        db.commit()
        return True
    return False
