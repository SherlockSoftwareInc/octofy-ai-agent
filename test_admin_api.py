import sys
import os
ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.services.admin_service import get_all_values

vals = get_all_values()
print(f"get_all_values returned {len(vals)} items")
if vals:
    print("First 2 items:")
    for i, v in enumerate(vals[:2]):
        print(f"  {i}: {v}")
