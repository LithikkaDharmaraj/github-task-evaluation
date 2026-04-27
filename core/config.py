"""
core/config.py — Central configuration and shared dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tempfile

SKIP_DIRS: frozenset[str] = frozenset({
    ".git", "node_modules", "dist", "build", "__pycache__",
    ".venv", "venv", "coverage", ".next", ".nuxt", "vendor",
    ".tox", "eggs", ".eggs", ".cache", "out", ".output",
})


@dataclass
class PipelineConfig:
    # --- Stage 01: Cloner ---
    clone_depth: int = 1
    clone_base_dir: str = field(
        default_factory=lambda: str(Path(tempfile.gettempdir()) / "repo_eval")
    )

    # --- Stage 02: Parser ---
    supported_languages: list[str] = field(default_factory=lambda: [
        "python", "javascript", "typescript", "java", "go",
        "rust", "cpp", "c", "ruby", "php", "csharp", "kotlin", "scala",
        "swift", "objectivec", "dart", "r", "matlab", "groovy", "sql",
        "sh", "bash", "lua", "clojure", "elixir", "haskell", "perl",
        "julia", "dockerfile", "yaml", "json", "xml", "html", "css",
    ])
    max_file_size_bytes: int = 500_000
    skip_dirs: set[str] = field(default_factory=lambda: {
        ".git", "node_modules", "dist", "build", "__pycache__",
        ".venv", "venv", "coverage", ".next", ".nuxt", "vendor",
        ".tox", "eggs", ".eggs", ".cache", "out", ".output",
    })

    # --- Stage 03: Static analysis ---
    semgrep_config: str = "auto"
    semgrep_timeout: int = 60
    semgrep_max_memory: int = 2048

    # --- Stage 07: LLM (Groq API) ---
    llm_model: str = "llama-3.3-70b-versatile"
    llm_max_new_tokens: int = 1024
    llm_temperature: float = 0.1
    groq_api_key: str = ""          # loaded from GROQ_API_KEY env var in s07

    # --- Hiring evaluation context ---
    project_title: str = ""
    project_description: str = ""

    # --- Stage 08: Scorer ---
    complexity_threshold_warn: int = 10
    complexity_threshold_error: int = 20
    maintainability_threshold: int = 50

    # --- Output ---
    output_dir: str = "output"
    report_filename: str = "eval_report.json"


# ---------------------------------------------------------------------------
# 10-parameter scoring rubric (key → display name, max marks)
# ---------------------------------------------------------------------------

PARAMETER_RUBRIC: list[tuple[str, str, int]] = [
    ("relevancy",      "Relevancy to Task",                    20),
    ("accuracy",       "Accuracy of Implementation",           15),
    ("completeness",   "Feature Completeness",                 15),
    ("code_quality",   "Code Quality & Maintainability",       10),
    ("architecture",   "Architecture & Structure",             10),
    ("performance",    "Latency & Performance",                10),
    ("security",       "Security & Validation",                 5),
    ("error_handling", "Error Handling",                        5),
    ("database",       "Database Design",                       5),
    ("documentation",  "Documentation, Testing & Deployment",   5),
]


# ---------------------------------------------------------------------------
# Shared dataclasses — passed between pipeline stages
# ---------------------------------------------------------------------------

@dataclass
class RepoMeta:
    url: str
    local_path: str
    default_branch: str
    head_commit: str
    total_files: int
    languages_detected: list[str] = field(default_factory=list)
    all_branches: list[str] = field(default_factory=list)
    total_commits: int = 0
    contributors: list[str] = field(default_factory=list)
    commits_per_day: float = 0.0
    repo_age_days: int = 0
    first_commit_sha: str = ""
    last_commit_sha: str = ""


@dataclass
class ParsedFile:
    path: str
    language: str
    size_bytes: int
    line_count: int
    function_names: list[str] = field(default_factory=list)
    class_names: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    ast_node_count: int = 0
    parse_error: bool = False


@dataclass
class StaticFinding:
    file_path: str
    rule_id: str
    severity: str
    message: str
    line_start: int
    line_end: int
    cwe: str = ""
    owasp: str = ""


@dataclass
class ParameterScore:
    """Score for one of the 10 evaluation parameters."""
    key: str            # e.g. "relevancy"
    name: str           # e.g. "Relevancy to Task"
    max_score: int      # e.g. 20
    score: float        # actual marks awarded
    reason: str         # LLM's justification
    evidence: list[str] = field(default_factory=list)   # referenced files
    suggestions: list[str] = field(default_factory=list) # improvement ideas


@dataclass
class LLMAnalysis:
    """LLM assessment record stored in the DB per evaluation."""
    file_path: str
    summary: str
    quality_assessment: str
    interview_notes: str


@dataclass
class HiringAnalysis:
    """Full structured result of the hiring evaluation."""
    project_match: str = ""
    implementation_quality: str = ""
    matched_requirements: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)
    recommendation: str = "needs_review"
    interviewer_notes: str = ""
    improvement_suggestions: list[str] = field(default_factory=list)
    parameter_scores: list[ParameterScore] = field(default_factory=list)


@dataclass
class FileEvaluation:
    """Per-file hiring assessment."""
    file_path: str
    language: str
    purpose: str
    relevance_to_task: str
    strengths: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    file_score: float = 0.0


@dataclass
class FileScore:
    """Radon/lizard code quality metrics for one file."""
    file_path: str
    language: str
    cyclomatic_complexity_avg: float
    cyclomatic_complexity_max: float
    maintainability_index: float
    mi_grade: str
    halstead_volume: float
    loc: int
    lloc: int
    security_findings: int
    complexity_grade: str


@dataclass
class PipelineResult:
    repo_meta: RepoMeta | None = None
    parsed_files: list[ParsedFile] = field(default_factory=list)
    static_findings: list[StaticFinding] = field(default_factory=list)
    llm_analyses: list[LLMAnalysis] = field(default_factory=list)
    file_scores: list[FileScore] = field(default_factory=list)
    file_evaluations: list[FileEvaluation] = field(default_factory=list)
    hiring_analysis: HiringAnalysis | None = None
    parameter_scores: list[ParameterScore] = field(default_factory=list)
    overall_score: float = 0.0
    overall_grade: str = "N/A"
    hiring_grade: str = "N/A"           # Strong | Good | Average | Weak
    recommendation: str = "needs_review"  # shortlisted | needs_review | rejected
    errors: list[str] = field(default_factory=list)
