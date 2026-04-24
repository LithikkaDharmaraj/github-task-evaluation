"""
core/prompts.py — Evaluation role enum for LLM code evaluation.
"""
from enum import Enum


class EvaluationRole(str, Enum):
    TECHNICAL_INTERVIEWER = "technical_interviewer"
    SECURITY_EXPERT = "security_expert"
    PERFORMANCE_ANALYST = "performance_analyst"
    MAINTAINABILITY_EXPERT = "maintainability_expert"
    GENERAL_REVIEWER = "general_reviewer"
