"""Split one continuous incident time series into reference/incident windows."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MetricWindows:
    normal: pd.DataFrame
    abnormal: pd.DataFrame


def split_metric_windows(
    data: pd.DataFrame,
    inject_time: int,
    window_minutes: int,
    minimum_points: int = 2,
) -> MetricWindows:
    """Split equally sized windows immediately before/after fault injection.

    The normal interval is ``[inject_time - window, inject_time)`` and the
    abnormal interval is ``[inject_time, inject_time + window)``.
    """

    if "time" not in data.columns:
        raise ValueError("data must contain a 'time' column")
    if window_minutes <= 0:
        raise ValueError("window_minutes must be positive")
    if data["time"].isna().any():
        raise ValueError("time column contains missing values")
    if data["time"].duplicated().any():
        raise ValueError("time column contains duplicate timestamps")

    ordered = data.sort_values("time").reset_index(drop=True)
    window_seconds = window_minutes * 60

    normal_mask = (ordered["time"] >= inject_time - window_seconds) & (
        ordered["time"] < inject_time
    )
    abnormal_mask = (ordered["time"] >= inject_time) & (
        ordered["time"] < inject_time + window_seconds
    )

    normal = ordered.loc[normal_mask].drop(columns="time").reset_index(drop=True)
    abnormal = ordered.loc[abnormal_mask].drop(columns="time").reset_index(drop=True)

    if len(normal) < minimum_points or len(abnormal) < minimum_points:
        raise ValueError(
            "not enough points around inject_time: "
            f"normal={len(normal)}, abnormal={len(abnormal)}, "
            f"minimum={minimum_points}"
        )
    if len(normal) != len(abnormal):
        raise ValueError(
            "normal and abnormal windows must contain equal points for the "
            f"installed EpsilonDiagnosis: normal={len(normal)}, "
            f"abnormal={len(abnormal)}"
        )
    if list(normal.columns) != list(abnormal.columns):
        raise ValueError("normal and abnormal metric columns do not match")
    if not all(pd.api.types.is_numeric_dtype(dtype) for dtype in normal.dtypes):
        raise ValueError("all metric columns must be numeric")

    return MetricWindows(normal=normal, abnormal=abnormal)
