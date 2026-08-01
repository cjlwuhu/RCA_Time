"""Step 4: run PyRCA EpsilonDiagnosis with a selectable synthetic fault.

This script deliberately avoids RE1 so that the algorithm input and output can
be understood before file parsing and window splitting are introduced.
"""

import argparse
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)

from pyrca.analyzers.epsilon_diagnosis import EpsilonDiagnosis


METRICS = ("checkout_latency", "cart_cpu", "payment_memory")


def build_demo_data(
    fault_metric: str = "checkout_latency", num_points: int = 120
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create equal-sized windows and inject one selectable metric fault."""

    if fault_metric not in METRICS:
        raise ValueError(f"fault_metric must be one of {METRICS}")

    rng = np.random.default_rng(42)
    time_axis = np.linspace(0, 8 * np.pi, num_points)
    normal_latency_pattern = np.sin(time_axis)

    normal_data = pd.DataFrame(
        {
            "checkout_latency": normal_latency_pattern
            + rng.normal(0, 0.05, num_points),
            "cart_cpu": rng.normal(0, 1, num_points),
            "payment_memory": rng.normal(0, 1, num_points),
        }
    )

    abnormal_data = pd.DataFrame(
        {
            "checkout_latency": rng.normal(0, 1, num_points),
            "cart_cpu": rng.normal(0, 1, num_points),
            "payment_memory": rng.normal(0, 1, num_points),
        }
    )

    # This controlled experiment keeps the selected metric's point-by-point
    # pattern but increases its level and amplitude. That produces the signal
    # measured by the installed PyRCA EpsilonDiagnosis implementation.
    abnormal_data[fault_metric] = (
        3 * normal_data[fault_metric].to_numpy()
        + 5
        + rng.normal(0, 0.05, num_points)
    )
    return normal_data, abnormal_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Learn EpsilonDiagnosis using one selectable synthetic fault."
    )
    parser.add_argument(
        "--fault-metric",
        choices=METRICS,
        default="checkout_latency",
        help="metric whose normal pattern will be amplified in the incident window",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    normal_data, abnormal_data = build_demo_data(args.fault_metric)

    print("Injected fault metric:", args.fault_metric)
    print("\n1. Input shapes")
    print("normal_data  :", normal_data.shape)
    print("abnormal_data:", abnormal_data.shape)
    print("same columns :", list(normal_data.columns) == list(abnormal_data.columns))

    print("\n2. Mean values before and during the incident")
    comparison = pd.DataFrame(
        {"normal_mean": normal_data.mean(), "abnormal_mean": abnormal_data.mean()}
    )
    print(comparison.round(3))

    # The installed implementation uses NumPy's global random generator while
    # bootstrapping. Fixing this seed makes the lesson reproducible.
    np.random.seed(42)
    model = EpsilonDiagnosis(
        config=EpsilonDiagnosis.config_class(
            alpha=0.05,
            bootstrap_time=50,
            root_cause_top_k=3,
        )
    )

    model.train(normal_data)
    result = model.find_root_causes(abnormal_data)

    print("\n3. Learned thresholds")
    for metric, threshold in model.statistics.items():
        print(f"{metric:20s} {float(threshold):.4f}")

    print("\n4. Incident scores")
    for metric, score in model.correlations.items():
        print(f"{metric:20s} {float(score):.4f}")

    print("\n5. PyRCA result")
    print(result.to_dict())


if __name__ == "__main__":
    main()
