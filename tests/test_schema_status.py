import sys
import os

# Add parent dir to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.admin_service import get_schema_status

if __name__ == "__main__":
    try:
        print("Getting schema status...")
        statuses = get_schema_status()
        print(f"\nFound {len(statuses)} schemas:")
        for status in statuses[:5]:  # Show first 5
            print(f"  - {status.schema_name}.{status.table_name} (indexed={status.is_indexed})")
        if len(statuses) > 5:
            print(f"  ... and {len(statuses) - 5} more")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
