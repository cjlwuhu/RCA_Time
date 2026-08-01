"""Step 7: visualize one real RE1 case around its fault injection time."""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.case_analysis import rank_metric_changes
from src.data_loader import RE1Case, load_re1_case
from src.window_splitter import MetricWindows, split_metric_windows


DEFAULT_CASE = Path("data/RE1/RE1-OB/adservice_delay/1")


def normalize_for_plot(series: pd.Series, normal_values: pd.Series) -> pd.Series:
    """Min-max scale each line so differently-unit metrics remain visible."""

    del normal_values  # kept in the signature to make the plotting contract explicit
    minimum = float(series.min())
    scale = float(series.max() - minimum)
    if not np.isfinite(scale) or scale < 1e-12:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - minimum) / scale


def plot_case(
    case: RE1Case,
    windows: MetricWindows,
    ranking: pd.DataFrame,
    window_minutes: int,
    top_k: int,
    output_path: Path,
) -> None:
    start = case.inject_time - window_minutes * 60
    end = case.inject_time + window_minutes * 60
    visible = case.metrics.loc[
        (case.metrics["time"] >= start) & (case.metrics["time"] < end)
    ].copy()
    relative_seconds = visible["time"] - case.inject_time

    service_metrics = [
        column
        for column in windows.normal.columns
        if case.service.lower() in column.lower()
    ]
    top_metrics = ranking.head(top_k)["metric"].tolist()

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    groups = [
        (axes[0], service_metrics, f"Metrics belonging to {case.service}"),
        (axes[1], top_metrics, f"Top {top_k} standardized mean shifts"),
    ]

    for axis, metric_names, title in groups:
        for metric in metric_names:
            normalized = normalize_for_plot(visible[metric], windows.normal[metric])
            axis.plot(relative_seconds, normalized, linewidth=1.1, label=metric)
        axis.axvspan(-window_minutes * 60, 0, color="#4C78A8", alpha=0.08)
        axis.axvspan(0, window_minutes * 60, color="#F58518", alpha=0.08)
        axis.axvline(0, color="#D62728", linestyle="--", linewidth=1.5, label="inject_time")
        axis.set_title(title)
        axis.set_ylabel("Per-metric scale (0 to 1)")
        axis.grid(alpha=0.2)
        axis.legend(loc="upper left", fontsize=7, ncol=2)

    axes[1].set_xlabel("Seconds relative to fault injection")
    fig.suptitle(
        f"RE1 case: {case.case_id} | normal window vs incident window",
        fontsize=14,
    )
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize one RE1 case.")
    parser.add_argument("case_path", nargs="?", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--window-minutes", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    case = load_re1_case(args.case_path)
    windows = split_metric_windows(
        case.metrics,
        inject_time=case.inject_time,
        window_minutes=args.window_minutes,
        minimum_points=20,
    )
    ranking = rank_metric_changes(windows.normal, windows.abnormal)
    output_path = args.output or Path("outputs/figures") / f"{case.case_id}.png"
    plot_case(
        case,
        windows,
        ranking,
        window_minutes=args.window_minutes,
        top_k=args.top_k,
        output_path=output_path,
    )

    print("case           :", case.case_id)
    print("window points  :", len(windows.normal), "normal +", len(windows.abnormal), "abnormal")
    print("output          :", output_path.resolve())
    print("\nTop metric changes (exploration only):")
    print(
        ranking.head(args.top_k)[
            ["metric", "normal_mean", "abnormal_mean", "change_score"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
