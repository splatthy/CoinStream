from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from app.models.trade import Trade
from app.utils.serialization import DataSerializer


class ParquetTradeStore:
    """
    Parquet-backed trade storage. For MVP, we store JSON-serialized fields as strings
    (consistent with existing JSON format) to minimize deserialization differences.
    """

    def __init__(self, data_path: str):
        self.base_path = Path(data_path)
        self.dataset_dir = self.base_path / "trades_parquet"
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

    def load_trades(self) -> List[Trade]:
        if not self.dataset_dir.exists() or not any(self.dataset_dir.glob("**/*.parquet")):
            return []

        dataset = ds.dataset(str(self.dataset_dir), format="parquet")
        table = dataset.to_table()
        df = table.to_pandas()

        # Drop partition/helper columns if present
        for col in ["entry_year", "entry_month"]:
            if col in df.columns:
                df = df.drop(columns=[col])

        records = df.to_dict(orient="records")
        trades = [DataSerializer.deserialize_trade(rec) for rec in records]
        return trades

    def save_trades(self, trades: List[Trade]) -> None:
        # Serialize trades to dicts (all fields as strings where appropriate)
        records = [DataSerializer.serialize_trade(t) for t in trades]
        if not records:
            # Write an empty dataset by clearing directory
            if self.dataset_dir.exists():
                shutil.rmtree(self.dataset_dir)
            self.dataset_dir.mkdir(parents=True, exist_ok=True)
            return

        # Build DataFrame and add partition columns derived from entry_time
        df = pd.DataFrame.from_records(records)
        # entry_time is an ISO string, derive year/month for partitioning
        df["entry_year"] = df["entry_time"].str.slice(0, 4)
        df["entry_month"] = df["entry_time"].str.slice(5, 7)

        # Overwrite dataset: clear existing directory, then write
        if self.dataset_dir.exists():
            shutil.rmtree(self.dataset_dir)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

        table = pa.Table.from_pandas(df, preserve_index=False)
        ds.write_dataset(
            data=table,
            base_dir=str(self.dataset_dir),
            format="parquet",
            partitioning=["entry_year", "entry_month"],
            existing_data_behavior="overwrite_or_ignore",
        )

