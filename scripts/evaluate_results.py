"""Evaluate unified RCA JSON files and build reproducible comparison reports."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

from src.metrics import service_hit_at_k, service_rank


DETAIL_FIELDS = [
    "incident_id",
    "fault_type",
    "ground_truth_service",
    "ground_truth_metric",
    "method",
    "status",
    "service_rank",
    "service_hit_at_1",
    "service_hit_at_3",
    "service_hit_at_5",
    "service_mrr",
    "metric_rank",
    "metric_hit_at_1",
    "metric_hit_at_3",
    "metric_hit_at_5",
    "metric_mrr",
    "runtime_seconds",
    "prediction_count",
    "top_1_metric",
    "error",
]

SUMMARY_FIELDS = [
    "method",
    "cases",
    "successful_runs",
    "service_hit_at_1",
    "service_hit_at_3",
    "service_hit_at_5",
    "service_mrr",
    "metric_hit_at_1",
    "metric_hit_at_3",
    "metric_hit_at_5",
    "metric_mrr",
    "mean_runtime_seconds",
]


def canonical_metric(metric: str) -> str:
    """Map raw RE1 metric names to the RCAEval label convention."""

    normalized = metric.strip().lower()
    if normalized.endswith("_latency-90"):
        return normalized.removesuffix("-90")
    return normalized


def metric_rank(predictions: Sequence[str], target: str) -> int | None:
    canonical_target = canonical_metric(target)
    for rank, prediction in enumerate(predictions, start=1):
        if canonical_metric(prediction) == canonical_target:
            return rank
    return None


def _hit(rank: int | None, k: int) -> float:
    return float(rank is not None and rank <= k)


def result_to_row(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert one unified result (or one error record) into a flat row."""

    if payload.get("status") == "error":
        return {
            "incident_id": payload["incident_id"],
            "fault_type": payload["fault_type"],
            "ground_truth_service": payload["ground_truth_service"],
            "ground_truth_metric": payload["ground_truth_metric"],
            "method": payload["method"],
            "status": "error",
            "service_rank": None,
            "service_hit_at_1": 0.0,
            "service_hit_at_3": 0.0,
            "service_hit_at_5": 0.0,
            "service_mrr": 0.0,
            "metric_rank": None,
            "metric_hit_at_1": 0.0,
            "metric_hit_at_3": 0.0,
            "metric_hit_at_5": 0.0,
            "metric_mrr": 0.0,
            "runtime_seconds": None,
            "prediction_count": 0,
            "top_1_metric": "",
            "error": payload.get("error", "unknown error"),
        }

    predictions = [item["metric"] for item in payload["root_causes"]]
    target_service = payload["ground_truth"]["service"]
    target_metric = payload["ground_truth"].get("metric")
    service_match_rank = service_rank(predictions, target_service)
    metric_match_rank = (
        metric_rank(predictions, target_metric) if target_metric else None
    )
    return {
        "incident_id": payload["incident_id"],
        "fault_type": payload["fault_type"],
        "ground_truth_service": target_service,
        "ground_truth_metric": target_metric or "",
        "method": payload["method"],
        "status": "ok",
        "service_rank": service_match_rank,
        "service_hit_at_1": service_hit_at_k(predictions, target_service, 1),
        "service_hit_at_3": service_hit_at_k(predictions, target_service, 3),
        "service_hit_at_5": service_hit_at_k(predictions, target_service, 5),
        "service_mrr": 1.0 / service_match_rank if service_match_rank else 0.0,
        "metric_rank": metric_match_rank,
        "metric_hit_at_1": _hit(metric_match_rank, 1),
        "metric_hit_at_3": _hit(metric_match_rank, 3),
        "metric_hit_at_5": _hit(metric_match_rank, 5),
        "metric_mrr": 1.0 / metric_match_rank if metric_match_rank else 0.0,
        "runtime_seconds": payload["runtime_seconds"],
        "prediction_count": len(predictions),
        "top_1_metric": predictions[0] if predictions else "",
        "error": "",
    }


def summarize(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["method"]].append(row)

    summaries: list[dict[str, Any]] = []
    for method, method_rows in sorted(grouped.items()):
        count = len(method_rows)
        runtimes = [
            float(row["runtime_seconds"])
            for row in method_rows
            if row["runtime_seconds"] is not None
        ]

        def average(field: str) -> float:
            return sum(float(row[field]) for row in method_rows) / count

        summaries.append(
            {
                "method": method,
                "cases": count,
                "successful_runs": sum(row["status"] == "ok" for row in method_rows),
                "service_hit_at_1": average("service_hit_at_1"),
                "service_hit_at_3": average("service_hit_at_3"),
                "service_hit_at_5": average("service_hit_at_5"),
                "service_mrr": average("service_mrr"),
                "metric_hit_at_1": average("metric_hit_at_1"),
                "metric_hit_at_3": average("metric_hit_at_3"),
                "metric_hit_at_5": average("metric_hit_at_5"),
                "metric_mrr": average("metric_mrr"),
                "mean_runtime_seconds": sum(runtimes) / len(runtimes)
                if runtimes
                else None,
            }
        )
    return summaries


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _format_score(value: Any) -> str:
    return "" if value is None else f"{float(value):.3f}"


def _write_markdown(path: Path, summaries: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# RE1-OB delay/loss 算法比较",
        "",
        f"共评价 {len(rows)} 次算法运行；错误运行也计入分母，得分按 0 处理。",
        "",
        "## 汇总结果",
        "",
        "| 方法 | 成功/案例 | 服务 Hit@1 | 服务 Hit@3 | 服务 MRR | 指标 Hit@1 | 指标 Hit@3 | 指标 MRR | 平均耗时(s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summaries:
        lines.append(
            f"| {item['method']} | {item['successful_runs']}/{item['cases']} | "
            f"{_format_score(item['service_hit_at_1'])} | "
            f"{_format_score(item['service_hit_at_3'])} | "
            f"{_format_score(item['service_mrr'])} | "
            f"{_format_score(item['metric_hit_at_1'])} | "
            f"{_format_score(item['metric_hit_at_3'])} | "
            f"{_format_score(item['metric_mrr'])} | "
            f"{_format_score(item['mean_runtime_seconds'])} |"
        )
    lines.extend(
        [
            "",
            "## 怎样读这些指标",
            "",
            "- 服务级：只要求找到故障服务，例如 `adservice`。",
            "- 指标级：还要求指标正确，例如 `adservice_latency`；原始 `latency-90` 会按 RCAEval 规则归一化为 `latency`。",
            "- Hit@K：正确答案是否出现在前 K 名；MRR 越接近 1，首次命中的排名越靠前。",
            "- 平均耗时只统计成功运行，准确率指标则把失败运行按 0 计入。",
            "",
            "详细到每个案例的结果见 `case_results.csv`。",
        ]
    )
    # utf-8-sig keeps Chinese readable in Windows PowerShell 5 and older Excel.
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def evaluate_directory(input_dir: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(input_dir.glob("*.json"))
    ]
    if not payloads:
        raise FileNotFoundError(f"no result JSON files found in {input_dir}")
    rows = [result_to_row(payload) for payload in payloads]
    rows.sort(key=lambda row: (row["incident_id"], row["method"]))
    summaries = summarize(rows)

    detail_path = output_dir / "case_results.csv"
    summary_path = output_dir / "algorithm_comparison.csv"
    markdown_path = output_dir / "algorithm_comparison.md"
    _write_csv(detail_path, rows, DETAIL_FIELDS)
    _write_csv(summary_path, summaries, SUMMARY_FIELDS)
    _write_markdown(markdown_path, summaries, rows)
    return detail_path, summary_path, markdown_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate unified RCA JSON files.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("outputs/predictions/re1_ob_delay_loss"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("outputs/reports/re1_ob_delay_loss")
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for path in evaluate_directory(args.input_dir, args.output_dir):
        print("saved:", path.resolve())


if __name__ == "__main__":
    main()
