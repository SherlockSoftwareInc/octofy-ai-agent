
from app.models.schemas import AgentSettings, LLMConfig, TargetDBConfig, VectorConfig, AppMeta
import json

def test_dump():
    # 1. Create with specific values
    cfg = LLMConfig(llm_model="test", llm_api_key="sk-test", llm_endpoint="http://test")
    settings = AgentSettings(
        target_db=TargetDBConfig(),
        llm_config=cfg,
        vector_config=VectorConfig(),
        app_meta=AppMeta()
    )
    
    dump1 = settings.model_dump()
    print("--- Dump with values ---")
    print(json.dumps(dump1['llm_config'], indent=2))
    
    # 2. Create with None values (logic in update_settings if frontend sends missing)
    cfg_none = LLMConfig(llm_model="test") # defaults are None
    settings_none = AgentSettings(
        target_db=TargetDBConfig(),
        llm_config=cfg_none,
        vector_config=VectorConfig(),
        app_meta=AppMeta()
    )
    
    dump2 = settings_none.model_dump()
    print("\n--- Dump with defaults (None) ---")
    print(json.dumps(dump2['llm_config'], indent=2))

if __name__ == "__main__":
    test_dump()
