import sys
import os
import re

# Add parent dir to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.vector_store import get_vector_store

if __name__ == "__main__":
    try:
        print("Checking for COLLATE in column data types...")
        vector_store = get_vector_store()
        schemas = vector_store.get_all_schemas()
        
        collate_found = False
        sample_types = []
        
        for schema in schemas:
            if schema.description:
                # Look for COLLATE in the description (which contains the markdown table)
                if 'COLLATE' in schema.description:
                    collate_found = True
                    print(f"\n❌ FOUND COLLATE in {schema.schema_name}.{schema.table_name}")
                    # Extract some lines around COLLATE
                    lines = schema.description.split('\n')
                    for i, line in enumerate(lines):
                        if 'COLLATE' in line:
                            print(f"  Line {i}: {line[:100]}")
                
                # Extract some sample data types
                if schema.table_name == "Customers":
                    # Find data type column entries
                    matches = re.findall(r'\| \d+ \| `(\w+)` \| ([^|]+) \|', schema.description)
                    if matches:
                        sample_types.extend([(schema.table_name, col, dtype.strip()) for col, dtype in matches[:5]])
        
        if not collate_found:
            print("\n✅ SUCCESS! No COLLATE clauses found in any column data types!")
        
        if sample_types:
            print("\nSample column data types:")
            for table, col, dtype in sample_types:
                print(f"  {table}.{col}: {dtype}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
