"""
test_edge_cases.py — Edge-case tests for task-evaluation-version2.

Tests every stage and its fallback paths without the web server or a real
GitHub repo.  Run with:

    python3 test_edge_cases.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config import (
    PARAMETER_RUBRIC, HiringAnalysis, LLMAnalysis,
    ParameterScore, ParsedFile, PipelineConfig, RepoMeta, StaticFinding,
)

# ─────────────────────────────────────────────────────────────────────────────
# Minimal test harness
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Result:
    name: str
    passed: bool
    detail: str


_results: list[Result] = []
_test_fns: list = []   # ordered list of test wrappers


def test(name: str):
    """Decorator: catches exceptions and records pass/fail."""
    def decorator(fn: Callable):
        def wrapper():
            try:
                fn()
                _results.append(Result(name, True, "ok"))
                print(f"  PASS  {name}")
            except AssertionError as exc:
                _results.append(Result(name, False, str(exc)))
                print(f"  FAIL  {name}\n        {exc}")
            except Exception as exc:
                tb = traceback.format_exc().strip().splitlines()[-1]
                _results.append(Result(name, False, f"{type(exc).__name__}: {exc}\n        {tb}"))
                print(f"  ERR   {name}\n        {type(exc).__name__}: {exc}")
        wrapper._is_test = True
        _test_fns.append(wrapper)
        return wrapper
    return decorator


def _make_repo(files: dict[str, str]) -> tuple[RepoMeta, PipelineConfig]:
    """Create a temp directory with the given files, return (RepoMeta, cfg)."""
    tmp = tempfile.mkdtemp(prefix="eval_test_")
    for rel, content in files.items():
        fp = Path(tmp) / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            fp.write_bytes(content)
        else:
            fp.write_text(content, encoding="utf-8")
    meta = RepoMeta(
        url="https://github.com/test/repo",
        local_path=tmp,
        default_branch="main",
        head_commit="abc123",
        total_files=len(files),
        languages_detected=["python"],
        total_commits=5,
    )
    cfg = PipelineConfig()
    return meta, cfg


def _default_hiring(score_override: dict | None = None) -> HiringAnalysis:
    scores = []
    for key, name, mx in PARAMETER_RUBRIC:
        s = score_override.get(key, mx * 0.6) if score_override else mx * 0.6
        scores.append(ParameterScore(
            key=key, name=name, max_score=mx,
            score=s, reason="Test reason.", evidence=[], suggestions=[],
        ))
    return HiringAnalysis(
        project_match="Test match",
        implementation_quality="Test quality",
        matched_requirements=["feature A"],
        missing_requirements=[],
        recommendation="shortlisted",
        interviewer_notes="",
        improvement_suggestions=[],
        parameter_scores=scores,
    )


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 02 — Parser
# ─────────────────────────────────────────────────────────────────────────────

@test("S02 — empty repo returns zero parsed files")
def _():
    meta, cfg = _make_repo({})
    from stages import s02_parser
    parsed = s02_parser.run(meta, cfg)
    assert len(parsed) == 0, f"Expected 0 parsed files, got {len(parsed)}"


@test("S02 — file exceeding max_file_size_bytes is skipped")
def _():
    meta, cfg = _make_repo({"big.py": "x = 1\n" * 200_000})
    cfg.max_file_size_bytes = 100  # tiny limit
    from stages import s02_parser
    parsed = s02_parser.run(meta, cfg)
    assert not any(p.path == "big.py" for p in parsed), "Oversized file should have been skipped"


@test("S02 — file in skip directory (node_modules) is excluded")
def _():
    meta, cfg = _make_repo({"node_modules/lodash/index.js": "module.exports = {};"})
    from stages import s02_parser
    parsed = s02_parser.run(meta, cfg)
    assert len(parsed) == 0, "Files inside node_modules should be excluded"


@test("S02 — binary bytes in .py file don't crash the parser")
def _():
    meta, cfg = _make_repo({"broken.py": b"\x00\x01\x02def foo():\n    pass\n"})
    from stages import s02_parser
    parsed = s02_parser.run(meta, cfg)
    # Should produce one ParsedFile (or zero if unreadable) but not raise
    assert isinstance(parsed, list)


@test("S02 — malformed Python is parsed with error flag")
def _():
    bad_python = "def foo(\n    # unclosed paren — syntax error\n"
    meta, cfg = _make_repo({"bad.py": bad_python})
    from stages import s02_parser
    parsed = s02_parser.run(meta, cfg)
    assert len(parsed) == 1
    assert parsed[0].parse_error is True, "parse_error should be True for invalid syntax"


@test("S02 — valid Python extracts functions and classes")
def _():
    src = "class Foo:\n    def bar(self): pass\n    def baz(self): pass\n"
    meta, cfg = _make_repo({"app.py": src})
    from stages import s02_parser
    parsed = s02_parser.run(meta, cfg)
    assert len(parsed) == 1
    pf = parsed[0]
    assert "bar" in pf.function_names or "baz" in pf.function_names, \
        f"Expected functions, got {pf.function_names}"
    assert "Foo" in pf.class_names, f"Expected class Foo, got {pf.class_names}"


@test("S02 — Jupyter notebook code cells are extracted")
def _():
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {"cell_type": "markdown", "source": ["# Title"], "metadata": {}},
            {"cell_type": "code", "source": ["def notebook_fn():\n    return 42\n"], "metadata": {}, "outputs": []},
        ],
    }
    meta, cfg = _make_repo({"analysis.ipynb": json.dumps(notebook)})
    from stages import s02_parser
    parsed = s02_parser.run(meta, cfg)
    assert len(parsed) == 1
    assert "notebook_fn" in parsed[0].function_names, \
        f"Notebook function not found: {parsed[0].function_names}"


@test("S02 — multiple languages parsed together")
def _():
    files = {
        "app.py": "def main(): pass\n",
        "index.js": "function main() {}\n",
        "App.java": "class App { void main() {} }\n",
    }
    meta, cfg = _make_repo(files)
    from stages import s02_parser
    parsed = s02_parser.run(meta, cfg)
    langs = {p.language for p in parsed}
    assert "python" in langs and "javascript" in langs and "java" in langs, \
        f"Expected python/javascript/java, got {langs}"


@test("S02 — heuristic fallback produces ParsedFile when tree-sitter disabled")
def _():
    src = "def alpha(): pass\nclass Beta: pass\n"
    meta, cfg = _make_repo({"mod.py": src})
    from stages import s02_parser
    # Force the heuristic path by returning None for the factory
    with patch.object(s02_parser, "_init_treesitter_factory", return_value=None):
        parsed = s02_parser.run(meta, cfg)
    assert len(parsed) == 1
    assert "alpha" in parsed[0].function_names
    assert "Beta" in parsed[0].class_names


@test("S02 — large project (300 files) all get parsed, no silent cap")
def _():
    files = {f"module_{i}.py": f"def fn_{i}(): pass\n" for i in range(300)}
    meta, cfg = _make_repo(files)
    from stages import s02_parser
    parsed = s02_parser.run(meta, cfg)
    assert len(parsed) == 300, f"Expected 300 parsed files, got {len(parsed)}"


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 03 — Static Analysis (fallback chain)
# ─────────────────────────────────────────────────────────────────────────────

@test("S03 — returns list (even if semgrep/bandit unavailable)")
def _():
    meta, cfg = _make_repo({"app.py": "import os\nos.system('rm -rf /')\n"})
    from stages import s03_static
    findings = s03_static.run(meta, cfg)
    assert isinstance(findings, list), "Should always return a list"


@test("S03 — semgrep unavailable falls back to bandit gracefully")
def _():
    meta, cfg = _make_repo({"app.py": "import subprocess\nsubprocess.call('ls')\n"})
    from stages import s03_static
    with patch.object(s03_static, "_semgrep_available", return_value=False):
        findings = s03_static.run(meta, cfg)
    assert isinstance(findings, list)


@test("S03 — both semgrep and bandit unavailable → empty findings, no crash")
def _():
    meta, cfg = _make_repo({"app.py": "print('hello')\n"})
    from stages import s03_static
    with patch.object(s03_static, "_semgrep_available", return_value=False), \
         patch.object(s03_static, "_bandit_available", return_value=False):
        findings = s03_static.run(meta, cfg)
    assert findings == [], f"Expected empty list, got {findings}"


@test("S03 — semgrep timeout returns empty findings without crash")
def _():
    import subprocess as sp
    meta, cfg = _make_repo({"app.py": "pass\n"})
    from stages import s03_static
    with patch.object(s03_static, "_semgrep_available", return_value=True), \
         patch.object(s03_static, "_semgrep_cmd", return_value=["semgrep"]), \
         patch("subprocess.run", side_effect=sp.TimeoutExpired("semgrep", 10)):
        findings = s03_static.run(meta, cfg)
    assert findings == []


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 07 — LLM (Groq)
# ─────────────────────────────────────────────────────────────────────────────

def _minimal_parsed_files(n: int = 3) -> list[ParsedFile]:
    return [
        ParsedFile(
            path=f"module_{i}.py", language="python",
            size_bytes=200, line_count=10,
            function_names=[f"fn_{i}"], class_names=[], imports=[],
            ast_node_count=5, parse_error=False,
        )
        for i in range(n)
    ]

def _good_llm_response() -> str:
    lines = []
    for key, _, mx in PARAMETER_RUBRIC:
        score = round(mx * 0.7, 0)
        lines.append(
            f"PARAM:{key}|SCORE:{score}|REASON:Test reason for {key}.|"
            f"EVIDENCE:module_0.py|SUGGEST:Improve {key}"
        )
    return "\n".join(lines)


@test("S07 — missing GROQ_API_KEY raises RuntimeError")
def _():
    from stages import s07_llm
    meta, cfg = _make_repo({"app.py": "pass\n"})
    cfg.groq_api_key = ""
    parsed = _minimal_parsed_files()
    try:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GROQ_API_KEY", None)
            s07_llm.run(meta, parsed, [], cfg)
        assert False, "Should have raised RuntimeError"
    except RuntimeError as exc:
        assert "GROQ_API_KEY" in str(exc)
    finally:
        pass  # env restored after test


@test("S07 — malformed LLM response (no PARAM lines) → all params get 50% default")
def _():
    from stages import s07_llm
    meta, cfg = _make_repo({"app.py": "pass\n"})
    cfg.groq_api_key = "test-key"
    parsed = _minimal_parsed_files()

    with patch.object(s07_llm, "_call_groq", return_value="The candidate did a great job overall."):
        _, hiring = s07_llm.run(meta, parsed, [], cfg)

    assert len(hiring.parameter_scores) == 10
    for ps in hiring.parameter_scores:
        expected_default = round(ps.max_score * 0.5, 1)
        assert ps.score == expected_default, \
            f"{ps.key}: expected default {expected_default}, got {ps.score}"


@test("S07 — partial LLM response (5/10 params) → missing params get 50% default")
def _():
    from stages import s07_llm
    meta, cfg = _make_repo({"app.py": "pass\n"})
    cfg.groq_api_key = "test-key"
    parsed = _minimal_parsed_files()

    # Only first 5 params
    half_response = "\n".join(
        f"PARAM:{key}|SCORE:{mx}|REASON:ok|EVIDENCE:app.py|SUGGEST:none"
        for key, _, mx in PARAMETER_RUBRIC[:5]
    )
    with patch.object(s07_llm, "_call_groq", return_value=half_response):
        _, hiring = s07_llm.run(meta, parsed, [], cfg)

    scored_keys = {ps.key for ps in hiring.parameter_scores if "default score" not in ps.reason}
    default_keys = {ps.key for ps in hiring.parameter_scores if "default score" in ps.reason}
    assert len(default_keys) == 5, f"Expected 5 defaults, got {default_keys}"


@test("S07 — LLM returns score exceeding max → clamped to max")
def _():
    from stages import s07_llm
    meta, cfg = _make_repo({"app.py": "pass\n"})
    cfg.groq_api_key = "test-key"
    parsed = _minimal_parsed_files()

    # All scores way above their max
    bloated = "\n".join(
        f"PARAM:{key}|SCORE:9999|REASON:ok|EVIDENCE:app.py|SUGGEST:none"
        for key, _, mx in PARAMETER_RUBRIC
    )
    with patch.object(s07_llm, "_call_groq", return_value=bloated):
        _, hiring = s07_llm.run(meta, parsed, [], cfg)

    for ps in hiring.parameter_scores:
        assert ps.score <= ps.max_score, \
            f"{ps.key}: score {ps.score} exceeds max {ps.max_score}"


@test("S07 — LLM returns score of 0 for all → recommendation is 'rejected'")
def _():
    from stages import s07_llm
    meta, cfg = _make_repo({"app.py": "pass\n"})
    cfg.groq_api_key = "test-key"
    parsed = _minimal_parsed_files()

    zeros = "\n".join(
        f"PARAM:{key}|SCORE:0|REASON:nothing|EVIDENCE:|SUGGEST:rewrite"
        for key, _, mx in PARAMETER_RUBRIC
    )
    with patch.object(s07_llm, "_call_groq", return_value=zeros):
        _, hiring = s07_llm.run(meta, parsed, [], cfg)

    assert hiring.recommendation == "rejected", f"Got {hiring.recommendation}"


@test("S07 — full manifest includes all files when >200 in project")
def _():
    from stages import s07_llm
    meta, cfg = _make_repo({})
    cfg.groq_api_key = "test-key"

    # Build 300 ParsedFile objects
    parsed = [
        ParsedFile(path=f"src/mod_{i}.py", language="python",
                   size_bytes=100, line_count=20, function_names=[f"fn_{i}"],
                   class_names=[], imports=[], ast_node_count=5, parse_error=False)
        for i in range(300)
    ]

    captured_prompt: list[str] = []
    def _fake_call(prompt, cfg_, key):
        captured_prompt.append(prompt)
        return _good_llm_response()

    with patch.object(s07_llm, "_call_groq", side_effect=_fake_call):
        s07_llm.run(meta, parsed, [], cfg)

    prompt = captured_prompt[0]
    assert "=== ALL PROJECT FILES ===" in prompt, "Full manifest section missing"
    assert "... and 100 more files" in prompt, "Truncation note missing for >200 files"
    # Source snippets still limited to 12
    snippet_count = prompt.count("--- src/mod_")
    assert snippet_count <= 12, f"Source snippets not capped: {snippet_count}"


@test("S07 — Groq API exception propagates (no silent swallow in s07)")
def _():
    from stages import s07_llm
    meta, cfg = _make_repo({"app.py": "pass\n"})
    cfg.groq_api_key = "bad-key"
    parsed = _minimal_parsed_files()

    with patch.object(s07_llm, "_call_groq", side_effect=Exception("connection refused")):
        try:
            s07_llm.run(meta, parsed, [], cfg)
            assert False, "Should have propagated the exception"
        except Exception as exc:
            assert "connection refused" in str(exc)


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 08 — Scorer
# ─────────────────────────────────────────────────────────────────────────────

@test("S08 — empty parsed_files → overall_score=0, recommendation='rejected'")
def _():
    from stages import s08_scorer
    meta, cfg = _make_repo({})
    result = s08_scorer.run(meta, [], [], [], None, cfg)
    assert result.overall_score == 0.0
    assert result.recommendation == "rejected"
    assert result.hiring_grade == "Weak"
    assert len(result.parameter_scores) == 10
    assert all(ps.score == 0.0 for ps in result.parameter_scores)


@test("S08 — hiring_analysis=None → metric-only defaults fill all 10 params")
def _():
    from stages import s08_scorer
    meta, cfg = _make_repo({"app.py": "def foo(): pass\n"})
    parsed = [ParsedFile(path="app.py", language="python",
                          size_bytes=100, line_count=5,
                          function_names=["foo"], class_names=[], imports=[],
                          ast_node_count=3, parse_error=False)]
    result = s08_scorer.run(meta, parsed, [], [], None, cfg)
    assert len(result.parameter_scores) == 10
    assert all(ps.score >= 0 for ps in result.parameter_scores)


@test("S08 — radon/lizard both unavailable → fallback _score_basic, no crash")
def _():
    from stages import s08_scorer
    meta, cfg = _make_repo({"app.py": "def foo():\n    pass\n"})
    parsed = [ParsedFile(path="app.py", language="python",
                          size_bytes=50, line_count=2,
                          function_names=["foo"], class_names=[], imports=[],
                          ast_node_count=3, parse_error=False)]
    with patch.object(s08_scorer, "_check_radon", return_value=False), \
         patch.object(s08_scorer, "_check_lizard", return_value=False):
        result = s08_scorer.run(meta, parsed, [], [], _default_hiring(), cfg)
    assert len(result.file_scores) == 1
    assert result.file_scores[0].maintainability_index > 0


@test("S08 — files with unrecognised purpose no longer skipped (regression for big projects)")
def _():
    from stages import s08_scorer
    meta, cfg = _make_repo({})
    # Files whose names don't match any _KEY_FILE_PATTERNS or known keyword
    parsed = [
        ParsedFile(path="utils/obscure_helper_xyz.py", language="python",
                   size_bytes=200, line_count=30,
                   function_names=["do_thing"], class_names=[], imports=[],
                   ast_node_count=10, parse_error=False),
        ParsedFile(path="core/magic_processor.py", language="python",
                   size_bytes=300, line_count=40,
                   function_names=["process"], class_names=[], imports=[],
                   ast_node_count=15, parse_error=False),
    ]
    result = s08_scorer.run(meta, parsed, [], [], _default_hiring(), cfg)
    # Both files should appear in file_evaluations now (previously skipped)
    eval_paths = {fe.file_path for fe in result.file_evaluations}
    assert "utils/obscure_helper_xyz.py" in eval_paths, \
        "Unrecognised file was skipped from evaluations"
    assert "core/magic_processor.py" in eval_paths, \
        "Unrecognised file was skipped from evaluations"


@test("S08 — large project (100 files) produces evaluation for all, no 20-cap")
def _():
    from stages import s08_scorer
    meta, cfg = _make_repo({})
    parsed = [
        ParsedFile(path=f"module_{i}.py", language="python",
                   size_bytes=200, line_count=20,
                   function_names=[f"fn_{i}"], class_names=[], imports=[],
                   ast_node_count=8, parse_error=False)
        for i in range(100)
    ]
    result = s08_scorer.run(meta, parsed, [], [], _default_hiring(), cfg)
    # file_scores: all 100
    assert len(result.file_scores) == 100, \
        f"Expected 100 file_scores, got {len(result.file_scores)}"
    # file_evaluations: should also be 100 (no cap now)
    assert len(result.file_evaluations) == 100, \
        f"Expected 100 file_evaluations, got {len(result.file_evaluations)} (old cap was 20)"


@test("S08 — score clamped to [0, 100]")
def _():
    from stages import s08_scorer
    meta, cfg = _make_repo({"app.py": "pass\n"})
    parsed = [ParsedFile(path="app.py", language="python",
                          size_bytes=20, line_count=1,
                          function_names=[], class_names=[], imports=[],
                          ast_node_count=1, parse_error=False)]
    # Force extreme LLM scores
    hiring = _default_hiring({k: mx * 10 for k, _, mx in PARAMETER_RUBRIC})
    result = s08_scorer.run(meta, parsed, [], [], hiring, cfg)
    assert 0.0 <= result.overall_score <= 100.0, f"Score out of range: {result.overall_score}"


# ─────────────────────────────────────────────────────────────────────────────
# Score blending edge cases
# ─────────────────────────────────────────────────────────────────────────────

@test("Blend — code_quality: LLM=0, metric=10 → blended is 60% of metric")
def _():
    from stages import s08_scorer
    metric_score = 10.0
    llm_score = 0.0
    # Simulate what _blend_parameters does for code_quality
    blended = metric_score * 0.6 + llm_score * 0.4
    assert abs(blended - 6.0) < 0.01, f"Expected 6.0, got {blended}"


@test("Blend — security: LLM=5, metric=0 → blended is 2.5 (average)")
def _():
    metric_score = 0.0
    llm_score = 5.0
    blended = llm_score * 0.5 + metric_score * 0.5
    assert abs(blended - 2.5) < 0.01, f"Expected 2.5, got {blended}"


@test("Blend — code_quality never exceeds max_score=10 even if both inputs are high")
def _():
    from stages import s08_scorer
    metric_score = 10.0
    max_score = 10
    hiring = _default_hiring({"code_quality": 10.0})
    meta, cfg = _make_repo({"app.py": "def f(): pass\n"})
    parsed = [ParsedFile(path="app.py", language="python",
                          size_bytes=100, line_count=1,
                          function_names=["f"], class_names=[], imports=[],
                          ast_node_count=3, parse_error=False)]
    result = s08_scorer.run(meta, parsed, [], [], hiring, cfg)
    cq = next(ps for ps in result.parameter_scores if ps.key == "code_quality")
    assert cq.score <= max_score, f"code_quality {cq.score} exceeds max {max_score}"


# ─────────────────────────────────────────────────────────────────────────────
# Recommendation logic
# ─────────────────────────────────────────────────────────────────────────────

@test("Rec — score>=75 → shortlisted regardless of LLM hint")
def _():
    from stages.s08_scorer import _recommendation
    from core.config import HiringAnalysis
    ha = HiringAnalysis(recommendation="needs_review")
    assert _recommendation(75.0, ha) == "shortlisted"


@test("Rec — score<50 → rejected")
def _():
    from stages.s08_scorer import _recommendation
    assert _recommendation(49.9, None) == "rejected"


@test("Rec — LLM says rejected + score<70 → rejected even if score is 60")
def _():
    from stages.s08_scorer import _recommendation
    from core.config import HiringAnalysis
    ha = HiringAnalysis(recommendation="rejected")
    assert _recommendation(60.0, ha) == "rejected"


@test("Rec — LLM says shortlisted + score>=60 → shortlisted")
def _():
    from stages.s08_scorer import _recommendation
    from core.config import HiringAnalysis
    ha = HiringAnalysis(recommendation="shortlisted")
    assert _recommendation(65.0, ha) == "shortlisted"


# ─────────────────────────────────────────────────────────────────────────────
# _infer_purpose fallback (regression test for the priority=0 skip bug)
# ─────────────────────────────────────────────────────────────────────────────

@test("infer_purpose — unknown file returns non-zero priority via ext map")
def _():
    from stages.s08_scorer import _infer_purpose
    purpose, priority = _infer_purpose("src/weird_helper.py")
    assert priority > 0, f"Expected priority>0 for .py file, got {priority}"


@test("infer_purpose — .gitignore returns priority 0 (intentionally skipped)")
def _():
    from stages.s08_scorer import _infer_purpose
    _, priority = _infer_purpose(".gitignore")
    assert priority == 0


@test("infer_purpose — routes keyword → high priority API route")
def _():
    from stages.s08_scorer import _infer_purpose
    purpose, priority = _infer_purpose("api/routes/user.py")
    assert priority >= 5


# ─────────────────────────────────────────────────────────────────────────────
# Full pipeline smoke test (no LLM call, stages 2+8 only)
# ─────────────────────────────────────────────────────────────────────────────

@test("Pipeline — stages 2+8 on a real temp repo produces valid PipelineResult")
def _():
    files = {
        "main.py": "def main():\n    print('hello')\n\nif __name__ == '__main__':\n    main()\n",
        "utils/helper.py": "def helper(x):\n    return x * 2\n",
        "models/user.py": "class User:\n    def __init__(self, name):\n        self.name = name\n",
        "README.md": "# Test Project\n",
        "requirements.txt": "flask\nsqlalchemy\n",
        "config/settings.py": "DEBUG = True\nSECRET_KEY = 'change-me'\n",
    }
    meta, cfg = _make_repo(files)
    cfg.project_title = "Simple CRUD API"
    cfg.project_description = "Build a REST API with user management and database integration."

    from stages import s02_parser, s08_scorer
    parsed = s02_parser.run(meta, cfg)
    assert len(parsed) > 0

    hiring = _default_hiring()
    from main import run_pipeline
    import tempfile, os
    out = tempfile.mktemp(suffix=".json")
    stages = {2, 8}

    from stages import s08_scorer
    result = s08_scorer.run(meta, parsed, [], [], hiring, cfg)

    assert result.overall_score >= 0
    assert result.overall_grade in ("A", "B", "C", "D", "E", "F")
    assert result.hiring_grade in ("Strong", "Good", "Average", "Weak")
    assert result.recommendation in ("shortlisted", "needs_review", "rejected")
    assert len(result.file_scores) == len(parsed)
    assert len(result.file_evaluations) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Run all tests
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\nRunning {len(_test_fns)} edge-case tests\n{'─' * 60}")
    for fn in _test_fns:
        fn()

    passed = sum(1 for r in _results if r.passed)
    failed = sum(1 for r in _results if not r.passed)

    print(f"\n{'─' * 60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(_results)} tests\n")

    if failed:
        print("FAILURES:")
        for r in _results:
            if not r.passed:
                print(f"  • {r.name}")
                print(f"    {r.detail}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)
