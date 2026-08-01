import unittest

from src.result_schema import GroundTruth, RCAResult, RankedRootCause


class ResultSchemaTests(unittest.TestCase):
    def test_result_is_json_ready_and_preserves_missing_score(self) -> None:
        result = RCAResult(
            incident_id="re1-ob-checkoutservice-delay-1",
            system="online-boutique",
            fault_type="delay",
            inject_time=1692569339,
            method="baro",
            root_causes=[RankedRootCause(rank=1, metric="checkoutservice_latency")],
            ground_truth=GroundTruth(
                service="checkoutservice", metric="checkoutservice_latency"
            ),
            runtime_seconds=1.43,
        )

        payload = result.to_dict()
        self.assertIsNone(payload["root_causes"][0]["score"])
        self.assertEqual(payload["ground_truth"]["service"], "checkoutservice")

    def test_result_rejects_nonconsecutive_ranks(self) -> None:
        with self.assertRaisesRegex(ValueError, "consecutive ranks"):
            RCAResult(
                incident_id="case-1",
                system="online-boutique",
                fault_type="loss",
                inject_time=1,
                method="baro",
                root_causes=[RankedRootCause(rank=2, metric="metric_a")],
                ground_truth=GroundTruth(service="service-a"),
                runtime_seconds=0.1,
            )


if __name__ == "__main__":
    unittest.main()
