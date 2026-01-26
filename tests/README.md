# Tests

This directory contains unit tests for the SQL Agent application.

## Setup

Install testing dependencies:
```bash
pip install -r requirements-dev.txt
```

## Running Tests

Run all tests:
```bash
python -m pytest
```

Run tests for a specific module:
```bash
python -m pytest tests/test_vector_store.py
```

Run tests with verbose output:
```bash
python -m pytest tests/ -v
```

## Test Coverage

### Vector Store Tests (`test_vector_store.py`)

Tests for the `MilvusVectorStore` class, specifically the `insert_fewshot_item` method:

- **test_insert_fewshot_item_success**: Tests successful insertion with valid inputs
- **test_insert_fewshot_item_with_special_characters**: Tests handling of special characters in questions and SQL
- **test_insert_fewshot_item_with_newlines**: Tests that newlines in questions are properly cleaned for embedding
- **test_insert_fewshot_item_openai_error**: Tests error handling when OpenAI API fails
- **test_insert_fewshot_item_milvus_error**: Tests error handling when Milvus insertion fails
- **test_insert_fewshot_item_empty_strings**: Tests behavior with empty strings
- **test_insert_fewshot_item_very_long_question**: Tests handling of very long questions
- **test_insert_fewshot_item_uses_correct_collection**: Tests that the correct Milvus collection is used

## Mocking Strategy

The tests use comprehensive mocking to avoid external dependencies:
- OpenAI API calls are mocked to return consistent embeddings
- Milvus connections and collections are mocked
- All external services are isolated for reliable unit testing
