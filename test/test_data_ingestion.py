import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.data_ingestion import DataIngestion, FileReader

SAMPLE_DATASET = Path(__file__).resolve().parent.parent / "sample_usage_data_month.csv"


class TestIngestData(unittest.TestCase):
    def setUp(self):
        self.ingestion = DataIngestion.__new__(DataIngestion)

    def test_valid_row_returns_parsed_record(self):
        data = pd.DataFrame(
            [
                ["2024-01-01 00:00:00", "1.5"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1, 0, 0, 0): 1.5})
        self.assertEqual(warnings, [])

    def test_minute_precision_timestamp_is_accepted(self):
        data = pd.DataFrame(
            [
                ["2024-01-01 00:00", "1.5"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1, 0, 0): 1.5})
        self.assertEqual(warnings, [])

    def test_date_only_timestamp_is_accepted(self):
        data = pd.DataFrame(
            [
                ["2024-01-01", "1.5"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1): 1.5})
        self.assertEqual(warnings, [])

    def test_mixed_timestamp_formats_in_same_column_are_accepted(self):
        data = pd.DataFrame(
            [
                ["2024-01-01 00:00:00", "1.5"],
                ["2024-01-01 01:00", "1.6"],
                ["2024-01-02", "1.7"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(
            records,
            {
                datetime(2024, 1, 1, 0, 0, 0): 1.5,
                datetime(2024, 1, 1, 1, 0): 1.6,
                datetime(2024, 1, 2): 1.7,
            },
        )
        self.assertEqual(warnings, [])

    def test_datetime_cell_is_accepted(self):
        stamp = datetime(2024, 1, 1, 0, 0, 0)
        data = pd.DataFrame(
            [
                [stamp, 1.5],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {stamp: 1.5})
        self.assertEqual(warnings, [])

    def test_header_is_case_insensitive(self):
        data = pd.DataFrame(
            [
                ["2024-01-01 00:00:00", "2.0"],
            ],
            columns=["Timestamp", "KWH"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1, 0, 0, 0): 2.0})
        self.assertEqual(warnings, [])

    def test_missing_header_raises_value_error(self):
        data = pd.DataFrame(
            [
                ["2024-01-01 00:00:00", "1.0"],
            ],
            columns=["time", "usage"],
        )

        with self.assertRaises(ValueError):
            self.ingestion._ingest_data(data)

    def test_header_only_file_raises_value_error(self):
        data = pd.DataFrame(columns=["timestamp", "kwh"])

        with self.assertRaises(ValueError):
            self.ingestion._ingest_data(data)

    def test_invalid_timestamp_adds_warning(self):
        data = pd.DataFrame(
            [
                ["not-a-timestamp", "1.5"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {})
        self.assertEqual(warnings, ["Invalid timestamp: not-a-timestamp"])

    def test_non_numeric_kwh_adds_warning(self):
        data = pd.DataFrame(
            [
                ["2024-01-01 00:00:00", "not-a-number"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {})
        self.assertEqual(warnings, ["Invalid KWH: not-a-number"])

    def test_negative_kwh_adds_warning(self):
        data = pd.DataFrame(
            [
                ["2024-01-01 00:00:00", "-1.0"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {})
        self.assertEqual(warnings, ["Invalid KWH: -1.0"])

    def test_duplicate_timestamp_adds_warning(self):
        stamp = datetime(2024, 1, 1, 0, 0, 0)
        data = pd.DataFrame(
            [
                ["2024-01-01 00:00:00", "1.5"],
                ["2024-01-01 00:00:00", "2.0"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {stamp: 1.5})
        self.assertEqual(warnings, [f"Duplicate timestamp: {stamp}"])

    def test_bad_row_does_not_block_later_valid_row(self):
        data = pd.DataFrame(
            [
                ["not-a-timestamp", "1.5"],
                ["2024-01-01 00:00:00", "2.0"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1, 0, 0, 0): 2.0})
        self.assertEqual(warnings, ["Invalid timestamp: not-a-timestamp"])

    def test_records_are_returned_in_timestamp_order(self):
        data = pd.DataFrame(
            [
                ["2024-01-01 02:00:00", "0.3"],
                ["2024-01-01 00:00:00", "0.1"],
                ["2024-01-01 01:00:00", "0.2"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(
            list(records),
            [
                datetime(2024, 1, 1, 0, 0, 0),
                datetime(2024, 1, 1, 1, 0, 0),
                datetime(2024, 1, 1, 2, 0, 0),
            ],
        )
        self.assertEqual(warnings, [])

    def test_missing_kwh_header_alone_raises_value_error(self):
        data = pd.DataFrame(
            [
                ["2024-01-01 00:00:00", "1.0"],
            ],
            columns=["timestamp", "usage"],
        )

        with self.assertRaises(ValueError):
            self.ingestion._ingest_data(data)

    def test_non_string_header_does_not_break_lookup(self):
        data = pd.DataFrame(
            [
                ["2024-01-01 00:00:00", "", "1.5"],
            ],
            columns=["timestamp", None, "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1, 0, 0, 0): 1.5})
        self.assertEqual(warnings, [])

    def test_blank_timestamp_adds_warning(self):
        data = pd.DataFrame(
            [
                [float("nan"), "1.5"],
                ["2024-01-01 00:00:00", "2.0"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1, 0, 0, 0): 2.0})
        self.assertEqual(warnings, ["Invalid timestamp: nan"])

    def test_blank_kwh_adds_warning(self):
        data = pd.DataFrame(
            [
                ["2024-01-01 00:00:00", float("nan")],
                ["2024-01-01 01:00:00", 2.0],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1, 1, 0, 0): 2.0})
        self.assertEqual(warnings, ["Invalid KWH: nan"])

    def test_duplicate_keeps_first_in_file_not_earliest_timestamp(self):
        stamp = datetime(2024, 1, 2, 0, 0, 0)
        data = pd.DataFrame(
            [
                ["2024-01-02 00:00:00", "2.0"],
                ["2024-01-01 00:00:00", "1.0"],
                ["2024-01-02 00:00:00", "9.9"],
            ],
            columns=["timestamp", "kwh"],
        )

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records[stamp], 2.0)
        self.assertEqual(warnings, [f"Duplicate timestamp: {stamp}"])


class TestFileReader(unittest.TestCase):
    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            FileReader("does_not_exist.csv")

    def test_unsupported_suffix_raises_value_error(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            path = tmp.name

        try:
            reader = FileReader(path)
            with self.assertRaises(ValueError):
                reader()
        finally:
            Path(path).unlink()

    def test_csv_returns_rows(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as tmp:
            tmp.write("timestamp,kwh\n2024-01-01 00:00:00,1.5\n")
            path = tmp.name

        try:
            pd.testing.assert_frame_equal(
                FileReader(path)(),
                pd.DataFrame(
                    {
                        "timestamp": ["2024-01-01 00:00:00"],
                        "kwh": [1.5],
                    }
                ),
            )
        finally:
            Path(path).unlink()

    def test_xlsx_returns_rows(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name

        try:
            pd.DataFrame(
                {"timestamp": ["2024-01-01 00:00:00"], "kwh": [1.5]}
            ).to_excel(path, index=False)

            frame = FileReader(path)()

            self.assertEqual(list(frame.columns), ["timestamp", "kwh"])
            self.assertEqual(len(frame), 1)
        finally:
            Path(path).unlink()

    def test_xls_is_routed_to_the_excel_reader(self):
        with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as tmp:
            path = tmp.name

        try:
            with patch("src.data_ingestion.pd.read_excel") as read_excel:
                FileReader(path)()

            read_excel.assert_called_once_with(Path(path))
        finally:
            Path(path).unlink()

    def test_oversized_file_raises_value_error(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as tmp:
            tmp.write("timestamp,kwh\n2024-01-01 00:00:00,1.5\n")
            path = tmp.name

        try:
            with patch("src.data_ingestion.MAX_FILE_BYTES", 1):
                with self.assertRaises(ValueError):
                    FileReader(path)
        finally:
            Path(path).unlink()


class TestDataIngestion(unittest.TestCase):
    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            DataIngestion("does_not_exist.csv")

    def test_run_reads_csv_and_ingests(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as tmp:
            tmp.write("timestamp,kwh\n2024-01-01 00:00:00,1.5\n")
            path = tmp.name

        try:
            records, warnings = DataIngestion(path).run()
        finally:
            Path(path).unlink()

        self.assertEqual(records, {datetime(2024, 1, 1, 0, 0, 0): 1.5})
        self.assertEqual(warnings, [])

    @unittest.skipUnless(
        SAMPLE_DATASET.exists(), f"{SAMPLE_DATASET.name} is not in the repository root"
    )
    def test_provided_sample_dataset(self):
        records, warnings = DataIngestion(SAMPLE_DATASET).run()

        self.assertEqual(len(records), 720)
        self.assertEqual(warnings, [])
        self.assertAlmostEqual(sum(records.values()), 850.67, places=2)


if __name__ == "__main__":
    unittest.main()
