"""
stages/s01_cloner.py — Stage 01: GitHub API / Repo Cloner.

Clones the FULL remote repository (all branches, all history) or opens a
local repository, then extracts rich git metadata including commit history,
contributors, branch list, repo age, and commit frequency.

Primary library : GitPython
Alt 1           : PyGithub  (GitHub metadata + API tokens)
Alt 2           : httpx + raw GitHub REST API  (no git binary needed)

Changes from shallow-clone version
-----------------------------------
* Removed  depth=cfg.clone_depth  — full history is now fetched.
* Removed  single_branch=True     — all branches are cloned.
* RepoMeta extended with: all_branches, total_commits, contributors,
  commits_per_day, repo_age_days.
* Detached-HEAD fallback now resolves via origin/HEAD reference.
* _extract_git_stats() helper added for rich commit-graph metrics.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import git  # gitpython

from core.config import PipelineConfig, RepoMeta
from core.logger import get_logger

log = get_logger("s01_cloner")

# ---------------------------------------------------------------------------
# Language detection by extension (lightweight, no linguist dependency)
# ---------------------------------------------------------------------------
_EXT_TO_LANG: dict[str, str] = {
    # Python
    ".py":    "python",
    ".ipynb": "python",
    # JavaScript / TypeScript
    ".js":    "javascript",
    ".jsx":   "javascript",
    ".ts":    "typescript",
    ".tsx":   "typescript",
    # JVM
    ".java":  "java",
    ".kt":    "kotlin",
    ".scala": "scala",
    # Systems
    ".go":    "go",
    ".rs":    "rust",
    ".cpp":   "cpp",
    ".cc":    "cpp",
    ".c":     "c",
    ".h":     "c",
    # Scripting
    ".rb":    "ruby",
    ".php":   "php",
    ".sh":    "shell",
    ".bash":  "shell",
    # Config / infra
    ".yaml":  "yaml",
    ".yml":   "yaml",
    ".json":  "json",
    ".toml":  "toml",
    ".tf":    "terraform",
    # Docs
    ".md":    "markdown",
    ".rst":   "restructuredtext",
}


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------
def run(repo_url_or_path: str, cfg: PipelineConfig) -> RepoMeta:
    """
    Clone (full) or open a repository and return a :class:`RepoMeta` object.

    Parameters
    ----------
    repo_url_or_path:
        A remote URL (https://github.com/…) or an absolute local path.
    cfg:
        Pipeline configuration (only clone_base_dir is used now).

    Returns
    -------
    RepoMeta
        Populated with local path, branch, HEAD commit, file stats,
        full commit history metrics, contributors, and branch list.
    """
    local_path = _resolve_repo(repo_url_or_path, cfg)

    log.info("Opening repo at %s", local_path)
    repo = git.Repo(local_path)

    # ── Basic HEAD info ──────────────────────────────────────────────────────
    head_commit = repo.head.commit.hexsha[:12]

    try:
        default_branch = repo.active_branch.name
    except TypeError:
        # Detached HEAD — resolve via remote HEAD reference
        try:
            default_branch = repo.remotes.origin.refs.HEAD.ref.name.split("/")[-1]
        except (AttributeError, IndexError):
            default_branch = "HEAD"

    # ── File manifest ────────────────────────────────────────────────────────
    all_files = _list_tracked_files(local_path)
    languages  = _detect_languages(all_files)

    # ── Rich git stats (new) ─────────────────────────────────────────────────
    git_stats = _extract_git_stats(repo)

    meta = RepoMeta(
        # core
        url                = repo_url_or_path,
        local_path         = local_path,
        default_branch     = default_branch,
        head_commit        = head_commit,
        total_files        = len(all_files),
        languages_detected = languages,
        # full-clone extras
        all_branches       = git_stats["all_branches"],
        total_commits      = git_stats["total_commits"],
        contributors       = git_stats["contributors"],
        commits_per_day    = git_stats["commits_per_day"],
        repo_age_days      = git_stats["repo_age_days"],
        first_commit_sha   = git_stats["first_commit_sha"],
        last_commit_sha    = git_stats["last_commit_sha"],
    )

    log.info(
        "Cloner done | files=%d | branches=%d | commits=%d | "
        "contributors=%d | age=%d days | commits/day=%.2f | languages=%s",
        meta.total_files,
        len(meta.all_branches),
        meta.total_commits,
        len(meta.contributors),
        meta.repo_age_days,
        meta.commits_per_day,
        meta.languages_detected,
    )
    return meta


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_github_url(url: str) -> tuple[str, str | None]:
    """
    Strip GitHub web-UI path segments and return (clone_url, branch_or_None).

    GitHub browser URLs look like:
      https://github.com/owner/repo/tree/branch[/subpath...]
    The '/tree/...' part is not a valid git remote path — git only accepts:
      https://github.com/owner/repo[.git]
    """
    parsed = urlparse(url)
    parts  = [p for p in parsed.path.strip("/").split("/") if p]

    # GitHub URLs: owner/repo are always parts[0] and parts[1]
    branch: str | None = None
    if len(parts) >= 4 and parts[2] == "tree":
        branch     = parts[3]
        clean_path = "/" + "/".join(parts[:2])
        clean_url  = parsed._replace(path=clean_path).geturl()
        log.info("Stripped GitHub web URL → clone URL: %s  branch: %s", clean_url, branch)
    else:
        clean_url = url

    return clean_url, branch


def _resolve_repo(repo_url_or_path: str, cfg: PipelineConfig) -> str:
    """
    Return local filesystem path.
    Performs a FULL clone (no depth limit, all branches) if the source is remote.
    Handles GitHub web browser URLs containing /tree/branch.
    """
    parsed    = urlparse(repo_url_or_path)
    is_remote = parsed.scheme in ("http", "https", "git", "ssh")

    if not is_remote:
        local = Path(repo_url_or_path).expanduser().resolve()
        if not local.exists():
            raise FileNotFoundError(f"Local path not found: {local}")
        log.info("Using local repo at %s", local)
        return str(local)

    # Strip any GitHub web-UI path segments (e.g. /tree/branch)
    clone_url, branch = _normalize_github_url(repo_url_or_path)

    # ── Remote: full clone ───────────────────────────────────────────────────
    os.makedirs(cfg.clone_base_dir, exist_ok=True)
    repo_slug = _slug_from_url(clone_url)
    dest      = Path(cfg.clone_base_dir) / repo_slug

    if dest.exists():
        log.info("Clone already exists at %s — skipping clone", dest)
        cloned = git.Repo(str(dest))
        if branch:
            _checkout_branch(cloned, branch)
        return str(dest)

    log.info("Full-cloning %s → %s  (all branches, full history)", clone_url, dest)
    cloned = git.Repo.clone_from(clone_url, str(dest))

    if branch:
        _checkout_branch(cloned, branch)

    log.info("Full clone complete → %s", dest)
    return str(dest)


def _checkout_branch(repo: git.Repo, branch: str) -> None:
    """Checkout a branch by name, tracking the remote if needed."""
    try:
        repo.git.checkout(branch)
        log.info("Checked out branch: %s", branch)
    except git.GitCommandError:
        try:
            repo.git.checkout("-b", branch, f"origin/{branch}")
            log.info("Checked out remote branch origin/%s as %s", branch, branch)
        except git.GitCommandError as exc:
            log.warning("Could not checkout branch '%s': %s — staying on default", branch, exc)


def _slug_from_url(url: str) -> str:
    """Turn https://github.com/owner/repo into 'owner__repo'."""
    path = urlparse(url).path.strip("/").replace("/", "__")
    return path.removesuffix(".git")


_SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "__pycache__",
    ".venv", "venv", "coverage", ".next", ".nuxt", "vendor",
    ".tox", "eggs", ".eggs", ".cache", "out", ".output",
}


def _list_tracked_files(local_path: str) -> list[Path]:
    """Return every file under the repo root, skipping noise directories."""
    base     = Path(local_path)
    tracked: list[Path] = []

    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fname in files:
            tracked.append(Path(root) / fname)

    return tracked


def _detect_languages(files: list[Path]) -> list[str]:
    """Return a sorted, deduplicated list of languages found in the repo."""
    langs: set[str] = set()
    for f in files:
        lang = _EXT_TO_LANG.get(f.suffix.lower())
        if lang:
            langs.add(lang)
    return sorted(langs)


def _extract_git_stats(repo: git.Repo) -> dict:
    """
    Walk the full commit graph and return rich metadata.

    Returns
    -------
    dict with keys:
        all_branches, total_commits, contributors,
        commits_per_day, repo_age_days,
        first_commit_sha, last_commit_sha
    """
    log.info("Extracting full git stats (this may take a moment on large repos) …")

    # ── All local branches ───────────────────────────────────────────────────
    all_branches = [b.name for b in repo.branches]

    # ── Walk ALL commits across ALL branches ─────────────────────────────────
    # Using repo.iter_commits with all=True covers every reachable commit.
    commits      = list(repo.iter_commits("--all"))
    total_commits = len(commits)

    if total_commits == 0:
        log.warning("No commits found — returning empty git stats")
        return {
            "all_branches":    all_branches,
            "total_commits":   0,
            "contributors":    [],
            "commits_per_day": 0.0,
            "repo_age_days":   0,
            "first_commit_sha": "",
            "last_commit_sha":  "",
        }

    # ── Contributors (unique author emails) ──────────────────────────────────
    contributors = sorted({
        c.author.email
        for c in commits
        if c.author and c.author.email
    })

    # ── Repo age and commit frequency ────────────────────────────────────────
    # commits are ordered newest → oldest
    newest_ts    = commits[0].committed_date
    oldest_ts    = commits[-1].committed_date
    age_seconds  = max(newest_ts - oldest_ts, 1)          # avoid div-by-zero
    repo_age_days   = age_seconds // 86_400
    commits_per_day = round(total_commits / max(repo_age_days, 1), 2)

    first_commit_sha = commits[-1].hexsha[:12]
    last_commit_sha  = commits[0].hexsha[:12]

    log.info(
        "Git stats | branches=%d | commits=%d | contributors=%d | "
        "age=%d days | commits/day=%.2f",
        len(all_branches), total_commits, len(contributors),
        repo_age_days, commits_per_day,
    )

    return {
        "all_branches":     all_branches,
        "total_commits":    total_commits,
        "contributors":     contributors,
        "commits_per_day":  commits_per_day,
        "repo_age_days":    repo_age_days,
        "first_commit_sha": first_commit_sha,
        "last_commit_sha":  last_commit_sha,
    }