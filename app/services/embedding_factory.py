from typing import List, Optional
from app.models.schemas import EmbeddingConfig
from app.core.config import settings
from openai import OpenAI
import os

class EmbeddingClient:
    def __init__(self, get_embedding_func, dimension: int):
        self.get_embedding_func = get_embedding_func
        self.dimension = dimension
        
    def embed_query(self, text: str) -> List[float]:
        return self.get_embedding_func(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if hasattr(self, 'get_embeddings_func'):
            return self.get_embeddings_func(texts)
        # Fallback to loop if batch func not available
        return [self.get_embedding_func(t) for t in texts]

class EmbeddingFactory:
    @staticmethod
    def create_client(config: EmbeddingConfig) -> EmbeddingClient:
        """
        Create an embedding client based on the configuration.
        """
        provider = config.provider.lower()
        
        if provider == "openai":
            return EmbeddingFactory._create_openai_client(config)
        elif provider == "azure":
             # Placeholder: Azure logic is similar to OpenAI but needs api_version and azure_endpoint
             # For now, mapping to standard OpenAI client configured for Azure if base_url provided
             return EmbeddingFactory._create_openai_client(config)
        elif provider == "openai_compatible":
            return EmbeddingFactory._create_openai_client(config)
        elif provider == "huggingface":
            return EmbeddingFactory._create_local_hf_client(config)
        else:
            # Default fallback to OpenAI if unknown
            return EmbeddingFactory._create_openai_client(config)

    @staticmethod
    def _create_openai_client(config: EmbeddingConfig) -> EmbeddingClient:
        # Resolve API Key
        api_key = config.api_key
        if not api_key:
            # Fallback to env var if not in config
            if config.provider == "openai":
                api_key = settings.OPENAI_API_KEY
                
        # Resolve Base URL
        base_url = config.base_url
        if not base_url and config.provider == "openai":
             # Default OpenAI URL is handled by the generic client, but we can be explicit
             base_url = "https://api.openai.com/v1"
             # If using env var override (e.g. for proxy)
             if hasattr(settings, "OPENAI_EMBEDDING_ENDPOINT") and settings.OPENAI_EMBEDDING_ENDPOINT:
                 base_url = settings.OPENAI_EMBEDDING_ENDPOINT

        # If still no key and no local base_url, we might have an issue
        # But for local providers (openai_compatible), key might be dummy
        if not api_key:
            api_key = "dummy-key"

        client = OpenAI(api_key=api_key, base_url=base_url)
        
        def get_embedding(text: str) -> List[float]:
            # Validate input
            if not text or not isinstance(text, str):
                raise ValueError(f"Invalid embedding input: text must be a non-empty string, got: {type(text).__name__}")
            
            text = text.replace("\n", " ").strip()
            
            # Additional safety check after cleaning
            if not text:
                raise ValueError("Embedding input is empty after cleaning")
            
            try:
                response = client.embeddings.create(input=[text], model=config.model)
                return response.data[0].embedding
            except Exception as e:
                print(f"Embedding error ({config.provider}): {e}")
                # Re-raise or return empty? distinct from dimensions mismatch check
                raise e

        def get_embeddings(texts: List[str]) -> List[List[float]]:
            # Validate inputs
            if not texts or not all(isinstance(t, str) and t.strip() for t in texts):
                invalid = [i for i, t in enumerate(texts) if not isinstance(t, str) or not t.strip()]
                raise ValueError(f"Invalid embedding inputs at indices: {invalid}. All texts must be non-empty strings.")
            
            # Replace newlines and strip
            clean_texts = [t.replace("\n", " ").strip() for t in texts]
            
            try:
                response = client.embeddings.create(input=clean_texts, model=config.model)
                # Ensure order is preserved. OpenAI returns list of embedding objects with index.
                # Usually sorted by index, but good to be safe.
                sorted_data = sorted(response.data, key=lambda x: x.index)
                return [d.embedding for d in sorted_data]
            except Exception as e:
                print(f"Batch embedding error ({config.provider}): {e}")
                raise e
        
        client_obj = EmbeddingClient(get_embedding, config.dimensions)
        client_obj.get_embeddings_func = get_embeddings
        return client_obj

    @staticmethod
    def _create_local_hf_client(config: EmbeddingConfig) -> EmbeddingClient:
        # Placeholder for local HuggingFace implementation
        # This would require sentence-transformers or similar installed
        # For now, we'll raise NotImplemented
        raise NotImplementedError("Local HuggingFace provider is not yet implemented.")
