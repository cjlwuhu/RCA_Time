"""Step 3: obtain normal/abnormal windows from one continuous time series."""

import numpy as np
import pandas as pd

from src.window_splitter import split_metric_windows


def build_continuous_incident() -> tuple[pd.DataFrame, int]:
    """Create 20 minutes of metrics with a fault injected after 10 minutes."""

    rng = np.random.default_rng(42)
    sample_interval_seconds = 10
    points_per_window = 60
    total_points = points_per_window * 2
    start_time = 1_692_569_000
    timestamps = start_time + np.arange(total_points) * sample_interval_seconds
    inject_time = int(timestamps[points_per_window])

    latency = rng.normal(100, 3, total_points)
    latency[points_per_window:] += 200  # fault starts at inject_time

    data = pd.DataFrame(
        {
            "time": timestamps,
            "checkout_latency": latency,
            "cart_cpu": rng.normal(40, 2, total_points),
            "payment_memory": rng.normal(60, 2, total_points),
        }
    )
    return data, inject_time


def main() -> None:
    data, inject_time = build_continuous_incident()
    windows = split_metric_windows(
        data=data,
        inject_time=inject_time,
        window_minutes=10,
        minimum_points=20,
    )

    print("inject_time:", inject_time)
    print("continuous data shape:", data.shape)
    print("normal window shape  :", windows.normal.shape)
    print("abnormal window shape:", windows.abnormal.shape)
    print("\nWindow means:")
    print(
        pd.DataFrame(
            {
                "before_fault": windows.normal.mean(),
                "after_fault": windows.abnormal.mean(),
            }
        ).round(2)
    )


if __name__ == "__main__":
    main()
