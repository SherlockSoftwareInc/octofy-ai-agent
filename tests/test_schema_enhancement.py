"""
Quick test script for schema enhancement service
"""

from app.services.schema_enhancement_service import SchemaEnhancementService

# Sample markdown content
sample_md = """# Table: [dbo].[ActiveProductsFedarated]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** Table  
**Era:** Unknown  
**Record Count:** Unknown  
**Update Frequency:** Unknown

## Description

# **Table:** `[dbo].[ActiveProductsFedarated]`
> Stores details of products that are currently active and federated across multiple systems or sources within the organization.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ProductID` | INTEGER | Primary key, Unique identifier for the product. Reference: Products.ProductID |
| 2 | `ProductName` | NVARCHAR(40) | Name of the active federated product. |
---


## Columns

## Common Queries

(Requires manual documentation)

## Related Tables

(Requires manual documentation)

## Data Quality Notes

(Requires manual documentation)
"""

def test_markdown_parser():
    """Test the markdown parser"""
    service = SchemaEnhancementService()
    
    print("Testing markdown parser...")
    result = service._parse_markdown(sample_md)
    
    print(f"\nParsed Results:")
    print(f"  Schema: {result['schema_name']}")
    print(f"  Table: {result['table_name']}")
    print(f"  Description: '{result['description']}'")
    print(f"  Description length: {len(result['description'])} chars")
    print(f"  Number of columns: {len(result['columns'])}")
    
    if result['columns']:
        print(f"\nFirst column:")
        col = result['columns'][0]
        print(f"  Name: {col['name']}")
        print(f"  Type: {col['data_type']}")
        print(f"  Desc: {col['description']}")
    
    # Verify results
    assert result['schema_name'] == 'dbo', f"Expected 'dbo', got '{result['schema_name']}'"
    assert result['table_name'] == 'ActiveProductsFedarated', f"Expected 'ActiveProductsFedarated', got '{result['table_name']}'"
    assert len(result['columns']) == 2, f"Expected 2 columns, got {len(result['columns'])}"
    
    print("\n[SUCCESS] All tests passed!")

if __name__ == "__main__":
    test_markdown_parser()
