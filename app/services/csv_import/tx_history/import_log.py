from __future__ import annotations

import json
import os
import uuid
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class ImportLogEntry:
    import_id: str
    timestamp: str  # ISO
    exchange: str
    account_label: Optional[str]
    file_name: str
    file_size: int
    file_hash: str
    counts: Dict[str, Any]
    risk_config_snapshot: Optional[Dict[str, Any]]
    max_fill_time: Optional[str]  # ISO of latest fill time processed


def hash_file(path: str, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class ImportLogStore:
    """JSONL-backed audit log under data/import_logs.jsonl"""

    def __init__(self, data_path: str) -> None:
        self.data_path = Path(data_path)
        self.log_path = self.data_path / 'import_logs.jsonl'
        self.data_path.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            # Ensure file exists
            self.log_path.touch()

    def append(self, entry: ImportLogEntry) -> None:
        line = json.dumps(asdict(entry), default=str)
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(line + "\n")

    def get_last_import_time(self, exchange: str, account_label: Optional[str] = None) -> Optional[datetime]:
        last: Optional[datetime] = None
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if obj.get('exchange') != exchange:
                        continue
                    if (obj.get('account_label') or None) != (account_label or None):
                        continue
                    mt = obj.get('max_fill_time')
                    if not mt:
                        continue
                    try:
                        dt = datetime.fromisoformat(mt)
                    except Exception:
                        continue
                    if last is None or dt > last:
                        last = dt
        except FileNotFoundError:
            return None
        return last

    @staticmethod
    def new_entry(
        exchange: str,
        account_label: Optional[str],
        file_path: str,
        counts: Dict[str, Any],
        risk_config_snapshot: Optional[Dict[str, Any]],
        max_fill_time: Optional[datetime],
    ) -> ImportLogEntry:
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        file_hash = hash_file(file_path) if os.path.exists(file_path) else ""
        return ImportLogEntry(
            import_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat(),
            exchange=exchange,
            account_label=account_label,
            file_name=file_name,
            file_size=file_size,
            file_hash=file_hash,
            counts=counts,
            risk_config_snapshot=risk_config_snapshot,
            max_fill_time=max_fill_time.isoformat() if max_fill_time else None,
        )

