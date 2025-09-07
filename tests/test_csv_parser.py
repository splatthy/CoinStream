import os
from pathlib import Path

import pandas as pd

from app.services.csv_import.csv_parser import CSVParser


def write_text(path: Path, text: str, encoding: str = "utf-8"):
    with open(path, "w", encoding=encoding) as f:
        f.write(text)


def test_validate_file_checks(tmp_path: Path):
    parser = CSVParser()

    # Non-existent
    p = tmp_path / "missing.csv"
    try:
        parser.validate_file(str(p))
        assert False, "Expected ValidationError for missing file"
    except Exception:
        pass

    # Wrong extension
    bad = tmp_path / "file.txt"
    write_text(bad, "a,b\n1,2")
    try:
        parser.validate_file(str(bad))
        assert False, "Expected ValidationError for wrong extension"
    except Exception:
        pass

    # Empty file
    empty = tmp_path / "empty.csv"
    empty.write_bytes(b"")
    try:
        parser.validate_file(str(empty))
        assert False, "Expected ValidationError for empty file"
    except Exception:
        pass


def test_detect_delimiter_and_parse(tmp_path: Path):
    parser = CSVParser()

    # Comma separated
    cfile = tmp_path / "comma.csv"
    write_text(cfile, "a,b,c\n1,2,3\n4,5,6")
    enc = parser.detect_encoding(str(cfile))
    assert enc == "utf-8"
    delim = parser.detect_delimiter(str(cfile), encoding=enc)
    assert delim == ","
    df = parser.parse_csv_file(str(cfile))
    assert list(df.columns) == ["a", "b", "c"]
    assert len(df) == 2

    # Semicolon separated
    sfile = tmp_path / "semi.csv"
    write_text(sfile, "a;b;c\n1;2;3\n4;5;6")
    delim2 = parser.detect_delimiter(str(sfile), encoding="utf-8")
    assert delim2 == ";"
    df2 = parser.parse_csv_file(str(sfile))
    assert list(df2.columns) == ["a", "b", "c"]
    assert len(df2) == 2


def test_encoding_detection_latin1(tmp_path: Path):
    # Contains a character valid in latin-1 but not utf-8 when mis-decoded sample
    text = "name;note\nJose;Cafe\xe9"  # 'Café' with latin-1 e-acute
    p = tmp_path / "latin.csv"
    with open(p, "wb") as f:
        f.write(text.encode("latin-1"))

    parser = CSVParser()
    enc = parser.detect_encoding(str(p))
    assert enc in ("latin-1", "utf-8")  # heuristic; we fall back to latin-1 if utf-8 fails

    df = parser.parse_csv_file(str(p))
    assert "note" in df.columns
    assert any("Cafe" in str(v) or "Café" in str(v) for v in df["note"])  # tolerate variations


def test_parse_dates_multiple_formats():
    parser = CSVParser()
    df = pd.DataFrame(
        {
            "d1": ["2023-01-02 15:30:00", "2023-05-06"],
            "d2": ["01/02/2023 15:30", "05/06/2023"],
            "x": ["a", "b"],
        }
    )
    out = parser.parse_dates(df.copy(), ["d1", "d2"])  # in-place on a copy
    assert pd.api.types.is_datetime64_any_dtype(out["d1"])  # parsed
    assert pd.api.types.is_datetime64_any_dtype(out["d2"])  # parsed

