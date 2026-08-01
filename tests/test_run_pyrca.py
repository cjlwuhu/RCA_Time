import unittest

from scripts.learn_epsilon_diagnosis import build_demo_data
from scripts.run_pyrca import run_epsilon_diagnosis, validate_metric_windows


class PyRCARunnerTests(unittest.TestCase):
    def test_demo_fault_is_ranked_first(self) -> None:
        normal, abnormal = build_demo_data("cart_cpu", num_points=40)
        result = run_epsilon_diagnosis(
            normal,
            abnormal,
            incident_id="demo-cart-cpu",
            system="synthetic-demo",
            fault_type="synthetic",
            inject_time=0,
            ground_truth_service="cartservice",
            ground_truth_metric="cart_cpu",
            bootstrap_time=10,
            root_cause_top_k=3,
        )

        self.assertEqual(result.root_causes[0].metric, "cart_cpu")
        self.assertGreaterEqual(result.runtime_seconds, 0)

    def test_validation_rejects_mismatched_columns(self) -> None:
        normal, abnormal = build_demo_data(num_points=20)
        abnormal = abnormal.rename(columns={"cart_cpu": "renamed_cpu"})
        with self.assertRaisesRegex(ValueError, "columns must match"):
            validate_metric_windows(normal, abnormal)


if __name__ == "__main__":
    unittest.main()
