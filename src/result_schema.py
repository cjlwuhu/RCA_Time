"""Shared result objects used by RCAEval and PyRCA adapters."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RankedRootCause:
    """One predicted root cause in rank order."""

    rank: int
    metric: str
    score: Optional[float] = None

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("rank must start at 1")
        if not self.metric.strip():
            raise ValueError("metric must not be empty")


@dataclass(frozen=True)
class GroundTruth:
    """Known label supplied by the benchmark dataset."""

    service: str
    metric: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.service.strip():
            raise ValueError("ground-truth service must not be empty")


@dataclass
class RCAResult:
    """Algorithm-independent output for one incident."""

    incident_id: str
    system: str
    fault_type: str
    inject_time: int
    method: str
    root_causes: List[RankedRootCause]
    ground_truth: GroundTruth
    runtime_seconds: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = {
            "incident_id": self.incident_id,
            "system": self.system,
            "fault_type": self.fault_type,
            "method": self.method,
        }
        empty = [name for name, value in required.items() if not value.strip()]
        if empty:
            raise ValueError(f"required text fields must not be empty: {empty}")
        if self.runtime_seconds < 0:
            raise ValueError("runtime_seconds must be non-negative")
        expected_ranks = list(range(1, len(self.root_causes) + 1))
        actual_ranks = [item.rank for item in self.root_causes]
        if actual_ranks != expected_ranks:
            raise ValueError("root_causes must be ordered with consecutive ranks")

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary."""

        return asdict(self)
