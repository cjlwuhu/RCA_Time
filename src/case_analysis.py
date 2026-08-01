"""Small, algorithm-independent helpers for understanding one RCA case."""

import numpy as np
import pandas as pd


def rank_metric_changes(
    normal: pd.DataFrame, abnormal: pd.DataFrame
) -> pd.DataFrame:
    """Rank metrics by standardized absolute mean shift.

    The pooled standard deviation makes CPU, bytes and latency comparable even
    though their raw units differ. This is an exploration score, not an RCA
    probability and not a claim of causality.
    """

    if list(normal.columns) != list(abnormal.columns):
        raise ValueError("normal and abnormal columns must match")

    normal_mean = normal.mean()
    abnormal_mean = abnormal.mean()
    pooled_std = np.sqrt((normal.var(ddof=0) + abnormal.var(ddof=0)) / 2)
    mean_shift = (abnormal_mean - normal_mean).abs()
    score = mean_shift / pooled_std.replace(0, np.nan)
    score = score.where(pooled_std > 0, other=(mean_shift > 0).astype(float) * np.inf)
    score = score.where(mean_shift > 0, other=0.0)

    return (
        pd.DataFrame(
            {
                "normal_mean": normal_mean,
                "abnormal_mean": abnormal_mean,
                "absolute_mean_shift": mean_shift,
                "pooled_std": pooled_std,
                "change_score": score,
            }
        )
        .sort_values("change_score", ascending=False)
        .rename_axis("metric")
        .reset_index()
    )
