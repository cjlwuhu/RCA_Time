import unittest

import numpy as np
import pandas as pd

from src.preprocessing import prepare_epsilon_windows


class PreprocessingTests(unittest.TestCase):
    def test_removes_constant_and_non_finite_metrics(self) -> None:
        normal = pd.DataFrame(
            {
                "a": [1, 2, 3],
                "b": [2, 3, 4],
                "c": [3, 4, 5],
                "constant": [1, 1, 1],
                "infinite": [1, np.inf, 2],
            }
        )
        abnormal = pd.DataFrame(
            {
                "a": [2, 3, 4],
                "b": [3, 4, 5],
                "c": [4, 5, 6],
                "constant": [2, 3, 4],
                "infinite": [2, 3, 4],
            }
        )

        clean_normal, clean_abnormal, report = prepare_epsilon_windows(
            normal, abnormal
        )

        self.assertEqual(list(clean_normal.columns), ["a", "b", "c"])
        self.assertEqual(list(clean_abnormal.columns), ["a", "b", "c"])
        self.assertIn("constant", report.removed_metrics["constant_in_normal"])
        self.assertIn("infinite", report.removed_metrics["non_finite"])


if __name__ == "__main__":
    unittest.main()
