import json
import os
from app.utils.logging_utils import log_llm_interaction

def verify_logging():
    print("Testing logging_utils...")
    
    # Test data with literal newline and escaped newline
    context = "System: You are an expert.\nUser: Hello"
    reply = "Hello there.\nHow can I help?"
    
    # Mock data that mimics what might happen if strings had escaped newlines
    # e.g. "Line 1\\nLine 2"
    reply_escaped = "Line 1\\nLine 2"

    print("Logging interaction 1...")
    log_llm_interaction(context, reply)
    
    print("Logging interaction 2 (with escaped input)...")
    log_llm_interaction(context, reply_escaped)
    
    # Find the latest log file
    log_dir = os.path.join(os.getcwd(), "context_logs")
    files = sorted([f for f in os.listdir(log_dir) if f.endswith(".log")])
    if not files:
        print("No log files found!")
        return
        
    latest_file = os.path.join(log_dir, files[-1])
    print(f"Checking {latest_file}...")
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    last_line = lines[-1]
    second_last = lines[-2]
    
    print("\n--- Content check ---")
    print(f"Last line (raw): {repr(last_line)}")
    
    # We expect the file to contain actual newlines where \n was.
    # However, since we are writing unescaped newlines into a JSON structure, 
    # reading it back line-by-line might split the JSON object if it has newlines!
    # Valid JSONL requires one JSON object per line.
    # By unescaping \n, we effectively broke strict JSONL format if the content has newlines.
    # The user asked for "real new line char", which implies they want readability over strict JSONL 
    # (or they want multi-line JSON which isn't standard JSONL but is human readable).
    
    # Let's see if we see "Line 1\nLine 2" in the file content.
    with open(latest_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if "Line 1\nLine 2" in content:
        print("SUCCESS: Found actual newline definition for escaped input.")
    elif "Line 1\\nLine 2" in content:
        print("FAILURE: Found literal escaped newline.")
    else:
        print("UNCLEAR: Could not find strict match.")
        
    if "Hello there.\nHow can I help?" in content:
        print("SUCCESS: Found actual newline for normal input.")

if __name__ == "__main__":
    verify_logging()
