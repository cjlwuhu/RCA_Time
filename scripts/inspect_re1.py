"""Step 6: inspect one RE1 case without running an RCA algorithm."""

import argparse
from pathlib import Path

from src.data_loader import load_re1_case


FIXTURE = (
    Path("tests")
    / "fixtures"
    / "re1-ob"
    / "re1-ob_checkoutservice_delay_1"
)
REAL_DEFAULT = Path("data") / "RE1" / "RE1-OB" / "adservice_delay" / "1"
DEFAULT_CASE = REAL_DEFAULT if REAL_DEFAULT.is_dir() else FIXTURE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect one RE1 case directory.")
    parser.add_argument(
        "case_path",
        nargs="?",
        type=Path,
        default=DEFAULT_CASE,
        help="directory containing metrics.json and inject_time.txt",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    case = load_re1_case(args.case_path)
    intervals = case.metrics["time"].diff().dropna()

    print("case_id          :", case.case_id)
    print("system           :", case.system)
    print("service          :", case.service)
    print("fault_type       :", case.fault_type)
    print("instance_id      :", case.instance_id)
    print("inject_time      :", case.inject_time)
    print("root cause metric:", case.root_cause_metric)
    print("rows             :", len(case.metrics))
    print("metric count     :", len(case.metrics.columns) - 1)
    print("time range       :", int(case.metrics.time.min()), "->", int(case.metrics.time.max()))
    print("sample interval  :", float(intervals.median()), "seconds")
    print("\nFirst three rows:")
    print(case.metrics.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
