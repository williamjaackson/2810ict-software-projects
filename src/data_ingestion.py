from pathlib import Path
import pandas as pd

TIMESTAMP_HEADER = "timestamp"
KWH_HEADER = "kwh"

MAX_FILE_BYTES = 50 * 1024 * 1024

class FileReader:
    def __init__(self, file_path):
        self.file_path = Path(file_path)
        if not self.file_path.is_file(): raise FileNotFoundError(f"File not found: {file_path}")

        size = self.file_path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError(f"File is {size / 1024 / 1024:.1f}MB, the limit is {MAX_FILE_BYTES / 1024 / 1024:.0f}MB")

    def __call__(self):
        readers = {".csv": pd.read_csv, ".xlsx": pd.read_excel, ".xls": pd.read_excel}
        suffix = self.file_path.suffix.lower()
        reader = readers.get(suffix)

        if reader is None:
            raise ValueError(f"Unsupported file type: {suffix}")

        return reader(self.file_path)

class DataIngestion:
    def __init__(self, file_path):
        self.file_reader = FileReader(file_path)
    
    def run(self):
        return self._ingest_data(self.file_reader())

    def _ingest_data(self, frame):
        if frame.empty:
            raise ValueError("No data found")

        frame = frame.rename(columns=lambda x: str(x).strip().lower())
        
        if TIMESTAMP_HEADER not in frame.columns or KWH_HEADER not in frame.columns:
            raise ValueError(f"Timestamp or KWH header not found: {TIMESTAMP_HEADER} or {KWH_HEADER}")
        
        timestamps = pd.to_datetime(frame[TIMESTAMP_HEADER], errors="coerce", format="mixed")
        values = pd.to_numeric(frame[KWH_HEADER], errors="coerce")

        bad_timestamp = timestamps.isna()
        bad_kwh = ~bad_timestamp & (values.isna() | (values < 0))

        clean = pd.DataFrame({"timestamp": timestamps, "kwh": values})[~bad_timestamp & ~bad_kwh]
        duplicated = clean["timestamp"].duplicated(keep="first")

        warnings = pd.concat([
            frame.loc[bad_timestamp, TIMESTAMP_HEADER].map(lambda x: f"Invalid timestamp: {x}"),
            frame.loc[bad_kwh, KWH_HEADER].map(lambda x: f"Invalid KWH: {x}"),
            clean.loc[duplicated, "timestamp"].map(lambda x: f"Duplicate timestamp: {x}"),
        ]).sort_index().tolist()

        clean = clean[~duplicated]

        records = {
            timestamp.to_pydatetime(): float(value)
            for timestamp, value in zip(clean["timestamp"], clean["kwh"])
        }

        return dict(sorted(records.items())), warnings

if __name__ == "__main__":
    data_ingestion = DataIngestion("data/data.csv")
    records, warnings = data_ingestion.run()

    print(f"records: {records}")
    print(f"warnings: {warnings}")
