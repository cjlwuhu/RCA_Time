import unittest

from scripts.evaluate_results import canonical_metric, result_to_row, summarize


class EvaluateResultsTests(unittest.TestCase):
    def test_latency_90_uses_official_metric_name(self) -> None:
        self.assertEqual(
            canonical_metric("adservice_latency-90"), "adservice_latency"
        )

    def test_result_has_service_and_metric_ranks(self) -> None:
        payload = {
            "incident_id": "adservice_delay_1",
            "fault_type": "delay",
            "method": "demo",
            "ground_truth": {
                "service": "adservice",
                "metric": "adservice_latency",
            },
            "root_causes": [
                {"rank": 1, "metric": "cartservice_cpu", "score": 1.0},
                {"rank": 2, "metric": "adservice_latency-90", "score": 0.8},
            ],
            "runtime_seconds": 0.25,
        }
        row = result_to_row(payload)
        self.assertEqual(row["service_rank"], 2)
        self.assertEqual(row["metric_rank"], 2)
        self.assertEqual(row["service_hit_at_1"], 0.0)
        self.assertEqual(row["metric_hit_at_3"], 1.0)

    def test_summary_counts_errors_as_zero(self) -> None:
        rows = [
            {
                "method": "demo",
                "status": "ok",
                "service_hit_at_1": 1.0,
                "service_hit_at_3": 1.0,
                "service_hit_at_5": 1.0,
                "service_mrr": 1.0,
                "metric_hit_at_1": 1.0,
                "metric_hit_at_3": 1.0,
                "metric_hit_at_5": 1.0,
                "metric_mrr": 1.0,
                "runtime_seconds": 0.2,
            },
            {
                "method": "demo",
                "status": "error",
                "service_hit_at_1": 0.0,
                "service_hit_at_3": 0.0,
                "service_hit_at_5": 0.0,
                "service_mrr": 0.0,
                "metric_hit_at_1": 0.0,
                "metric_hit_at_3": 0.0,
                "metric_hit_at_5": 0.0,
                "metric_mrr": 0.0,
                "runtime_seconds": None,
            },
        ]
        summary = summarize(rows)[0]
        self.assertEqual(summary["cases"], 2)
        self.assertEqual(summary["successful_runs"], 1)
        self.assertEqual(summary["service_hit_at_1"], 0.5)
        self.assertEqual(summary["mean_runtime_seconds"], 0.2)


if __name__ == "__main__":
    unittest.main()
