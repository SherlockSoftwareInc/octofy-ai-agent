
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.services.execution_service import execute_python_code
import pandas as pd

code = """
print('Hello from executed code')
df = pd.DataFrame({'col1': [1, 2], 'col2': ['A', 'B']})
"""

result = execute_python_code(code)
print("Execution Result:")
print(f"Success: {result['success']}")
print(f"Output: {result['output']}")
if result['results']:
    print(f"Captured {len(result['results'])} dataframe(s)")
    print(result['results'][0]['data'])
else:
    print("No dataframes captured")
