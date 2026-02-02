import sys
import os
ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.services.vector_store import get_vector_store

vs = get_vector_store()
items = vs.get_all_values()
print(f"Total items: {len(items)}")
if items:
    print("First 3 items:")
    for i, item in enumerate(items[:3]):
        print(f"  [{i}] value={item.get('value')}, table={item.get('table_name')}, col={item.get('column_name')}")
else:
    print("No items found in value index")
