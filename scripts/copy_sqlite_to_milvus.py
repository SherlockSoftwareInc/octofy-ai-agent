"""Copy every SQLite contract table into Milvus and verify row counts.

Pass/fail is the `schemas` table: Milvus must have the same number of rows as SQLite.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.stores.milvus_provider import MilvusProvider
from app.services.stores.milvus_replicate import prepare_milvus_row
from app.services.stores.schema_contracts import COLLECTIONS, COLLECTION_BY_NAME
from app.services.stores.sqlite_vec_provider import SqliteVecProvider, default_sqlite_path

BATCH = 50
REQUIRED_TABLE = "schemas"


def _milvus_count(milvus: MilvusProvider, collection: str) -> int:
    utility = milvus._pymilvus["utility"]
    Collection = milvus._pymilvus["Collection"]
    if not utility.has_collection(collection):
        return -1
    col = Collection(collection)
    try:
        col.flush()
    except Exception:
        pass
    try:
        col.load()
    except Exception:
        pass
    try:
        return int(col.num_entities)
    except Exception:
        return -1


def _recreate_contract_collection(milvus: MilvusProvider, name: str) -> None:
    utility = milvus._pymilvus["utility"]
    if utility.has_collection(name):
        utility.drop_collection(name)
    milvus.ensure_schema()


def copy_table(sqlite: SqliteVecProvider, milvus: MilvusProvider, name: str) -> dict:
    spec = COLLECTION_BY_NAME[name]
    raw = sqlite.fetch_all_rows(name)
    prepared = []
    skipped = 0
    for row in raw:
        rec = prepare_milvus_row(spec, row)
        if rec is None:
            skipped += 1
            continue
        prepared.append(rec)

    _recreate_contract_collection(milvus, name)
    Collection = milvus._pymilvus["Collection"]
    utility = milvus._pymilvus["utility"]
    if not utility.has_collection(name):
        raise RuntimeError(f"Milvus collection was not created: {name}")
    col = Collection(name)
    try:
        col.load()
    except Exception as exc:
        print(f"  load {name}: {exc}", flush=True)

    errors = []
    inserted = 0
    for start in range(0, len(prepared), BATCH):
        batch = prepared[start : start + BATCH]
        try:
            result = col.upsert(batch)
            inserted += len(batch)
            print(f"  {name} batch {start}:{start + len(batch)} upsert={result}", flush=True)
        except Exception as exc:
            errors.append(f"batch {start}: {type(exc).__name__}: {exc}")
            print(f"  {name} batch {start} FAILED: {exc}", flush=True)
            break
    try:
        col.flush()
        col.load()
    except Exception as exc:
        errors.append(f"flush/load: {exc}")
    milvus_rows = _milvus_count(milvus, name)
    return {
        "table": name,
        "sqlite": len(raw),
        "prepared": len(prepared),
        "skipped": skipped,
        "inserted": inserted,
        "milvus": milvus_rows,
        "errors": errors,
        "ok": milvus_rows == len(raw) and not errors,
    }


def main() -> int:
    print(f"SQLite: {default_sqlite_path()}", flush=True)
    sqlite = SqliteVecProvider()
    milvus = MilvusProvider()
    if not getattr(milvus, "_connected", False):
        print("FAIL: Milvus is not connected")
        return 1

    populated = []
    for spec in COLLECTIONS:
        n = len(sqlite.fetch_all_rows(spec.name))
        if n:
            populated.append(spec.name)
            print(f"  sqlite {spec.name}: {n}", flush=True)
    if REQUIRED_TABLE not in populated:
        print(f"FAIL: SQLite has no rows in {REQUIRED_TABLE}")
        return 1

    print(f"\nCopying {len(populated)} populated tables to Milvus...", flush=True)
    results = []
    for name in populated:
        print(f"\n[{name}]", flush=True)
        try:
            results.append(copy_table(sqlite, milvus, name))
        except Exception as exc:
            results.append(
                {
                    "table": name,
                    "sqlite": len(sqlite.fetch_all_rows(name)),
                    "prepared": 0,
                    "skipped": 0,
                    "inserted": 0,
                    "milvus": -1,
                    "errors": [f"{type(exc).__name__}: {exc}"],
                    "ok": False,
                }
            )
            print(f"  FAILED: {exc}", flush=True)

    print("\n=== counts ===", flush=True)
    print(f"{'table':40} {'sqlite':>8} {'milvus':>8} status", flush=True)
    failed = []
    for row in results:
        status = "OK" if row["ok"] else "FAIL"
        print(f"{row['table']:40} {row['sqlite']:8} {row['milvus']:8} {status}", flush=True)
        if row["errors"]:
            for err in row["errors"]:
                print(f"    error: {err}", flush=True)
        if not row["ok"]:
            failed.append(row)

    schemas = next((r for r in results if r["table"] == REQUIRED_TABLE), None)
    if schemas is None or not schemas["ok"]:
        print(
            f"\nFAIL: {REQUIRED_TABLE} sqlite={schemas and schemas['sqlite']} "
            f"milvus={schemas and schemas['milvus']}",
            flush=True,
        )
        return 1
    print(
        f"\nPASS: {REQUIRED_TABLE} sqlite={schemas['sqlite']} milvus={schemas['milvus']}",
        flush=True,
    )
    if failed:
        print(f"Other tables failed: {[r['table'] for r in failed]}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
