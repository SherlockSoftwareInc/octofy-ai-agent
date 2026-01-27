# DEBUG: Auto-generated test script with connection string
# This file was auto-generated for debugging purposes

DB_CONNECTION_STRING = '''mssql+pyodbc://sql_agent:AppleWood7500@host.docker.internal/northwind?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes&Encrypt=yes'''

"""
Approach:
1. Connect to the database using the provided connection string.
2. Retrieve order details (Order Details table) which contain product sales data.
3. Calculate total quantity sold per product by summing the Quantity column.
4. Join with Products table to get product names.
5. Sort by total quantity sold in descending order to get top selling products.
6. Return the result as a DataFrame with ProductID, ProductName, and TotalQuantitySold.
"""

import pandas as pd
import sqlalchemy as sa

# DB_CONNECTION_STRING = ("mssql+pyodbc://@your_server_name/your_database_name?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes")
engine = sa.create_engine(DB_CONNECTION_STRING)

with engine.connect() as conn:
    # Load order details and products
    order_details_df = pd.read_sql("SELECT ProductID, Quantity FROM [dbo].[Order Details]", conn)
    products_df = pd.read_sql("SELECT ProductID, ProductName FROM [dbo].[Products]", conn)

# Calculate total quantity sold per product
product_sales = (
    order_details_df.groupby('ProductID', as_index=False)['Quantity']
    .sum()
    .rename(columns={'Quantity': 'TotalQuantitySold'})
)

# Merge with products to get product names
merged_df = pd.merge(
    product_sales,
    products_df,
    on='ProductID',
    how='left'
)

# Sort by total quantity sold descending
final_result_df = merged_df.sort_values('TotalQuantitySold', ascending=False).reset_index(drop=True)

# Dispose engine
engine.dispose()
