"""Run three RCA methods over the 10 RE1-OB delay/loss cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from scripts.evaluate_results import evaluate_directory
from scripts.run_pyrca import run_epsilon_diagnosis
from scripts.run_rcaeval import (
    official_fault_indicator,
    prepare_official_re1_input,
    run_baro,
    run_e_diagnosis,
)
from src.data_loader import RE1Case, load_re1_case
from src.preprocessing import prepare_epsilon_windows
from src.result_schema import RCAResult
from src.window_splitter import split_metric_windows


METHOD_NAMES = {
    "pyrca": "pyrca_epsilon_diagnosis",
    "baro": "rcaeval_baro",
    "e_diagnosis": "rcaeval_e_diagnosis",
}


def discover_cases(
    dataset_root: Path,
    fault_types: tuple[str, ...] = ("delay", "loss"),
    instance_id: str = "1",
) -> list[Path]:
    """Find services that have every selected fault type."""

    by_fault: dict[str, set[str]] = {}
    for fault_type in fault_types:
        suffix = f"_{fault_type}"
        services = {
            path.name[: -len(suffix)]
            for path in dataset_root.glob(f"*{suffix}")
            if path.is_dir() and (path / instance_id).is_dir()
        }
        by_fault[fault_type] = services

    common_services = set.intersection(*by_fault.values()) if by_fault else set()
    return [
        dataset_root / f"{service}_{fault_type}" / instance_id
        for service in sorted(common_services)
        for fault_type in fault_types
    ]


def run_pyrca_case(case: RE1Case, top_k: int) -> RCAResult:
    windows = split_metric_windows(
        case.metrics,
        inject_time=case.inject_time,
        window_minutes=5,
        minimum_points=20,
    )
    normal, abnormal, report = prepare_epsilon_windows(
        windows.normal, windows.abnormal
    )
    result = run_epsilon_diagnosis(
        normal,
        abnormal,
        incident_id=case.case_id,
        system=case.system,
        fault_type=case.fault_type,
        inject_time=case.inject_time,
        ground_truth_service=case.root_cause_service,
        ground_truth_metric=official_fault_indicator(case),
        alpha=0.05,
        bootstrap_time=50,
        root_cause_top_k=top_k,
        random_seed=42,
    )
    result.metadata.update(
        {
            "dataset": "re1-ob",
            "window_minutes": 5,
            "preprocessing": report.to_dict(),
        }
    )
    return result


def _save_payload(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run_batch(
    case_paths: list[Path],
    methods: tuple[str, ...],
    output_dir: Path,
    top_k: int,
) -> None:
    total = len(case_paths) * len(methods)
    current = 0
    for case_path in case_paths:
        case = load_re1_case(case_path)
        official_data = None
        for method in methods:
            current += 1
            method_name = METHOD_NAMES[method]
            output_path = output_dir / f"{case.case_id}-{method_name}.json"
            print(f"[{current:02d}/{total:02d}] {case.case_id} / {method}", flush=True)
            try:
                if method == "pyrca":
                    result = run_pyrca_case(case, top_k)
                else:
                    if official_data is None:
                        official_data = prepare_official_re1_input(case)
                    runners: dict[str, Callable[[], RCAResult]] = {
                        "baro": lambda: run_baro(case, official_data, top_k),
                        "e_diagnosis": lambda: run_e_diagnosis(case, official_data),
                    }
                    result = runners[method]()
                _save_payload(result.to_dict(), output_path)
                top_metric = result.root_causes[0].metric if result.root_causes else "-"
                print(f"         ok  top1={top_metric}  {result.runtime_seconds:.3f}s")
            except Exception as exc:  # keep the other experiments running
                error_payload = {
                    "status": "error",
                    "incident_id": case.case_id,
                    "system": case.system,
                    "fault_type": case.fault_type,
                    "method": method_name,
                    "ground_truth_service": case.root_cause_service,
                    "ground_truth_metric": official_fault_indicator(case),
                    "error": f"{type(exc).__name__}: {exc}",
                }
                _save_payload(error_payload, output_path)
                print(f"         error: {error_payload['error']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the RE1-OB 10-case experiment.")
    parser.add_argument("--dataset-root", type=Path, default=Path("data/RE1/RE1-OB"))
    parser.add_argument("--instance-id", default="1")
    parser.add_argument(
        "--fault-types", nargs="+", choices=["delay", "loss"], default=["delay", "loss"]
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=list(METHOD_NAMES),
        default=list(METHOD_NAMES),
    )
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/predictions/re1_ob_delay_loss"),
    )
    parser.add_argument(
        "--report-dir", type=Path, default=Path("outputs/reports/re1_ob_delay_loss")
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    case_paths = discover_cases(
        args.dataset_root, tuple(args.fault_types), args.instance_id
    )
    if not case_paths:
        raise FileNotFoundError("no matching RE1-OB cases were found")
    print(f"discovered {len(case_paths)} cases")
    run_batch(case_paths, tuple(args.methods), args.output_dir, args.top_k)
    print("\nBuilding reports")
    for path in evaluate_directory(args.output_dir, args.report_dir):
        print("saved:", path.resolve())


if __name__ == "__main__":
    main()
