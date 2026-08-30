from pathlib import Path
from datetime import datetime

import csv
import openpyxl as excel

TIMESTAMP_HEADER = "timestamp"
KWH_HEADER = "kwh"

TIMESTAMP_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")

class DataIngestion:
    def __init__(self, file_path):
        self.file_path = Path(file_path)
        if not self.file_path.is_file(): raise FileNotFoundError(f"File not found: {file_path}")

        self.reader = self._get_reader()
    
    def __call__(self):
        data = self.reader(self.file_path)
        return self._ingest_data(data)

    def _get_reader(self):
        suffix = self.file_path.suffix.lower()
        match suffix:
            case ".csv":
                return self._read_csv
            case ".xlsx":
                return self._read_excel
            case _:
                raise ValueError(f"Unsupported file type: {suffix}")
    
    def _read_csv(self, path):
        with open(path, "r") as file:
            reader = csv.reader(file)
            return list(reader)

    def _read_excel(self, path):
        workbook = excel.load_workbook(path)
        sheet = workbook.active
        return list(sheet.iter_rows(values_only=True))
    
    def _parse_timestamp(self, timestamp):
        if isinstance(timestamp, datetime):
            return timestamp
        
        for timestamp_format in TIMESTAMP_FORMATS:
            try:
                return datetime.strptime(timestamp, timestamp_format)
            except (ValueError, TypeError):
                continue
        return None
    
    def _parse_kwh(self, kwh):
        try:
            return float(kwh)
        except (ValueError, TypeError):
            return None
    
    def _ingest_data(self, data):
        records  = {}
        warnings = []

        if len(data) < 2:
            raise ValueError("No data found")

        headers = [header.lower() for header in data[0]]
        
        if TIMESTAMP_HEADER not in headers or KWH_HEADER not in headers:
            raise ValueError(f"Timestamp or KWH header not found: {TIMESTAMP_HEADER} or {KWH_HEADER}")
        
        for row in data[1:]:
            cells = dict(zip(headers, row))
            timestamp = self._parse_timestamp(cells[TIMESTAMP_HEADER])
            if timestamp is None:
                warnings.append(f"Invalid timestamp: {cells[TIMESTAMP_HEADER]}")
                continue
            
            kwh = self._parse_kwh(cells[KWH_HEADER])
            if kwh is None or kwh < 0:
                warnings.append(f"Invalid KWH: {cells[KWH_HEADER]}")
                continue
                
            if timestamp in records:
                warnings.append(f"Duplicate timestamp: {timestamp}")
                continue

            records[timestamp] = kwh
            
        return records, warnings
