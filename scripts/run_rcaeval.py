"""Run selected RCAEval 1.2.0 methods from the pinned official source tree."""

import argparse
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Callable

import numpy as np
import pandas as pd

from src.data_loader import RE1Case, load_re1_case
from src.metrics import service_hit_at_k, service_rank
from src.result_schema import GroundTruth, RCAResult, RankedRootCause


RCAEVAL_ROOT = Path("vendor/RCAEval").resolve()
RCAEVAL_COMMIT = "bc49dbd85bd14032101fb9a69a5a37e9d6d55178"


def _activate_pinned_source() -> None:
    if not (RCAEVAL_ROOT / "RCAEval" / "e2e" / "baro.py").is_file():
        raise FileNotFoundError(
            "pinned RCAEval source is missing; expected vendor/RCAEval at tag 1.2.0"
        )
    root_text = str(RCAEVAL_ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def load_official_baro() -> Callable:
    """Load only baro.py, avoiding unrelated optional e2e dependencies."""

    _activate_pinned_source()
    source_path = RCAEVAL_ROOT / "RCAEval" / "e2e" / "baro.py"
    spec = importlib.util.spec_from_file_location("rcaeval_120_baro", source_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load official BARO source: {source_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.baro


def load_official_preprocess() -> Callable:
    _activate_pinned_source()
    module = importlib.import_module("RCAEval.io.time_series")
    return module.preprocess


def official_fault_indicator(case: RE1Case) -> str:
    mapping = {"delay": "latency", "loss": "latency", "disk": "diskio"}
    indicator = mapping.get(case.fault_type, case.fault_type)
    return f"{case.service}_{indicator}"


def prepare_official_re1_input(
    case: RE1Case, points_per_window: int = 300
) -> pd.DataFrame:
    """Mirror the RE1 preprocessing in RCAEval 1.2.0 main.py."""

    data = case.metrics.copy()
    data = data.loc[:, ~data.columns.str.endswith("_latency-50")]
    data = data.replace([np.inf, -np.inf], np.nan).ffill().fillna(0)

    normal = data[data["time"] < case.inject_time].tail(points_per_window)
    abnormal = data[data["time"] >= case.inject_time].head(points_per_window)
    if len(normal) != points_per_window or len(abnormal) != points_per_window:
        raise ValueError(
            "RCAEval input does not contain enough points around inject_time: "
            f"normal={len(normal)}, abnormal={len(abnormal)}, "
            f"required={points_per_window}"
        )
    data = pd.concat([normal, abnormal], ignore_index=True)
    return data.rename(
        columns={
            column: column.replace("_latency-90", "_latency")
            for column in data.columns
            if column.endswith("_latency-90")
        }
    )


def _build_result(
    case: RE1Case,
    method: str,
    ranked: list[tuple[str, float | None]],
    runtime_seconds: float,
    points_per_window: int,
) -> RCAResult:
    return RCAResult(
        incident_id=case.case_id,
        system=case.system,
        fault_type=case.fault_type,
        inject_time=case.inject_time,
        method=method,
        root_causes=[
            RankedRootCause(rank=i, metric=metric, score=score)
            for i, (metric, score) in enumerate(ranked, start=1)
        ],
        ground_truth=GroundTruth(
            service=case.root_cause_service,
            metric=official_fault_indicator(case),
        ),
        runtime_seconds=runtime_seconds,
        metadata={
            "rcaeval_version": "1.2.0",
            "rcaeval_commit": RCAEVAL_COMMIT,
            "dataset": "re1-ob",
            "points_per_window": points_per_window,
            "source_mode": "pinned_official_source_minimal_import",
        },
    )


def run_baro(case: RE1Case, data: pd.DataFrame, top_k: int) -> RCAResult:
    baro = load_official_baro()
    started = time.perf_counter()
    output = baro(
        data,
        inject_time=case.inject_time,
        dataset="re1-ob",
        dk_select_useful=False,
    )
    runtime_seconds = time.perf_counter() - started
    ranked = [(str(metric), None) for metric in output["ranks"][:top_k]]
    return _build_result(
        case, "rcaeval_baro", ranked, runtime_seconds, points_per_window=300
    )


def run_e_diagnosis(case: RE1Case, data: pd.DataFrame) -> RCAResult:
    """Mirror RCAEval 1.2.0 e_diagnosis, including alpha=0.01 and Top-3."""

    from pyrca.analyzers.epsilon_diagnosis import EpsilonDiagnosis

    preprocess = load_official_preprocess()
    normal = preprocess(data[data["time"] < case.inject_time], dataset="re1-ob")
    abnormal = preprocess(data[data["time"] >= case.inject_time], dataset="re1-ob")
    columns = [column for column in normal.columns if column in abnormal.columns]
    normal, abnormal = normal[columns], abnormal[columns]
    min_length = min(len(normal), len(abnormal))
    normal, abnormal = normal.tail(min_length), abnormal.head(min_length)

    np.random.seed(42)
    model = EpsilonDiagnosis(config=EpsilonDiagnosis.config_class(alpha=0.01))
    started = time.perf_counter()
    model.train(normal)
    output = model.find_root_causes(abnormal)
    runtime_seconds = time.perf_counter() - started
    ranked = [
        (str(metric), float(score)) for metric, score in output.root_cause_nodes
    ]
    return _build_result(
        case,
        "rcaeval_e_diagnosis",
        ranked,
        runtime_seconds,
        points_per_window=300,
    )


def save_result(result: RCAResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{result.incident_id}-{result.method}.json"
    output_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def print_evaluation(result: RCAResult) -> None:
    predictions = [item.metric for item in result.root_causes]
    service = result.ground_truth.service
    print(f"\n{result.method}")
    print("Top predictions:", predictions[:5])
    print("ground truth   :", result.ground_truth.metric)
    print("service rank   :", service_rank(predictions, service))
    print(
        "Hit@1/3/5     :",
        [service_hit_at_k(predictions, service, k) for k in (1, 3, 5)],
    )
    print("runtime        :", f"{result.runtime_seconds:.4f}s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run minimal RCAEval methods.")
    parser.add_argument(
        "--case-path",
        type=Path,
        default=Path("data/RE1/RE1-OB/adservice_delay/1"),
    )
    parser.add_argument(
        "--methods", nargs="+", choices=["baro", "e_diagnosis"], default=["baro", "e_diagnosis"]
    )
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/predictions"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    case = load_re1_case(args.case_path)
    data = prepare_official_re1_input(case)
    results: list[RCAResult] = []
    if "baro" in args.methods:
        results.append(run_baro(case, data, args.top_k))
    if "e_diagnosis" in args.methods:
        results.append(run_e_diagnosis(case, data))

    for result in results:
        print_evaluation(result)
        print("saved          :", save_result(result, args.output_dir).resolve())


if __name__ == "__main__":
    main()
