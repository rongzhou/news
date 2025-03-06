from datetime import datetime
import logging
import pandas as pd

class DataSaver:
    def __init__(self, base_filename: str = "articles", batch_size: int = 100, format: str = "parquet"):
        self.base_filename = base_filename
        self.batch_size = batch_size
        self.format = format.lower()
        self.records = []
        self.file_counter = 0
        self.logger = logging.getLogger('DataSaver')

    def _generate_filename(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = "parquet" if self.format == "parquet" else "csv"
        return f"{self.base_filename}_{timestamp}_{self.file_counter}.{extension}"

    def add_record(self, record: dict) -> None:
        self.records.append(record)
        if len(self.records) >= self.batch_size:
            self.save()
            self.clear_records()

    def save(self) -> None:
        if not self.records:
            print("No data to save")
            return
        filename = self._generate_filename()
        try:
            df = pd.DataFrame(self.records)
            if self.format == "parquet":
                df.to_parquet(filename, engine='pyarrow', index=False)
            elif self.format == "csv":
                df.to_csv(filename, index=False, encoding='utf-8-sig')
            else:
                raise ValueError(f"Unsupported format: {self.format}")
            self.logger.info(f"Saved {len(self.records)} records to {filename}")
            self.file_counter += 1
        except Exception as e:
            self.logger.error(f"Failed to save to {self.format}: {str(e)}")

    def save_remaining(self) -> None:
        if self.records:
            self.save()

    def clear_records(self) -> None:
        self.records.clear()

    def get_record_count(self) -> int:
        return len(self.records)