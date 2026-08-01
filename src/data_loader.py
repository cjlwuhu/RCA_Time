"""Load and validate one metric-only RCAEval RE1 incident."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Optional

import pandas as pd


FAULT_TYPES = {"cpu", "mem", "disk", "delay", "loss"}
SYSTEM_ALIASES = {
    "ob": "online-boutique",
    "online-boutique": "online-boutique",
    "online_boutique": "online-boutique",
    "ss": "sock-shop",
    "sock-shop": "sock-shop",
    "sock_shop": "sock-shop",
    "tt": "train-ticket",
    "train-ticket": "train-ticket",
    "train_ticket": "train-ticket",
}


@dataclass(frozen=True)
class RE1Case:
    """One RE1 case plus the labels inferred from its directory name."""

    case_id: str
    system: str
    service: str
    fault_type: str
    instance_id: str
    inject_time: int
    metrics: pd.DataFrame
    root_cause_service: str
    root_cause_metric: Optional[str]


def _parse_case_name(case_path: Path) -> tuple[str, str, str]:
    """Support both nested and newer flat RCAEval case layouts."""

    # Older RE1 layout: RE1-OB/adservice_delay/1/data.csv
    nested_match = re.fullmatch(
        r"(?P<service>.+)_(?P<fault>cpu|mem|disk|delay|loss)",
        case_path.parent.name.lower(),
    )
    if nested_match and case_path.name:
        return (
            nested_match.group("service"),
            nested_match.group("fault"),
            case_path.name,
        )

    # Newer flat layout: re1-ob_checkoutservice_delay_1/metrics.json
    flat_match = re.search(
        r"(?P<service>[^_]+)_(?P<fault>cpu|mem|disk|delay|loss)_(?P<instance>[^_]+)$",
        case_path.name.lower(),
    )
    if flat_match:
        return (
            flat_match.group("service"),
            flat_match.group("fault"),
            flat_match.group("instance"),
        )

    raise ValueError(
        "case path must look like <service>_<fault>/<instance> or "
        "<benchmark>_<service>_<fault>_<instance>"
    )


def _infer_system(case_path: Path) -> str:
    normalized_parts = [part.lower().replace(" ", "-") for part in case_path.parts]
    joined = "/".join(normalized_parts)
    for alias, system in SYSTEM_ALIASES.items():
        alias_pattern = rf"(^|[-_/]){re.escape(alias)}($|[-_/])"
        if re.search(alias_pattern, joined):
            return system
    raise ValueError(
        "cannot infer system from path; include ob/online-boutique, "
        "ss/sock-shop or tt/train-ticket in the path"
    )


def _read_metrics_json(metrics_path: Path) -> pd.DataFrame:
    """Support records, columns and pandas split-style JSON layouts."""

    try:
        payload: Any = json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        records = [
            json.loads(line)
            for line in metrics_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        payload = records

    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict) and {"columns", "data"}.issubset(payload):
        return pd.DataFrame(
            payload["data"],
            columns=payload["columns"],
            index=payload.get("index"),
        )
    if isinstance(payload, dict):
        return pd.DataFrame(payload)
    raise ValueError("metrics.json must contain a JSON array or object")


def _read_metrics(case_path: Path) -> pd.DataFrame:
    json_path = case_path / "metrics.json"
    csv_path = case_path / "data.csv"
    simple_csv_path = case_path / "simple_data.csv"
    if json_path.is_file():
        return _read_metrics_json(json_path)
    if csv_path.is_file():
        return pd.read_csv(csv_path)
    if simple_csv_path.is_file():
        return pd.read_csv(simple_csv_path)
    raise FileNotFoundError(
        f"missing metrics file in {case_path}; expected metrics.json, "
        "data.csv or simple_data.csv"
    )


def _validate_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        raise ValueError("metrics.json contains no rows")
    if "time" not in metrics.columns:
        raise ValueError("metrics.json must contain a 'time' column")
    if len(metrics.columns) < 2:
        raise ValueError("metrics.json must contain at least one metric column")

    numeric = metrics.copy()
    for column in numeric.columns:
        try:
            numeric[column] = pd.to_numeric(numeric[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"column '{column}' contains non-numeric values") from exc

    if numeric.isna().any().any():
        raise ValueError("metrics.json contains missing values")
    if numeric["time"].duplicated().any():
        raise ValueError("metrics.json contains duplicate timestamps")
    return numeric.sort_values("time").reset_index(drop=True)


def _infer_root_cause_metric(
    columns: list[str], service: str, fault_type: str
) -> Optional[str]:
    suffix = "latency" if fault_type in {"delay", "loss"} else fault_type
    exact = f"{service}_{suffix}"
    if exact in columns:
        return exact

    matches = [
        column
        for column in columns
        if service in column.lower()
        and (
            column.lower().endswith(f"_{suffix}")
            or f"_{suffix}-" in column.lower()
        )
    ]
    return matches[0] if len(matches) == 1 else None


def load_re1_case(case_path: str | Path) -> RE1Case:
    """Read one RE1 case directory into a validated domain object."""

    path = Path(case_path)
    if not path.is_dir():
        raise FileNotFoundError(f"case directory does not exist: {path}")

    inject_path = path / "inject_time.txt"
    if not inject_path.is_file():
        raise FileNotFoundError(f"missing injection time file: {inject_path}")

    service, fault_type, instance_id = _parse_case_name(path)
    system = _infer_system(path)
    metrics = _validate_metrics(_read_metrics(path))

    inject_text = inject_path.read_text(encoding="utf-8").strip()
    try:
        inject_time = int(inject_text)
    except ValueError as exc:
        raise ValueError("inject_time.txt must contain one Unix timestamp") from exc
    if not metrics["time"].min() <= inject_time <= metrics["time"].max():
        raise ValueError("inject_time is outside the metrics time range")

    metric_columns = [str(column) for column in metrics.columns if column != "time"]
    return RE1Case(
        case_id=(
            f"{path.parent.name}_{path.name}"
            if re.fullmatch(r"\d+", path.name)
            else path.name
        ),
        system=system,
        service=service,
        fault_type=fault_type,
        instance_id=instance_id,
        inject_time=inject_time,
        metrics=metrics,
        root_cause_service=service,
        root_cause_metric=_infer_root_cause_metric(
            metric_columns, service, fault_type
        ),
    )
