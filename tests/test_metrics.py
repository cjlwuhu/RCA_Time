import unittest

from src.metrics import (
    hit_at_k,
    mean,
    reciprocal_rank,
    service_hit_at_k,
    service_rank,
)


class MetricsTests(unittest.TestCase):
    def test_hit_at_k(self) -> None:
        predictions = ["metric_a", "metric_b", "metric_c"]
        self.assertEqual(hit_at_k(predictions, "metric_b", 1), 0.0)
        self.assertEqual(hit_at_k(predictions, "metric_b", 3), 1.0)

    def test_reciprocal_rank(self) -> None:
        self.assertAlmostEqual(reciprocal_rank(["a", "b", "c"], "b"), 0.5)
        self.assertEqual(reciprocal_rank(["a", "b", "c"], "missing"), 0.0)

    def test_mean_handles_empty_input(self) -> None:
        self.assertIsNone(mean([]))
        self.assertAlmostEqual(mean([1.0, 0.0, 1.0]), 2 / 3)

    def test_service_level_rank(self) -> None:
        predictions = ["checkoutservice_latency-90", "adservice_latency-90"]
        self.assertEqual(service_rank(predictions, "adservice"), 2)
        self.assertEqual(service_hit_at_k(predictions, "adservice", 1), 0.0)
        self.assertEqual(service_hit_at_k(predictions, "adservice", 3), 1.0)


if __name__ == "__main__":
    unittest.main()
