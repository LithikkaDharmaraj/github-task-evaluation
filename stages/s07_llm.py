"""
stages/s07_llm.py — Stage 07: LLM Hiring Evaluation via Groq API.

Uses LLaMA 3.3 70B Versatile (via Groq) to score the candidate's repository
on 10 hiring parameters against the given project title and description.

Scoring rubric (100 marks total):
  relevancy      20  How well the project matches the task description
  accuracy       15  Features implemented correctly
  completeness   15  All expected features present
  code_quality   10  Clean, readable, maintainable code  [blended with Radon]
  architecture   10  Proper structure and separation of concerns
  performance    10  Efficient, avoids unnecessary heavy operations
  security        5  Validation, auth, no exposed secrets  [blended with Semgrep]
  error_handling  5  Proper failure and edge-case handling
  database        5  Schema design, queries, relationships
  documentation   5  README, setup, tests, deployment readiness
"""

from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from core.config import (
    PARAMETER_RUBRIC, SKIP_DIRS,
    HiringAnalysis, LLMAnalysis, ParameterScore,
    ParsedFile, PipelineConfig, RepoMeta, StaticFinding,
)
from core.logger import get_logger

log = get_logger("s07_llm")

_MAX_SOURCE_CHARS_PER_FILE = 2_500
_MAX_FINDINGS              = 20
_MAX_FILES_FOR_CONTEXT     = 12
_MAX_MANIFEST_FILES        = 200   # full file list sent to LLM (paths only, no source)

# Keys whose scores are blended with rule-based metrics in s08
_METRIC_BLENDED_KEYS = {"code_quality", "security"}

# Regex to parse one PARAM line from LLM output
_PARAM_RE = re.compile(
    r"PARAM\s*:\s*(\w+)\s*\|\s*SCORE\s*:\s*(\d+(?:\.\d+)?)\s*\|"
    r"\s*REASON\s*:\s*([^|]*?)\s*\|\s*EVIDENCE\s*:\s*([^|]*?)\s*\|\s*SUGGEST\s*:\s*(.*)",
    re.IGNORECASE,
)


def run(
    repo_meta: RepoMeta,
    parsed_files: list[ParsedFile],
    static_findings: list[StaticFinding],
    cfg: PipelineConfig,
) -> tuple[list[LLMAnalysis], HiringAnalysis]:

    api_key = cfg.groq_api_key or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. "
            "Add it to your .env file or set the environment variable."
        )

    log.info("Using Groq model: %s", cfg.llm_model)

    base   = Path(repo_meta.local_path)
    prompt = _build_prompt(
        repo_meta=repo_meta,
        parsed_files=parsed_files,
        static_findings=static_findings,
        base=base,
        project_title=cfg.project_title,
        project_description=cfg.project_description,
    )

    response = _call_groq(prompt, cfg, api_key)
    log.info("Groq response received — parsing parameter scores…")

    param_scores = _parse_parameter_scores(response)
    hiring       = _build_hiring_analysis(param_scores, cfg.project_title)
    llm_record   = _hiring_to_llm_analysis(hiring)

    log.info(
        "LLM eval done — %d/10 params from LLM, %d defaulted | total=%.1f",
        sum(1 for ps in param_scores if "default score" not in ps.reason),
        sum(1 for ps in param_scores if "default score" in ps.reason),
        sum(ps.score for ps in param_scores),
    )
    return [llm_record], hiring


# ---------------------------------------------------------------------------
# Groq API call
# ---------------------------------------------------------------------------

def _call_groq(prompt: str, cfg: PipelineConfig, api_key: str) -> str:
    try:
        from groq import Groq
    except ImportError:
        raise ImportError("groq package not installed. Run: pip install groq")

    client = Groq(api_key=api_key)

    completion = client.chat.completions.create(
        model=cfg.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=cfg.llm_temperature,
        max_tokens=cfg.llm_max_new_tokens,
    )
    return completion.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_prompt(
    repo_meta: RepoMeta,
    parsed_files: list[ParsedFile],
    static_findings: list[StaticFinding],
    base: Path,
    project_title: str,
    project_description: str,
) -> str:
    file_overview    = _build_file_overview(parsed_files, static_findings)
    full_manifest    = _build_full_file_manifest(parsed_files)
    source_snippets  = _build_source_context(base, parsed_files)
    findings_block   = _format_findings(static_findings)

    rubric_lines = "\n".join(
        f"  {key} (max {mx}): {_RUBRIC_DESC[key]}"
        for key, _, mx in PARAMETER_RUBRIC
    )

    return (
        "You are a senior technical interviewer scoring a candidate's coding assignment.\n\n"
        "=== HIRING TASK ===\n"
        f"Title: {project_title or 'Not specified'}\n"
        f"Requirements:\n{project_description or 'Not specified'}\n\n"
        "=== CANDIDATE REPOSITORY ===\n"
        f"URL: {repo_meta.url}\n"
        f"Files: {repo_meta.total_files} | "
        f"Languages: {', '.join(repo_meta.languages_detected) or 'unknown'} | "
        f"Commits: {repo_meta.total_commits}\n\n"
        "=== ALL PROJECT FILES ===\n"
        f"{full_manifest}\n\n"
        "=== KEY FILES (detailed) ===\n"
        f"{file_overview}\n\n"
        "=== STATIC ANALYSIS ===\n"
        f"{findings_block}\n\n"
        "=== SOURCE SNIPPETS ===\n"
        f"{source_snippets}\n\n"
        "=== SCORING TASK ===\n"
        "Score the candidate on ALL 10 parameters below.\n"
        "Use the full file list above to assess completeness and architecture across the ENTIRE project,\n"
        "not just the source snippets shown.\n"
        "Output EXACTLY 10 lines, ONE line per parameter, in this EXACT format:\n"
        "PARAM:key|SCORE:number|REASON:brief explanation|EVIDENCE:file1,file2|SUGGEST:one suggestion\n\n"
        "Rules:\n"
        "- Score must not exceed the max for each parameter\n"
        "- REASON: 1-2 sentences, specific to the code you saw\n"
        "- EVIDENCE: comma-separated file paths (use actual file names from the repo)\n"
        "- SUGGEST: one concrete, actionable improvement\n"
        "- Output ONLY the 10 PARAM lines, no extra text\n\n"
        "Parameters to score:\n"
        f"{rubric_lines}\n\n"
        "Example line:\n"
        "PARAM:relevancy|SCORE:15|REASON:Implements JWT auth as described in requirements|"
        "EVIDENCE:routes/auth.py,models/user.py|SUGGEST:Add refresh token rotation\n\n"
        "Output all 10 PARAM lines now:"
    )


_RUBRIC_DESC: dict[str, str] = {
    "relevancy":      "Does the project match what was asked?",
    "accuracy":       "Are the implemented features correct and functional?",
    "completeness":   "Are all expected modules/features present?",
    "code_quality":   "Readability, naming, modularity, maintainability",
    "architecture":   "Proper separation: frontend/backend/db/routes/services",
    "performance":    "Efficient code, no unnecessary heavy operations",
    "security":       "Input validation, auth/authz, no exposed secrets",
    "error_handling": "Handles failures, invalid input, edge cases",
    "database":       "Schema correctness, relationships, query quality",
    "documentation":  "README quality, setup steps, tests, deployment readiness",
}


def _build_file_overview(parsed_files: list[ParsedFile], static_findings: list[StaticFinding]) -> str:
    if not parsed_files:
        return "(no parsed files)"

    findings_by_file: dict[str, int] = defaultdict(int)
    for f in static_findings:
        findings_by_file[f.file_path] += 1

    selected = _select_key_files(parsed_files)
    lines: list[str] = []
    for pf in selected:
        funcs  = ", ".join(pf.function_names[:6]) or "(none)"
        issues = findings_by_file.get(pf.path, 0)
        lines.append(
            f"- {pf.path} ({pf.language}, {pf.line_count}L, {issues} issues) funcs: {funcs}"
        )
    return "\n".join(lines)


def _build_source_context(base: Path, parsed_files: list[ParsedFile]) -> str:
    if not parsed_files:
        return "(none)"
    selected = _select_key_files(parsed_files)[:_MAX_FILES_FOR_CONTEXT]
    blocks: list[str] = []
    for pf in selected:
        text = _read_source(base / pf.path, _MAX_SOURCE_CHARS_PER_FILE)
        blocks.append(f"--- {pf.path} ---\n{text}")
    return "\n\n".join(blocks)


def _format_findings(findings: list[StaticFinding]) -> str:
    if not findings:
        return "(none)"
    counts = Counter((f.severity or "INFO").upper() for f in findings)
    lines  = [
        f"ERROR={counts.get('ERROR', 0)}, "
        f"WARNING={counts.get('WARNING', 0)}, "
        f"INFO={counts.get('INFO', 0)}"
    ]
    for f in findings[:_MAX_FINDINGS]:
        lines.append(f"- [{f.severity}] {f.rule_id} line {f.line_start}: {f.message}")
    return "\n".join(lines)


def _build_full_file_manifest(parsed_files: list[ParsedFile]) -> str:
    """List every parsed file (path + language + lines) so the LLM sees the full project scope."""
    if not parsed_files:
        return "(no files)"
    filtered = [pf for pf in parsed_files if not any(skip in pf.path.lower() for skip in SKIP_DIRS)]
    lines = [
        f"{pf.path} ({pf.language}, {pf.line_count}L)"
        for pf in filtered[:_MAX_MANIFEST_FILES]
    ]
    suffix = (
        f"\n... and {len(filtered) - _MAX_MANIFEST_FILES} more files"
        if len(filtered) > _MAX_MANIFEST_FILES else ""
    )
    return "\n".join(lines) + suffix


_KEY_FILE_NAMES = {
    "readme", "package.json", "requirements.txt", "pyproject.toml",
    "main.", "app.", "index.", "server.", "routes.", "router.",
    "models.", "schema.", "database.", "db.", "config.", "settings.",
    "api.", "views.", "controllers.", "auth.", "middleware.",
}


def _select_key_files(parsed_files: list[ParsedFile]) -> list[ParsedFile]:
    scored: list[tuple[int, ParsedFile]] = []
    for pf in parsed_files:
        if any(skip in pf.path.lower() for skip in SKIP_DIRS):
            continue
        name_lower = Path(pf.path).name.lower()
        priority   = 0
        if any(name_lower.startswith(p) or name_lower == p.rstrip(".") for p in _KEY_FILE_NAMES):
            priority += 10
        priority += min(5, pf.line_count // 50)
        if any(kw in pf.path.lower() for kw in ("api", "route", "controller", "model", "schema",
                                                  "service", "backend", "frontend", "src")):
            priority += 3
        scored.append((priority, pf))
    scored.sort(key=lambda x: (-x[0], -x[1].line_count))
    return [pf for _, pf in scored[:_MAX_FILES_FOR_CONTEXT]]


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_parameter_scores(response: str) -> list[ParameterScore]:
    rubric_map = {key: (name, mx) for key, name, mx in PARAMETER_RUBRIC}

    parsed: dict[str, dict] = {}
    for line in response.splitlines():
        m = _PARAM_RE.search(line)
        if not m:
            continue
        key = m.group(1).lower().strip()
        if key not in rubric_map:
            continue
        _, max_score = rubric_map[key]
        parsed[key] = {
            "score":       min(float(max_score), max(0.0, float(m.group(2)))),
            "reason":      m.group(3).strip(),
            "evidence":    [e.strip() for e in m.group(4).split(",") if e.strip()],
            "suggestions": [s.strip() for s in [m.group(5).strip()] if s.strip()],
        }

    result: list[ParameterScore] = []
    for key, name, max_score in PARAMETER_RUBRIC:
        if key in parsed:
            p = parsed[key]
            result.append(ParameterScore(
                key=key, name=name, max_score=max_score,
                score=p["score"], reason=p["reason"],
                evidence=p["evidence"], suggestions=p["suggestions"],
            ))
        else:
            result.append(ParameterScore(
                key=key, name=name, max_score=max_score,
                score=round(max_score * 0.5, 1),
                reason="Could not be evaluated — using default score.",
                evidence=[],
                suggestions=[f"Ensure {name.lower()} requirements are clearly demonstrated."],
            ))
    return result


# ---------------------------------------------------------------------------
# Analysis builders
# ---------------------------------------------------------------------------

def _build_hiring_analysis(
    param_scores: list[ParameterScore],
    project_title: str,
) -> HiringAnalysis:
    score_by_key = {ps.key: ps for ps in param_scores}
    total        = sum(ps.score for ps in param_scores)

    if total >= 75:
        recommendation = "shortlisted"
    elif total >= 50:
        recommendation = "needs_review"
    else:
        recommendation = "rejected"

    matched = [
        f"{ps.name}: {ps.reason}"
        for ps in param_scores
        if ps.score >= ps.max_score * 0.6
        and ps.reason
        and "default score" not in ps.reason
    ]

    missing = [
        f"{ps.name} ({ps.score:.0f}/{ps.max_score}): "
        f"{ps.suggestions[0] if ps.suggestions else 'Needs improvement'}"
        for ps in param_scores
        if ps.score < ps.max_score * 0.5
    ]

    project_match = " | ".join(
        score_by_key[k].reason
        for k in ("relevancy", "accuracy")
        if k in score_by_key and score_by_key[k].reason
    ) or f"Evaluation for: {project_title}"

    implementation_quality = " | ".join(
        score_by_key[k].reason
        for k in ("completeness", "architecture", "performance")
        if k in score_by_key and score_by_key[k].reason
    )

    low_params = [ps for ps in param_scores if ps.score < ps.max_score * 0.6]
    interviewer_notes = "\n".join(
        f"- [{ps.name}] {ps.suggestions[0]}"
        for ps in low_params[:5]
        if ps.suggestions
    )

    from itertools import chain, islice
    suggestions = list(islice(
        dict.fromkeys(chain.from_iterable(
            ps.suggestions for ps in sorted(param_scores, key=lambda x: x.score / x.max_score)
        )),
        6,
    ))

    return HiringAnalysis(
        project_match=project_match,
        implementation_quality=implementation_quality,
        matched_requirements=matched,
        missing_requirements=missing,
        recommendation=recommendation,
        interviewer_notes=interviewer_notes,
        improvement_suggestions=suggestions,
        parameter_scores=param_scores,
    )


def _hiring_to_llm_analysis(ha: HiringAnalysis) -> LLMAnalysis:
    summary_parts  = [p for p in (ha.project_match, ha.implementation_quality) if p]
    matched_text   = "\n".join(f"- {r}" for r in ha.matched_requirements) or "(none identified)"
    missing_text   = "\n".join(f"- {r}" for r in ha.missing_requirements)  or "(none identified)"

    return LLMAnalysis(
        file_path="HIRING_SUMMARY",
        summary="\n\n".join(summary_parts),
        quality_assessment=f"MATCHED:\n{matched_text}\n\nMISSING:\n{missing_text}",
        interview_notes=f"RECOMMENDATION: {ha.recommendation.upper()}\n\n{ha.interviewer_notes}",
    )


def _read_source(path: Path, max_chars: int) -> str:
    try:
        t = path.read_text(encoding="utf-8", errors="replace")
        return t[:max_chars] + ("\n...(truncated)" if len(t) > max_chars else "")
    except OSError:
        return "(could not read)"
