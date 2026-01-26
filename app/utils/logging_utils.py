import os
import json
from datetime import datetime

def log_llm_interaction(context, reply):
    """
    Logs LLM interactions to a time-segmented JSONL file.
    
    Args:
        context: The input prompt or messages sent to the LLM.
        reply: The raw response received from the LLM.
    """
    try:
        # 1. Ensure directory exists
        # Use absolute path relative to the current working directory (project root)
        log_dir = os.path.join(os.getcwd(), "context_logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 2. Generate filename based on current hour
        now = datetime.now()
        filename = now.strftime("%Y-%m-%d_%H.log")
        filepath = os.path.join(log_dir, filename)

        # 3. Prepare the log entry
        log_entry = {
            "timestamp": now.isoformat(),
            "context_sent": context,
            "llm_reply": reply
        }

        # 4. Append to the file (JSON Lines format)
        with open(filepath, "a", encoding="utf-8") as f:
            json_str = json.dumps(log_entry, ensure_ascii=False)
            # Replace literal \n with actual newline character for readability
            # This makes the file technically not valid JSONL if strings contain newlines,
            # but fulfills the requirement for readable logs.
            json_str = json_str.replace("\\n", "\n")
            f.write(json_str + "\n")
            
    except Exception as e:
        # Fail silently or print error to avoid crashing the main application
        print(f"Failed to log LLM interaction: {e}")
