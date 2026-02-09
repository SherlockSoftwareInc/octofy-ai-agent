import os
import re
import sys

# Add parent dir to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import clear_engine_cache
from app.services.ingest_service import create_milvus_collections, ingest_metadata
from app.services.skills_service import SkillsService


def _resolve_source_id(data_source) -> str:
    if data_source and data_source.source_id:
        return data_source.source_id
    if data_source and data_source.name:
        slug = re.sub(r'[^a-zA-Z0-9]', '_', data_source.name.lower()).strip('_')
        if slug:
            return f"skill_{slug}"
    return "legacy"


def main() -> None:
    skills_service = SkillsService()
    sources = skills_service.load_data_sources_index()
    if not sources:
        primary = skills_service.load_primary_data_source()
        if primary:
            sources = [primary]

    if not sources:
        print("No skills data sources found. Nothing to rebuild.")
        return

    print(f"Rebuilding Milvus for {len(sources)} data source(s)...")
    create_milvus_collections()

    for source in sources:
        source_id = _resolve_source_id(source)
        print(f"\n=== Ingesting source: {source.name} ({source_id}) ===")
        try:
            ingest_metadata(source_id=source_id)
        except Exception as exc:
            print(f"Error ingesting {source.name} ({source_id}): {exc}")
        finally:
            clear_engine_cache(source_id)

    print("Milvus rebuild complete.")


if __name__ == "__main__":
    main()
