import numpy as np
import pandas as pd
import pytest

from risk_engine.data_loader import load_history


def write_csv(tmp_path, body):
    path = tmp_path / "observations.csv"
    path.write_text(body, encoding="utf-8")
    return path


def test_strategy_returns_sorted_and_aligned(tmp_path):
    path = write_csv(tmp_path, "date,A,B\n2024-01-03,-0.25,0.10\n2024-01-02,0.50,0\n")
    panel = load_history(path, "simple_returns")
    assert panel.log_returns.index.equals(pd.to_datetime(["2024-01-02", "2024-01-03"]))
    np.testing.assert_allclose(panel.log_returns, np.log([[1.5, 1], [0.75, 1.1]]))
    assert panel.input_rows == 2


def test_missing_price_suppresses_both_adjacent_returns(tmp_path):
    path = write_csv(tmp_path, "date,A,B\n2024-01-01,2,10\n2024-01-02,4,11\n"
                     "2024-01-03,,12\n2024-01-04,16,13\n2024-01-05,32,26\n")
    with pytest.raises(ValueError, match="Missing A"):
        load_history(path, "prices")
    panel = load_history(path, "prices", missing="drop")
    assert list(panel.log_returns.index.day) == [2, 5]
    np.testing.assert_allclose(panel.log_returns, np.log([[2, 1.1], [2, 2]]))
    assert panel.incomplete_return_rows_removed == 2


def test_duplicate_and_missing_policies(tmp_path):
    path = write_csv(tmp_path, "date,A,B\n2024-01-03,0.4,0.2\n2024-01-02,0.1,0.1\n"
                     "2024-01-03,0.7,0.5\n2024-01-04,NA,0.1\n")
    with pytest.raises(ValueError, match="Duplicate"):
        load_history(path, "simple_returns")
    panel = load_history(path, "simple_returns", duplicates="last", missing="drop")
    np.testing.assert_allclose(panel.log_returns, np.log1p([[0.1, 0.1], [0.7, 0.5]]))
    assert (panel.duplicate_rows_removed, panel.incomplete_return_rows_removed) == (1, 1)


@pytest.mark.parametrize(("header", "row", "kind", "message"), [
    ("date,A", "2024-01-01,-1", "simple_returns", "exceed -100%"),
    ("date,A", "2024-01-01,-1.1", "simple_returns", "exceed -100%"),
    ("date,A", "2024-01-01,0", "prices", "positive"),
    ("date,A", "2024-01-01,inf", "prices", "Invalid numeric"),
    ("date,A", "2024-01-01,2%", "simple_returns", "Invalid numeric"),
    ("date,A", "2024-02-30,1", "prices", "YYYY-MM-DD"),
    ("date,A,A", "2024-01-01,1,2", "prices", "unique"),
    ("date,A", "2024-01-01,1,2", "prices", "width"),
    ("other,A", "2024-01-01,1", "prices", "requires 'date'"),
    ("date,A", "2024-01-01,0.01", "simple_returns", "two complete"),
])
def test_rejects_invalid_input(tmp_path, header, row, kind, message):
    with pytest.raises(ValueError, match=message):
        load_history(write_csv(tmp_path, f"{header}\n{row}\n"), kind, missing="drop")


def test_header_only_csv(tmp_path):
    with pytest.raises(ValueError, match="no observations"):
        load_history(write_csv(tmp_path, "date,A\n"), "prices")
