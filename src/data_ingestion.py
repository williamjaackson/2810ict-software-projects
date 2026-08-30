from pathlib import Path
from datetime import datetime

import csv
import openpyxl as excel

TIMESTAMP_HEADER = "timestamp"
KWH_HEADER = "kwh"

TIMESTAMP_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")

class DataIngestion:
    def __init__(self, file_path: str):
        path = Path(file_path)
        
        if not path.is_file(): raise FileNotFoundError(f"File not found: {file_path}")

        suffix = path.suffix.lower()

        match suffix:
            case ".csv":
                reader = self._read_csv
            case ".xlsx":
                reader = self._read_excel
            case _:
                raise ValueError(f"Unsupported file type: {suffix}")
        
        return self._ingest_data(reader(path))
    
    def _read_csv(self, path: Path):
        with open(path, "r") as file:
            reader = csv.reader(file)
            return [row for row in reader]

    def _read_excel(self, path: Path):
        workbook = excel.load_workbook(path)
        sheet = workbook.active
        return [row for row in sheet.iter_rows(values_only=True)]
    
    def _parse_timestamp(self, timestamp: str) -> datetime:
        for timestamp_format in TIMESTAMP_FORMATS:
            try:
                return datetime.strptime(timestamp, timestamp_format)
            except ValueError:
                continue
        return None
    
    def _parse_kwh(self, kwh: str) -> float:
        try:
            return float(kwh)
        except ValueError:
            return None
    
    def _ingest_data(self, data: list[list[str]]):
        records  = {}
        warnings = []

        data[0] = [header.lower() for header in data[0]]

        timestamp_index = data[0].index(TIMESTAMP_HEADER)
        kwh_index = data[0].index(KWH_HEADER)
        
        if timestamp_index is None or kwh_index is None:
            raise ValueError(f"Timestamp or KWH header not found: {TIMESTAMP_HEADER} or {KWH_HEADER}")
        
        for row in data[1:]:
            timestamp = self._parse_timestamp(row[timestamp_index])
            if timestamp is None:
                warnings.append(f"Invalid timestamp: {row[timestamp_index]}")
                continue
            
            kwh = self._parse_kwh(row[kwh_index])
            if kwh is None or kwh < 0:
                warnings.append(f"Invalid KWH: {row[kwh_index]}")
                continue

            if timestamp in records:
                warnings.append(f"Duplicate timestamp: {timestamp}")
                continue

            records[timestamp] = kwh

        return records, warnings