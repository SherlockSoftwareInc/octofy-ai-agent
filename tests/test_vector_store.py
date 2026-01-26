import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.vector_store import MilvusVectorStore
from app.core.config import settings


class TestInsertFewshotItem:
    """Test cases for the insert_fewshot_item method in MilvusVectorStore"""

    @pytest.fixture
    def vector_store(self):
        """Create a vector store instance with mocked dependencies"""
        with patch('app.services.vector_store.connections'), \
             patch('app.services.vector_store.utility'), \
             patch('app.services.vector_store.OpenAI') as mock_openai:

            # Mock OpenAI client
            mock_client = Mock()
            mock_openai.return_value = mock_client

            # Mock embeddings response
            mock_embedding = [0.1, 0.2, 0.3] * 512  # 1536 dimensions for text-embedding-3-small
            mock_client.embeddings.create.return_value.data = [Mock(embedding=mock_embedding)]

            store = MilvusVectorStore()
            store.openai_client = mock_client
            return store

    def test_insert_fewshot_item_success(self, vector_store):
        """Test successful insertion of a fewshot item"""
        question = "What is the total sales for last month?"
        sql_query = "SELECT SUM(amount) FROM sales WHERE date >= DATEADD(MONTH, -1, GETDATE())"

        with patch('app.services.vector_store.Collection') as mock_collection_class:
            mock_collection = Mock()
            mock_collection_class.return_value = mock_collection

            # Call the method
            vector_store.insert_fewshot_item(question, sql_query)

            # Verify OpenAI embedding was called with the question
            vector_store.openai_client.embeddings.create.assert_called_once_with(
                input=[question],
                model="text-embedding-3-small"
            )

            # Verify collection insert was called with correct data structure
            expected_embedding = [0.1, 0.2, 0.3] * 512
            expected_data = [
                [expected_embedding],  # embedding
                [question],           # question
                [sql_query]           # sql_query
            ]

            mock_collection.insert.assert_called_once_with(expected_data)
            mock_collection.flush.assert_called_once()

    def test_insert_fewshot_item_with_special_characters(self, vector_store):
        """Test insertion with special characters in question and SQL"""
        question = "Find customers with email containing '@gmail.com'?"
        sql_query = "SELECT * FROM customers WHERE email LIKE '%@gmail.com%'"

        with patch('app.services.vector_store.Collection') as mock_collection_class:
            mock_collection = Mock()
            mock_collection_class.return_value = mock_collection

            vector_store.insert_fewshot_item(question, sql_query)

            # Verify the data was inserted (embedding details checked in previous test)
            assert mock_collection.insert.called
            assert mock_collection.flush.called

    def test_insert_fewshot_item_with_newlines(self, vector_store):
        """Test that newlines in question are replaced with spaces for embedding"""
        question = "Find all users\nwho registered\nlast week"
        sql_query = "SELECT * FROM users WHERE registration_date >= DATEADD(WEEK, -1, GETDATE())"

        with patch('app.services.vector_store.Collection') as mock_collection_class:
            mock_collection = Mock()
            mock_collection_class.return_value = mock_collection

            vector_store.insert_fewshot_item(question, sql_query)

            # Verify that the question with newlines replaced by spaces was sent to OpenAI
            expected_clean_question = "Find all users who registered last week"
            vector_store.openai_client.embeddings.create.assert_called_once_with(
                input=[expected_clean_question],
                model="text-embedding-3-small"
            )

    def test_insert_fewshot_item_openai_error(self, vector_store):
        """Test handling of OpenAI API errors"""
        question = "Test question"
        sql_query = "SELECT 1"

        # Mock OpenAI to raise an exception
        vector_store.openai_client.embeddings.create.side_effect = Exception("API Error")

        with patch('app.services.vector_store.Collection') as mock_collection_class:
            mock_collection = Mock()
            mock_collection_class.return_value = mock_collection

            # The method should propagate the exception
            with pytest.raises(Exception, match="API Error"):
                vector_store.insert_fewshot_item(question, sql_query)

            # Verify collection methods were not called due to the error
            mock_collection.insert.assert_not_called()
            mock_collection.flush.assert_not_called()

    def test_insert_fewshot_item_milvus_error(self, vector_store):
        """Test handling of Milvus insertion errors"""
        question = "Test question"
        sql_query = "SELECT 1"

        with patch('app.services.vector_store.Collection') as mock_collection_class:
            mock_collection = Mock()
            mock_collection_class.return_value = mock_collection

            # Mock Milvus insert to raise an exception
            mock_collection.insert.side_effect = Exception("Milvus Error")

            with pytest.raises(Exception, match="Milvus Error"):
                vector_store.insert_fewshot_item(question, sql_query)

            # Verify flush was not called due to the error
            mock_collection.flush.assert_not_called()

    def test_insert_fewshot_item_empty_strings(self, vector_store):
        """Test insertion with empty question and SQL query"""
        question = ""
        sql_query = ""

        with patch('app.services.vector_store.Collection') as mock_collection_class:
            mock_collection = Mock()
            mock_collection_class.return_value = mock_collection

            vector_store.insert_fewshot_item(question, sql_query)

            # Should still work with empty strings
            assert mock_collection.insert.called
            assert mock_collection.flush.called

    def test_insert_fewshot_item_very_long_question(self, vector_store):
        """Test insertion with a very long question"""
        question = "What is the average sales amount by product category for customers located in California who have made purchases in the last quarter and have a total purchase history greater than $1000, including tax calculations and discount applications?" * 10
        sql_query = "SELECT AVG(amount) FROM sales WHERE state='CA' AND date >= DATEADD(QUARTER, -1, GETDATE()) AND customer_total > 1000"

        with patch('app.services.vector_store.Collection') as mock_collection_class:
            mock_collection = Mock()
            mock_collection_class.return_value = mock_collection

            vector_store.insert_fewshot_item(question, sql_query)

            # Should handle long questions
            assert mock_collection.insert.called
            assert mock_collection.flush.called

    @patch('app.services.vector_store.settings')
    def test_insert_fewshot_item_uses_correct_collection(self, mock_settings, vector_store):
        """Test that the correct Milvus collection is used"""
        mock_settings.MILVUS_COLLECTION_FEWSHOT = "test_fewshot_collection"

        question = "Test question"
        sql_query = "SELECT 1"

        with patch('app.services.vector_store.Collection') as mock_collection_class:
            mock_collection = Mock()
            mock_collection_class.return_value = mock_collection

            vector_store.insert_fewshot_item(question, sql_query)

            # Verify Collection was instantiated with the correct collection name
            mock_collection_class.assert_called_once_with("test_fewshot_collection")


if __name__ == "__main__":
    pytest.main([__file__])
