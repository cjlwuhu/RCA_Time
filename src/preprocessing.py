"""Preprocessing rules required by the installed PyRCA implementation."""

from dataclasses import asdict, dataclass
from typing import Dict, List

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PreprocessingReport:
    original_metric_count: int
    retained_metric_count: int
    removed_metrics: Dict[str, List[str]]

    def to_dict(self) -> dict:
        return asdict(self)


def prepare_epsilon_windows(
    normal: pd.DataFrame, abnormal: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, PreprocessingReport]:
    """Remove columns that EpsilonDiagnosis cannot compare reliably."""

    if list(normal.columns) != list(abnormal.columns):
        raise ValueError("normal and abnormal columns must match")
    if len(normal) != len(abnormal):
        raise ValueError("normal and abnormal windows must have equal rows")

    removed: Dict[str, List[str]] = {
        "non_numeric": [],
        "non_finite": [],
        "constant_in_normal": [],
        "constant_in_abnormal": [],
    }
    retained: List[str] = []

    for column in normal.columns:
        if not pd.api.types.is_numeric_dtype(normal[column]) or not pd.api.types.is_numeric_dtype(
            abnormal[column]
        ):
            removed["non_numeric"].append(column)
            continue
        if not np.isfinite(normal[column].to_numpy()).all() or not np.isfinite(
            abnormal[column].to_numpy()
        ).all():
            removed["non_finite"].append(column)
            continue
        if normal[column].nunique(dropna=False) <= 1:
            removed["constant_in_normal"].append(column)
            continue
        if abnormal[column].nunique(dropna=False) <= 1:
            removed["constant_in_abnormal"].append(column)
            continue
        retained.append(column)

    if len(retained) < 3:
        raise ValueError(
            f"EpsilonDiagnosis needs at least three usable metrics; retained={len(retained)}"
        )

    report = PreprocessingReport(
        original_metric_count=len(normal.columns),
        retained_metric_count=len(retained),
        removed_metrics=removed,
    )
    return normal[retained].copy(), abnormal[retained].copy(), report
