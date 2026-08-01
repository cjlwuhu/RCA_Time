import unittest

import pandas as pd

from src.case_analysis import rank_metric_changes


class CaseAnalysisTests(unittest.TestCase):
    def test_changed_metric_ranks_above_unchanged_metric(self) -> None:
        normal = pd.DataFrame({"changed": [1, 2, 1, 2], "stable": [5, 6, 5, 6]})
        abnormal = pd.DataFrame({"changed": [10, 11, 10, 11], "stable": [5, 6, 5, 6]})

        ranking = rank_metric_changes(normal, abnormal)

        self.assertEqual(ranking.iloc[0]["metric"], "changed")
        self.assertEqual(ranking.iloc[1]["change_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
