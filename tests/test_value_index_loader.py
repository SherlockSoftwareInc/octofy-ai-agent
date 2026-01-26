import os
import sys
import subprocess
import time
import pytest
import pandas as pd

from app.services.vector_store import get_vector_store

CSV_PATH = r"F:\sql-agent2\value_set_products.csv"


def _read_csv_with_fallbacks(path: str) -> pd.DataFrame:
    encodings = [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin1",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
    ]
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Unable to read CSV with fallbacks. Last error: {last_err}")


@pytest.mark.integration
def test_load_value_index_from_csv_and_verify():
    # Preconditions
    if not os.path.exists(CSV_PATH):
        pytest.skip(f"CSV not found at {CSV_PATH}")

    # Ensure Milvus is reachable via vector store
    vs = get_vector_store()

    # Clear existing values
    vs.clear_values_collection()

    # Compute expected count from CSV (dedup on required cols)
    df = _read_csv_with_fallbacks(CSV_PATH)
    df.columns = df.columns.str.strip().str.lower()
    required = ['value', 'schema_name', 'table_name', 'column_name']
    for col in required:
        if col not in df.columns:
            pytest.skip(f"Required column '{col}' missing in CSV")
    df = df[required + [c for c in df.columns if c not in required]].copy()
    df['value'] = df['value'].astype(str).str.strip()
    df = df.drop_duplicates(subset=required)
    df = df[df['value'].notna() & (df['value'] != '')]
    expected_count = len(df)
    assert expected_count > 0, "Expected at least one row to ingest"

    # Run loader in replace mode
    cmd = [
        sys.executable,
        "-m",
        "scripts.load_value_index_file",
        CSV_PATH,
        "--mode",
        "replace",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"Loader failed: {proc.stdout}\n{proc.stderr}"

    # Small wait to ensure flush propagates
    time.sleep(1)

    # Verify rows ingested
    items = vs.get_all_values()
    assert isinstance(items, list), "get_all_values did not return a list"
    assert len(items) == expected_count, f"Expected {expected_count} items, got {len(items)}"

    # Spot-check first few entries have required fields
    for item in items[:5]:
        for key in ["value", "schema_name", "table_name", "column_name"]:
            assert key in item, f"Missing '{key}' in value index item"
