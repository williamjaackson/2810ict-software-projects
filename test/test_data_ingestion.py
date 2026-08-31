import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.data_ingestion import DataIngestion, FileReader


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


if __name__ == "__main__":
    unittest.main()
