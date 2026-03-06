"""
Tests for the Schema Sufficiency Pre-Flight Check feature.

This feature validates that retrieved schemas contain all columns needed 
to answer the user's query before generating SQL/Python code.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from typing import List

from app.models.schemas import (
    TableSchema, 
    ColumnInfo, 
    DiscoveryContext,
    DiscoveryResponse,
    RequiredDataPoint,
    SchemaSufficiencyResult
)


class TestSchemaSufficiencyModels:
    """Test the Pydantic models for schema sufficiency"""
    
    def test_required_data_point_creation(self):
        """Test RequiredDataPoint model creation"""
        point = RequiredDataPoint(
            name="customer name",
            column_mapping="[dbo].[Customers].[CustomerName]",
            found=True,
            reasoning="Needed to filter by customer"
        )
        assert point.name == "customer name"
        assert point.found is True
        assert point.column_mapping == "[dbo].[Customers].[CustomerName]"
    
    def test_required_data_point_missing(self):
        """Test RequiredDataPoint when column is not found"""
        point = RequiredDataPoint(
            name="sales tax",
            column_mapping=None,
            found=False,
            reasoning="User asked for tax breakdown but no tax column exists"
        )
        assert point.found is False
        assert point.column_mapping is None
    
    def test_schema_sufficiency_result_sufficient(self):
        """Test SchemaSufficiencyResult when schema is sufficient"""
        result = SchemaSufficiencyResult(
            status="sufficient",
            required_data_points=[
                RequiredDataPoint(name="order total", column_mapping="[dbo].[Orders].[Total]", found=True, reasoning="test")
            ],
            missing_data_points=[],
            search_suggestions=[],
            analysis="All required columns present"
        )
        assert result.status == "sufficient"
        assert len(result.missing_data_points) == 0
    
    def test_schema_sufficiency_result_insufficient(self):
        """Test SchemaSufficiencyResult when schema is insufficient"""
        result = SchemaSufficiencyResult(
            status="insufficient_data",
            required_data_points=[],
            missing_data_points=[
                RequiredDataPoint(name="tax amount", column_mapping=None, found=False, reasoning="No tax column")
            ],
            search_suggestions=["tax", "SalesTax"],
            analysis="Tax data not available"
        )
        assert result.status == "insufficient_data"
        assert len(result.missing_data_points) == 1
        assert "tax" in result.search_suggestions


class TestExpandContextForMissingData:
    """Test the auto-expansion helper function"""
    
    @pytest.fixture
    def initial_context(self) -> DiscoveryContext:
        """Initial context with one table"""
        return DiscoveryContext(
            relevant_tables=[
                TableSchema(
                    schema_name="dbo",
                    table_name="Orders",
                    columns=[ColumnInfo(name="OrderID", data_type="int")],
                    description="Orders table"
                )
            ],
            similar_queries=[]
        )
    
    @patch("app.services.generation_service.perform_discovery")
    def test_adds_new_tables_from_suggestions(self, mock_discovery, initial_context):
        """Should add new tables found from search suggestions"""
        from app.services.generation_service import expand_context_for_missing_data
        
        # Mock discovery to return a new table
        new_table = TableSchema(
            schema_name="dbo",
            table_name="OrderTax",
            columns=[ColumnInfo(name="TaxAmount", data_type="decimal")],
            description="Order tax information"
        )
        mock_discovery.return_value = DiscoveryResponse(
            query="tax",
            reasoning="Found tax table",
            context=DiscoveryContext(relevant_tables=[new_table], similar_queries=[])
        )
        
        tables_added, updated_context = expand_context_for_missing_data(
            initial_context,
            search_suggestions=["tax", "SalesTax"],
            max_suggestions=2
        )
        
        assert len(tables_added) > 0
        assert "dbo.OrderTax" in tables_added
        assert any(t.table_name == "OrderTax" for t in updated_context.relevant_tables)
    
    @patch("app.services.generation_service.perform_discovery")
    def test_does_not_add_duplicate_tables(self, mock_discovery, initial_context):
        """Should not add tables that already exist in context"""
        from app.services.generation_service import expand_context_for_missing_data
        
        # Mock discovery to return the same table that's already in context
        existing_table = TableSchema(
            schema_name="dbo",
            table_name="Orders",
            columns=[ColumnInfo(name="OrderID", data_type="int")],
            description="Orders table"
        )
        mock_discovery.return_value = DiscoveryResponse(
            query="orders",
            reasoning="Found orders table",
            context=DiscoveryContext(relevant_tables=[existing_table], similar_queries=[])
        )
        
        tables_added, updated_context = expand_context_for_missing_data(
            initial_context,
            search_suggestions=["orders"],
            max_suggestions=1
        )
        
        assert len(tables_added) == 0
        assert len(updated_context.relevant_tables) == 1  # Still just the original
    
    @patch("app.services.generation_service.perform_discovery")
    def test_handles_discovery_errors_gracefully(self, mock_discovery, initial_context):
        """Should continue processing even if discovery fails for some suggestions"""
        from app.services.generation_service import expand_context_for_missing_data
        
        # Mock discovery to raise an exception
        mock_discovery.side_effect = Exception("Discovery service unavailable")
        
        # Should not raise, should return empty additions
        tables_added, updated_context = expand_context_for_missing_data(
            initial_context,
            search_suggestions=["tax"],
            max_suggestions=1
        )
        
        assert len(tables_added) == 0
        assert len(updated_context.relevant_tables) == 1  # Original unchanged


class TestLLMServiceSchemaSufficiency:
    """Test the LLM service check_schema_sufficiency method"""
    
    @pytest.fixture
    def sample_schemas(self) -> List[TableSchema]:
        """Sample schemas for testing"""
        return [
            TableSchema(
                schema_name="dbo",
                table_name="Orders",
                columns=[
                    ColumnInfo(name="OrderID", data_type="int"),
                    ColumnInfo(name="CustomerID", data_type="int"),
                    ColumnInfo(name="OrderTotal", data_type="decimal"),
                    ColumnInfo(name="OrderDate", data_type="datetime"),
                ]
            ),
            TableSchema(
                schema_name="dbo",
                table_name="Customers",
                columns=[
                    ColumnInfo(name="CustomerID", data_type="int"),
                    ColumnInfo(name="CustomerName", data_type="nvarchar"),
                    ColumnInfo(name="Country", data_type="nvarchar"),
                ]
            )
        ]
    
    def test_mock_mode_returns_sufficient(self, sample_schemas):
        """When client is None (mock mode), should return sufficient"""
        from app.services.llm_service import OpenAICompatibleLLMService
        
        with patch.object(OpenAICompatibleLLMService, '__init__', lambda self: None):
            llm = OpenAICompatibleLLMService()
            llm.client = None  # Mock mode
            llm.model = "gpt-4o"
            
            result = llm.check_schema_sufficiency(
                user_query="Any query",
                schemas=sample_schemas,
                code_type="sql"
            )
        
        assert result["status"] == "sufficient"
        assert "Mock validation" in result["analysis"]
    
    @patch("app.services.llm_service.OpenAI")
    def test_sufficient_schema_returns_success(self, mock_openai_class, sample_schemas):
        """When all required columns exist, status should be 'sufficient'"""
        from app.services.llm_service import OpenAICompatibleLLMService
        
        # Setup mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "status": "sufficient",
            "required_data_points": [
                {"name": "order total", "column_mapping": "[dbo].[Orders].[OrderTotal]", "found": True, "reasoning": "User asked for totals"},
                {"name": "customer name", "column_mapping": "[dbo].[Customers].[CustomerName]", "found": True, "reasoning": "User asked for customer"}
            ],
            "missing_data_points": [],
            "search_suggestions": [],
            "analysis": "All required columns are present"
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch.object(OpenAICompatibleLLMService, '__init__', lambda self: None):
            llm = OpenAICompatibleLLMService()
            llm.client = mock_client
            llm.model = "gpt-4o"
            
            result = llm.check_schema_sufficiency(
                user_query="Show me total sales by customer name",
                schemas=sample_schemas,
                code_type="sql"
            )
        
        assert result["status"] == "sufficient"
        assert len(result["missing_data_points"]) == 0
    
    @patch("app.services.llm_service.OpenAI")
    def test_insufficient_schema_returns_missing_points(self, mock_openai_class, sample_schemas):
        """When required columns are missing, status should be 'insufficient_data'"""
        from app.services.llm_service import OpenAICompatibleLLMService
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "status": "insufficient_data",
            "required_data_points": [
                {"name": "order total", "column_mapping": "[dbo].[Orders].[OrderTotal]", "found": True, "reasoning": "User asked for totals"},
                {"name": "sales tax", "column_mapping": None, "found": False, "reasoning": "User asked for tax breakdown"}
            ],
            "missing_data_points": [
                {"name": "sales tax", "column_mapping": None, "found": False, "reasoning": "No tax column exists in available schemas"}
            ],
            "search_suggestions": ["tax", "SalesTax", "TaxAmount", "OrderTax"],
            "analysis": "The schemas do not contain tax information. User asked for tax breakdown but no tax-related columns found."
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch.object(OpenAICompatibleLLMService, '__init__', lambda self: None):
            llm = OpenAICompatibleLLMService()
            llm.client = mock_client
            llm.model = "gpt-4o"
            
            result = llm.check_schema_sufficiency(
                user_query="Show me sales with tax breakdown by customer",
                schemas=sample_schemas,
                code_type="sql"
            )
        
        assert result["status"] == "insufficient_data"
        assert len(result["missing_data_points"]) > 0
        assert any("tax" in s.lower() for s in result["search_suggestions"])
    
    @patch("app.services.llm_service.OpenAI")
    def test_json_parse_error_returns_sufficient(self, mock_openai_class, sample_schemas):
        """On JSON parse error, should return sufficient to avoid blocking"""
        from app.services.llm_service import OpenAICompatibleLLMService
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Invalid JSON response"
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch.object(OpenAICompatibleLLMService, '__init__', lambda self: None):
            llm = OpenAICompatibleLLMService()
            llm.client = mock_client
            llm.model = "gpt-4o"
            
            result = llm.check_schema_sufficiency(
                user_query="Any query",
                schemas=sample_schemas,
                code_type="sql"
            )
        
        # Should return sufficient on error to avoid blocking
        assert result["status"] == "sufficient"
        assert "parse error" in result["analysis"].lower()
    
    @pytest.fixture
    def product_order_schemas(self) -> List[TableSchema]:
        """Product and order schemas for derived value testing"""
        return [
            TableSchema(
                schema_name="dbo",
                table_name="Products",
                columns=[
                    ColumnInfo(name="ProductID", data_type="int"),
                    ColumnInfo(name="ProductName", data_type="nvarchar"),
                    ColumnInfo(name="UnitPrice", data_type="decimal"),
                ]
            ),
            TableSchema(
                schema_name="dbo",
                table_name="OrderDetails",
                columns=[
                    ColumnInfo(name="OrderID", data_type="int"),
                    ColumnInfo(name="ProductID", data_type="int"),
                    ColumnInfo(name="Quantity", data_type="int"),
                    ColumnInfo(name="UnitPrice", data_type="decimal"),
                ]
            )
        ]
    
    @patch("app.services.llm_service.OpenAI")
    def test_derivable_values_are_sufficient(self, mock_openai_class, product_order_schemas):
        """
        When values can be DERIVED from existing columns (e.g., SUM(quantity * price) 
        for sales amount), the schema should be marked as 'sufficient'.
        
        This tests the key fix: "Find top selling products" should NOT fail just 
        because there's no explicit 'sales_amount' column.
        """
        from app.services.llm_service import OpenAICompatibleLLMService
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Simulate the LLM correctly recognizing derivable values
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "status": "sufficient",
            "required_data_points": [
                {
                    "name": "product identification",
                    "column_mapping": "[dbo].[Products].[ProductName]",
                    "found": True,
                    "reasoning": "Product name available for display"
                },
                {
                    "name": "sales amount/volume",
                    "column_mapping": "DERIVED: SUM(Quantity * UnitPrice)",
                    "found": True,
                    "reasoning": "Can be calculated from Quantity and UnitPrice columns in OrderDetails"
                },
                {
                    "name": "ranking (top N)",
                    "column_mapping": "DERIVED: ORDER BY ... DESC with TOP N",
                    "found": True,
                    "reasoning": "Standard SQL ranking capability"
                }
            ],
            "missing_data_points": [],
            "search_suggestions": [],
            "analysis": "All required data is available - either directly or derivable through SQL calculations"
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch.object(OpenAICompatibleLLMService, '__init__', lambda self: None):
            llm = OpenAICompatibleLLMService()
            llm.client = mock_client
            llm.model = "gpt-4o"
            
            result = llm.check_schema_sufficiency(
                user_query="Find top selling products",
                schemas=product_order_schemas,
                code_type="sql"
            )
        
        # Key assertion: derivable values should result in 'sufficient' status
        assert result["status"] == "sufficient"
        assert len(result["missing_data_points"]) == 0
        
        # Verify that derived mappings are recognized
        derived_points = [p for p in result["required_data_points"] if "DERIVED" in str(p.get("column_mapping", ""))]
        assert len(derived_points) >= 1, "Should have at least one derived data point"
    
    @patch("app.services.llm_service.OpenAI")
    def test_python_code_type_allows_pandas_derivations(self, mock_openai_class, product_order_schemas):
        """
        When code_type is 'python', even more derivations should be allowed.
        Python/pandas can compute virtually anything from raw columns.
        
        This tests that: "Find top selling products" with Python should be sufficient
        because pandas can do df.groupby().agg(), df.nlargest(), etc.
        """
        from app.services.llm_service import OpenAICompatibleLLMService
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Simulate the LLM correctly recognizing Python/pandas capabilities
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "status": "sufficient",
            "required_data_points": [
                {
                    "name": "product identification",
                    "column_mapping": "[dbo].[Products].[ProductName]",
                    "found": True,
                    "reasoning": "Product name available for display"
                },
                {
                    "name": "sales volume calculation",
                    "column_mapping": "DERIVED: df.groupby('ProductID')['Quantity'].sum()",
                    "found": True,
                    "reasoning": "Can compute total sales using pandas groupby and aggregation"
                },
                {
                    "name": "ranking top products",
                    "column_mapping": "DERIVED: df.nlargest(n, 'total_sales')",
                    "found": True,
                    "reasoning": "Python pandas nlargest() provides ranking capability"
                }
            ],
            "missing_data_points": [],
            "search_suggestions": [],
            "analysis": "All required data is available - Python/pandas can compute sales metrics from Quantity and UnitPrice columns"
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch.object(OpenAICompatibleLLMService, '__init__', lambda self: None):
            llm = OpenAICompatibleLLMService()
            llm.client = mock_client
            llm.model = "gpt-4o"
            
            result = llm.check_schema_sufficiency(
                user_query="Find top selling products",
                schemas=product_order_schemas,
                code_type="python"  # KEY: Using Python code type
            )
        
        # Key assertion: Python code type should also result in 'sufficient'
        assert result["status"] == "sufficient"
        assert len(result["missing_data_points"]) == 0
        
        # Verify pandas-style derivations are recognized
        derived_points = [p for p in result["required_data_points"] if "DERIVED" in str(p.get("column_mapping", ""))]
        assert len(derived_points) >= 1, "Should have pandas-style derived data points"
    
    @pytest.fixture
    def schemas_with_description_only(self) -> List[TableSchema]:
        """
        Schemas where columns array is empty but description contains column info.
        This simulates what get_all_schemas() returns from Milvus.
        """
        return [
            TableSchema(
                schema_name="dbo",
                table_name="Products",
                columns=[],  # Empty columns array
                description="""## [dbo].[Products]
**Table Description:** Product catalog

### Columns
| Column | Type | Description |
|--------|------|-------------|
| ProductID | int | Primary key |
| ProductName | nvarchar(100) | Name of the product |
| UnitPrice | decimal(10,2) | Price per unit |
"""
            ),
            TableSchema(
                schema_name="dbo",
                table_name="OrderDetails",
                columns=[],  # Empty columns array
                description="""## [dbo].[OrderDetails]
**Table Description:** Order line items

### Columns
| Column | Type | Description |
|--------|------|-------------|
| OrderID | int | Foreign key to Orders |
| ProductID | int | Foreign key to Products |
| Quantity | int | Number of units ordered |
| UnitPrice | decimal(10,2) | Price at time of order |
"""
            )
        ]
    
    @patch("app.services.llm_service.OpenAI")
    def test_uses_description_when_columns_empty(self, mock_openai_class, schemas_with_description_only):
        """
        When schemas have empty columns array but description contains column info,
        the sufficiency check should use the description to find column information.
        
        This is the key fix for Python code generation failing when get_all_schemas()
        returns schemas without populated columns arrays.
        """
        from app.services.llm_service import OpenAICompatibleLLMService
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Simulate the LLM correctly parsing columns from the markdown description
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "status": "sufficient",
            "required_data_points": [
                {
                    "name": "product identification",
                    "column_mapping": "[dbo].[Products].[ProductName]",
                    "found": True,
                    "reasoning": "ProductName column found in description"
                },
                {
                    "name": "sales calculation",
                    "column_mapping": "DERIVED: SUM(Quantity * UnitPrice)",
                    "found": True,
                    "reasoning": "Quantity and UnitPrice columns found in OrderDetails description"
                }
            ],
            "missing_data_points": [],
            "search_suggestions": [],
            "analysis": "Column information extracted from table descriptions - all required data available"
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch.object(OpenAICompatibleLLMService, '__init__', lambda self: None):
            llm = OpenAICompatibleLLMService()
            llm.client = mock_client
            llm.model = "gpt-4o"
            
            result = llm.check_schema_sufficiency(
                user_query="Find top selling products",
                schemas=schemas_with_description_only,
                code_type="python"
            )
        
        # Key assertion: should work even with empty columns array
        assert result["status"] == "sufficient"
        assert len(result["missing_data_points"]) == 0


from app.models.schemas import ValidationDetail, JoinPathValidationResult


class TestJoinPathValidationModels:
    """Test the new join-path validation Pydantic models"""
    
    def test_validation_detail_creation(self):
        detail = ValidationDetail(
            requirement="customer name",
            mapping="[dbo].[Customers].[CustomerName]",
            found=True,
            reason="Direct column match"
        )
        assert detail.requirement == "customer name"
        assert detail.found is True
    
    def test_validation_detail_missing(self):
        detail = ValidationDetail(
            requirement="tax rate",
            mapping=None,
            found=False,
            reason="No tax column in any schema"
        )
        assert detail.found is False
        assert detail.mapping is None
    
    def test_join_path_result_sufficient(self):
        result = JoinPathValidationResult(
            status="sufficient",
            join_path="Orders -> OrderDetails ON OrderID -> Products ON ProductID",
            validation_details=[
                ValidationDetail(requirement="order total", mapping="[dbo].[Orders].[Total]", found=True, reason="test")
            ],
            analysis="All data points found with valid join path"
        )
        assert result.status == "sufficient"
        assert result.join_path is not None
    
    def test_join_path_result_insufficient_joins(self):
        result = JoinPathValidationResult(
            status="insufficient_joins",
            join_path=None,
            missing_logic="No FK path between Customers and Invoices",
            validation_details=[
                ValidationDetail(requirement="customer name", found=True, reason="found"),
                ValidationDetail(requirement="invoice total", found=True, reason="found"),
            ],
            search_suggestions=["CustomerInvoice", "bridge table"],
            analysis="Data exists but cannot be joined"
        )
        assert result.status == "insufficient_joins"
        assert result.missing_logic is not None
        assert len(result.search_suggestions) == 2
    
    def test_join_path_result_insufficient_data(self):
        result = JoinPathValidationResult(
            status="insufficient_data",
            validation_details=[
                ValidationDetail(requirement="tax rate", found=False, reason="missing"),
            ],
            search_suggestions=["tax", "tax_rate"],
            analysis="Missing required data"
        )
        assert result.status == "insufficient_data"
