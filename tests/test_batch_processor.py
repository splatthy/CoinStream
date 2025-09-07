import pandas as pd

from app.services.csv_import.batch_processor import process_dataframe


def test_progress_is_called_and_all_rows_processed():
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5]})
    calls = []

    def worker(row):
        return row["a"] * 2

    def on_progress(current, total):
        calls.append((current, total))
        return True

    results, processed, errors, cancelled = process_dataframe(
        df, worker, on_progress=on_progress
    )

    assert results == [2, 4, 6, 8, 10]
    assert processed == 5
    assert errors == 0
    assert cancelled is False
    assert calls and calls[-1][0] == 5 and calls[-1][1] == 5


def test_cancellation_via_progress_callback():
    df = pd.DataFrame({"a": list(range(10))})
    def worker(row):
        return row["a"]

    def on_progress(current, total):
        return current < 5  # cancel once current reaches 5

    results, processed, errors, cancelled = process_dataframe(
        df, worker, on_progress=on_progress
    )

    assert cancelled is True
    assert processed <= 5
    assert len(results) <= 5


def test_chunked_processing_produces_same_results():
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6]})
    def worker(row):
        return row["a"] + 1

    results1, p1, e1, c1 = process_dataframe(df, worker, chunk_size=None)
    results2, p2, e2, c2 = process_dataframe(df, worker, chunk_size=2)

    assert results1 == results2 == [2, 3, 4, 5, 6, 7]
    assert p1 == p2 == 6
    assert e1 == e2 == 0
    assert c1 == c2 is False

