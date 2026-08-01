import unittest
from pathlib import Path

from scripts.run_rcaeval import official_fault_indicator, prepare_official_re1_input
from src.data_loader import load_re1_case


REAL_CASE = Path("data/RE1/RE1-OB/adservice_delay/1")


@unittest.skipUnless(REAL_CASE.is_dir(), "real RE1 dataset is not available")
class RCAEvalInputTests(unittest.TestCase):
    def test_official_re1_preprocessing_shape_and_names(self) -> None:
        case = load_re1_case(REAL_CASE)
        data = prepare_official_re1_input(case)

        self.assertEqual(len(data), 600)
        self.assertIn("adservice_latency", data.columns)
        self.assertFalse(any(c.endswith("_latency-50") for c in data.columns))
        self.assertFalse(any(c.endswith("_latency-90") for c in data.columns))
        self.assertEqual(official_fault_indicator(case), "adservice_latency")


if __name__ == "__main__":
    unittest.main()
