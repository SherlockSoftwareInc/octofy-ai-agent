from app.services.admin_service import schema_rows_to_admin_status


def test_schema_rows_to_admin_status_uses_object_name():
    rows = [
        {
            "data_source_id": "src-1",
            "schema_name": "dbo",
            "object_name": "Customers",
            "object_type": "Table",
            "entity_type": "Table",
            "description": "Customer master",
        },
        {
            "data_source_id": "src-1",
            "schema_name": "dbo",
            "object_name": "Customers",
            "object_type": "Table",
            "entity_type": "Column",
            "column_name": "CustomerID",
            "description": "id",
        },
        {
            "data_source_id": "src-1",
            "schema_name": "dbo",
            "object_name": "Customers",
            "object_type": "Table",
            "entity_type": "Column",
            "column_name": "CompanyName",
            "description": "name",
        },
        {
            "data_source_id": "src-1",
            "schema_name": "dbo",
            "object_name": "Ten Most Expensive Products",
            "object_type": "Function",
            "entity_type": "Function",
            "description": "top products",
        },
    ]
    items = schema_rows_to_admin_status(rows, "src-1")
    assert len(items) == 2
    customers = next(i for i in items if i.object_name == "Customers")
    assert customers.table_name == "Customers"
    assert customers.object_type == "table"
    assert customers.column_count == 2
    assert customers.source_id == "src-1"
    fn = next(i for i in items if i.object_name == "Ten Most Expensive Products")
    assert fn.object_type == "function"
    assert fn.table_type == "function"
