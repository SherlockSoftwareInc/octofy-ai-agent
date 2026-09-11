import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.vector_store import get_vector_store


def debug_schemas():
    vector_store = get_vector_store()
    print("Querying schemas from the contract schemas collection")
    try:
        schemas = vector_store.get_all_schemas()
        print(f"Found {len(schemas)} schemas.")
        for s in schemas:
            print(f" - {s.schema_name}.{s.table_name}")
    except Exception as e:
        print(f"Error querying schemas: {e}")


if __name__ == "__main__":
    debug_schemas()
