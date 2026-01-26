
import sys
import os

sys.path.append(os.getcwd())

try:
    from app.services.llm_service import LiteLLMService, get_llm_service
    print("Successfully imported LiteLLMService.")
    
    service = get_llm_service()
    if isinstance(service, LiteLLMService):
        print("get_llm_service returned LiteLLMService instance.")
    else:
        print(f"get_llm_service returned {type(service)}")
        
    print("Verification successful.")
    
except Exception as e:
    print(f"Verification failed: {e}")
    sys.exit(1)
