"""Ranking metrics for root-cause predictions."""

from typing import Iterable, List, Optional, Sequence


def _normalize(name: str) -> str:
    return name.strip().lower()


def hit_at_k(predictions: Sequence[str], target: str, k: int) -> float:
    """Return 1.0 when *target* occurs in the first *k* predictions."""

    if k < 1:
        raise ValueError("k must be at least 1")
    normalized_target = _normalize(target)
    return float(
        normalized_target in {_normalize(item) for item in predictions[:k]}
    )


def reciprocal_rank(predictions: Sequence[str], target: str) -> float:
    """Return 1/rank for the first target match, otherwise 0.0."""

    normalized_target = _normalize(target)
    for rank, item in enumerate(predictions, start=1):
        if _normalize(item) == normalized_target:
            return 1.0 / rank
    return 0.0


def mean(values: Iterable[float]) -> Optional[float]:
    """Return the arithmetic mean, or None for an empty collection."""

    items: List[float] = list(values)
    return sum(items) / len(items) if items else None


def service_rank(predictions: Sequence[str], target_service: str) -> Optional[int]:
    """Return the first rank whose metric belongs to the target service."""

    service = _normalize(target_service)
    prefixes = (f"{service}_", f"{service}-")
    for rank, metric in enumerate(predictions, start=1):
        if _normalize(metric).startswith(prefixes):
            return rank
    return None


def service_hit_at_k(
    predictions: Sequence[str], target_service: str, k: int
) -> float:
    if k < 1:
        raise ValueError("k must be at least 1")
    rank = service_rank(predictions, target_service)
    return float(rank is not None and rank <= k)
