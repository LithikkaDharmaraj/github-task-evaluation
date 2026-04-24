"""
stages/s08_scorer.py — Stage 08: Hiring Scorer & Metrics Engine.

• Computes per-file code quality metrics (Radon / lizard).
• Blends metric-based scores into the LLM's code_quality and security parameters.
• Sums all 10 parameter scores → overall_score (0–100).
• Derives hiring_grade (Strong / Good / Average / Weak) and
  recommendation (shortlisted / needs_review / rejected).
• Generates rule-based per-file hiring evaluations.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path

from core.config import (
    PARAMETER_RUBRIC,
    FileEvaluation, FileScore, HiringAnalysis,
    LLMAnalysis, ParameterScore, ParsedFile,
    PipelineConfig, PipelineResult, RepoMeta, StaticFinding,
)
from core.logger import get_logger

log = get_logger("s08_scorer")

_MI_GRADE_THRESHOLDS = [
    (80, "A"), (60, "B"), (40, "C"), (20, "D"), (10, "E"), (0, "F"),
]
_CC_GRADE_THRESHOLDS = [
    (1, "A"), (5, "B"), (10, "C"), (15, "D"), (20, "E"),
]

_KEY_FILE_PATTERNS = {
    "readme":         ("Documentation", 10),
    "package.json":   ("Dependency configuration", 8),
    "requirements.txt": ("Dependency configuration", 8),
    "pyproject.toml": ("Project configuration", 8),
    "main.":          ("Entry point", 9),
    "app.":           ("Application root", 9),
    "index.":         ("Entry point", 7),
    "server.":        ("Server setup", 8),
    "routes.":        ("API routes", 9),
    "router.":        ("API routing", 9),
    "api.":           ("API layer", 8),
    "models.":        ("Data models", 9),
    "schema.":        ("Data schema", 9),
    "database.":      ("Database layer", 9),
    "db.":            ("Database layer", 8),
    "config.":        ("Configuration", 6),
    "settings.":      ("Settings", 6),
    "views.":         ("Views/controllers", 7),
    "controllers.":   ("Controllers", 8),
    "services.":      ("Business logic", 8),
    "auth.":          ("Authentication", 8),
    "middleware.":    ("Middleware", 7),
}

_SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "__pycache__",
    ".venv", "venv", "coverage", ".next", ".nuxt", "vendor",
    ".tox", "eggs", ".eggs", ".cache",
}


def run(
    repo_meta: RepoMeta,
    parsed_files: list[ParsedFile],
    static_findings: list[StaticFinding],
    llm_analyses: list[LLMAnalysis],
    hiring_analysis: HiringAnalysis | None,
    cfg: PipelineConfig,
) -> PipelineResult:
    base = Path(repo_meta.local_path)

    findings_by_file: dict[str, list[StaticFinding]] = defaultdict(list)
    for f in static_findings:
        findings_by_file[f.file_path].append(f)

    radon_ok  = _check_radon()
    lizard_ok = _check_lizard()

    # --- Per-file code quality scores ---
    file_scores: list[FileScore] = []
    for pf in parsed_files:
        n_issues = len(findings_by_file.get(pf.path, []))
        if pf.language == "python" and radon_ok:
            fs = _score_radon(pf, base / pf.path, n_issues)
        elif lizard_ok:
            fs = _score_lizard(pf, base / pf.path, n_issues)
        else:
            fs = _score_basic(pf, n_issues)
        file_scores.append(fs)

    # --- Metric-based code quality and security scores ---
    code_quality_metric = _metric_code_quality(file_scores)   # 0–10
    security_metric     = _metric_security(static_findings)   # 0–5

    # --- Blend metric scores into LLM parameter scores ---
    param_scores = _blend_parameters(
        hiring_analysis, code_quality_metric, security_metric
    )

    # --- Final overall score = sum of all 10 parameter scores ---
    overall_score = round(sum(ps.score for ps in param_scores), 1)
    overall_score = max(0.0, min(100.0, overall_score))

    # Keep classic A-F grade from code metrics for reference
    code_quality_avg = (
        sum(fs.maintainability_index for fs in file_scores) / len(file_scores)
        if file_scores else 0.0
    )
    overall_grade = _mi_grade(code_quality_avg)

    hiring_grade   = _hiring_grade(overall_score)
    recommendation = _recommendation(overall_score, hiring_analysis)

    # --- Per-file hiring evaluations ---
    keywords = _extract_keywords(cfg.project_description + " " + cfg.project_title)
    file_evaluations = _build_file_evaluations(
        parsed_files, file_scores, findings_by_file, base, keywords
    )

    result = PipelineResult(
        repo_meta=repo_meta,
        parsed_files=parsed_files,
        static_findings=static_findings,
        llm_analyses=llm_analyses,
        hiring_analysis=hiring_analysis,
        file_scores=file_scores,
        file_evaluations=file_evaluations,
        parameter_scores=param_scores,
        overall_score=overall_score,
        overall_grade=overall_grade,
        hiring_grade=hiring_grade,
        recommendation=recommendation,
    )

    # Sync the updated parameter scores back into hiring_analysis
    if hiring_analysis:
        hiring_analysis.parameter_scores = param_scores

    _log_summary(result)
    return result


# ---------------------------------------------------------------------------
# Parameter score blending
# ---------------------------------------------------------------------------

def _blend_parameters(
    hiring_analysis: HiringAnalysis | None,
    code_quality_metric: float,
    security_metric: float,
) -> list[ParameterScore]:
    """Merge LLM parameter scores with Radon/Semgrep metrics."""
    if hiring_analysis and hiring_analysis.parameter_scores:
        base_scores = {ps.key: ps for ps in hiring_analysis.parameter_scores}
    else:
        # No LLM scores — build defaults
        base_scores = {
            key: ParameterScore(
                key=key, name=name, max_score=mx,
                score=round(mx * 0.5, 1),
                reason="Computed from code metrics (LLM stage skipped).",
                evidence=[],
                suggestions=[],
            )
            for key, name, mx in PARAMETER_RUBRIC
        }

    result: list[ParameterScore] = []
    for key, name, max_score in PARAMETER_RUBRIC:
        ps = base_scores.get(key)
        if ps is None:
            ps = ParameterScore(key=key, name=name, max_score=max_score,
                                score=round(max_score * 0.5, 1),
                                reason="Not evaluated.", evidence=[], suggestions=[])

        if key == "code_quality":
            # 60% Radon MI + 40% LLM
            blended = code_quality_metric * 0.6 + ps.score * 0.4
            ps = ParameterScore(
                key=ps.key, name=ps.name, max_score=ps.max_score,
                score=round(min(max_score, max(0.0, blended)), 1),
                reason=f"{ps.reason} (Metric MI score: {code_quality_metric:.1f}/10)",
                evidence=ps.evidence,
                suggestions=ps.suggestions + (["Reduce cyclomatic complexity"] if code_quality_metric < 6 else []),
            )

        elif key == "security":
            # Take the lower of LLM and Semgrep scores (conservative)
            blended = ps.score * 0.5 + security_metric * 0.5
            ps = ParameterScore(
                key=ps.key, name=ps.name, max_score=ps.max_score,
                score=round(min(max_score, max(0.0, blended)), 1),
                reason=f"{ps.reason} (Semgrep metric: {security_metric:.1f}/5)",
                evidence=ps.evidence,
                suggestions=ps.suggestions + (["Fix critical security findings from static analysis"] if security_metric < 3 else []),
            )

        result.append(ps)
    return result


# ---------------------------------------------------------------------------
# Metric-based parameter scores
# ---------------------------------------------------------------------------

def _metric_code_quality(file_scores: list[FileScore]) -> float:
    """Return a 0–10 score based on average MI and cyclomatic complexity."""
    if not file_scores:
        return 5.0
    mi_avg = sum(fs.maintainability_index for fs in file_scores) / len(file_scores)
    cc_avg = sum(fs.cyclomatic_complexity_avg for fs in file_scores) / len(file_scores)
    mi_score = mi_avg / 100 * 10          # normalise MI (0-100) → 0-10
    cc_penalty = min(4.0, max(0.0, (cc_avg - 1) * 0.5))  # penalty for high CC
    return round(max(0.0, min(10.0, mi_score - cc_penalty)), 1)


def _metric_security(findings: list[StaticFinding]) -> float:
    """Return a 0–5 score: 5 with no findings, penalised for errors/warnings."""
    errors   = sum(1 for f in findings if (f.severity or "").upper() == "ERROR")
    warnings = sum(1 for f in findings if (f.severity or "").upper() == "WARNING")
    penalty  = min(5.0, errors * 0.7 + warnings * 0.2)
    return round(max(0.0, 5.0 - penalty), 1)


# ---------------------------------------------------------------------------
# Grade / recommendation derivation
# ---------------------------------------------------------------------------

def _hiring_grade(score: float) -> str:
    if score >= 80: return "Strong"
    if score >= 65: return "Good"
    if score >= 50: return "Average"
    return "Weak"


def _recommendation(score: float, ha: HiringAnalysis | None) -> str:
    # LLM recommendation signals take priority within reason
    if ha and ha.recommendation == "rejected" and score < 70:
        return "rejected"
    if ha and ha.recommendation == "shortlisted" and score >= 60:
        return "shortlisted"
    if score >= 75: return "shortlisted"
    if score >= 50: return "needs_review"
    return "rejected"


# ---------------------------------------------------------------------------
# Per-file hiring evaluations
# ---------------------------------------------------------------------------

def _build_file_evaluations(
    parsed_files: list[ParsedFile],
    file_scores: list[FileScore],
    findings_by_file: dict[str, list],
    base: Path,
    keywords: set[str],
) -> list[FileEvaluation]:
    scores_by_path = {fs.file_path: fs for fs in file_scores}
    evaluations: list[FileEvaluation] = []

    for pf in parsed_files:
        if any(skip in pf.path.lower() for skip in _SKIP_DIRS):
            continue
        purpose, base_priority = _infer_purpose(pf.path)
        if base_priority == 0:
            continue

        content = _read_content(base / pf.path, max_chars=3000)
        relevance, relevance_score = _compute_relevance(pf.path, content, keywords)
        fs = scores_by_path.get(pf.path)
        strengths = _derive_strengths(pf, fs, content)
        issues    = _derive_issues(pf, fs, findings_by_file.get(pf.path, []))

        code_score = fs.maintainability_index if fs else 60.0
        file_score = round(code_score * 0.6 + relevance_score * 0.4, 1)

        evaluations.append(FileEvaluation(
            file_path=pf.path, language=pf.language,
            purpose=purpose, relevance_to_task=relevance,
            strengths=strengths, issues=issues,
            file_score=min(100.0, file_score),
        ))

    evaluations.sort(key=lambda e: e.file_score, reverse=True)
    return evaluations[:20]


def _infer_purpose(file_path: str) -> tuple[str, int]:
    name  = Path(file_path).name.lower()
    parts = file_path.lower()
    skip_names = {".gitignore", ".gitkeep", ".ds_store", "license", "license.md", "license.txt"}
    if name in skip_names:
        return ("", 0)
    for pattern, (purpose, priority) in _KEY_FILE_PATTERNS.items():
        if name.startswith(pattern) or name == pattern.rstrip("."):
            return (purpose, priority)
    for kw, desc in [
        ("api", "API endpoint"), ("route", "Route handler"), ("controller", "Controller"),
        ("model", "Data model"), ("schema", "Schema definition"), ("service", "Service layer"),
        ("component", "UI component"), ("page", "Page component"), ("hook", "React hook"),
        ("util", "Utility"), ("helper", "Helper"), ("middleware", "Middleware"),
        ("test", "Test file"), ("spec", "Test file"),
    ]:
        if kw in parts:
            return (desc, 5)
    ext_map = {
        ".py": ("Python module", 4), ".js": ("JavaScript module", 4),
        ".ts": ("TypeScript module", 4), ".jsx": ("React component", 5),
        ".tsx": ("React component (TS)", 5), ".java": ("Java class", 4),
        ".go": ("Go module", 4), ".rs": ("Rust module", 4),
        ".yaml": ("Configuration", 3), ".yml": ("Configuration", 3),
        ".sql": ("SQL schema/query", 6), ".md": ("Documentation", 4),
        ".html": ("HTML template", 3), ".css": ("Stylesheet", 2),
    }
    ext = Path(file_path).suffix.lower()
    return ext_map.get(ext, ("", 0))


def _extract_keywords(text: str) -> set[str]:
    stopwords = {
        "a","an","the","and","or","but","in","on","at","to","for","of","with",
        "is","are","was","be","it","this","that","as","by","from","use","using",
        "build","create","make","develop","implement","should","must","can","will",
        "have","has","need","its","their",
    }
    return {w for w in re.findall(r"[a-zA-Z]{3,}", text.lower()) if w not in stopwords}


def _compute_relevance(file_path: str, content: str, keywords: set[str]) -> tuple[str, float]:
    if not keywords:
        return ("General project file", 50.0)
    search = (file_path + " " + content).lower()
    matched = {kw for kw in keywords if kw in search}
    score = min(100.0, len(matched) / max(len(keywords), 1) * 100)
    if score >= 60:
        desc = f"Directly relevant — implements {len(matched)} task concepts"
    elif score >= 30:
        desc = f"Partially relevant — touches {len(matched)} task concepts"
    else:
        desc = "Tangentially related"
    return (desc, score)


def _derive_strengths(pf: ParsedFile, fs: FileScore | None, content: str) -> list[str]:
    s = []
    if fs:
        if fs.maintainability_index >= 70: s.append(f"High maintainability (MI={fs.maintainability_index:.0f})")
        if fs.cyclomatic_complexity_avg <= 5: s.append("Low complexity — clean logic flow")
        if fs.security_findings == 0: s.append("No security issues detected")
    if pf.function_names: s.append(f"Well-structured with {len(pf.function_names)} functions")
    if pf.class_names:    s.append(f"OOP design with {len(pf.class_names)} classes")
    if pf.line_count > 50: s.append("Substantive implementation")
    if ("try" in content and "except" in content) or ("try" in content and "catch" in content):
        s.append("Implements error handling")
    if "test" in pf.path.lower() or "spec" in pf.path.lower():
        s.append("Includes tests")
    return s[:5]


def _derive_issues(pf: ParsedFile, fs: FileScore | None, findings: list) -> list[str]:
    i = []
    if fs:
        if fs.maintainability_index < 40:  i.append(f"Low maintainability (MI={fs.maintainability_index:.0f})")
        if fs.cyclomatic_complexity_avg > 10: i.append(f"High complexity (CC={fs.cyclomatic_complexity_avg:.1f})")
        if fs.security_findings > 0:       i.append(f"{fs.security_findings} security finding(s)")
    if 0 < pf.line_count < 10: i.append("Very short — may be incomplete")
    errors = [f for f in findings if (f.severity or "").upper() == "ERROR"]
    if errors: i.append(f"{len(errors)} critical static analysis error(s)")
    return i[:4]


def _read_content(path: Path, max_chars: int = 3000) -> str:
    try:
        t = path.read_text(encoding="utf-8", errors="replace")
        return t[:max_chars]
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Per-file code quality scoring (radon / lizard / basic)
# ---------------------------------------------------------------------------

def _score_radon(pf: ParsedFile, source_path: Path, n_issues: int) -> FileScore:
    try:
        import radon.complexity as rc, radon.metrics as rm, radon.raw as rr
        source = source_path.read_text(encoding="utf-8", errors="replace")
        raw = rr.analyze(source)
        cc_vals = [b.complexity for b in rc.cc_visit(source)] or [1]
        cc_avg, cc_max = sum(cc_vals) / len(cc_vals), max(cc_vals)
        mi = max(0.0, min(100.0, rm.mi_visit(source, multi=True)))
        try:
            h = rm.h_visit(source)
            halstead_vol = h[0].volume if h else 0.0
        except Exception:
            halstead_vol = 0.0
        return FileScore(
            file_path=pf.path, language=pf.language,
            cyclomatic_complexity_avg=round(cc_avg, 2), cyclomatic_complexity_max=int(cc_max),
            maintainability_index=round(mi, 1), mi_grade=_mi_grade(mi),
            halstead_volume=round(halstead_vol, 1),
            loc=raw.loc, lloc=raw.lloc,
            security_findings=n_issues, complexity_grade=_cc_grade(cc_max),
        )
    except Exception as exc:
        log.debug("Radon failed on %s: %s", pf.path, exc)
        return _score_basic(pf, n_issues)


def _score_lizard(pf: ParsedFile, source_path: Path, n_issues: int) -> FileScore:
    try:
        import lizard
        res = lizard.analyze_file(str(source_path))
        fns = res.function_list or []
        cc_vals = [f.cyclomatic_complexity for f in fns] or [1]
        cc_avg, cc_max = sum(cc_vals) / len(cc_vals), max(cc_vals)
        loc = res.nloc or pf.line_count
        mi = _mi_proxy(cc_avg, loc)
        return FileScore(
            file_path=pf.path, language=pf.language,
            cyclomatic_complexity_avg=round(cc_avg, 2), cyclomatic_complexity_max=int(cc_max),
            maintainability_index=round(mi, 1), mi_grade=_mi_grade(mi),
            halstead_volume=0.0, loc=loc, lloc=loc,
            security_findings=n_issues, complexity_grade=_cc_grade(cc_max),
        )
    except Exception as exc:
        log.debug("lizard failed on %s: %s", pf.path, exc)
        return _score_basic(pf, n_issues)


def _score_basic(pf: ParsedFile, n_issues: int) -> FileScore:
    n_funcs = max(1, len(pf.function_names))
    cc_est  = max(1.0, pf.line_count / n_funcs / 10)
    mi_est  = _mi_proxy(cc_est, pf.line_count)
    return FileScore(
        file_path=pf.path, language=pf.language,
        cyclomatic_complexity_avg=round(cc_est, 2), cyclomatic_complexity_max=int(cc_est),
        maintainability_index=round(mi_est, 1), mi_grade=_mi_grade(mi_est),
        halstead_volume=0.0, loc=pf.line_count, lloc=pf.line_count,
        security_findings=n_issues, complexity_grade=_cc_grade(cc_est),
    )


# ---------------------------------------------------------------------------
# Grade helpers
# ---------------------------------------------------------------------------

def _mi_grade(score: float) -> str:
    for t, g in _MI_GRADE_THRESHOLDS:
        if score >= t: return g
    return "F"


def _cc_grade(cc: float) -> str:
    for t, g in _CC_GRADE_THRESHOLDS:
        if cc <= t: return g
    return "F"


def _mi_proxy(cc_avg: float, loc: int) -> float:
    return max(0.0, 100.0 - min(40.0, (cc_avg - 1) * 4) - min(20.0, math.log1p(loc) * 2))


def _check_radon() -> bool:
    try:
        import radon; return True
    except ImportError:
        log.warning("radon not installed"); return False


def _check_lizard() -> bool:
    try:
        import lizard; return True
    except ImportError:
        log.warning("lizard not installed"); return False


# ---------------------------------------------------------------------------
# Summary log
# ---------------------------------------------------------------------------

def _log_summary(result: PipelineResult) -> None:
    log.info("=" * 64)
    log.info("HIRING EVALUATION COMPLETE")
    log.info("  Score  : %.1f/100  (code grade %s)", result.overall_score, result.overall_grade)
    log.info("  Hiring : %s → %s", result.hiring_grade, result.recommendation.upper())
    log.info("  Params :")
    for ps in result.parameter_scores:
        bar = "█" * int(ps.score / ps.max_score * 10)
        log.info("    %-14s %4.1f/%d  %s", ps.key, ps.score, ps.max_score, bar)
    log.info("  Files  : %d scored, %d evaluated", len(result.file_scores), len(result.file_evaluations))
    log.info("  Issues : %d", len(result.static_findings))
    log.info("=" * 64)
