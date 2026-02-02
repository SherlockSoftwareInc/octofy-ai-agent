
import sys
import os

# Add parent dir to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.vector_store import get_vector_store
from app.services.settings_service import load_settings
from app.core.config import settings

def debug_schemas():
    vector_config = load_settings().vector_config
    print(f"Connecting to Milvus at {vector_config.host}:{vector_config.port}")
    vector_store = get_vector_store()
    
    print(f"Querying schemas from collection: {settings.MILVUS_COLLECTION_SCHEMA}")
    try:
        schemas = vector_store.get_all_schemas()
        print(f"Found {len(schemas)} schemas.")
        for s in schemas:
            print(f" - {s.schema_name}.{s.table_name}")
    except Exception as e:
        print(f"Error querying schemas: {e}")

if __name__ == "__main__":
    debug_schemas()
