from __future__ import annotations

import argparse
import json
from pathlib import Path

from relluna.services.benchmark import (
    evaluate_cases,
    evaluate_semantic_gate,
    load_benchmark_cases,
    render_markdown_report,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN_DIR = ROOT / "tests" / "golden"
DEFAULT_REPORT_PATH = ROOT / "BENCHMARK_MEDICO_JURIDICO.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Relluna medical-legal benchmark.")
    parser.add_argument(
        "--golden-dir",
        default=str(DEFAULT_GOLDEN_DIR),
        help="Directory with golden cases. Supports *.json and */case.json.",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT_PATH),
        help="Markdown report output path.",
    )
    parser.add_argument(
        "--json",
        default=None,
        help="Optional JSON summary output path.",
    )
    parser.add_argument(
        "--gate-critical",
        action="store_true",
        help="Fail when critical clean cases regress or critical sentinel cases stop detecting regressions.",
    )
    parser.add_argument(
        "--min-clean-score",
        type=float,
        default=90.0,
        help="Minimum score required for critical clean cases when --gate-critical is enabled.",
    )
    args = parser.parse_args()

    cases = load_benchmark_cases(args.golden_dir)
    summary = evaluate_cases(cases)

    report_path = Path(args.report)
    report_path.write_text(render_markdown_report(summary), encoding="utf-8")

    if args.json:
        Path(args.json).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"Benchmark: {summary['overall_score']:.2f}/100 across {summary['case_count']} cases")
    print(f"Report: {report_path}")

    if not args.gate_critical:
        return 0

    gate = evaluate_semantic_gate(summary, min_clean_score=args.min_clean_score)
    if gate["ok"]:
        print(
            "Semantic gate: OK "
            f"(clean cases: {len(gate['checked_clean_cases'])}, "
            f"sentinel cases: {len(gate['checked_sentinel_cases'])})"
        )
        return 0

    print("Semantic gate: FAILED")
    for failure in gate["failures"]:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
