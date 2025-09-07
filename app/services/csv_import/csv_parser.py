"""
CSV parsing utilities with delimiter and encoding detection and basic validations.
"""

from __future__ import annotations

import csv
import os
from typing import List, Optional

import pandas as pd

from app.utils.validators import ValidationError


MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB


class CSVParser:
    """Parse CSV files with automatic delimiter and encoding detection."""

    def validate_file(self, file_path: str) -> None:
        """Validate file exists, has .csv extension, and is within size limits."""
        if not os.path.exists(file_path):
            raise ValidationError(f"CSV file not found: {file_path}")

        if not file_path.lower().endswith(".csv"):
            raise ValidationError("Only .csv files are supported")

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValidationError("CSV file is empty")
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValidationError("CSV file exceeds 50MB size limit")

    def detect_encoding(self, file_path: str) -> str:
        """Detect file encoding using a simple utf-8 fallback to latin-1."""
        # Try UTF-8 first
        try:
            with open(file_path, "rb") as f:
                sample = f.read(4096)
            sample.decode("utf-8")
            return "utf-8"
        except Exception:
            return "latin-1"

    def detect_delimiter(self, file_path: str, encoding: Optional[str] = None) -> str:
        """Detect CSV delimiter using csv.Sniffer (defaults to comma)."""
        enc = encoding or "utf-8"
        try:
            with open(file_path, "r", encoding=enc, errors="strict") as f:
                sample = f.read(4096)
                if not sample:
                    return ","
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
                    return dialect.delimiter
                except Exception:
                    return ","
        except UnicodeDecodeError:
            # If encoding was wrong, default delimiter to comma; caller should retry with different encoding
            return ","

    def parse_csv_file(self, file_path: str) -> pd.DataFrame:
        """
        Parse CSV file with automatic delimiter and encoding detection.

        Returns a DataFrame with raw values as strings where possible; date parsing is handled separately.
        """
        self.validate_file(file_path)

        encoding = self.detect_encoding(file_path)
        delimiter = self.detect_delimiter(file_path, encoding=encoding)

        try:
            df = pd.read_csv(
                file_path,
                encoding=encoding,
                sep=delimiter,
                dtype=str,  # keep raw; transform later
                engine="python",
            )
        except Exception as e:
            raise ValidationError(f"Failed to parse CSV: {e}")

        # Normalize header names by stripping whitespace
        df.rename(columns={c: c.strip() for c in df.columns}, inplace=True)
        return df

    def parse_dates(self, df: pd.DataFrame, date_columns: List[str]) -> pd.DataFrame:
        """Parse date columns with multiple format support, coercing invalid entries to NaT."""
        if not date_columns:
            return df

        for col in date_columns:
            if col not in df.columns:
                continue
            # Try pandas fast path with inference
            parsed = pd.to_datetime(df[col], errors="coerce", utc=False, infer_datetime_format=True)

            # If many NaT values, try common explicit formats
            if parsed.isna().mean() > 0.5:
                for fmt in (
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y-%m-%d",
                    "%m/%d/%Y %H:%M:%S",
                    "%m/%d/%Y %H:%M",
                    "%m/%d/%Y",
                    "%d/%m/%Y %H:%M:%S",
                    "%d/%m/%Y %H:%M",
                    "%d/%m/%Y",
                    "%Y/%m/%d %H:%M:%S",
                    "%Y/%m/%d",
                ):
                    try:
                        parsed_try = pd.to_datetime(df[col], format=fmt, errors="coerce")
                        # Use if it improves parse rate
                        if parsed_try.isna().mean() < parsed.isna().mean():
                            parsed = parsed_try
                            break
                    except Exception:
                        continue

            df[col] = parsed

        return df

