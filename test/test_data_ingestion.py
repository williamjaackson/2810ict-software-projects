import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.data_ingestion import DataIngestion, FileReader


class TestIngestData(unittest.TestCase):
    def setUp(self):
        self.ingestion = DataIngestion.__new__(DataIngestion)

    def test_valid_row_returns_parsed_record(self):
        data = [
            ["timestamp", "kwh"],
            ["2024-01-01 00:00:00", "1.5"],
        ]

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1, 0, 0, 0): 1.5})
        self.assertEqual(warnings, [])

    def test_minute_precision_timestamp_is_accepted(self):
        data = [
            ["timestamp", "kwh"],
            ["2024-01-01 00:00", "1.5"],
        ]

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1, 0, 0): 1.5})
        self.assertEqual(warnings, [])

    def test_date_only_timestamp_is_accepted(self):
        data = [
            ["timestamp", "kwh"],
            ["2024-01-01", "1.5"],
        ]

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1): 1.5})
        self.assertEqual(warnings, [])

    def test_datetime_cell_is_accepted(self):
        stamp = datetime(2024, 1, 1, 0, 0, 0)
        data = [
            ["timestamp", "kwh"],
            [stamp, 1.5],
        ]

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {stamp: 1.5})
        self.assertEqual(warnings, [])

    def test_header_is_case_insensitive(self):
        data = [
            ["Timestamp", "KWH"],
            ["2024-01-01 00:00:00", "2.0"],
        ]

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1, 0, 0, 0): 2.0})
        self.assertEqual(warnings, [])

    def test_missing_header_raises_value_error(self):
        data = [
            ["time", "usage"],
            ["2024-01-01 00:00:00", "1.0"],
        ]

        with self.assertRaises(ValueError):
            self.ingestion._ingest_data(data)

    def test_header_only_file_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.ingestion._ingest_data([["timestamp", "kwh"]])

    def test_invalid_timestamp_adds_warning(self):
        data = [
            ["timestamp", "kwh"],
            ["not-a-timestamp", "1.5"],
        ]

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {})
        self.assertEqual(warnings, ["Invalid timestamp: not-a-timestamp"])

    def test_non_numeric_kwh_adds_warning(self):
        data = [
            ["timestamp", "kwh"],
            ["2024-01-01 00:00:00", "not-a-number"],
        ]

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {})
        self.assertEqual(warnings, ["Invalid KWH: not-a-number"])

    def test_negative_kwh_adds_warning(self):
        data = [
            ["timestamp", "kwh"],
            ["2024-01-01 00:00:00", "-1.0"],
        ]

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {})
        self.assertEqual(warnings, ["Invalid KWH: -1.0"])

    def test_duplicate_timestamp_adds_warning(self):
        stamp = datetime(2024, 1, 1, 0, 0, 0)
        data = [
            ["timestamp", "kwh"],
            ["2024-01-01 00:00:00", "1.5"],
            ["2024-01-01 00:00:00", "2.0"],
        ]

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {stamp: 1.5})
        self.assertEqual(warnings, [f"Duplicate timestamp: {stamp}"])

    def test_bad_row_does_not_block_later_valid_row(self):
        data = [
            ["timestamp", "kwh"],
            ["not-a-timestamp", "1.5"],
            ["2024-01-01 00:00:00", "2.0"],
        ]

        records, warnings = self.ingestion._ingest_data(data)

        self.assertEqual(records, {datetime(2024, 1, 1, 0, 0, 0): 2.0})
        self.assertEqual(warnings, ["Invalid timestamp: not-a-timestamp"])


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
            self.assertEqual(
                FileReader(path)(),
                [["timestamp", "kwh"], ["2024-01-01 00:00:00", "1.5"]],
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