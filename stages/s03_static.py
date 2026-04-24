"""
stages/s03_static.py — Stage 03: Static Analysis Layer.

Runs Semgrep OSS over the repo to find security issues and code smells.
Outputs a list of StaticFinding objects (SARIF-derived).

Primary library : Semgrep OSS  (semgrep · PyPI)
Alt 1           : Bandit        (Python-only, very lightweight)
Alt 2           : Pylint / ESLint (style + complexity, not security)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from core.config import PipelineConfig, RepoMeta, StaticFinding
from core.logger import get_logger

log = get_logger("s03_static")

# Semgrep severity strings → normalised
_SEVERITY_MAP = {
    "ERROR":   "ERROR",
    "WARNING": "WARNING",
    "INFO":    "INFO",
    "NOTE":    "INFO",
}


def run(repo_meta: RepoMeta, cfg: PipelineConfig) -> list[StaticFinding]:
    """
    Run Semgrep over the repository and return parsed findings.

    Falls back to Bandit (Python files only) if Semgrep is not installed.

    Returns
    -------
    list[StaticFinding]
    """
    if _semgrep_available():
        log.info("Running Semgrep OSS (config=%s) on %s", cfg.semgrep_config, repo_meta.local_path)
        return _run_semgrep(repo_meta, cfg)

    log.warning("Semgrep unavailable — falling back to Bandit (Python only)")
    if _bandit_available():
        return _run_bandit(repo_meta)

    log.warning("Neither Semgrep nor Bandit is available — skipping static analysis")
    return []


# ---------------------------------------------------------------------------
# Semgrep runner
# ---------------------------------------------------------------------------

def _run_semgrep(repo_meta: RepoMeta, cfg: PipelineConfig) -> list[StaticFinding]:
    semgrep_bin = _semgrep_cmd() or ["semgrep"]
    cmd = semgrep_bin + [
        "--config", cfg.semgrep_config,
        "--json",
        "--timeout", str(cfg.semgrep_timeout),
        "--max-memory", str(cfg.semgrep_max_memory),
        "--quiet",
        repo_meta.local_path,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=cfg.semgrep_timeout * 10,
        )
    except subprocess.TimeoutExpired:
        log.error("Semgrep timed out")
        return []
    except FileNotFoundError:
        log.error("Semgrep binary not found")
        return []

    # Semgrep exits 1 when findings exist — that is normal
    if proc.returncode not in (0, 1):
        log.error("Semgrep error (exit %d): %s", proc.returncode, proc.stderr[:500])
        return []

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        log.error("Could not parse Semgrep JSON output")
        return []

    findings: list[StaticFinding] = []
    base = repo_meta.local_path.rstrip("/") + "/"

    for result in data.get("results", []):
        file_path = result.get("path", "")
        # Make path relative
        if file_path.startswith(base):
            file_path = file_path[len(base):]

        meta = result.get("extra", {})
        metadata = meta.get("metadata", {})

        severity = _SEVERITY_MAP.get(
            meta.get("severity", "INFO").upper(), "INFO"
        )

        findings.append(StaticFinding(
            file_path=file_path,
            rule_id=result.get("check_id", "unknown"),
            severity=severity,
            message=meta.get("message", ""),
            line_start=result.get("start", {}).get("line", 0),
            line_end=result.get("end", {}).get("line", 0),
            cwe=str(metadata.get("cwe", "")),
            owasp=str(metadata.get("owasp", "")),
        ))

    log.info("Semgrep — %d findings (%d errors, %d warnings)",
             len(findings),
             sum(1 for f in findings if f.severity == "ERROR"),
             sum(1 for f in findings if f.severity == "WARNING"))
    return findings


# ---------------------------------------------------------------------------
# Bandit fallback (Python-only)
# ---------------------------------------------------------------------------

def _run_bandit(repo_meta: RepoMeta) -> list[StaticFinding]:
    cmd = [
        sys.executable, "-m", "bandit",
        "-r", repo_meta.local_path,
        "-f", "json",
        "-q",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log.error("Bandit failed: %s", exc)
        return []

    # Bandit returns:
    # - 0 when no issues
    # - 1 when issues are found
    # Any other return code means execution/config error.
    if proc.returncode not in (0, 1):
        stderr = (proc.stderr or "").strip()
        if "No module named bandit" in stderr:
            log.error("Bandit is not installed in the current Python environment")
        else:
            log.error("Bandit error (exit %d): %s", proc.returncode, stderr[:500])
        return []

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        log.error("Could not parse Bandit JSON output")
        return []

    findings: list[StaticFinding] = []
    base = repo_meta.local_path.rstrip("/") + "/"

    for issue in data.get("results", []):
        file_path = issue.get("filename", "")
        if file_path.startswith(base):
            file_path = file_path[len(base):]

        sev = issue.get("issue_severity", "LOW").upper()
        severity = "ERROR" if sev == "HIGH" else "WARNING" if sev == "MEDIUM" else "INFO"

        findings.append(StaticFinding(
            file_path=file_path,
            rule_id=issue.get("test_id", "bandit"),
            severity=severity,
            message=issue.get("issue_text", ""),
            line_start=issue.get("line_number", 0),
            line_end=issue.get("line_number", 0),
            cwe=issue.get("issue_cwe", {}).get("id", ""),
        ))

    log.info("Bandit — %d findings", len(findings))
    return findings


# ---------------------------------------------------------------------------
# Availability checks
# ---------------------------------------------------------------------------

def _semgrep_cmd() -> list[str] | None:
    """Return the semgrep command list, or None if not found."""
    import shutil, site
    # 1. On PATH
    if shutil.which("semgrep"):
        return ["semgrep"]
    # 2. Windows: check Python Scripts folder (pip install puts it there)
    scripts = Path(sys.executable).parent / "Scripts" / "semgrep.exe"
    if scripts.exists():
        return [str(scripts)]
    # 3. Also check user-level Scripts
    if hasattr(site, "getusersitepackages"):
        user_site = site.getusersitepackages()
        user_sites = user_site if isinstance(user_site, (list, tuple)) else [user_site]
        for sp in user_sites:
            candidate = Path(sp).parent / "Scripts" / "semgrep.exe"
            if candidate.exists():
                return [str(candidate)]
    return None

def _semgrep_available() -> bool:
    try:
        cmd = _semgrep_cmd()
        if not cmd:
            return False
        proc = subprocess.run(cmd + ["--version"], capture_output=True, timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


def _bandit_available() -> bool:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "bandit", "--version"],
            capture_output=True, timeout=10,
        )
        return proc.returncode == 0
    except Exception:
        return False
