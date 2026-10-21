"""Run every backend test suite with coverage and print an aggregated report (E2.10).

Each service enforces ``--cov-fail-under=70`` through its ``pyproject.toml`` and
writes ``coverage.xml`` in its own directory.
"""

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    "common",
    "auth-service",
    "user-service",
    "role-service",
    "audit-service",
    "ai-service",
)


@dataclass(frozen=True)
class SuiteResult:
    service: str
    exit_code: int
    coverage: float | None


def _coverage_percent(service_dir: Path) -> float | None:
    report = service_dir / "coverage.xml"
    if not report.is_file():
        return None
    line_rate = ElementTree.parse(report).getroot().get("line-rate")
    return round(float(line_rate) * 100, 2) if line_rate else None


def run_suite(service: str, extra_args: list[str]) -> SuiteResult:
    service_dir = _REPO_ROOT / "services" / service
    (service_dir / "coverage.xml").unlink(missing_ok=True)
    print(f"\n=== {service} ===", flush=True)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *extra_args],
        cwd=service_dir,
        check=False,
    )
    return SuiteResult(service, completed.returncode, _coverage_percent(service_dir))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "services",
        nargs="*",
        help=f"subset of services to run (default: all of {', '.join(SERVICES)})",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="also write an HTML report to services/<service>/htmlcov/",
    )
    args = parser.parse_args()
    unknown = sorted(set(args.services) - set(SERVICES))
    if unknown:
        parser.error(f"unknown services: {', '.join(unknown)}")

    extra_args = ["--cov-report=html"] if args.html else []
    results = [run_suite(service, extra_args) for service in args.services or SERVICES]

    print("\n=== Summary ===")
    print(f"{'service':<16}{'result':<8}coverage")
    for result in results:
        status = "PASS" if result.exit_code == 0 else "FAIL"
        coverage = f"{result.coverage:.2f}%" if result.coverage is not None else "-"
        print(f"{result.service:<16}{status:<8}{coverage}")

    return 0 if all(result.exit_code == 0 for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
