"""Built-in skills folder layout + import/rebuild (reject vector-index.db)."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.services.stores.embeddings import embed_text
from app.services.stores.schema_contracts import column_embedding_text, parent_embedding_text


FORBIDDEN_VECTOR_DB = "vector-index.db"
_SOURCE_ID_RE = re.compile(r"(?im)^source_id:\s*['\"]?([^\s'\"#]+)['\"]?")


def default_data_sources_root() -> Path:
    return Path(__file__).resolve().parents[3] / "skills" / "data-sources"


def resolve_data_source_folder(source_id: str, skills_root: Optional[Path] = None) -> Path:
    """Locate skills/data-sources/{name} by source_id in _data-source.md."""
    root = Path(skills_root) if skills_root else default_data_sources_root()
    wanted = (source_id or "").strip().lower()
    if not wanted:
        raise FileNotFoundError("source_id is required to resolve a skills folder")
    if not root.exists():
        raise FileNotFoundError(f"skills data-sources folder not found: {root}")
    for md in sorted(root.rglob("_data-source.md")):
        text = md.read_text(encoding="utf-8", errors="ignore")
        match = _SOURCE_ID_RE.search(text)
        if match and match.group(1).strip().lower() == wanted:
            return md.parent
    direct = root / source_id
    if direct.is_dir() and ((direct / "_data-source.md").exists() or (direct / "schemas").exists()):
        return direct
    raise FileNotFoundError(f"No skills folder found for source_id={source_id}")


@dataclass
class ImportReport:
    source_id: str
    objects: int = 0
    groups: int = 0
    qas: int = 0
    tools: int = 0
    rejected_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class SkillsFolderLayout:
    def __init__(self, root: Path):
        self.root = Path(root)

    def data_source_dir(self, folder_name: str) -> Path:
        return self.root / "data-sources" / folder_name


def import_skills_folder(src: Path, dest_root: Path, source_id: str, provider) -> ImportReport:
    src = Path(src)
    dest_root = Path(dest_root)
    report = ImportReport(source_id=source_id)
    if not src.exists():
        report.errors.append(f"source folder not found: {src}")
        return report
    forbidden = list(src.rglob(FORBIDDEN_VECTOR_DB))
    if forbidden:
        report.rejected_files = [str(p) for p in forbidden]
        report.errors.append("uploads containing vector-index.db are rejected")
        return report
    dest = dest_root / "data-sources" / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(FORBIDDEN_VECTOR_DB))
    report.tools = len(list((dest / "tools").glob("*.md"))) if (dest / "tools").exists() else 0
    rebuild_vectors_from_folder(dest, source_id, provider, report)
    return report


_REBUILD_COLLECTIONS = (
    "schemas",
    "data_group_metadata",
    "data_group_vectors_cache",
    "data_group_vectors_map",
    "data_group_vectors_vec0",
    "vec_data_group_queries",
    "vec_data_group_query_vectors_cache",
)


def _wipe_source_collections(provider, source_id: str, report: ImportReport) -> None:
    for name in _REBUILD_COLLECTIONS:
        try:
            provider.delete_source(name, source_id)
        except Exception as exc:
            report.errors.append(f"wipe {name}: {exc}")


def rebuild_vectors_from_folder(folder: Path, source_id: str, provider, report: Optional[ImportReport] = None) -> ImportReport:
    report = report or ImportReport(source_id=source_id)
    folder = Path(folder)
    _wipe_source_collections(provider, source_id, report)
    schemas_dir = folder / "schemas"
    rows = []
    if schemas_dir.exists():
        for md in schemas_dir.rglob("*.md"):
            text = md.read_text(encoding="utf-8", errors="ignore")
            schema_name, object_name, object_type = _parse_object_file(md)
            key = f"[{source_id}].[{schema_name}].[{object_name}]"
            desc = text[:4000]
            rows.append({
                "data_source_id": source_id,
                "key": key,
                "schema_name": schema_name,
                "object_name": object_name,
                "object_type": object_type,
                "entity_type": "Table" if object_type == "Table" else object_type,
                "column_name": "",
                "description": parent_embedding_text(object_type, object_name, desc),
                "vector": embed_text(parent_embedding_text(object_type, object_name, desc), provider, source_id),
            })
            for col_name, col_type, col_desc in _parse_columns(text):
                col_key = f"{key}.[{col_name}]"
                payload = column_embedding_text(object_name, col_name, col_type, col_desc)
                rows.append({
                    "data_source_id": source_id,
                    "key": col_key,
                    "schema_name": schema_name,
                    "object_name": object_name,
                    "object_type": object_type,
                    "entity_type": "Column",
                    "column_name": col_name,
                    "description": payload,
                    "vector": embed_text(payload, provider, source_id),
                })
            report.objects += 1
            if report.objects % 5 == 0:
                print(f"  embedded {report.objects} objects...", flush=True)
    if rows:
        provider.upsert("schemas", rows)

    index_path = folder / "data-groups" / ".data-group-index.json"
    if index_path.exists():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception as exc:
            report.errors.append(str(exc))
            data = []
        groups = data if isinstance(data, list) else data.get("groups") or data.get("data_groups") or []
        from app.services.stores.data_group_store import DataGroupStore
        from app.services.stores.precomputed_store import PrecomputedQueryStore

        dg = DataGroupStore(provider, source_id)
        pq = PrecomputedQueryStore(provider, source_id)
        for group in groups:
            name = group.get("name") or group.get("group_name")
            try:
                dg.upsert(
                    group_name=name,
                    description=group.get("description") or "",
                    keywords=group.get("keywords") or [],
                    members=group.get("members") or [],
                )
                report.groups += 1
            except Exception as exc:
                report.errors.append(f"group {name}: {exc}")
                continue
            qas = (
                group.get("qas")
                or group.get("precomputed")
                or group.get("precomputed_queries")
                or []
            )
            for qa in qas:
                try:
                    pq.upsert(
                        question=qa.get("question") or "",
                        sql_query=qa.get("sql_query") or qa.get("sql") or "",
                        group_name=name,
                        smq_query=qa.get("smq_query") or "",
                        status=qa.get("status") or "Approved",
                        query_id=qa.get("id") or qa.get("query_id"),
                    )
                    report.qas += 1
                except Exception as exc:
                    report.errors.append(f"qa {name}: {exc}")
    return report


def _parse_object_file(path: Path) -> tuple:
    name = path.stem
    if ".fn." in name:
        schema, _, obj = name.partition(".fn.")
        return schema, obj, "Function"
    if "." in name:
        schema, obj = name.split(".", 1)
        return schema, obj, "Table"
    parent = path.parent.name
    return parent, name, "Table"


def _parse_columns(markdown: str):
    cols = []
    for line in markdown.splitlines():
        if line.strip().startswith("|") and "---" not in line:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 2 and parts[0].lower() not in {"column", "name", "column name"}:
                cols.append((parts[0], parts[1] if len(parts) > 1 else "", parts[2] if len(parts) > 2 else ""))
    return cols
