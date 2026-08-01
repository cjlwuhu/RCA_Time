import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.data_loader import load_re1_case


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "re1-ob"
    / "re1-ob_checkoutservice_delay_1"
)


class RE1DataLoaderTests(unittest.TestCase):
    def test_loads_case_files_and_directory_labels(self) -> None:
        case = load_re1_case(FIXTURE)

        self.assertEqual(case.system, "online-boutique")
        self.assertEqual(case.service, "checkoutservice")
        self.assertEqual(case.fault_type, "delay")
        self.assertEqual(case.instance_id, "1")
        self.assertEqual(case.inject_time, 1692569339)
        self.assertEqual(case.root_cause_metric, "checkoutservice_latency")
        self.assertEqual(list(case.metrics.columns)[0], "time")

    def test_missing_case_directory_has_clear_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "re1-ob_checkoutservice_delay_1"
            with self.assertRaises(FileNotFoundError):
                load_re1_case(missing)


if __name__ == "__main__":
    unittest.main()
