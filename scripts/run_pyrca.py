"""Run PyRCA algorithms and convert their output to the project JSON schema."""

import argparse
import json
import time
import warnings
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)

from pyrca.analyzers.epsilon_diagnosis import EpsilonDiagnosis

from scripts.learn_epsilon_diagnosis import METRICS, build_demo_data
from src.data_loader import load_re1_case
from src.metrics import service_hit_at_k, service_rank
from src.preprocessing import prepare_epsilon_windows
from src.result_schema import GroundTruth, RCAResult, RankedRootCause
from src.window_splitter import split_metric_windows


def validate_metric_windows(
    normal_data: pd.DataFrame, abnormal_data: pd.DataFrame
) -> None:
    """Fail early when the two windows cannot be compared safely."""

    if normal_data.empty or abnormal_data.empty:
        raise ValueError("normal_data and abnormal_data must not be empty")
    if "time" in normal_data.columns or "time" in abnormal_data.columns:
        raise ValueError("remove the time column before calling PyRCA")
    if list(normal_data.columns) != list(abnormal_data.columns):
        raise ValueError("normal and abnormal metric columns must match in order")
    if len(normal_data) != len(abnormal_data):
        raise ValueError(
            "the installed EpsilonDiagnosis requires equally sized windows: "
            f"normal={len(normal_data)}, abnormal={len(abnormal_data)}"
        )
    if len(normal_data.columns) < 3:
        raise ValueError("this PyRCA implementation needs at least three metrics")
    if normal_data.isna().any().any() or abnormal_data.isna().any().any():
        raise ValueError("metric windows must not contain NaN values")
    if not all(pd.api.types.is_numeric_dtype(t) for t in normal_data.dtypes):
        raise ValueError("all metric columns must be numeric")
    if not all(pd.api.types.is_numeric_dtype(t) for t in abnormal_data.dtypes):
        raise ValueError("all metric columns must be numeric")


def run_epsilon_diagnosis(
    normal_data: pd.DataFrame,
    abnormal_data: pd.DataFrame,
    *,
    incident_id: str,
    system: str,
    fault_type: str,
    inject_time: int,
    ground_truth_service: str,
    ground_truth_metric: str | None,
    alpha: float = 0.05,
    bootstrap_time: int = 200,
    root_cause_top_k: int = 5,
    random_seed: int = 42,
) -> RCAResult:
    """Run EpsilonDiagnosis and return an algorithm-independent result."""

    validate_metric_windows(normal_data, abnormal_data)
    np.random.seed(random_seed)

    model = EpsilonDiagnosis(
        config=EpsilonDiagnosis.config_class(
            alpha=alpha,
            bootstrap_time=bootstrap_time,
            root_cause_top_k=root_cause_top_k,
        )
    )

    started = time.perf_counter()
    model.train(normal_data)
    pyrca_result = model.find_root_causes(abnormal_data)
    runtime_seconds = time.perf_counter() - started

    ranked = [
        RankedRootCause(rank=rank, metric=str(metric), score=float(score))
        for rank, (metric, score) in enumerate(
            pyrca_result.root_cause_nodes, start=1
        )
    ]

    return RCAResult(
        incident_id=incident_id,
        system=system,
        fault_type=fault_type,
        inject_time=inject_time,
        method="pyrca_epsilon_diagnosis",
        root_causes=ranked,
        ground_truth=GroundTruth(
            service=ground_truth_service,
            metric=ground_truth_metric,
        ),
        runtime_seconds=runtime_seconds,
        metadata={
            "alpha": alpha,
            "bootstrap_time": bootstrap_time,
            "root_cause_top_k": root_cause_top_k,
            "random_seed": random_seed,
            "normal_points": len(normal_data),
            "abnormal_points": len(abnormal_data),
        },
    )


def save_result(result: RCAResult, output_path: Path) -> None:
    """Write UTF-8, human-readable JSON and create its parent directory."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PyRCA in the learning project.")
    parser.add_argument(
        "--demo-fault-metric",
        choices=METRICS,
        default="checkout_latency",
        help="synthetic fault used until the RE1 loader is ready",
    )
    parser.add_argument(
        "--case-path",
        type=Path,
        default=None,
        help="real RE1 case directory; when set, the demo data is not used",
    )
    parser.add_argument("--window-minutes", type=int, default=5)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--bootstrap-time", type=int, default=50)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="default: outputs/predictions/demo-<metric>.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    preprocessing_metadata: Dict[str, Any] = {}

    if args.case_path is not None:
        case = load_re1_case(args.case_path)
        windows = split_metric_windows(
            case.metrics,
            inject_time=case.inject_time,
            window_minutes=args.window_minutes,
            minimum_points=20,
        )
        normal_data, abnormal_data, report = prepare_epsilon_windows(
            windows.normal, windows.abnormal
        )
        incident_id = case.case_id
        system = case.system
        fault_type = case.fault_type
        inject_time = case.inject_time
        ground_truth_service = case.root_cause_service
        ground_truth_metric = case.root_cause_metric
        preprocessing_metadata = {
            "window_minutes": args.window_minutes,
            "preprocessing": report.to_dict(),
        }
    else:
        normal_data, abnormal_data = build_demo_data(args.demo_fault_metric)
        service_by_metric: Dict[str, str] = {
            "checkout_latency": "checkoutservice",
            "cart_cpu": "cartservice",
            "payment_memory": "paymentservice",
        }
        incident_id = f"demo-{args.demo_fault_metric}"
        system = "synthetic-demo"
        fault_type = "synthetic"
        inject_time = 0
        ground_truth_service = service_by_metric[args.demo_fault_metric]
        ground_truth_metric = args.demo_fault_metric

    result = run_epsilon_diagnosis(
        normal_data,
        abnormal_data,
        incident_id=incident_id,
        system=system,
        fault_type=fault_type,
        inject_time=inject_time,
        ground_truth_service=ground_truth_service,
        ground_truth_metric=ground_truth_metric,
        alpha=args.alpha,
        bootstrap_time=args.bootstrap_time,
        root_cause_top_k=args.top_k,
    )
    result.metadata.update(preprocessing_metadata)

    output_path = args.output or Path(
        f"outputs/predictions/{incident_id}-pyrca-epsilon.json"
    )
    save_result(result, output_path)

    payload: Dict[str, Any] = result.to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    predictions = [item.metric for item in result.root_causes]
    rank = service_rank(predictions, ground_truth_service)
    print("\nService-level evaluation")
    print("ground truth service:", ground_truth_service)
    print("first matching rank  :", rank)
    print("Hit@1 / Hit@3 / Hit@5:", [
        service_hit_at_k(predictions, ground_truth_service, k)
        for k in (1, 3, 5)
    ])
    print(f"\nSaved: {output_path.resolve()}")


if __name__ == "__main__":
    main()
