"""
main.py — CLI entry point for the GitHub Repo Evaluator pipeline.

Usage examples:
    python main.py --repo https://github.com/owner/repo
    python main.py --repo /path/to/local/repo --stages 1,2,3,7,8
    python main.py --repo https://github.com/owner/repo --model Qwen/Qwen2.5-Coder-7B-Instruct
    python main.py --repo https://github.com/owner/repo --output report.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import dataclasses
from pathlib import Path

# Make sure the package root (the folder containing main.py) is always on
# sys.path, regardless of which directory the user runs the script from.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from core.config import PipelineConfig, PipelineResult
from core.logger import get_logger

log = get_logger("main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GitHub Repo Evaluator - SLM-only code quality pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--repo", required=True,
        help="GitHub URL or local path to the repository",
    )
    parser.add_argument(
        "--stages", default="1,2,3,7,8",
        help="Comma-separated list of stages to run (e.g. '1,2,3,7,8')",
    )
    parser.add_argument(
        "--model", default=None,
        help=f"HuggingFace model ID for Stage 07 (overrides config default)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Path to write JSON report (default: output/eval_report.json)",
    )
    parser.add_argument(
        "--clone-dir", default=None,
        help="Directory to clone remote repos into",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> PipelineConfig:
    cfg = PipelineConfig()
    if args.model:
        cfg.llm_model = args.model
    if args.clone_dir:
        cfg.clone_base_dir = args.clone_dir
    return cfg


def run_pipeline(
    repo: str,
    stages: set[int],
    cfg: PipelineConfig,
    output_path: str,
) -> PipelineResult:
    result = PipelineResult()

    # ------------------------------------------------------------------
    # Stage 01 — Repo Cloner
    # ------------------------------------------------------------------
    if 1 in stages:
        log.info("--- Stage 01: Repo Cloner ---")
        from stages import s01_cloner
        result.repo_meta = s01_cloner.run(repo, cfg)
    else:
        log.warning("Stage 01 skipped - repo_meta will be empty")
        from core.config import RepoMeta
        result.repo_meta = RepoMeta(
            url=repo, local_path=repo,
            default_branch="HEAD", head_commit="unknown", total_files=0,
        )

    # ------------------------------------------------------------------
    # Stage 02 — Repo Parser
    # ------------------------------------------------------------------
    if 2 in stages:
        log.info("--- Stage 02: Repo Parser ---")
        from stages import s02_parser
        result.parsed_files = s02_parser.run(result.repo_meta, cfg)
    else:
        log.warning("Stage 02 skipped - parsed_files will be empty")

    # ------------------------------------------------------------------
    # Stage 03 — Static Analysis
    # ------------------------------------------------------------------
    if 3 in stages:
        log.info("--- Stage 03: Static Analysis ---")
        from stages import s03_static
        result.static_findings = s03_static.run(result.repo_meta, cfg)
    else:
        log.warning("Stage 03 skipped")

    # ------------------------------------------------------------------
    # Stages 04 + 05 + 06 — Retrieval pipeline (disabled in SLM-only mode)
    # ------------------------------------------------------------------
    if any(stage in stages for stage in (4, 5, 6)):
        log.info("Stages 04-06 are disabled in SLM-only mode - skipping retrieval pipeline")

    # ------------------------------------------------------------------
    # Stage 07 — LLM Evaluation Engine
    # ------------------------------------------------------------------
    if 7 in stages:
        if not result.parsed_files:
            log.warning("No parsed files - skipping Stage 07")
        else:
            log.info("--- Stage 07: LLM Evaluation Engine ---")
            from stages import s07_llm
            try:
                result.llm_analyses, result.hiring_analysis = s07_llm.run(
                    result.repo_meta,
                    result.parsed_files,
                    result.static_findings,
                    cfg,
                )
            except Exception as exc:
                log.warning("Stage 07 failed - continuing without LLM analyses: %s", exc)
    else:
        log.warning("Stage 07 skipped")

    # ------------------------------------------------------------------
    # Stage 08 — Scoring & Metrics Engine
    # ------------------------------------------------------------------
    if 8 in stages:
        log.info("--- Stage 08: Scoring & Metrics ---")
        from stages import s08_scorer
        result = s08_scorer.run(
            result.repo_meta,
            result.parsed_files,
            result.static_findings,
            result.llm_analyses,
            result.hiring_analysis,
            cfg,
        )
    else:
        log.warning("Stage 08 skipped")

    # ------------------------------------------------------------------
    # Persist report
    # ------------------------------------------------------------------
    _write_report(result, output_path)
    return result


def _write_report(result: PipelineResult, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    def _default(obj):
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        return str(obj)

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(dataclasses.asdict(result), fh, indent=2, default=_default)

    log.info("Report written to %s", output_path)


def main() -> None:
    args   = parse_args()
    cfg    = build_config(args)
    stages = {int(s.strip()) for s in args.stages.split(",")}

    output_path = args.output or os.path.join(cfg.output_dir, cfg.report_filename)

    log.info("Starting GitHub Repo Evaluator")
    log.info("  Repo   : %s", args.repo)
    log.info("  Stages : %s", sorted(stages))
    log.info("  Model  : %s", cfg.llm_model)
    log.info("  Output : %s", output_path)

    try:
        result = run_pipeline(args.repo, stages, cfg, output_path)
    except KeyboardInterrupt:
        log.warning("Interrupted by user")
        sys.exit(1)
    except Exception as exc:
        log.exception("Pipeline failed: %s", exc)
        sys.exit(1)

    grade = getattr(result, "overall_grade", "?")
    score = getattr(result, "overall_score", 0)
    log.info("Done - overall score: %.1f / 100  grade: %s", score, grade)


if __name__ == "__main__":
    main()
