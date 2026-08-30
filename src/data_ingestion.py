from pathlib import Path
from datetime import datetime

import csv
import openpyxl as excel

TIMESTAMP_HEADER = "timestamp"
KWH_HEADER = "kwh"

TIMESTAMP_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")

class FileReader:
    def __init__(self, file_path):
        self.file_path = Path(file_path)
        if not self.file_path.is_file(): raise FileNotFoundError(f"File not found: {file_path}")

    def __call__(self):
        readers = {".csv": self._read_csv, ".xlsx": self._read_excel}
        suffix = self.file_path.suffix.lower()
        reader = readers.get(suffix)

        if reader is None:
            raise ValueError(f"Unsupported file type: {suffix}")

        return reader()

    def _read_csv(self):
        with open(self.file_path, "r") as file:
            reader = csv.reader(file)
            return list(reader)
    
    def _read_excel(self):
        workbook = excel.load_workbook(self.file_path)
        sheet = workbook.active
        return list(sheet.iter_rows(values_only=True))

class DataIngestion:
    def __init__(self, file_path):
        self.file_reader = FileReader(file_path)
    
    def run(self):
        return self._ingest_data(self.file_reader())
    
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
            timestamp = self._parse_timestamp(cells.get(TIMESTAMP_HEADER))
            if timestamp is None:
                warnings.append(f"Invalid timestamp: {cells.get(TIMESTAMP_HEADER)}")
                continue
            
            kwh = self._parse_kwh(cells.get(KWH_HEADER))
            if kwh is None or kwh < 0:
                warnings.append(f"Invalid KWH: {cells.get(KWH_HEADER)}")
                continue
                
            if timestamp in records:
                warnings.append(f"Duplicate timestamp: {timestamp}")
                continue

            records[timestamp] = kwh
            
        return records, warnings
