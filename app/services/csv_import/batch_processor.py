from __future__ import annotations

from typing import Callable, Any, List, Optional, Tuple

import pandas as pd


ProgressCallback = Callable[[int, int], bool]
"""
Progress callback signature: given (current_index, total_rows),
return True to continue or False to cancel.
"""


def process_dataframe(
    df: pd.DataFrame,
    worker: Callable[[pd.Series], Any],
    on_progress: Optional[ProgressCallback] = None,
    chunk_size: Optional[int] = None,
) -> Tuple[List[Any], int, int, bool]:
    """
    Process a DataFrame row-by-row, invoking a worker per row and an optional
    progress callback. Returns (results, processed_count, error_count, cancelled).

    If chunk_size is provided, iteration checkpoints occur at chunk boundaries
    to allow responsive UI updates; otherwise iterates linearly.
    """
    results: List[Any] = []
    errors = 0
    total = len(df)

    if total == 0:
        return results, 0, 0, False

    indices = range(total)

    def call_progress(i: int) -> bool:
        if on_progress is None:
            return True
        try:
            return bool(on_progress(i + 1, total))
        except Exception:
            # Do not break processing due to progress handler errors
            return True

    cancelled = False

    if chunk_size and chunk_size > 0:
        # Iterate in chunks for better UI responsiveness
        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            for i in range(start, end):
                try:
                    res = worker(df.iloc[i])
                    results.append(res)
                except Exception:
                    errors += 1
                # progress per row
                if not call_progress(i):
                    cancelled = True
                    break
            if cancelled:
                break
    else:
        for i in indices:
            try:
                res = worker(df.iloc[i])
                results.append(res)
            except Exception:
                errors += 1
            if not call_progress(i):
                cancelled = True
                break

    processed = len(results) + errors
    return results, processed, errors, cancelled

