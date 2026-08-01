import unittest

import pandas as pd

from src.window_splitter import split_metric_windows


class WindowSplitterTests(unittest.TestCase):
    def test_split_uses_pre_injection_as_normal_window(self) -> None:
        data = pd.DataFrame(
            {
                "time": list(range(0, 120, 10)),
                "metric_a": list(range(12)),
            }
        )

        windows = split_metric_windows(
            data=data,
            inject_time=60,
            window_minutes=1,
            minimum_points=6,
        )

        self.assertEqual(windows.normal["metric_a"].tolist(), list(range(6)))
        self.assertEqual(windows.abnormal["metric_a"].tolist(), list(range(6, 12)))

    def test_split_rejects_duplicate_timestamps(self) -> None:
        data = pd.DataFrame({"time": [0, 0, 10, 20], "metric_a": [1, 2, 3, 4]})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            split_metric_windows(data, inject_time=10, window_minutes=1)


if __name__ == "__main__":
    unittest.main()
