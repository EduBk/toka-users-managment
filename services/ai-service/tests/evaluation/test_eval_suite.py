import json
from pathlib import Path

from eval.run_eval import main, run_evaluation

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def _corpus(directory: Path) -> Path:
    (directory / "arquitectura.md").write_text(
        "# Arquitectura\n\nEl sistema usa auth-service, user-service, role-service "
        "y audit-service. Los tokens JWT se validan con el JWKS del auth-service. "
        "Los eventos de dominio se publican en RabbitMQ.",
        encoding="utf-8",
    )
    return directory


def _dataset(path: Path, cases: list[dict]) -> Path:
    path.write_text(json.dumps(cases), encoding="utf-8")
    return path


async def test_evaluation_suite_reports_passing_cases(tmp_path: Path) -> None:
    dataset = _dataset(
        tmp_path / "dataset.json",
        [
            {
                "id": "arquitectura",
                "question": "¿Qué microservicios forman el sistema?",
                "expect": {"sources_min": 1, "quality": True},
            },
            {
                "id": "fuera-de-alcance",
                "question": "¿Cuál es la capital de Francia?",
                "expect": {"no_context": True, "quality": True},
            },
        ],
    )

    report = await run_evaluation(
        docs_path=_corpus(tmp_path),
        dataset_path=dataset,
        prompts_path=PROMPTS,
    )

    assert report.passed == 2
    assert report.failed == 0
    assert all(case.sources for case in report.cases[:1])
    assert report.total_tokens > 0
    assert report.total_cost_usd > 0


async def test_evaluation_suite_flags_failed_expectations(tmp_path: Path) -> None:
    dataset = _dataset(
        tmp_path / "dataset.json",
        [
            {
                "id": "exigente",
                "question": "¿Qué microservicios forman el sistema?",
                "expect": {
                    "sources_min": 5,
                    "must_include": "texto que no existe",
                },
            }
        ],
    )

    report = await run_evaluation(
        docs_path=_corpus(tmp_path),
        dataset_path=dataset,
        prompts_path=PROMPTS,
    )

    assert report.failed == 1
    assert set(report.cases[0].failures) == {"sources_min", "must_include"}
    assert json.loads(json.dumps(report.to_dict()))["failed"] == 1


def test_cli_returns_a_non_zero_exit_code_on_failures(
    tmp_path: Path, capsys
) -> None:
    corpus = _corpus(tmp_path)
    dataset = _dataset(
        tmp_path / "dataset.json",
        [{"id": "x", "question": "¿Qué es el sistema?", "expect": {"sources_min": 9}}],
    )

    exit_code = main(["--docs", str(corpus), "--dataset", str(dataset), "--json"])

    assert exit_code == 1
    assert '"failed": 1' in capsys.readouterr().out
