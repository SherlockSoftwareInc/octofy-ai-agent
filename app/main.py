from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import (
    discovery, generation, admin, settings as settings_endpoint, 
    contributions, schema as schema_endpoint, summarize,
    data_sources, schema_tree
)
from app.services.ingest_service import create_milvus_collections, ingest_metadata
from app.services.vector_store import get_vector_store
from app.services.migration_service import auto_migrate_if_needed
import logging

# Setup Logger
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(discovery.router, prefix=settings.API_V1_STR, tags=["discovery"])
app.include_router(generation.router, prefix=settings.API_V1_STR, tags=["generation"])
app.include_router(schema_endpoint.router, prefix=settings.API_V1_STR, tags=["schema"])
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])
app.include_router(settings_endpoint.router, prefix=f"{settings.API_V1_STR}/admin", tags=["settings"])
app.include_router(contributions.router, prefix=settings.API_V1_STR, tags=["contributions"])
app.include_router(summarize.router, prefix=settings.API_V1_STR, tags=["summarize"])

# NEW: Multi-source management routers
app.include_router(data_sources.router, prefix=f"{settings.API_V1_STR}/admin", tags=["data-sources"])
app.include_router(schema_tree.router, prefix=f"{settings.API_V1_STR}/admin", tags=["schema-tree"])

@app.on_event("startup")
async def startup_event():
    # Run configuration migration if needed
    logger.info("Checking for configuration migration...")
    try:
        migration_result = auto_migrate_if_needed()
        if migration_result == "migrated":
            logger.info("✅ Configuration migrated from v1 to v2 successfully!")
        elif migration_result == "v2":
            logger.info("Configuration is already v2 format.")
        elif migration_result == "error":
            logger.warning("⚠️ Configuration migration encountered an error. Check logs.")
    except Exception as e:
        logger.error(f"Migration check failed: {e}")
    
    if not settings.VECTOR_DB_ENABLED:
        logger.info("Vector DB disabled. Skipping startup ingestion.")
        return
    try:
        logger.info("Checking Vector Database Schema Index...")
        vector_store = get_vector_store()
        schemas = vector_store.get_all_schemas()
        
        if not schemas:
            logger.info("Schema index is empty or does not exist. Initiating auto-ingestion...")
            try:
                # Ensure collections exist
                create_milvus_collections()
                # Ingest metadata
                ingest_metadata()
                logger.info("Auto-ingestion complete.")
            except Exception as e:
                logger.error(f"Auto-ingestion failed: {e}")
        else:
            logger.info(f"Schema index contains {len(schemas)} items. Skipping auto-ingestion.")
            
    except Exception as e:
        logger.error(f"Error during startup check: {e}")

@app.get("/")
def root():
    return {"message": "Database AI Agent API is running"}